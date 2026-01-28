from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory

class ApplicationLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, AL_rx, AL_tx, PL_rx, PL_tx):
        super().__init__(AL_rx, AL_tx, PL_rx, PL_tx)
        self.name = "Application Layer "
        self.logger = LoggerFactory.get_logger(self.name)

    def process_tx(self, message):
        self.logger.info(message)
        return self.encode(message)

    def process_rx(self, message):
        return self.decode(message)

    def encode(self, message):
        msg = Audimus_pb2.Application_Message()
        msg.message = message
        return msg.SerializeToString()

    def decode(self, msg):
        message = Audimus_pb2.Application_Message()
        message.ParseFromString(msg)
        return message.message

class GroundStationApplicationLayer(ApplicationLayer):
    def __init__(self, AL_rx, AL_tx, PL_rx, PL_tx):
        super().__init__(AL_rx, AL_tx, PL_rx, PL_tx)


class AudimusApplicationLayer(ApplicationLayer):
    def __init__(self, AL_rx, AL_tx, PL_rx, PL_tx):
        super().__init__(AL_rx, AL_tx, PL_rx, PL_tx)


