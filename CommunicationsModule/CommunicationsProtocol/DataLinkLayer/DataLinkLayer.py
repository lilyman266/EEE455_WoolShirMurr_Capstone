

import sys
import asyncio
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

HOST = "127.0.0.1"
PORT = 9000

from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import zmq.asyncio
import random

from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode
import zmq
import xmlrpc.client


CHUNK_SIZE = 1024
LEN_BYTES = 4
MAX_PAYLOAD = CHUNK_SIZE - LEN_BYTES

PREAMBLE = b'\xff' * CHUNK_SIZE


class DataLinkLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, DLL_rx, DLL_tx, reader, writer):
        super().__init__(DLL_rx, DLL_tx, None, None)
        self.name = "Data Link Layer   "
        self.logger = LoggerFactory.get_logger(self.name)

        self.reader = reader
        self.writer = writer
        self.mode_lock = asyncio.Lock()
        self.mode = None
        self.current_process = None
        self.tasks = []

        self.proxy = xmlrpc.client.ServerProxy("http://localhost:8080")

        self.ctx = zmq.asyncio.Context.instance()
        self.tx_socket = None
        self.rx_socket = None

        self.tx_addr = "tcp://127.0.0.1:5557"
        self.rx_addr = "tcp://127.0.0.1:5558"

        self.socket_ready = asyncio.Event()
        self.running = False

    async def rx_tcp(self):
        while True:

            # receive a message from tcp
            msg = await self.reader.read(1024)

            # Check for EOF / connection closed
            if not msg:
                self.logger.info("Connection closed, stopping rx")
                break  # or handle reconnection logic hereF

            if random.randint(1, 10) > 10:
                print("packet dropped")
                continue

            # put the message in the layers rx queue
            await self.layer_rx.put(msg)
            self.logger.info(f"rx: {msg} ")

    async def tx_tcp(self):
        while True:

            # grab the message from this layer's tx queue
            message = await self.layer_tx.get()

            # send the message over tcp
            self.writer.write(message)

            self.logger.info(f"tx: {message} ")
            await asyncio.sleep(0.1)
            await self.writer.drain()


    async def mode_switch(self, new_mode):

        if self.mode != new_mode:
            self.logger.info(f"mode switched to {new_mode}")



class GroundStationDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx, DLL_tx, reader, writer):
        super().__init__(DLL_rx,DLL_tx, reader,writer)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message


class AudimusDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx, DLL_tx, reader, writer):
        super().__init__(DLL_rx,DLL_tx, reader,writer)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message