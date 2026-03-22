import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode

MAX_TRIES = 5
TIMEOUT   = 5


class ConnectionlessDownlink(Session):

    def __init__(self, layer):
        super().__init__(layer)
        self.layer               = layer
        self.name                = "ConnectionlessDownlink"
        self.logger              = LoggerFactory.get_logger(self.name)
        self.connecting          = False

    async def handle_rx(self, packet: bytes):
        pass

    async def handle_tx(self, message: bytes):
        pass

    async def on_enter(self):
        self.logger.info("Entered ConnectionlessDownlink Mode")

    async def on_exit(self):
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
class GroundStationConnectionlessDownlink(ConnectionlessDownlink):
    """ rx receives data frames from Audimus, deframes, tracks dropped packets
    tx Sends SYN requests to Audimus to initiate a connected session
    Any other outgoing message is an error."""

    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )
        self.packet_number = self.read_packet_number()
        super().__init__(layer)

    async def on_enter(self):
        self.logger.info("Entered ConnectionlessDownlink Mode")
        self.layer.mode_switch(RadioMode.RX)


    async def handle_rx(self, raw: bytes):

        try:
            frame =  self.deframe(raw)
        except Exception as e:
            self.logger.error(f"Failed to deframe packet: {e}")
            return None
        return frame.presentation_message


    #deframe incoming packet
    def deframe(self, raw: bytes):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)
        print(frame.packet_number)
        self.track_packet(frame.packet_number)
        return frame

    #tracks incoming packet numbers, if one is dropped, we record it
    def track_packet(self, received_number: int):
        expected = self.packet_number + 1

        if received_number != expected:
            for dropped in range(expected, received_number):
                self.layer.packet_tracker.record_drop(dropped)
                self.logger.warning(f"Dropped packet: {dropped}")

        self.packet_number = received_number
        self.write_packet_number(self.packet_number)

    async def handle_tx(self, message: bytes):
        self.logger.info("Ground station does not send during connectionless downlink. Wait for next pass")

    def frame_syn(self, mode: Audimus_pb2.SESSION_MODE) -> bytes:
        msg = Audimus_pb2.Session_Message(SYN=True, mode=mode)
        return msg.SerializeToString()


    async def on_exit(self):
        await super().on_exit()



##############Audimus #####################################################

class AudimusConnectionlessDownlink(ConnectionlessDownlink):

    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/AudimusCurrentPacketNumber"
        )
        super().__init__(layer)
        self.packet_number = self.read_packet_number()



    async def on_enter(self):
        await super().on_enter()
        await self.layer.mode_put(RadioMode.TX)



    async def handle_tx(self, message: bytes) -> bytes | None:
        try:
            self.packet_number += 1
            await self.layer.packet_store.store_packet(self.packet_number, message)
            frame = self.frame(message)
            self.write_packet_number(self.packet_number)
            return frame
        except Exception as e:
            self.logger.error(f"Failed to frame message: {e}")
            self.packet_number -= 1  # roll back        await self.layer.mode_put(RadioMode.TX)
            return None


    def frame(self, presentation_message: bytes) -> bytes:
        msg = Audimus_pb2.Session_Message(
            presentation_message = presentation_message,
            mode = Audimus_pb2.SESSION_MODE.ConnectionlessDownlink,
            packet_number = self.packet_number,
            SYN = False,
        )
        return msg.SerializeToString()


    async def handle_rx(self, raw: bytes):
        self.logger.info("Audimus should not rx in connectionless downlink")



    #syn will trigger handshake
    async def deframe(self, raw: bytes):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)
        return frame



    async def on_exit(self):
        await super().on_exit()

