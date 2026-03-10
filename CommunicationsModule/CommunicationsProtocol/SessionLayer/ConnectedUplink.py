import asyncio
import time

import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session

MAX_TRIES        = 5
TIMEOUT          = 1.5
TEARDOWN_TIMEOUT = 3.0


class ConnectedUplink(Session):
    """Full-duplex connected uplink session.
    TX: Frame outgoing payload with sequence number
        Send message to layer below
        Wait for ACK with same SEQ
        Retransmit on timeout up to MAX_TRIES
    RX: ACK frame: route to internal ACK queue
        If DATA frame: ACK immediately, suppress duplicates, deliver upward
        FIN frame: ACK immediately, push mode change via session_queue
    Teardown (ground station only):
        on_exit sends FIN and waits for FIN-ACK up to MAX_TRIES times."""

    def __init__(self, layer):
        super().__init__(layer)
        self.name          = "ConnectedUplink"
        self.logger        = LoggerFactory.get_logger(self.name)
        self.ack_queue     = asyncio.Queue()
        self.fin_ack_queue = asyncio.Queue()
        self.tx_seq        = 0
        self.last_rx_seq   = 0
        self.tx_lock       = asyncio.Lock()

        # ── teardown coordination ──────────────────────────────────────────
        # Set just before _send_teardown acquires tx_lock.
        # handle_tx checks this BEFORE acquiring the lock so it fails fast
        # without queuing another frame behind the FIN.
        self._teardown_requested = asyncio.Event()

    # ------------------------------------------------------------------ rx ---

    async def handle_rx(self, raw: bytes):
        """ACK frames are consumed internally and not passed upward.
           DATA frames are ACKed immediately and delivered upward.
           Duplicate DATA frames are ACKed again but not redelivered.
           FIN frames are ACKed and trigger a mode change on the satellite."""

        try:
            frame = Audimus_pb2.Session_Message()
            frame.ParseFromString(raw)

            self.logger.info(
                f"handle_rx self={id(self)} queue={id(self.ack_queue)} "
                f"ACK={frame.ACK} FIN={frame.FIN} seq={frame.packet_number}"
            )

            if frame.mode != Audimus_pb2.SESSION_MODE.ConnectedUplink:
                self.logger.warning(
                    f"Unexpected mode received: {frame.mode} in {self.name}"
                )

            # FIN-ACK path (ground station teardown receiving confirmation)
            if frame.FIN and frame.ACK:
                self.logger.debug("FIN-ACK received")
                await self.fin_ack_queue.put(frame)
                return None

            # ACK path
            if frame.ACK:
                self.logger.debug(f"ACK received for seq={frame.packet_number}")
                await self.ack_queue.put(frame)
                return None

            # FIN path (satellite receiving teardown notice)
            if frame.FIN:
                self.logger.info("FIN received – sending FIN-ACK and triggering mode change")
                fin_ack = self._build_fin_ack()
                await self.layer.below_tx.put(fin_ack)
                await self.layer.session_queue.put(
                    Audimus_pb2.SESSION_MODE.ConnectionlessDownlink
                )
                return None

            # DATA path: ACK immediately
            ack = self._build_ack(frame.packet_number)
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

    # ------------------------------------------------------------------ tx ---

    async def handle_tx(self, message):
        # ── Fast-path rejection BEFORE we try to acquire the lock ─────────
        # If teardown has been requested we will never get a useful ACK
        # back, so refuse immediately rather than queuing behind the FIN.
        if self._teardown_requested.is_set():
            self.logger.warning("handle_tx called during teardown – message dropped")
            return None

        async with self.tx_lock:
            # Re-check inside the lock: teardown may have been requested
            # while we were waiting to acquire it.
            if self._teardown_requested.is_set():
                self.logger.warning("handle_tx: teardown started while waiting for lock – message dropped")
                return None

            self.tx_seq += 1
            seq   = self.tx_seq
            frame = self._frame(message, seq)

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

                    self.logger.warning(
                        f"Stale ACK received seq={ack.packet_number}, expected {seq}"
                    )

                self.logger.warning(
                    f"Timeout waiting for ACK (seq={seq}, attempt {attempt})"
                )

            self.logger.error(f"Packet seq={seq} failed after {MAX_TRIES} attempts")
            return None

    # --------------------------------------------------------------- teardown ---

    async def _send_teardown(self):
        # Signal intent first so any concurrent handle_tx call that has
        # NOT yet acquired the lock will bail out immediately.
        self._teardown_requested.set()
        self.logger.info("Teardown requested – waiting for tx_lock")

        # Acquire the lock so we are guaranteed no data frame is in-flight
        # when the FIN hits the wire.
        async with self.tx_lock:
            self.logger.info("tx_lock acquired – sending FIN")
            fin = self._build_fin()
            for attempt in range(1, MAX_TRIES + 1):
                await self.layer.below_tx.put(fin)
                self.logger.info(f"FIN sent (attempt {attempt}/{MAX_TRIES})")

                try:
                    await asyncio.wait_for(
                        self.fin_ack_queue.get(),
                        timeout=TEARDOWN_TIMEOUT
                    )
                    self.logger.info("FIN-ACK received – teardown complete")
                    return  # success

                except asyncio.TimeoutError:
                    self.logger.warning(
                        f"Teardown timeout waiting for FIN-ACK "
                        f"(attempt {attempt}/{MAX_TRIES})"
                    )

        self.logger.error(f"Teardown failed after {MAX_TRIES} attempts")

    # ---------------------------------------------------------------- helpers ---

    async def on_enter(self):
        self.logger.info(f"{self.name} entered")

    async def on_exit(self):
        self.logger.info(f"{self.name} exiting")

    def _frame(self, presentation_message, seq) -> bytes:
        msg = Audimus_pb2.Session_Message(
            presentation_message=presentation_message,
            mode=Audimus_pb2.SESSION_MODE.ConnectedUplink,
            packet_number=seq,
            SYN=False,
            ACK=False,
            FIN=False
        )
        return msg.SerializeToString()

    def _build_ack(self, seq: int) -> bytes:
        ack = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedUplink,
            packet_number=seq,
            SYN=False,
            ACK=True,
            FIN=False
        )
        return ack.SerializeToString()

    def _build_fin(self) -> bytes:
        fin = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedUplink,
            SYN=False,
            ACK=False,
            FIN=True
        )
        return fin.SerializeToString()

    def _build_fin_ack(self) -> bytes:
        fin_ack = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedUplink,
            SYN=False,
            ACK=True,
            FIN=True
        )
        return fin_ack.SerializeToString()


# ──────────────────────────────────────────────────────────────────────────────
#  Ground Station
# ──────────────────────────────────────────────────────────────────────────────

class GroundStationConnectedUplink(ConnectedUplink):
    """Ground station side – initiates teardown on exit."""

    def __init__(self, layer):
        super().__init__(layer)

    async def on_exit(self):
        self.logger.info("GroundStation ConnectedUplink: initiating teardown")
        await self._send_teardown()
        await super().on_exit()


# ──────────────────────────────────────────────────────────────────────────────
#  Audimus (Satellite)
# ──────────────────────────────────────────────────────────────────────────────

class AudimusConnectedUplink(ConnectedUplink):
    """Satellite side – reacts to FIN in handle_rx, no teardown initiation."""

    def __init__(self, layer):
        super().__init__(layer)

    async def on_exit(self):
        self.logger.info("Audimus ConnectedUplink: exiting after FIN")
        await super().on_exit()
