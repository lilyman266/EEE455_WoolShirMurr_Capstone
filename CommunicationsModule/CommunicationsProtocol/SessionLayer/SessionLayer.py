from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import asyncio
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectionlessDownlink import  GroundStationConnectionlessDownlink, AudimusConnectionlessDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedDownlink import GroundStationConnectedDownlink, AudimusConnectedDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedUplink import GroundStationConnectedUplink, AudimusConnectedUplink
from CommunicationsModule.Logger.Errors import StateChangeError as SessionChangeError
import CommunicationsModule.Audimus_pb2 as Audimus_pb2

import asyncio
import time
from enum import Enum

class SessionLayer:
    def __init__(self, sl_rx, sl_tx, dll_rx, dll_tx, session_queue):
        self.below_rx      = dll_rx
        self.below_tx      = dll_tx
        self.layer_rx      = sl_rx
        self.layer_tx      = sl_tx
        self.mode          = None
        self.session       = None                          # explicit init
        self.name          = "Session Layer"
        self.logger        = LoggerFactory.get_logger(self.name)
        self.session_queue = session_queue
        self._tasks        = []
        self._session_lock = asyncio.Lock()

    async def start(self):
        """Call this after the event loop is running"""
        self._tasks = [
            asyncio.create_task(self.state_watcher(), name="state_watcher"),
            asyncio.create_task(self.rx(),            name="session_rx"),
            asyncio.create_task(self.tx(),            name="session_tx"),
        ]

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def rx(self):
        while True:
            packet = await self.below_rx.get()

            async with self._session_lock:
                session = self.session

            if session is None:
                self.logger.warning("Packet dropped - no active session")
                continue

            message = await session.handle_rx(packet)

            if message is not None:
                await self.layer_rx.put(message)

    async def tx(self):
        while True:
            message = await self.layer_tx.get()

            async with self._session_lock:
                session = self.session

            if session is None:
                self.logger.warning("Message dropped - no active session")
                continue

            packet = await session.handle_tx(message)

            if packet is not None:
                await self.below_tx.put(packet)

    async def state_watcher(self):              # lives in base, not duplicated
        while True:

            new_mode = await self.session_queue.get()

            if self.mode == new_mode:
                self.logger.info(f"Already in mode: {new_mode}")
                continue

            await self.set_session(new_mode)

    async def set_session(self, new_mode: Audimus_pb2.SESSION_MODE):
        pass






##################################Ground Station###########################################


class GroundStationSessionLayer(SessionLayer):
    def __init__(self, layer_rx, layer_tx, dll_rx, dll_tx, sl_sc):
        super().__init__(layer_rx, layer_tx, dll_rx, dll_tx, sl_sc)

    async def start(self):
        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
        await super().start()


    async def set_session(self, new_mode: Audimus_pb2.SESSION_MODE):

        async with self._session_lock:

            if self.session:
                await self.session.on_exit()

            self.mode = new_mode
            match self.mode:
                case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                    self.session = GroundStationConnectionlessDownlink(self)
                case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                    self.session = GroundStationConnectedUplink(self)
                case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                    self.session = GroundStationConnectedDownlink(self)
                case _:
                    raise SessionChangeError("Error changing session")

            await self.session.on_enter()



##################################Audimus###########################################

class AudimusSessionLayer(SessionLayer):
    def __init__(self, layer_rx, layer_tx, dll_rx, dll_tx, sl_sq):
        super().__init__(layer_rx, layer_tx, dll_rx, dll_tx, sl_sq)

    async def start(self):
        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
        await super().start()

    async def set_session(self, new_mode: Audimus_pb2.SESSION_MODE):


        async with self._session_lock:

            if self.session:
                await self.session.on_exit()

            self.mode = new_mode
            match self.mode:
                case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                    self.session = AudimusConnectionlessDownlink(self)
                case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                    self.session = AudimusConnectedUplink(self)
                case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                    self.session = AudimusConnectedDownlink(self)
                case _:
                    raise SessionChangeError("Error changing session")

            await self.session.on_enter()