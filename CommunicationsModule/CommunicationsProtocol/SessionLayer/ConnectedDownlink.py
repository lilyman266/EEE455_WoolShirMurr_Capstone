import asyncio

import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session

MAX_TRIES        = 5
TIMEOUT          = 5.0
TEARDOWN_TIMEOUT = 3.0
POLL_INTERVAL    = 0.1


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

class ConnectedDownlink(Session):
    def __init__(self, layer):
        super().__init__(layer)
        self.name               = "ConnectedDownlink"
        self.logger             = LoggerFactory.get_logger(self.name)

        self.ack_queue          = asyncio.Queue()
        self.fin_ack_queue      = asyncio.Queue()
        self.request_queue      = asyncio.Queue()
        self.data_queue         = asyncio.Queue()

        self.tx_lock            = asyncio.Lock()
        self.teardown_requested = asyncio.Event()
        self.stop_event         = asyncio.Event()
        self.layer              = layer
        self.tasks              = []

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def on_enter(self):
        self.logger.info(f"{self.name} entered")
        self.stop_event.clear()
        self.teardown_requested.clear()

    async def on_exit(self):
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

    def start_task(self, coro, name=None):
        task = asyncio.create_task(coro, name=name)
        self.tasks.append(task)
        return task

    # ── rx dispatcher ────────────────────────────────────────────────────────

    async def handle_rx(self, raw: bytes):
        try:

            frame = Audimus_pb2.Session_Message()
            frame.ParseFromString(raw)

            if frame.mode != Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                self.logger.warning(f"Unexpected mode {frame.mode} in {self.name}")

            if frame.FIN and frame.ACK:
                self.logger.debug("FIN-ACK received → fin_ack_queue")
                await self.fin_ack_queue.put(frame)
                return None

            if frame.ACK:
                self.logger.debug(f"ACK received seq={frame.packet_number} → ack_queue")
                await self.ack_queue.put(frame)
                return None

            if frame.FIN:
                self.logger.info("FIN received – sending FIN-ACK and returning to connectionless")
                await self.layer.below_tx.put(self.build_fin_ack())
                await self.layer.session_queue.put(
                    Audimus_pb2.SESSION_MODE.ConnectionlessDownlink
                )
                return None

            if frame.retransmit_request:
                self.logger.info(f"RETRANSMIT_REQUEST received: {frame.packet_number}")
                await self.request_queue.put(frame)
                return None


            # Data frame (no FIN, ACK, or retransmit_request flags)
            self.logger.debug(f"DATA frame received seq={frame.packet_number} → data_queue")
            await self.data_queue.put(frame)
            return None




        except Exception as e:
            self.logger.error(f"handle_rx error: {e}")
            return None

    async def handle_tx(self, message: bytes):
        self.logger.warning("TX attempted in ConnectedDownlink – message dropped.")
        return None

    # ── teardown ─────────────────────────────────────────────────────────────

    async def teardown(self):
        self.teardown_requested.set()
        self.logger.info("Teardown requested – waiting for tx_lock")

        async with self.tx_lock:
            self.logger.info("tx_lock acquired – sending FIN")
            fin = self.build_fin()

            for attempt in range(1, MAX_TRIES + 1):
                await self.layer.below_tx.put(fin)
                self.logger.info(f"FIN sent (attempt {attempt}/{MAX_TRIES})")

                try:
                    await asyncio.wait_for(
                        self.fin_ack_queue.get(),
                        timeout=TEARDOWN_TIMEOUT
                    )
                    self.logger.info("FIN-ACK received – teardown complete")
                    await self.layer.set_session(
                        Audimus_pb2.SESSION_MODE.ConnectionlessDownlink
                    )
                    return

                except asyncio.TimeoutError:
                    self.logger.warning(
                        f"Teardown timeout waiting for FIN-ACK "
                        f"(attempt {attempt}/{MAX_TRIES})"
                    )

        self.logger.error(f"Teardown failed after {MAX_TRIES} attempts")

    # ── frame builders ────────────────────────────────────────────────────────

    def build_retransmit_request(self, missing_seqs: list[int]) -> bytes:
        msg = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedDownlink,
            retransmit_request=missing_seqs,
        )
        return msg.SerializeToString()


    def build_data_frame(self, seq: int, payload: bytes) -> bytes:
        msg = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedDownlink,
            packet_number=seq,
            presentation_message=payload,
        )
        return msg.SerializeToString()

    def build_fin(self) -> bytes:
        return Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedDownlink,
            FIN=True,
        ).SerializeToString()

    def build_fin_ack(self) -> bytes:
        return Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedDownlink,
            FIN=True,
            ACK=True,
        ).SerializeToString()


# ─────────────────────────────────────────────────────────────────────────────
# Ground Station
# ─────────────────────────────────────────────────────────────────────────────

