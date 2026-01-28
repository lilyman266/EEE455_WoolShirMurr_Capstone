from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
from asyncio import QueueEmpty
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import AudimusConnectedUplink, AudimusConnectedDownlink, AudimusConnectionlessDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import GroundStationConnectedUplink, GroundStationConnectedDownlink, GroundStationConnectionlessDownlink
from enum import Enum
import CommunicationsModule.Audimus_pb2 as Audimus_pb2



class SessionMode(Enum):
    CONNECTED_UPLINK = 0
    CONNECTED_DOWNLINK = 1
    CONNECTIONLESS_DOWNLINK =2


class SessionLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.DLL_rx = DLL_rx
        self.DLL_tx = DLL_tx
        self.name = "Session Layer     "
        self.logger = LoggerFactory.get_logger(self.name)
        self.session = GroundStationConnectionlessDownlink(DLL_rx, DLL_tx)


        # check state by checking state_change_queue

    async def rx(self):
        while True:

            # grab message from the below layers rx queue
            message = await self.below_rx.get()

            # put message into session
            await self.session.rx()


    async def tx(self):
        while True:
            # grab the message from this layer's tx queue
            message = await self.layer_tx.get()

            message = self.process_tx(message)

            # put message into the tx queue of the layer below
            await self.session.tx(message)


class GroundStationSessionLayer(SessionLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx, state_change_queue):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.state_change_queue = state_change_queue

    def process_tx(self, message):
        self.check_state()
        self.logger.info(message)
        return message


    def change_state(self, state):
        self.logger.info(f"state changing to: {state}")
        match state:
            case SessionMode.CONNECTED_UPLINK:
                self.session = GroundStationConnectedUplink(self.DLL_rx, self.DLL_tx)
            case SessionMode.CONNECTED_DOWNLINK:
                self.session = GroundStationConnectedDownlink(self.DLL_rx, self.DLL_tx)
            case SessionMode.CONNECTIONLESS_DOWNLINK:
                self.session = GroundStationConnectionlessDownlink(self.DLL_rx, self.DLL_tx)
            case _ :
                print("Error!!!! state passing getting fucked up again")


    def check_state(self):
        try:
            state = self.state_change_queue.get_nowait()
        except QueueEmpty:
            return
        self.change_state(state)


class AudimusSessionLayer(SessionLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)

    def change_state(self, state):
        self.logger.info(f"state changing to: {state}")
        match state:
            case SessionMode.CONNECTED_UPLINK:
                self.session = AudimusConnectedUplink(self.DLL_rx, self.DLL_tx)
            case SessionMode.CONNECTED_DOWNLINK:
                self.session = AudimusConnectedDownlink(self.DLL_rx, self.DLL_tx)
            case SessionMode.CONNECTIONLESS_DOWNLINK:
                self.session = AudimusConnectionlessDownlink(self.DLL_rx, self.DLL_tx)
            case _ :
                print("Error!!!! state passing getting fucked up again")


    def process_tx(self, message):
        self.logger.info(str(message))
        return message

    def process_rx(self, message):


        return message

    # check state by examining incoming messages
    def check_state(self):
        pass


