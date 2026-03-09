import asyncio
import time

import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session

MAX_TRIES = 5
TIMEOUT   = 1.5


class ConnectedUplink(Session):
    """Full-duplex connected uplink session.
    TX: Frame outgoing payload with sequence number
        Send message to layer below
        Wait for ACK with same SEQ
        Retransmit on timeout up to MAX_TRIES
    RX: ACK frame: route to internal ACK queue
        If DATA frame: ACK immediately, suppress duplicates, deliver upward"""

    def __init__(self, layer):
        super().__init__(layer)
        self.name = "ConnectedUplink"
        self.logger = LoggerFactory.get_logger(self.name)
        self.ack_queue = asyncio.Queue()
        self.tx_seq = 0
        self.last_rx_seq = 0
        self.tx_lock = asyncio.Lock()

    async def on_enter(self):
        self.logger.info(f"{self.name} entered")

    async def on_exit(self):
        self.logger.info(f"{self.name} exiting")

    async def handle_rx(self, raw: bytes):
        """ACKs frames are consumed internally and not passed upward.
           DATA frames are ACKed immediately and delivered upward.
           Duplicate DATA frames are ACKed again but not redelivered."""

        try:
            frame = Audimus_pb2.Session_Message()
            frame.ParseFromString(raw)

            self.logger.info(
                f"handle_rx self={id(self)} queue={id(self.ack_queue)} "
                f"ACK={frame.ACK} seq={frame.packet_number}"
            )

            if frame.mode != Audimus_pb2.SESSION_MODE.ConnectedUplink:
                self.logger.warning(
                    f"Unexpected mode received: {frame.mode} in {self.name}"
                )

            # ACK path
            if frame.ACK:
                self.logger.debug(f"ACK received for seq={frame.packet_number}")
                await self.ack_queue.put(frame)
                return None

            # DATA path: ACK immediately
            ack = self.build_ack(frame.packet_number)
            await self.layer.below_tx.put(ack)
            self.logger.info(f"ACK sent for seq={frame.packet_number}")

            # Duplicate / retransmitted frame: ACKed already, do not redeliver
            if frame.packet_number <= self.last_rx_seq:
                self.logger.warning(
                    f"Duplicate/old packet received seq={frame.packet_number}, "
                    f"last_rx_seq={self.last_rx_seq}; payload dropped after ACK"
                )
                return None

            # Ordered delivery is expected; log if there is a jump
            expected_seq = self.last_rx_seq + 1
            if frame.packet_number != expected_seq:
                self.logger.warning(
                    f"Sequence jump detected: got seq={frame.packet_number}, "
                    f"expected seq={expected_seq}; accepting anyway"
                )

            self.last_rx_seq = frame.packet_number
            return frame.presentation_message

        except Exception as e:
            self.logger.error(f"handle_rx error: {e}")
            return None

    async def handle_tx(self, message):
        """Frame, send, and wait for ACK.
        Retransmits up to MAX_TRIES times before giving up."""


        async with self.tx_lock:
            self.tx_seq += 1
            seq = self.tx_seq
            frame = self.frame(message, seq)



            for attempt in range(1, MAX_TRIES + 1):

                await self.layer.below_tx.put(frame)
                deadline = time.monotonic() + TIMEOUT

                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break

                    try:
                        ack = await asyncio.wait_for(
                            self.ack_queue.get(),
                            timeout=remaining
                        )
                    except asyncio.TimeoutError:
                        break

                    if ack.packet_number == seq:
                        return None

                    # Old ACK from an earlier packet/retry
                    self.logger.warning(
                        f"Stale ACK received seq={ack.packet_number}, expected {seq}"
                    )

                self.logger.warning(
                    f"Timeout waiting for ACK (seq={seq}, attempt {attempt})"
                )

            self.logger.error(f"Packet seq={seq} failed after {MAX_TRIES} attempts")
            return None

    def frame(self, presentation_message, seq):
        msg = Audimus_pb2.Session_Message(
            presentation_message = presentation_message,
            mode = Audimus_pb2.SESSION_MODE.ConnectedUplink,
            packet_number = seq,
            SYN = False,
            ACK = False
        )

        return msg.SerializeToString()

    def build_ack(self, seq: int) -> bytes:
        ack  = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedUplink,
            packet_number=seq,
            SYN=False,
            ACK=True
        )
        return ack.SerializeToString()


################################## Ground Station ###########################################

class GroundStationConnectedUplink(ConnectedUplink):
    """Ground station side of full-duplex connected uplink."""

    def __init__(self, layer):
        super().__init__(layer)




################################## Audimus ###########################################

class AudimusConnectedUplink(ConnectedUplink):
    """Audimus side of full-duplex connected uplink."""

    def __init__(self, layer):
        super().__init__(layer)

