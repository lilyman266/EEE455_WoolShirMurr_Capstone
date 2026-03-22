from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from DatabaseModule.Database.database_stub import CommsModDatabaseStub
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
        self.db_stub = CommsModDatabaseStub()


    def process_tx(self, message):
        message= self.encode(message)
        self.logger.info(message)
        return message

    def process_rx(self, message):
        message =  self.decode(message)
        self.logger.info(f"tx: {message}")
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
            await self.distribute(message)

    #distributes data to necessary parties
    async def distribute(self, message):
        value = self.db_stub.add_acoustic_data(message)
        self.logger.info(f"database result:{value}")

    async def tx(self):
        while True:
            async for message in self.command_line():
                print("message")
                match message:
                    case "idle mode":
                        await self.session_queue.put(Audimus_pb2.SESSION_MODE.Idle)
                    case "connected uplink mode":
                        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectedUplink)
                    case "connected downlink mode":
                        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectedDownlink)
                    case "connectionless downlink mode":
                        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
                    case _:
                        message = self.encode(message)
                        await self.below_tx.put(message)




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

        self.aros_mode = Audimus_pb2.SESSION_MODE.Idle
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
                current_mode = self.aros_mode


            match current_mode:

                case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                    try:
                        message = await asyncio.wait_for(self.below_rx.get(), timeout=0.1)
                    except asyncio.TimeoutError:
                        continue

                    message = self.decode(message)
                    self.logger.info(message)

                case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                    await asyncio.sleep(0.1)

                case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                    print("sending from connectionless downlink")
                    #wait a random amount of time, then send a message burst of random length
                    await asyncio.sleep(1)

                    line = self.read_one_line("CommunicationsModule/TestTXAudimus")
                    if not line:
                        break

                    message = self.encode(line)
                    await self.below_tx.put(message)

                case Audimus_pb2.SESSION_MODE.Idle:
                    # await to prevent spinning
                    await asyncio.sleep(random.expovariate(0.1))




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

