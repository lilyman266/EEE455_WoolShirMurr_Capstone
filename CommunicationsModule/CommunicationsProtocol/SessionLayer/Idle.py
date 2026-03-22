import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode




class Idle(Session):

    def __init__(self, layer):
        super().__init__(layer)
        self.layer               = layer
        self.name                = "Idle"
        self.logger              = LoggerFactory.get_logger(self.name)


    async def on_enter(self):
        await super().on_enter()
        await self.layer.mode_put(RadioMode.RX)
        self.logger.info("Entered Idle Mode")

    async def handle_rx(self, packet: bytes):
        pass

    async def handle_tx(self, message: bytes):
        pass


############## Ground Station #####################################################
class GroundStationIdle(Idle):
    def __init__(self, layer):
        super().__init__(layer)

    async def handle_rx(self, message):
        self.logger.info("GS should not rx in idle")


    async def handle_tx(self, message: bytes):
        self.logger.info("GS should not send tx in idle")



##############Audimus #####################################################

class AudimusIdle(Idle):
    """ only rx syn for handshake. sends packets oblivious to drops. GS records and will request for retarnsmit it
    connected downlink"""

    def __init__(self, layer):
        super().__init__(layer)



    def frame(self, presentation_message: bytes) -> bytes:
        msg = Audimus_pb2.Session_Message(
            presentation_message = presentation_message,
            mode = Audimus_pb2.SESSION_MODE.Idle,
            packet_number = self.packet_number,
            SYN = False,
        )
        return msg.SerializeToString()


    # if we recieve a new mode, change to that mode
    async def handle_rx(self, message):

        try:
            frame =  await self.deframe(message)

            if frame.mode:
                if frame.mode != Audimus_pb2.SESSION_MODE.Idle:
                    await self.layer.set_session(frame.mode)
                if frame.mode == Audimus_pb2.SESSION_MODE.Idle:
                    return

            return None
        except Exception as e:
            self.logger.error(f"Failed to deframe message: {e}")
            return None


    async def deframe(self, raw: bytes):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)
        return frame









