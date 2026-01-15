from CommunicationsProtocol import ProtocolLayer
from Logger.Logger import LoggerFactory
from asyncio import QueueEmpty
from CommunicationsProtocol.SessionLayer.Session import ConnectedUplink, ConnectedDownlink, ConnectionlessDownlink
from enum import Enum



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
        self.state = None
        self.logger = LoggerFactory.get_logger(self.name)

    def change_state(self, state):
        self.logger.info(f"state changing to: {state}")
        match state:
            case SessionMode.CONNECTED_UPLINK:
                self.state = ConnectedUplink(self.DLL_rx, self.DLL_tx)
            case SessionMode.CONNECTED_DOWNLINK:
                self.state = ConnectedDownlink(self.DLL_rx, self.DLL_tx)
            case SessionMode.CONNECTIONLESS_DOWNLINK:
                self.state = ConnectionlessDownlink(self.DLL_rx, self.DLL_tx)
            case _ :
                print("Error!!!! state passing getting fucked up again")

        # check state by checking state_change_queue

    async def rx(self):
        while True:

            # grab message from the below layers rx queue
            message = await self.below_rx.get()

            # do the thing to the message
            message = self.process_rx(message)

            # put message into rx queue of this layer
            await self.layer_rx.put(message)


    async def tx(self):
        while True:
            # grab the message from this layer's tx queue
            message = await self.layer_tx.get()

            # do the thing to the message
            message = await self.process_tx(message)

            # put message into the tx queue of the layer below
            await self.below_tx.put(message)


class GroundStationSessionLayer(SessionLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx, state_change_queue):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.state_change_queue = state_change_queue
        self.state = ConnectionlessDownlink(DLL_rx, DLL_tx)

    async def process_tx(self, message):
        self.tx_state_change()
        self.logger.info(str(message))
        return message

    def process_rx(self, message):
        return message

    def tx_state_change(self):
        try:
            state = self.state_change_queue.get_nowait()
        except QueueEmpty:
            return
        self.change_state(state)


class AudimusSessionLayer(SessionLayer):
    def __init__(self, SL_rx,SL_tx, DLL_rx, DLL_tx):
        super().__init__(SL_rx,SL_tx, DLL_rx, DLL_tx)
        self.state = ConnectionlessDownlink(DLL_rx, DLL_tx)

    async def process_tx(self, message):
        self.logger.info(str(message))
        return message

    def process_rx(self, message):
        return message

    # check state by examining incoming messages
    def check_state(self):
        pass


