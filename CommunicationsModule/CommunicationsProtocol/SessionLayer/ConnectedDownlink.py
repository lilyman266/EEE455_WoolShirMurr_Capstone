import asyncio

import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session

MAX_TRIES        = 5
TIMEOUT          = 10
TEARDOWN_TIMEOUT = 3.0
POLL_INTERVAL    = 10

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

    async def on_enter(self):
        await super().on_enter()
        self.logger.info(f"{self.name} entered")
        self.stop_event.clear()
        self.teardown_requested.clear()

    async def on_exit(self):
        self.stop_event.set()
        current = asyncio.current_task()

        tasks_to_cancel = [t for t in self.tasks if t is not current]
        for task in tasks_to_cancel:
            task.cancel()

        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        self.tasks.clear()

    def start_task(self, coro, name=None):
        task = asyncio.create_task(coro, name=name)
        self.tasks.append(task)
        return task

    async def handle_rx(self, raw: bytes):
        try:

            frame = Audimus_pb2.Session_Message()
            frame.ParseFromString(raw)



            if frame.FIN and frame.ACK:
                self.logger.debug("FIN-ACK received → fin_ack_queue")
                await self.fin_ack_queue.put(frame)
                return None

            if frame.ACK and not frame.RET:
                self.logger.debug(f"ACK received seq={frame.packet_number} → ack_queue")
                await self.ack_queue.put(frame)
                return None

            if frame.FIN:
                self.logger.info("FIN received – sending FIN-ACK and returning to idle")
                fin_ack = self.build_fin_ack()
                await self.layer.swap_put(fin_ack)
                await self.layer.session_queue.put(Audimus_pb2.SESSION_MODE.Idle)
                return None

            #retransmission request
            if frame.RET:
                self.logger.info(f"RETRANSMIT_REQUEST received: {frame.retransmit_request}")
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
        self.logger.info("TX attempted in ConnectedDownlink – message dropped.")
        return None

        # Signal intent first so any concurrent handle_tx call that has not yet acquired the lock will stop.

    async def teardown(self):

        self.teardown_requested.set()
        self.logger.info("Teardown requested – waiting for tx_lock")

        # Lock to protect moving data
        async with self.tx_lock:
            self.logger.info("tx_lock acquired – sending FIN")
            fin = self.build_fin()
            for attempt in range(1, MAX_TRIES + 1):
                await self.layer.swap_put(fin)
                self.logger.info(f"FIN sent (attempt {attempt}/{MAX_TRIES})")

                try:
                    await asyncio.wait_for(self.fin_ack_queue.get(),timeout=TEARDOWN_TIMEOUT)
                    await asyncio.wait_for(self.fin_ack_queue.get(),timeout=TEARDOWN_TIMEOUT)
                    self.logger.info("FIN-ACK received – teardown complete")
                    await self.layer.set_session(Audimus_pb2.SESSION_MODE.Idle)
                    return  # success

                except asyncio.TimeoutError:
                    self.logger.warning(
                        f"Teardown timeout waiting for FIN-ACK "
                        f"(attempt {attempt}/{MAX_TRIES})"
                    )

        self.logger.error(f"Teardown failed after {MAX_TRIES} attempts")



    def build_retransmit_request(self, missing_seqs: list[int]) -> bytes:
        msg = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedDownlink,
            retransmit_request=missing_seqs,
            RET = True,
            ACK = True,
        )
        return msg.SerializeToString()


    def build_data_frame(self, seq: int, payload: bytes) -> bytes:
        msg = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedDownlink,
            packet_number=seq,
            presentation_message=payload,
            RET = False,
        )
        return msg.SerializeToString()

    def build_fin(self) -> bytes:
        return Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedDownlink,
            FIN=True,
            RET = False,
        ).SerializeToString()

    def build_fin_ack(self) -> bytes:
        return Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectedDownlink,
            FIN=True,
            ACK=True,
            RET=False,
        ).SerializeToString()


