from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import random
import zmq.asyncio
import time
import asyncio
CHUNK_SIZE = 1024
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode

class DataLinkLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, DLL_rx, DLL_tx, reader, writer, radio_mode_queue):
        super().__init__(DLL_rx, DLL_tx, None, None)
        self.name = "Data Link Layer   "
        self.logger = LoggerFactory.get_logger(self.name)
        self.reader = reader
        self.writer = writer
        self.radio_mode_queue = radio_mode_queue
        self.mode_lock = asyncio.Lock()
        self.mode = RadioMode.RX
        self.tasks = []

    async def start(self):
        self.tasks.append(asyncio.create_task(self.mode_watcher()))
        self.tasks.append(asyncio.create_task(self.rx_tcp()))
        self.tasks.append(asyncio.create_task(self.tx_tcp()))

    async def mode_watcher(self):
        while True:
            new_mode = await self.radio_mode_queue.get()
            async with self.mode_lock:
                self.mode = new_mode
            self.logger.info(f"switching radio mode to: {new_mode}")

    async def rx_tcp(self):
        while True:
            # Safely check the mode
            async with self.mode_lock:
                current_mode = self.mode

            if current_mode == RadioMode.RX:
                # Do the blocking network read OUTSIDE the lock
                msg = await self.reader.read(1024)
                if not msg:
                    self.logger.info("Connection closed, stopping rx")
                    break
                await self.layer_rx.put(msg)
            else:
                # Sleep briefly to yield control if not in RX mode
                await asyncio.sleep(0.001)

    async def tx_tcp(self):
        while True:
            # Safely check the mode
            async with self.mode_lock:
                current_mode = self.mode

            if current_mode == RadioMode.TX:

                # Do the blocking queue get OUTSIDE the lock
                message = await self.layer_tx.get()


                self.logger.info(f"tx: {message}")

                if random.randint(1,10) > 8:
                    print("dropped packet")
                    continue

                self.writer.write(message)
                await self.writer.drain()
            else:
                # Sleep briefly to yield control if not in TX mode
                await asyncio.sleep(0.001)

    # sends to GNU Radio with ZMQ
    async def tx_zmq(self):
        context = zmq.asyncio.Context()
        socket = context.socket(zmq.PUB)
        socket.bind("tcp://0.0.0.0:5557")
        await asyncio.sleep(1)

        while True:
            msg =  await self.layer_tx.get()
            padded = msg.ljust(CHUNK_SIZE, b'\x00')[:CHUNK_SIZE]
            await socket.send(padded)
            await asyncio.sleep(0.1)


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
    def __init__(self, DLL_rx,DLL_tx, reader, writer, radio_mode_queue):
        super().__init__(DLL_rx,DLL_tx, reader,writer, radio_mode_queue)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message





class AudimusDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx,DLL_tx, reader, writer, radio_mode_queue):
        super().__init__(DLL_rx,DLL_tx, reader, writer, radio_mode_queue)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message


