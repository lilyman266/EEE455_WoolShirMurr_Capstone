

import sys
import asyncio
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import zmq.asyncio


from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode
import zmq
import xmlrpc.client


CHUNK_SIZE = 1024
LEN_BYTES = 4
MAX_PAYLOAD = CHUNK_SIZE - LEN_BYTES

PREAMBLE = b'\xff' * CHUNK_SIZE


class DataLinkLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx, DLL_tx, None, None)
        self.name = "Data Link Layer   "
        self.logger = LoggerFactory.get_logger(self.name)


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

    async def start_zmq(self):
        await asyncio.sleep(20)
        self.tasks.append(asyncio.create_task(self.setup_sockets()))
        self.tasks.append(asyncio.create_task(self.rx_zmq()))
        self.tasks.append(asyncio.create_task(self.tx_zmq()))


    async def mode_switch(self, new_mode):

        if self.mode != new_mode:
            # before switching modes, change the flowgraph
            async with self.mode_lock:
                self.logger.info(f"got lock switching mode to {new_mode}")

                if new_mode == RadioMode.TX:
                    self.proxy.set_mode(1)
                    self.logger.info("Radio switched to TX")
                if new_mode == RadioMode.RX:
                    self.proxy.set_mode(0)
                    self.logger.info("Radio switched to RX")
                await asyncio.sleep(5)
                self.mode = new_mode
            self.logger.info(f"mode switched to {new_mode}")




    async def tx_zmq(self):
        while True:

            message = await self.layer_tx.get()
            print("run tx")
            message = await self.pack(message)

            async with self.mode_lock:
                current_mode = self.mode

            if current_mode != RadioMode.TX:
                self.logger.info("Dropped TX message: not in TX mode")

            await self.send_preamble(10)
            await self.tx_socket.send(message)
            self.logger.info(f"TX: {message}")
            await self.send_preamble(5)
            print("finish tx")


    async def rx_zmq(self):
        while True:

            async with self.mode_lock:
                current_mode = self.mode

            if current_mode != RadioMode.RX:
                await asyncio.sleep(0.01)
                continue


            message = await self.rx_socket.recv()
            if message == PREAMBLE:
                continue
            self.logger.info(f"RX: {message}")

            message = await self.unpack(message)
            await self.layer_rx.put(message)



    #send preamble for lock-on
    async def send_preamble(self, preamble_count):
        for rounds in range(preamble_count):
            await self.tx_socket.send(PREAMBLE)
            await asyncio.sleep(0.01)


    async def pack(self, payload):
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError(f"Expected bytes, got {type(payload)}")

        payload_len = len(payload)
        if payload_len > MAX_PAYLOAD:
            raise ValueError(f"Payload too large: {payload_len} bytes, max is {MAX_PAYLOAD}")

        header = payload_len.to_bytes(LEN_BYTES, byteorder="big")
        padding = b"\x00" * (CHUNK_SIZE - LEN_BYTES - payload_len)
        return header + payload + padding



    async def unpack(self, frame):
        if len(frame) != CHUNK_SIZE:
            return None

        payload_len = int.from_bytes(frame[:LEN_BYTES], byteorder="big")

        if payload_len < 0 or payload_len > MAX_PAYLOAD:
            return None

        return frame[LEN_BYTES:LEN_BYTES + payload_len]


    async def setup_sockets(self):
        self.tx_socket = self.ctx.socket(zmq.PUSH)
        self.rx_socket = self.ctx.socket(zmq.PULL)

        #do not hang forever on close
        self.tx_socket.setsockopt(zmq.LINGER, 0)
        self.rx_socket.setsockopt(zmq.LINGER, 0)

        self.tx_socket.bind(self.tx_addr)
        self.rx_socket.connect(self.rx_addr)

        self.logger.info(f"ZMQ sockets initialized: TX={self.tx_addr}, RX={self.rx_addr}")






class GroundStationDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx,DLL_tx)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message


class AudimusDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx,DLL_tx)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message