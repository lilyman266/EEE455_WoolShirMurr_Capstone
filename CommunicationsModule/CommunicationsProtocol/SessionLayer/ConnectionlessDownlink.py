import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session

MAX_TRIES = 5
TIMEOUT   = 5


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

class ConnectionlessDownlink(Session):
    """Base class for connectionless downlink sessions."""

    def __init__(self, layer):
        super().__init__(layer)
        self.layer               = layer
        self.name                = "ConnectionlessDownlink"
        self.logger              = LoggerFactory.get_logger(self.name)
        self.packet_number       = self.read_packet_number()
        self.handshake_rx_queue  = asyncio.Queue()
        self.connecting          = False

    async def handle_rx(self, packet: bytes):
        pass

    async def handle_tx(self, message: bytes):
        pass

    async def on_enter(self):
        self.logger.info(f"{self.name} entered")

    async def on_exit(self):
        pass


############## Ground Station #####################################################

class GroundStationConnectionlessDownlink(ConnectionlessDownlink):
    """
    RX: Receives data frames from Audimus, deframes, tracks dropped packets.
    TX: Sends SYN requests to Audimus to initiate a connected session.
        Any other outgoing message is an error.
    """

    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )
        super().__init__(layer)


    async def handle_rx(self, raw: bytes):
        """Deframe incoming packet.
        If a handshake is in progress route to the handshake queue instead."""

        if self.connecting:
            await self.handshake_rx_queue.put(raw)
            return None

        try:
            return self.deframe(raw)
        except Exception as e:
            self.logger.error(f"Failed to deframe packet: {e}")
            return None

    def deframe(self, raw: bytes):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)
        self.track_packet(frame.packet_number)
        return frame.presentation_message

    def track_packet(self, received_number: int):
        """Record any dropped packets between last received and current."""
        expected = self.packet_number + 1

        if received_number != expected:
            for dropped in range(expected, received_number):
                self.packet_tracker.record_drop(dropped)
                self.logger.warning(f"Dropped packet: {dropped}")

        self.packet_number = received_number
        self.write_packet_number(self.packet_number)


    async def handle_tx(self, message: bytes):
        """Ground station only sends SYN requests in this mode."""
        try:
            frame = self.frame_syn(message)
            return frame
        except Exception as e:
            self.logger.error(f"Failed to frame SYN: {e}")
            return None

    def frame_syn(self, mode: Audimus_pb2.SESSION_MODE) -> bytes:
        msg = Audimus_pb2.Session_Message(SYN=True, mode=mode)
        return msg.SerializeToString()


    async def on_exit(self):
        await super().on_exit()



    async def handshake(self, new_mode: Audimus_pb2.SESSION_MODE):
        """
        3-way handshake (initiator side).
        Sends SYN → waits for SYN-ACK → sends ACK → requests mode change.
        Retries up to MAX_TRIES times on timeout.
        """
        self.logger.info(f"Initiating handshake for mode {new_mode}")
        self.connecting = True

        for attempt in range(1, MAX_TRIES + 1):
            try:

                syn = Audimus_pb2.Session_Message(SYN=True, mode=new_mode)
                await self.layer.below_tx.put(syn.SerializeToString())

                raw     = await asyncio.wait_for(
                    self.handshake_rx_queue.get(), timeout=TIMEOUT
                )
                syn_ack = Audimus_pb2.Session_Message()
                syn_ack.ParseFromString(raw)

                if not syn_ack.SYNACK:
                    self.logger.warning(
                        f"Expected SYNACK, got unexpected frame (attempt {attempt}) – retrying"
                    )
                    continue


                ack = Audimus_pb2.Session_Message(ACK=True, mode=new_mode)
                await self.layer.below_tx.put(ack.SerializeToString())
                self.logger.info("handshake complete")

                await self.layer.session_queue.put(new_mode)
                self.connecting = False
                return  # success

            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Timeout waiting for SYN-ACK (attempt {attempt}/{MAX_TRIES})"
                )

        self.logger.error(f"Handshake failed after {MAX_TRIES} attempts")
        self.connecting = False


##############Audimus #####################################################

class AudimusConnectionlessDownlink(ConnectionlessDownlink):
    """
    TX: Frames outgoing data with an incrementing packet number.
    RX: Delivers payload upward. SYN frames trigger a handshake task.
    """

    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/AudimusCurrentPacketNumber"
        )
        super().__init__(layer)


    async def handle_tx(self, message: bytes) -> bytes | None:
        """Frame outgoing data. Increments and persists packet number on every
        successful transmission; rolls back on failure."""
        try:
            self.packet_number += 1
            frame = self.frame(message)
            self.write_packet_number(self.packet_number)
            await self.packet_store.store_packet(self.packet_number, frame)
            return frame
        except Exception as e:
            self.logger.error(f"Failed to frame message: {e}")
            self.packet_number -= 1  # roll back
            return None

    def frame(self, presentation_message: bytes) -> bytes:
        msg = Audimus_pb2.Session_Message(
            presentation_message = presentation_message,
            mode                 = Audimus_pb2.SESSION_MODE.ConnectionlessDownlink,
            packet_number        = self.packet_number,
            SYN                  = False,
        )
        return msg.SerializeToString()


    async def handle_rx(self, raw: bytes):
        """Deliver payload upward.
        SYN frames trigger a handshake task and return None.
        If a handshake is already in progress, route to the handshake queue."""

        if self.connecting:
            await self.handshake_rx_queue.put(raw)
            return None

        try:
            return self.deframe(raw)
        except Exception as e:
            self.logger.error(f"Failed to deframe message: {e}")
            return None

    def deframe(self, raw: bytes):
        """Parse frame. SYN triggers handshake task; data frames return payload."""
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)

        if frame.SYN:
            self.connecting = True                          # set BEFORE spawning task
            asyncio.create_task(self.handshake(frame))
            return None                                     # no payload for presentation

        return frame.presentation_message


    async def on_exit(self):
        await super().on_exit()


    async def handshake(self, syn: Audimus_pb2.Session_Message):
        """
        3-way handshake (responder side).
        Sends SYN-ACK → waits for ACK → requests mode change.
        Retries up to MAX_TRIES times on timeout.
        """
        new_mode = syn.mode
        self.logger.info(f"Handshake started for mode {new_mode}")

        for attempt in range(1, MAX_TRIES + 1):
            try:

                syn_ack = Audimus_pb2.Session_Message(SYNACK=True, mode=new_mode)
                await self.layer.below_tx.put(syn_ack.SerializeToString())


                raw      = await asyncio.wait_for(
                    self.handshake_rx_queue.get(), timeout=TIMEOUT
                )
                response = Audimus_pb2.Session_Message()
                response.ParseFromString(raw)

                if not response.ACK:
                    self.logger.warning(
                        f"Expected ACK, got unexpected frame (attempt {attempt}) – retrying"
                    )
                    continue

                self.logger.info(f"Handshake complete")
                await self.layer.session_queue.put(new_mode)
                self.connecting = False
                return  # success

            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Timeout waiting for ACK (attempt {attempt}/{MAX_TRIES})"
                )

        self.logger.error(f"Handshake failed after {MAX_TRIES} attempts")
        self.connecting = False
