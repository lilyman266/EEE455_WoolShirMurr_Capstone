from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
import asyncio

class ApplicationLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self,  PL_rx, PL_tx, sl):
        super().__init__(None, None, PL_rx, PL_tx)
        self.name = "Application Layer "
        self.logger = LoggerFactory.get_logger(self.name)
        self.below_rx = PL_rx
        self.below_tx = PL_tx
        self.session_layer = sl

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
                        await self.session_layer.session.handshake(Audimus_pb2.SESSION_MODE.ConnectedUplink)
                    case "connected downlink mode":
                        await self.session_layer.session.handshake(Audimus_pb2.SESSION_MODE.ConnectedDownlink)
                    case "connectionless downlink mode":
                        await self.session_layer.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
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



class AudimusApplicationLayer(ApplicationLayer):
    def __init__(self, PL_rx, PL_tx):
        super().__init__(PL_rx, PL_tx, None)

    def read_lines(self, path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                yield line.rstrip("\n")


    async def rx(self):
        while True:
            message = await self.below_rx.get()
            message = self.decode(message)
            self.logger.info(message)



    #send lines from files
    async def tx_file(self):
        for line in self.read_lines("CommunicationsModule/TestTXAudimus"):
            message = self.process_tx(line)
            self.logger.info(message)
            await self.below_tx.put(message)
            await asyncio.sleep(1)