####################Ground Station############################################################
class GroundStationConnectedDownlink(ConnectedDownlink):
    def __init__(self, layer):
        super().__init__(layer)


    async def on_enter(self):
        await super().on_enter()
        self._drain_queues()
        self.start_task(self.retransmit_loop(), name="gs_retransmit_loop")

    async def on_exit(self):
        self.logger.info("GroundStation ConnectedDownlink: on_exit")
        await super().on_exit()


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


    async def retransmit_loop(self):
        self.logger.info("retransmit_loop started (implicit-ACK mode)")
        try:
            while not self.stop_event.is_set():

                missing = self.layer.packet_tracker.get_missing_packets()

                if not missing:
                    # ── Send empty request as final implicit-ACK flush ────────
                    self.logger.info("No missing packets – sending empty RETRANSMIT_REQUEST to let satellite flush its store then tearing down")
                    flush = self.build_retransmit_request([])
                    await self.layer.put(flush)
                    await self.layer.put(flush)
                    await self.layer.put(flush)

                    # Give the satellite a moment to process the flush before FIN
                    await asyncio.sleep(POLL_INTERVAL)
                    await self.teardown()
                    return

                self.logger.info(f"Requesting retransmission of {missing}")
                await self._request_round(missing)
                await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            self.logger.info("retransmit_loop cancelled")

    async def _request_round(self, missing: list[int]):
        """
        1. sends the request
        2. collects data frames untill timeout
        3. loops untill no packets left
        """

        async with self.tx_lock:
            for attempt in range(1, MAX_TRIES + 1):

                request = self.build_retransmit_request(missing)
                await self.layer.swap_put(request)
                self.logger.info(
                    f"RETRANSMIT_REQUEST sent {missing} "
                    f"(attempt {attempt}/{MAX_TRIES})"
                )

                received: dict[int, bytes] = {}
                deadline = asyncio.get_running_loop().time() + TIMEOUT

                while len(received) < len(missing):
                    time_left = deadline - asyncio.get_running_loop().time()
                    if time_left <= 0:
                        break
                    try:
                        frame = await asyncio.wait_for(self.data_queue.get(),timeout=time_left)
                    except asyncio.TimeoutError:
                        break

                    seq = frame.packet_number

                    if seq in missing and seq not in received:
                        received[seq] = frame.presentation_message
                        self.logger.debug(f"Received retransmitted packet seq={seq}")
                        self.layer.packet_tracker.acknowledge(seq)
                        await self.layer.swap_put(frame.presentation_message)
                    else:
                        self.logger.info(
                            f"Unexpected seq={seq} in retransmit round "
                            f"(missing={missing}) – discarding"
                        )

                for seq, payload in received.items():
                    self.layer.packet_tracker.acknowledge(seq)
                    self.logger.info(
                        f"Packet seq={seq} stored & marked received "
                        f"(implicit ACK will be sent next round)"
                    )

                if len(received) == len(missing):
                    self.logger.info(
                        f"All {len(missing)} packets received in attempt {attempt}"
                    )
                    return True

                still_missing = [s for s in missing if s not in received]
                self.logger.info(
                    f"Attempt {attempt}/{MAX_TRIES}: received "
                    f"{len(received)}/{len(missing)}, "
                    f"still missing {still_missing}"
                )
                missing = still_missing

            self.logger.error(
                f"_request_round failed after {MAX_TRIES} attempts; "
                f"packets {missing} still outstanding"
            )
            return False


############################ Audimus ###############################################
class AudimusConnectedDownlink(ConnectedDownlink):

    def __init__(self, layer):
        super().__init__(layer)
        self._last_sent_set: set[int] = set()


    async def on_enter(self):
        await super().on_enter()
        self._last_sent_set.clear()
        self.start_task(self._serve_loop(), name="sat_serve_loop")

    async def on_exit(self):
        self.logger.info("Satellite ConnectedDownlink: on_exit")
        await super().on_exit()

    async def _serve_loop(self):
        self.logger.info("Satellite serve_loop started (implicit-ACK mode)")
        try:
            while not self.stop_event.is_set():
                try:
                    frame = await asyncio.wait_for(
                        self.request_queue.get(),
                        timeout=POLL_INTERVAL
                    )
                except asyncio.TimeoutError:
                    self.logger.debug("No retransmit request within poll interval — continuing")
                    continue

                #calculate what has been implicitly acked
                new_missing = set(frame.retransmit_request)
                implicitly_acked = self._last_sent_set - new_missing

                #deletes whatever has been implicitly acked
                if implicitly_acked:
                    self.logger.info(
                        f"Implicit ACK for packets {implicitly_acked} "
                        f"(absent from new request) — deleting from store"
                    )
                    for seq in implicitly_acked:
                        await self.layer.packet_store.acknowledge(seq)
                    self._last_sent_set -= implicitly_acked

                #if we receive an emtpy set, we can delete the whole store
                if new_missing == set():
                    self.logger.info("Empty RETRANSMIT_REQUEST received — all packets implicitly ACK'd; awaiting FIN")
                    await self.layer.packet_store.empty_store()
                    continue

                #send whatever has not been implicitely acked
                self.logger.info(f"Serving retransmit request: {new_missing}")
                actually_sent = await self._send_packets(new_missing)
                self._last_sent_set = actually_sent


        except asyncio.CancelledError:
            self.logger.info("Satellite serve_loop cancelled")

    async def _send_packets(self, seqs: set[int]) -> set[int]:
        sent: set[int] = set()
        async with self.tx_lock:

            sorted_seqs = sorted(seqs)

            for i, seq in enumerate(sorted_seqs):
                is_last = i == len(sorted_seqs) - 1

                try:
                    payload = await self.layer.packet_store.get_packet(seq)
                except Exception:
                    self.logger.info(f"Packet seq={seq} requested but not in store — sending empty packet")
                    payload = "Packet was dropped and unable to be recovered"

                frame = self.build_data_frame(seq, payload)
                if is_last:
                    await self.layer.swap_put(frame)
                else:
                    await self.layer.put(frame)

                sent.add(seq)
                self.logger.info(f"Retransmitted packet seq={seq}")

        return sent


    def _delete_from_store(self, seqs: set[int]):
        """Remove implicitly-acknowledged packets from the persistent store."""
        for seq in seqs:
            deleted = self.layer.packet_store.acknowledge(seq, None)
            if deleted is not None:
                self.logger.info(
                    f"Deleted implicitly-ACK'd packet seq={seq} from store"
                )
            else:
                self.logger.info(
                    f"Tried to delete seq={seq} but it was not in store "
                    f"(already deleted or never stored)"
                )
