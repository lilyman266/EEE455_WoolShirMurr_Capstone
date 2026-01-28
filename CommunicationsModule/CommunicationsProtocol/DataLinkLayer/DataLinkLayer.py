from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory

class DataLinkLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, DLL_rx,DLL_tx, SDR_rx, SDR_tx):
        super().__init__(DLL_rx,DLL_tx, SDR_rx, SDR_tx)
        self.name = "Data Link Layer   "
        self.logger = LoggerFactory.get_logger(self.name)


    def process_rx(self, message):
        return message

    def process_tx(self, message):
        self.logger.info(message)
        return message


class GroundStationDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx,DLL_tx, SDR_rx, SDR_tx):
        super().__init__(DLL_rx,DLL_tx, SDR_rx, SDR_tx)


class AudimusDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx,DLL_tx, SDR_rx, SDR_tx):
        super().__init__(DLL_rx,DLL_tx, SDR_rx, SDR_tx)