class GroundStationConnectedDownlink(ConnectedDownlink):
    """
    Implicit-ACK protocol:
      - Sends RETRANSMIT_REQUEST containing only still-missing packets.
      - The satellite infers that anything it sent last round that is
        absent from the new request was successfully received.
      - When nothing is missing, sends an empty RETRANSMIT_REQUEST as a
        final flush signal, then initiates FIN teardown.
      - No per-packet ACK frames are ever sent.
    """

    def __init__(self, layer):
        super().__init__(layer)

    async def on_enter(self):
        await super().on_enter()
        self._drain_queues()
        self.start_task(self.retransmit_loop(), name="gs_retransmit_loop")

    async def on_exit(self):
        self.logger.info("GroundStation ConnectedDownlink: on_exit")
        await super().on_exit()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _drain_queues(self):
        """Discard any stale frames left in queues from a previous session."""
        for queue in (self.data_queue, self.ack_queue,
                      self.fin_ack_queue, self.request_queue):
            drained = 0
            while not queue.empty():
                try:
                    queue.get_nowait()
                    drained += 1
                except asyncio.QueueEmpty:
                    break
            if drained:
                self.logger.debug(
                    f"Drained {drained} stale frame(s) from queue on enter"
                )

    # ── retransmit loop ───────────────────────────────────────────────────────

    async def retransmit_loop(self):
        """
        Main ground-station loop.

        Each iteration:
          1. Ask the packet tracker for still-missing sequence numbers.
          2. If none are missing, send an empty RETRANSMIT_REQUEST so the
             satellite can flush its last sent-set, then tear down.
          3. Otherwise send a RETRANSMIT_REQUEST and collect DATA frames
             until the timeout expires or all packets arrive.
          4. Mark any newly received packets in the packet tracker so they
             won't appear in the next request (that absence = implicit ACK).
        """
        self.logger.info("retransmit_loop started (implicit-ACK mode)")

        try:
            while not self.stop_event.is_set():

                missing = self.layer.packet_tracker.get_missing_packets()

                if not missing:
                    # ── Send empty request as final implicit-ACK flush ────────
                    self.logger.info(
                        "No missing packets – sending empty RETRANSMIT_REQUEST "
                        "to let satellite flush last round, then tearing down"
                    )
                    flush = self.build_retransmit_request([])
                    await self.layer.below_tx.put(flush)

                    # Give the satellite a moment to process the flush before FIN
                    await asyncio.sleep(POLL_INTERVAL)
                    await self.teardown()
                    return

                self.logger.info(f"Requesting retransmission of {missing}")
                await self._request_round(missing)

                await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            self.logger.info("retransmit_loop cancelled")

    # ── single request/collect round ─────────────────────────────────────────

    async def _request_round(self, missing: list[int]) -> bool:
        """
        Send one RETRANSMIT_REQUEST and collect DATA frames until the
        deadline expires or all requested packets have arrived.

        Received packets are stored via the packet store and marked in the
        packet tracker so they will be absent from the *next* request —
        that absence serves as the implicit ACK to the satellite.

        Returns True if every requested packet was received, False otherwise.
        """
        async with self.tx_lock:
            for attempt in range(1, MAX_TRIES + 1):

                # ── 1. Send the request ───────────────────────────────────
                request = self.build_retransmit_request(missing)
                await self.layer.below_tx.put(request)
                self.logger.info(
                    f"RETRANSMIT_REQUEST sent {missing} "
                    f"(attempt {attempt}/{MAX_TRIES})"
                )

                # ── 2. Collect DATA frames until timeout ──────────────────
                received: dict[int, bytes] = {}
                deadline = asyncio.get_event_loop().time() + TIMEOUT

                while len(received) < len(missing):
                    time_left = deadline - asyncio.get_event_loop().time()
                    if time_left <= 0:
                        break

                    try:
                        frame = await asyncio.wait_for(
                            self.data_queue.get(),
                            timeout=time_left,
                        )

                    except asyncio.TimeoutError:
                        break

                    seq = frame.packet_number
                    if seq in missing and seq not in received:
                        received[seq] = frame.presentation_message
                        self.logger.debug(f"Received retransmitted packet seq={seq}")
                        await self.layer.layer_rx.put(frame.presentation_message)
                    else:
                        self.logger.warning(
                            f"Unexpected seq={seq} in retransmit round "
                            f"(missing={missing}) – discarding"
                        )

                # ── 3. Persist received packets & update tracker ──────────
                # Marking these packets in the tracker means they will NOT
                # appear in the next RETRANSMIT_REQUEST.  Their absence in
                # that next request is what tells the satellite it can delete
                # them — no explicit ACK frame is needed.
                for seq, payload in received.items():
                    self.layer.packet_store.store_packet(seq, payload)
                    self.layer.packet_tracker.mark_received(seq)
                    self.logger.info(
                        f"Packet seq={seq} stored & marked received "
                        f"(implicit ACK will be sent next round)"
                    )

                # ── 4. Decide whether to retry ────────────────────────────
                if len(received) == len(missing):
                    self.logger.info(
                        f"All {len(missing)} packets received in attempt {attempt}"
                    )
                    return True

                still_missing = [s for s in missing if s not in received]
                self.logger.warning(
                    f"Attempt {attempt}/{MAX_TRIES}: received "
                    f"{len(received)}/{len(missing)}, "
                    f"still missing {still_missing}"
                )
                # Update `missing` to only the packets still needed before retry
                missing = still_missing
                print(f"still missing {missing}")

            # Exhausted all attempts
            self.logger.error(
                f"_request_round failed after {MAX_TRIES} attempts; "
                f"packets {missing} still outstanding"
            )
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Satellite
# ─────────────────────────────────────────────────────────────────────────────

