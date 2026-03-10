from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import random



class DataLinkLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader, writer):
        super().__init__(DLL_rx,DLL_tx, SDR_rx, SDR_tx)
        self.name = "Data Link Layer   "
        self.logger = LoggerFactory.get_logger(self.name)
        self.reader = reader
        self.writer = writer

    async def rx_tcp(self):
        while True:
            # receive a message from tcp
            msg = await self.reader.read(1024)

            # Check for EOF / connection closed
            if not msg:
                self.logger.info("Connection closed, stopping rx")
                break  # or handle reconnection logic here


            self.logger.info(b'rx: ' + msg)
            #do the thing ot the message

            #put the message in the layers rx queue
            await self.layer_rx.put(msg)

    async def tx_tcp(self):
        while True:
            # grab the message from this layer's tx queue
            message = await self.layer_tx.get()

            #send the message over tcp
            self.writer.write(message)
            await self.writer.drain()


class GroundStationDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader, writer):
        super().__init__(DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader,writer)


class AudimusDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader, writer):
        super().__init__(DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader, writer)



