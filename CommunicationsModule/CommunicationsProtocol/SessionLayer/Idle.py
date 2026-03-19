import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode

MAX_TRIES = 5
TIMEOUT   = 5


class Idle(Session):

    def __init__(self, layer):
        super().__init__(layer)
        self.layer               = layer
        self.name                = "Idle"
        self.logger              = LoggerFactory.get_logger(self.name)

        self.packet_number       = self.read_packet_number()
        self.handshake_rx_queue  = asyncio.Queue()
        self.connecting          = False

    async def handle_rx(self, packet: bytes):
        pass

    async def handle_tx(self, message: bytes):
        pass


    def read_packet_number(self):
        try:
            with open(self.packet_number_path, 'r') as file:
                line = file.readline()
                return int(line.strip()) if line else None
        except FileNotFoundError:
            # Handle the case where the file doesn't exist yet
            print(f"File not found: {self.packet_number_path}")
            return None




############## Ground Station #####################################################
class GroundStationIdle(Idle):
    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )
        self.packet_number = self.read_packet_number()
        super().__init__(layer)


    async def handle_rx(self, message):
        self.logger.info("GS should not recieve message in idle")



    #deframe incoming packet
    def deframe(self, raw: bytes):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)
        return frame


    async def handle_tx(self, message: bytes):
        try:
            frame = self.frame_syn(message)
            return frame
        except Exception as e:
            self.logger.error(f"Failed to frame SYN: {e}")
            return None


    # #tracks incoming packet numbers, if one is dropped, we record it
    # def track_packet(self, received_number: int):
    #     expected = self.packet_number + 1
    #
    #     if received_number != expected:
    #         for dropped in range(expected, received_number):
    #             self.layer.packet_tracker.record_drop(dropped)
    #             self.logger.warning(f"Dropped packet: {dropped}")
    #
    #     self.packet_number = received_number
    #     self.write_packet_number(self.packet_number)


##############Audimus #####################################################

class AudimusIdle(Idle):
    """ only rx syn for handshake. sends packets oblivious to drops. GS records and will request for retarnsmit it
    connected downlink"""

    def __init__(self, layer):

        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/AudimusCurrentPacketNumber"
        )
        self.packet_number = self.read_packet_number()
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





    # async def handle_tx(self, message: bytes) -> bytes | None:
    #     try:
    #         return self.frame(message)
    #     except Exception as e:
    #         self.logger.error(f"Failed to frame message: {e}")
    #         self.packet_number -= 1  # roll back
    #         return None