class AudimusConnectedDownlink(ConnectedDownlink):
    """
    Implicit-ACK protocol (satellite side):

    The satellite tracks which packet sequence numbers it transmitted in the
    most recent round (_last_sent_set).  When the *next* RETRANSMIT_REQUEST
    arrives, any sequence number that was in _last_sent_set but is absent
    from the new request is implicitly acknowledged — the ground station
    received it — and can be deleted from persistent storage.

    An *empty* RETRANSMIT_REQUEST means "I have everything; prepare for FIN".
    In that case the entire _last_sent_set is implicitly acknowledged and
    deleted.
    """

    def __init__(self, layer):
        super().__init__(layer)
        # Sequence numbers transmitted in the most recent retransmit round.
        self._last_sent_set: set[int] = set()

    async def on_enter(self):
        await super().on_enter()
        self._last_sent_set.clear()
        self.start_task(self._serve_loop(), name="sat_serve_loop")

    async def on_exit(self):
        self.logger.info("Satellite ConnectedDownlink: on_exit")
        await super().on_exit()

    # ── main serving loop ─────────────────────────────────────────────────────

    async def _serve_loop(self):
        """
        Wait for RETRANSMIT_REQUEST frames and serve them.

        Protocol:
          received request  │  action
          ──────────────────┼──────────────────────────────────────────────────
          non-empty         │  implicit-ACK absent seqs, send requested packets
          empty             │  implicit-ACK all remaining, wait for FIN
        """
        self.logger.info("Satellite serve_loop started (implicit-ACK mode)")
        try:
            while not self.stop_event.is_set():

                # ── Wait for next request (with timeout so stop_event is polled)
                try:
                    frame = await asyncio.wait_for(
                        self.request_queue.get(),
                        timeout=POLL_INTERVAL,
                    )
                except asyncio.TimeoutError:
                    continue

                new_missing = set(frame.retransmit_request)
                print(f"still missing {new_missing}")
                # ── Implicit ACK: confirm everything sent last round that
                #    the ground station is no longer asking for ──────────────
                implicitly_acked = self._last_sent_set - new_missing
                if implicitly_acked:
                    self.logger.info(
                        f"Implicit ACK for packets {implicitly_acked} "
                        f"(absent from new request) — deleting from store"
                    )
                    self._delete_from_store(implicitly_acked)

                # ── Empty request = ground station has everything ─────────────
                if not new_missing:
                    self.logger.info(
                        "Empty RETRANSMIT_REQUEST received — "
                        "all packets implicitly ACK'd; awaiting FIN"
                    )
                    # Any remainder (e.g. from a partially-received last round)
                    if self._last_sent_set:
                        self._delete_from_store(self._last_sent_set)
                    self._last_sent_set.clear()
                    continue   # will now just wait for FIN via handle_rx

                # ── Serve the requested packets ───────────────────────────────
                self.logger.info(f"Serving retransmit request: {new_missing}")
                actually_sent = await self._send_packets(new_missing)

                self._last_sent_set = actually_sent

        except asyncio.CancelledError:
            self.logger.info("Satellite serve_loop cancelled")

    # ── packet transmission ───────────────────────────────────────────────────

    async def _send_packets(self, seqs: set[int]) -> set[int]:
        """
        Fetch and transmit each requested packet from the persistent store.
        Returns the set of sequence numbers that were actually sent
        (a sequence number is skipped if it is no longer in the store).
        """
        sent: set[int] = set()

        async with self.tx_lock:

            for seq in sorted(seqs):
                payload = await self.layer.packet_store.get_packet(seq)

                if payload is None:
                    self.logger.warning(
                        f"Packet seq={seq} requested but not in store — skipping"
                    )
                    continue
                frame = self.build_data_frame(seq, payload)


                await self.layer.below_tx.put(frame)


                sent.add(seq)
                self.logger.debug(f"Retransmitted packet seq={seq}")
        return sent

    # ── storage management ────────────────────────────────────────────────────

    def _delete_from_store(self, seqs: set[int]):
        """Remove implicitly-acknowledged packets from the persistent store."""
        for seq in seqs:
            deleted = self.layer.packet_store.acknowledge(seq, None)
            if deleted is not None:
                self.logger.info(
                    f"Deleted implicitly-ACK'd packet seq={seq} from store"
                )
            else:
                self.logger.warning(
                    f"Tried to delete seq={seq} but it was not in store "
                    f"(already deleted or never stored)"
                )
