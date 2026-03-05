
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.Logger.Errors import InvalidSendError
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session


class ConnectedDownlink(Session):
    def __init__(self,  DLL_rx, DLL_tx, file_path):
        self.name = "ConnectedDownlink"
        self.logger = LoggerFactory.get_logger(self.name)
        super().__init__( DLL_rx, DLL_tx, file_path)

class GroundStationConnectedDownlink(ConnectedDownlink):
    def __init__(self,  DLL_rx, DLL_tx):
        super().__init__( DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/GroundStationData")

class AudimusConnectedDownlink(ConnectedDownlink):
    def __init__(self, DLL_rx, DLL_tx, session_queue):
        super().__init__( DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/AudimusData")




