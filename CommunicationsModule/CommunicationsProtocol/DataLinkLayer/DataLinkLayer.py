from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import zmq.asyncio
import asyncio
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode
import zmq
import xmlrpc.client
import subprocess



CHUNK_SIZE = 1024
LEN_BYTES = 4
MAX_PAYLOAD = CHUNK_SIZE - LEN_BYTES

PREAMBLE = b'\xff' * CHUNK_SIZE

TX_FLOWGRAPH = "CommunicationsModule/CommunicationsProtocol/DataLinkLayer/transmit_bpsk.py"
RX_FLOWGRAPH = "CommunicationsModule/CommunicationsProtocol/DataLinkLayer/receive_bpsk.py"

class DataLinkLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, DLL_rx, DLL_tx,):
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
        self.tasks.append(asyncio.create_task(self.setup_sockets()))
        self.tasks.append(asyncio.create_task(self.rx_zmq()))
        self.tasks.append(asyncio.create_task(self.tx_zmq()))


    # changes radio mode
    async def mode_switch(self, new_mode):
        print(new_mode)
        if new_mode != self.mode:

            # before switching modes, change the flowgraph
            async with self.mode_lock:
                self.logger.info(f"got lock, switching mode: {new_mode}")

                if self.current_process:
                    self.current_process.terminate()
                    self.current_process.wait()
                    await asyncio.sleep(2)

                if new_mode == RadioMode.RX:
                    self.current_process = subprocess.Popen(['python3', RX_FLOWGRAPH])
                if new_mode == RadioMode.TX:
                    self.current_process = subprocess.Popen(['python3', TX_FLOWGRAPH])
                await asyncio.sleep(4)
                self.mode = new_mode

            self.logger.info(f"Radio switched to: {self.mode}")

    # send to GNU radio with ZMQ
    async def tx_zmq(self):
        while True:
            message = await self.layer_tx.get()

            message = await self.pack(message)
            self.logger.info(f"tx: {message}")
            async with self.mode_lock:
                current_mode = self.mode

            if current_mode != RadioMode.TX:
                self.logger.warning("Dropping TX message: not in TX mode")

            await self.send_preamble(10)
            await self.tx_socket.send(message)
            self.logger.info(f"TX: {message}")
            await self.send_preamble(5)


    # receives from GNU radio with ZMQ
    async def rx_zmq(self):
        while True:
            # Receive the message as fast as possible to prevent buffer overflow
            async with self.mode_lock:
                current_mode = self.mode

            if current_mode != RadioMode.RX:
                await asyncio.sleep(0.01)
                continue


            message = await self.rx_socket.recv()
            if message == PREAMBLE:
                continue

            message = await self.unpack(message)

            self.logger.info(message)
            await self.layer_rx.put(message)

    async def send_preamble(self, preamble_count):
        for rounds in range(preamble_count):
            await self.tx_socket.send(PREAMBLE)
            await asyncio.sleep(0.01)




    async def pack(self, payload):
        payload_len = len(payload)
        if payload_len > MAX_PAYLOAD:
            raise ValueError(f"Payload too large: {payload_len} bytes, max is {MAX_PAYLOAD}")

        header = payload_len.to_bytes(LEN_BYTES, byteorder='big')
        padding = b"\x00" * (CHUNK_SIZE - LEN_BYTES - payload_len)
        return header + payload + padding

    async def unpack(self, frame):
        if len(frame) != CHUNK_SIZE:
            return None

        payload_len = int.from_bytes(frame[:LEN_BYTES], byteorder='big')

        if payload_len < 0 or payload_len > MAX_PAYLOAD:
            return None

        return frame [LEN_BYTES:LEN_BYTES + payload_len]

    async def setup_sockets(self):
        self.tx_socket = self.ctx.socket(zmq.PUSH)
        self.rx_socket = self.ctx.socket(zmq.PULL)

        # Do not hang forever on close
        self.tx_socket.setsockopt(zmq.LINGER, 0)
        self.rx_socket.setsockopt(zmq.LINGER, 0)

        # Set High watermark to drop messages if buffer reaches 1000 messages
        self.tx_socket.setsockopt(zmq.SNDHWM, 10)
        self.rx_socket.setsockopt(zmq.RCVHWM, 10)

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