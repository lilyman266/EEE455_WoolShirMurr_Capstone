from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
import asyncio
import random

class ApplicationLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self,  PL_rx, PL_tx, session_queue):
        super().__init__(None, None, PL_rx, PL_tx)
        self.name = "Application Layer "
        self.logger = LoggerFactory.get_logger(self.name)
        self.below_rx = PL_rx
        self.below_tx = PL_tx
        self.session_queue = session_queue


    def process_tx(self, message):
        return self.encode(message)

    def process_rx(self, message):
        message =  self.decode(message)
        return message

    def encode(self, message):
        msg = Audimus_pb2.Application_Message()
        msg.message = message
        return msg.SerializeToString()

    def decode(self, msg):
        message = Audimus_pb2.Application_Message()
        message.ParseFromString(msg)
        return message.message

class GroundStationApplicationLayer(ApplicationLayer):
    def __init__(self,  PL_rx, PL_tx, sl):
        super().__init__(PL_rx, PL_tx, sl)

    async def rx(self):
        while True:
            message = await self.below_rx.get()
            message = self.decode(message)
            self.logger.info(f"rx: {message}")


    async def tx(self):
        while True:
            async for message in self.command_line():

                match message:
                    case "connected uplink mode":
                        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectedUplink)
                    case "connected downlink mode":
                        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectedDownlink)
                    case "connectionless downlink mode":
                        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
                    case _:
                        message = self.encode(message)
                        await self.below_tx.put(message)

    async def distribute(self):
        message= await self.command_line()
        # send session change commands to the session layer


    async def command_line(self):
        """Yield messages from the command line asynchronously."""
        loop = asyncio.get_running_loop()
        print("Enter messages (type 'exit' to quit):")

        while True:
            line = await loop.run_in_executor(None, input, "> ")

            if line.lower() == "exit":
                break

            yield line


############################# Audimus application layer ############################



class AudimusApplicationLayer(ApplicationLayer):
    def __init__(self, PL_rx, PL_tx, ASQ):
        super().__init__(PL_rx, PL_tx, None)

        self.aros_mode = Audimus_pb2.SESSION_MODE.ConnectionlessDownlink
        self.session_queue = ASQ
        self.session_lock = asyncio.Lock()


    def read_lines(self, path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                yield line.rstrip("\n")


############################# AROS simulator living in audimus application layer #############################

    # Script to model AROS behavior
    async def AROS_sim(self):
        while True:
            async with self.session_lock:
                match self.aros_mode:

                    case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                        message = await self.below_rx.get()
                        message = self.decode(message)
                        self.logger.info(message)

                    case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                        await asyncio.sleep(0.1)

                    case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                        #wait a random amount of time, then send a message burst of random length
                        await asyncio.sleep(random.expovariate(0.1))
                        #for burst in range(int(random.expovariate(2))):
                        #    line = self.read_one_line("CommunicationsModule/TestTXAudimus")
                        #    message = self.encode(line)

                         #   await self.below_tx.put(message)



    def read_one_line(self, path: str):
            with open(path, "r", encoding="utf-8") as f:
                return f.readline().rstrip("\n")

    async def state_watcher(self):
        self.logger.info(f"starting state watcher")
        while True:
            new_mode = await self.session_queue.get()
            async with self.session_lock:
                self.aros_mode = new_mode
                self.logger.info(f"New AROS mode: {new_mode}")

