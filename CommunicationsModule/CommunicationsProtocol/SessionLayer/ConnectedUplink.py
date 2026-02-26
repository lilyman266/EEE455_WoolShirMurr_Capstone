
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.Logger.Errors import InvalidSendError
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session


class ConnectedUplink(Session):
    def __init__(self, context, DLL_rx, DLL_tx, file_path):
        self.name = "ConnectedUplink"
        self.logger = LoggerFactory.get_logger(self.name)
        super().__init__(context, DLL_rx, DLL_tx, file_path)

    async def rx(self):
        message = self.below_rx.get()
        self.logger.info(b'rx: '+ message)
        return message

    async def tx(self, message):
        self.logger.info(b'tx: ' + message)
        await self.below_tx.put(message)


class GroundStationConnectedUplink(ConnectedUplink):
    def __init__(self, context, DLL_rx, DLL_tx):
        super().__init__(context, DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/GroundStationData")


class AudimusConnectedUplink(ConnectedUplink):
    def __init__(self, context, DLL_rx, DLL_tx):
        super().__init__(context, DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/AudimusData")




