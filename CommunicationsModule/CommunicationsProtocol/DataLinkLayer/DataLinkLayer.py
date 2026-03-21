from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import zmq.asyncio
import asyncio
CHUNK_SIZE = 1024
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode
import zmq
import xmlrpc.client


class DataLinkLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, DLL_rx, DLL_tx,radio_mode_queue):
        super().__init__(DLL_rx, DLL_tx, None, None)
        self.name = "Data Link Layer   "
        self.logger = LoggerFactory.get_logger(self.name)
        self.radio_mode_queue = radio_mode_queue
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
        self.tasks.append(asyncio.create_task(self.mode_watcher()))
        self.tasks.append(asyncio.create_task(self.rx_zmq()))
        self.tasks.append(asyncio.create_task(self.tx_zmq()))


    async def mode_watcher(self):
        while True:

            new_mode = await self.radio_mode_queue.get()
            print(new_mode)
            if new_mode != self.mode:

                # before switching modes, change the flowgraph
                async with self.mode_lock:
                    self.logger.info(f"radio switching to: {new_mode}")

                    if new_mode == RadioMode.TX:
                        self.proxy.set_mode(1)
                    if new_mode == RadioMode.RX:
                        self.proxy.set_mode(2)
                    await asyncio.sleep(10)
                self.logger.info(f"radio switched to: {self.mode}")

    async def tx_zmq(self):
        while True:
            print("entering TX loop")
            message = await self.layer_tx.get()
            self.logger.info(f"TX got: {message}")
            async with self.mode_lock:
                current_mode = self.mode
            print(current_mode)
            if current_mode != RadioMode.TX:
                self.logger.warning("Dropping TX message: not in TX mode")


            if isinstance(message, str):
                message = message.encode()

            padded = message.ljust(CHUNK_SIZE, b'\x00')[:CHUNK_SIZE]
            await self.tx_socket.send(padded)
            self.logger.info(f"TX: {message}")

    # receives from GNU radio with ZMQ
    async def rx_zmq(self):
        while True:
            async with self.mode_lock:
                current_mode = self.mode

            if current_mode != RadioMode.RX:
                await asyncio.sleep(0.05)
                continue

            message = await self.rx_socket.recv()
            await self.layer_rx.put(message)



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
    def __init__(self, DLL_rx, DLL_tx, radio_mode_queue):
        super().__init__(DLL_rx,DLL_tx, radio_mode_queue)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message


class AudimusDataLinkLayer(DataLinkLayer):
    def __init__(self, DLL_rx, DLL_tx, radio_mode_queue):
        super().__init__(DLL_rx,DLL_tx, radio_mode_queue)

    def process_rx(self, message):
        return message

    def process_tx(self, message):
        return message