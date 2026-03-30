import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode

ATTEMPTS = 5
TIMEOUT = 1


class Idle(Session):

    def __init__(self, layer):
        super().__init__(layer)
        self.layer               = layer
        self.name                = "Idle"
        self.logger              = LoggerFactory.get_logger(self.name)

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

    async def deframe(self, msg):
        message = Audimus_pb2.Session_Message()
        message.ParseFromString(msg)
        return message


############## Ground Station #####################################################
class GroundStationIdle(Idle):
    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )
        self.packet_number = self.read_packet_number()
        super().__init__(layer)
        self.SYNACK_queue = asyncio.Queue()



    async def switch_mode(self, new_mode):
        syn = await self.frame_SYN(new_mode)
        for attempt in range(ATTEMPTS):
            await self.layer.swap_put(syn)
            try:
                await asyncio.wait_for(self.SYNACK_queue.get(), timeout=TIMEOUT)
                await self.layer.set_session(new_mode)
                return

            except asyncio.TimeoutError:
                self.logger.warning(f"ACK timeout, retrying SYN for mode {new_mode}...")
        self.logger.info(f"Attempts exhausted, failed to switch to {new_mode}, staying in idle")

    async def frame_SYN(self, new_mode):
        msg = Audimus_pb2.Session_Message(
            mode=new_mode,
            SYN=True
        )
        return msg.SerializeToString()


    async def handle_rx(self, message):
        message = await self.deframe(message)
        if message.SYN and message.ACK:
            await self.SYNACK_queue.put(message)


    async def handle_tx(self, message: bytes):
        self.logger.info("GS should not send tx in idle")



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



    def frame_SYNACK(self, new_mode):
        msg = Audimus_pb2.Session_Message(
            mode=new_mode,
            SYN=True,
            ACK=True
        )
        return msg.SerializeToString()

    def frame_FINACK(self, new_mode):
        msg = Audimus_pb2.Session_Message(
            mode=new_mode,
            FIN=True,
            ACK=True,
        )
        return msg.SerializeToString()

    async def handle_rx(self, msg):
        """# if we recieve a new mode, change to that mode, put a SYNACK in the queue."""

        self.activity_timer.reset()
        message = await self.deframe(msg)

        if message.SYN:
            ack = self.frame_SYNACK(message.mode)
            await self.layer.swap_put(ack)
            await self.layer.set_session(message.mode)
            return None

        if message.FIN:
            fin_ack = self.frame_FINACK(message.mode)
            await self.layer.swap_put(fin_ack)
            await self.layer.set_session(message.mode)
            return None

        return None











    # async def handle_tx(self, message: bytes) -> bytes | None:
    #     try:
    #         return self.frame(message)
    #     except Exception as e:
    #         self.logger.error(f"Failed to frame message: {e}")
    #         self.packet_number -= 1  # roll back
    #         return None




