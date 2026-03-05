from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
import asyncio
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectionlessDownlink import  GroundStationConnectionlessDownlink, AudimusConnectionlessDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedDownlink import GroundStationConnectedDownlink, AudimusConnectedDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedUplink import GroundStationConnectedUplink, AudimusConnectedUplink
from CommunicationsModule.Logger.Errors import StateChangeError as SessionChangeError
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import SessionMode



class SessionLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.name = "Session Layer     "
        self.logger = LoggerFactory.get_logger(self.name)
        self.transition_lock = asyncio.Lock()
        self.DLL_rx = DLL_rx


class GroundStationSessionLayer(SessionLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx, state_change_queue):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.session_queue = state_change_queue
        self.session = None
        self.mode = None
        self.tx_handler = None
        self.rx_handler = None
        asyncio.create_task(self.set_session(SessionMode.CONNECTIONLESS_DOWNLINK))


    async def rx(self):
        try:
            while True:
                message = await self.session.rx()
                await self.layer_rx.put(message)
        except asyncio.CancelledError:
            raise

    async def tx(self):
        try:
            while True:
                message = await self.layer_tx.get()
                message = self.process_tx(message)
                await self.session.tx(message)
        except asyncio.CancelledError:
            raise

    def process_tx(self, message):
        self.logger.info(message)
        return message


    #sets session and makes connection if necessary. Stops rx and tx handlers.
    async def set_session(self, new_mode: SessionMode):
        async with self.transition_lock:

            if self.mode == new_mode:
                self.logger.info(f"allready in mode: {new_mode}")
                return

            self.logger.info(f"session changing to: {new_mode}")

            #cancel the running tx and rx
            if self.tx_handler:
                self.tx_handler.cancel()
                try:
                    await self.tx_handler
                except asyncio.CancelledError:
                    pass

            if self.rx_handler:
                self.rx_handler.cancel()
                try:
                    await self.rx_handler
                except asyncio.CancelledError:
                    pass

            #if there is a connection, tear it down
            if self.mode == SessionMode.CONNECTED_UPLINK or self.mode == SessionMode.CONNECTED_DOWNLINK:
                asyncio.create_task(self.session.tear_down())

            self.mode = new_mode

            #match for new connection
            match self.mode:
                case SessionMode.CONNECTIONLESS_DOWNLINK:
                    self.session = GroundStationConnectionlessDownlink(self.below_rx, self.below_tx)

                case SessionMode.CONNECTED_UPLINK:
                    self.session = GroundStationConnectedUplink(self.below_rx, self.below_tx, self.session_queue)
                    await asyncio.create_task(self.session.handshake())

                case SessionMode.CONNECTED_DOWNLINK:
                    self.session = GroundStationConnectedDownlink(self.below_rx, self.below_tx)

                case _:
                    raise SessionChangeError("Error changing session")

            #restart rx and tx coroutines
            self.tx_handler = asyncio.create_task(self.tx())
            self.rx_handler = asyncio.create_task(self.rx())


    async def state_watcher(self):
        while True:
            session = await self.session_queue.get()
            await self.set_session(session)



class AudimusSessionLayer(SessionLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx, SSQ):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.session_queue = SSQ
        self.session = None
        self.mode = None
        self.tx_handler = None
        self.rx_handler = None
        asyncio.create_task(self.set_session(SessionMode.CONNECTIONLESS_DOWNLINK))

    async def rx(self):
        while True:
            message = await self.session.rx()
            print(message)
            await self.layer_rx.put(message)

    async def tx(self):
        while True:
            message = await self.layer_tx.get()
            self.logger.info(message)
            message = self.process_tx(message)
            await self.session.tx(message)

    async def state_watcher(self):
        while True:
            session = await self.session_queue.get()
            await self.set_session(session)

    async def set_session(self, new_mode):
        async with self.transition_lock:

            if self.mode == new_mode:
                self.logger.info(f"allready in mode: {new_mode}")
                return

            self.logger.info(f"session changing to: {new_mode}")

            # cancel rx and tx couroutines
            if self.tx_handler:
                self.tx_handler.cancel()

            if self.rx_handler:
                self.rx_handler.cancel()

            # if there is a connection, tear it down
            if self.mode == SessionMode.CONNECTED_UPLINK or self.mode == SessionMode.CONNECTED_DOWNLINK:
                asyncio.create_task(self.session.tear_down())

            self.mode = new_mode

            # match for new connection
            match self.mode:
                case SessionMode.CONNECTIONLESS_DOWNLINK:
                    self.session = AudimusConnectionlessDownlink(self.below_rx, self.below_tx, self.session_queue)

                case SessionMode.CONNECTED_UPLINK:
                    self.session = AudimusConnectedUplink(self.below_rx, self.below_tx, self.session_queue)
                    await asyncio.create_task(self.session.handshake())

                case SessionMode.CONNECTED_DOWNLINK:
                    self.session = AudimusConnectedDownlink(self.below_rx, self.below_tx, self.session_queue)

                case _:
                    raise SessionChangeError("Error changing session")

            # restart rx and tx coroutines
            self.tx_handler = asyncio.create_task(self.tx())
            self.rx_handler = asyncio.create_task(self.rx())


    def process_tx(self, message):
        return message

    def process_rx(self, message):
        return message




