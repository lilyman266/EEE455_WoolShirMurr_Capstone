from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
from asyncio import QueueEmpty
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectionlessDownlink import  GroundStationConnectionlessDownlink, AudimusConnectionlessDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedDownlink import GroundStationConnectedDownlink, AudimusConnectedDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedUplink import GroundStationConnectedUplink, AudimusConnectedUplink
from enum import Enum


from CommunicationsModule.Logger.Errors import StateChangeError


class SessionMode(Enum):
    CONNECTED_UPLINK = 0
    CONNECTED_DOWNLINK = 1
    CONNECTIONLESS_DOWNLINK =2


class SessionLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.name = "Session Layer     "
        self.logger = LoggerFactory.get_logger(self.name)

class GroundStationSessionLayer(SessionLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx, state_change_queue):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.state_change_queue = state_change_queue
        self.set_state(SessionMode.CONNECTIONLESS_DOWNLINK)

    async def rx(self):
        while True:
            message = await self.session.rx()
            self.logger.info(f"Rx: {str(message)}")
            await self.layer_rx.put(message)


    async def tx(self):
        while True:
            message = await self.layer_tx.get()
            self.logger.info(f"Tx: {str(message)}")
            message = self.process_tx(message)
            await self.session.tx(message)

    def process_tx(self, message):
        self.check_state()
        self.logger.info(message)
        return message

    def set_state(self, state):
        self.logger.info(f"state changing to: {state}")

        match state:
            case SessionMode.CONNECTED_UPLINK:
                self.session = GroundStationConnectedUplink(self, self.below_rx, self.below_tx)
            case SessionMode.CONNECTED_DOWNLINK:
                self.session = GroundStationConnectedDownlink(self, self.below_rx, self.below_tx)
            case SessionMode.CONNECTIONLESS_DOWNLINK:
                self.session = GroundStationConnectionlessDownlink(self, self.below_rx, self.below_tx)

            case _ :
                raise StateChangeError("Error changing state")


    def check_state(self):
        try:
            state = self.state_change_queue.get_nowait()
        except QueueEmpty:
            return
        self.set_state(state)


class AudimusSessionLayer(SessionLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.set_state(SessionMode.CONNECTIONLESS_DOWNLINK)

    async def rx(self):
        while True:
            message = await self.session.rx()
            self.logger.info(f"Rx: {str(message)}")
            await self.layer_rx.put(message)


    async def tx(self):
        while True:
            message = await self.layer_tx.get()
            self.logger.info(f"Tx: {str(message)}")
            message = self.process_tx(message)
            await self.session.tx(message)


    def set_state(self, state):
        self.logger.info(f"state changing to: {state}")
        match state:
            case SessionMode.CONNECTED_UPLINK:
                self.session = AudimusConnectedUplink(self, self.below_rx, self.below_tx)
            case SessionMode.CONNECTED_DOWNLINK:
                self.session = AudimusConnectedDownlink(self, self.below_rx, self.below_tx)
            case SessionMode.CONNECTIONLESS_DOWNLINK:
                self.session = AudimusConnectionlessDownlink(self, self.below_rx, self.below_tx)
            case _ :
                raise StateChangeError("Error changing state")


    def process_tx(self, message):
        self.logger.info(f"Tx: {str(message)}")
        return message

    def process_rx(self, message):
        self.logger.info(f"Rx: {str(message)}")
        return message




