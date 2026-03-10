from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import random
import zmq.asyncio
import time
CHUNK_SIZE = 1024


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


    # sends to GNU Radio with ZMQ
    async def tx_zmq(self):
        context = zmq.asyncio.Context()
        socket = context.socket(zmq.PUB)
        socket.bind("tcp://0.0.0.0:5557")
        time.sleep(1)

        while True:
            msg =  await self.layer_tx.get()
            padded = msg.ljust(CHUNK_SIZE, b'\x00')[:CHUNK_SIZE]
            await socket.send(padded)
            time.sleep(0.1)


    # receives from GNU radio with ZMQ
    async def rx_zmq(self):
        context = zmq.asyncio.Context()
        socket = context.socket(zmq.SUB)
        socket.connect("tcp://0.0.0.0:5557")
        socket.setsockopt(zmq.SUBSCRIBE, b"")

        while True:
            msg = await socket.recv()
            msg = msg.strip(b'\x00')
            if random.randint(0, 10) > 10:
                print("dropped a packet")
                continue
            if msg == b"":  # connection closed
                break
            await self.layer_rx.put(msg)


class GroundStationDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader, writer):
        super().__init__(DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader,writer)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message





class AudimusDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader, writer):
        super().__init__(DLL_rx,DLL_tx, SDR_rx, SDR_tx, reader, writer)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message


