import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session

MAX_TRIES = 5
TIMEOUT   = 5.0
BURST_TIMEOUT = 10.0  # total time to wait for the full burst


class ConnectionlessDownlink(Session):
    """Base class for connectionless downlink sessions."""

    def __init__(self, layer):
        super().__init__(layer)
        self.layer              = layer
        self.name               = "ConnectionlessDownlink"
        self.logger             = LoggerFactory.get_logger(self.name)
        self.packet_number      = self.read_packet_number()
        self.handshake_rx_queue = asyncio.Queue()
        self.recovery_rx_queue  = asyncio.Queue()
        self.connecting         = False
        self.recovering         = False

    async def handle_rx(self, packet: bytes):
        pass

    async def handle_tx(self, message: bytes):
        pass

    async def on_enter(self):
        self.logger.info(f"{self.name} entered")

    async def on_exit(self):
        pass


################################## Ground Station ###########################################

class GroundStationConnectedDownlink(ConnectionlessDownlink):

    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )
        super().__init__(layer)



    async def handle_rx(self, raw: bytes):
        """Route incoming bytes to the correct internal queue or deliver upward."""

        if self.connecting:
            await self.handshake_rx_queue.put(raw)
            return None

        if self.recovering:
            await self.recovery_rx_queue.put(raw)
            return None

        try:
            return self._deframe(raw)
        except Exception as e:
            self.logger.error(f"handle_rx deframe error: {e}")
            return None

    def _deframe(self, raw: bytes):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)
        self._track_packet(frame.packet_number)
        return frame.presentation_message

    def _track_packet(self, received_number: int):
        """Record any sequence gaps between last received and current packet."""
        expected = self.packet_number + 1
        if received_number != expected:
            for dropped in range(expected, received_number):
                self.packet_tracker.record_drop(dropped)
                self.logger.warning(f"Dropped packet detected: seq={dropped}")
        self.packet_number = received_number
        self.write_packet_number(self.packet_number)

    async def handle_tx(self, message: bytes):
        """ The ground station cant send new data """
        self.logger.warning(
            "handle_tx called on GroundStationConnectionlessDownlink – "
            "sending new data is not permitted in this mode. Message dropped."
        )
        return None


    async def handshake(self, new_mode: Audimus_pb2.SESSION_MODE):
        """3-way handshake """
        self.logger.info(f"Initiating handshake for mode={new_mode}")
        self.connecting = True

        for attempt in range(1, MAX_TRIES + 1):
            try:
                # Step 1 – SYN
                syn = Audimus_pb2.Session_Message(
                    SYN=True,
                    mode=new_mode
                )
                await self.layer.below_tx.put(syn.SerializeToString())
                self.logger.debug(f"SYN sent (attempt {attempt})")

                # Step 2 – wait for SYN-ACK
                raw = await asyncio.wait_for(
                    self.handshake_rx_queue.get(),
                    timeout=TIMEOUT
                )
                syn_ack = Audimus_pb2.Session_Message()
                syn_ack.ParseFromString(raw)

                if not syn_ack.SYNACK:
                    self.logger.warning(
                        f"Expected SYNACK, got unexpected frame – retrying"
                    )
                    continue

                # Step 3 – ACK
                ack = Audimus_pb2.Session_Message(
                    ACK=True,
                    mode=new_mode
                )
                await self.layer.below_tx.put(ack.SerializeToString())
                self.logger.info("Handshake complete")
                self.connecting = False

                # Kick off missed-packet recovery before switching mode
                await self._request_missed_packets()
                return

            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Handshake timeout on attempt {attempt}/{MAX_TRIES}"
                )

        self.logger.error(f"Handshake failed after {MAX_TRIES} attempts")
        self.connecting = False



    async def _request_missed_packets(self):
        """
        Recovery sub-protocol (ground station side):
          1. Build a list of all missing sequence numbers from MissingPacketIndex
          2. Send a single NACK frame containing that list
          3. Receive the burst – one DATA frame per missing packet
          4. Deliver each recovered payload upward and acknowledge it
        """
        missing = self.packet_tracker.get_missing_packets()

        if not missing:
            self.logger.info("No missed packets – recovery skipped")
            return

        self.logger.info(f"Requesting {len(missing)} missed packets: {missing}")
        self.recovering = True

        # Step 1 – send NACK listing all missing sequence numbers
        nack = Audimus_pb2.Session_Message(
            mode=Audimus_pb2.SESSION_MODE.ConnectionlessDownlink,
            NACK=True,
            missing_packets=missing          # repeated uint32 field
        )
        await self.layer.below_tx.put(nack.SerializeToString())
        self.logger.debug("NACK sent")

        # Step 2 – collect exactly len(missing) DATA frames (or timeout)
        recovered = 0
        deadline  = asyncio.get_event_loop().time() + BURST_TIMEOUT

        while recovered < len(missing):
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                self.logger.error(
                    f"Burst timeout: received {recovered}/{len(missing)} packets"
                )
                break

            try:
                raw = await asyncio.wait_for(
                    self.recovery_rx_queue.get(),
                    timeout=remaining
                )
            except asyncio.TimeoutError:
                self.logger.error(
                    f"Burst timeout: received {recovered}/{len(missing)} packets"
                )
                break

            try:
                frame = Audimus_pb2.Session_Message()
                frame.ParseFromString(raw)

                self.logger.info(
                    f"Recovered packet seq={frame.packet_number}"
                )

                # Mark as no longer missing
                self.packet_tracker.acknowledge(frame.packet_number)
                recovered += 1

                # Deliver payload upward
                if frame.presentation_message:
                    await self.layer.layer_rx.put(frame.presentation_message)

            except Exception as e:
                self.logger.error(f"Failed to deframe recovered packet: {e}")

        self.recovering = False
        self.logger.info(
            f"Recovery complete: {recovered}/{len(missing)} packets recovered"
        )

    # ---------------------------------------------------------------- exit --

    async def on_exit(self):
        await super().on_exit()
        self.logger.info(
            f"GroundStation connectionless downlink exiting. "
            f"Final packet number: {self.packet_number}"
        )


################################## Audimus ###########################################

class AudimusConnectedDownlink(ConnectionlessDownlink):
    """
    TX  : Frames outgoing data, increments sequence number, persists to
          PacketStore.  Sending new data is blocked while a recovery burst
          is in progress so that the burst is not interleaved with live frames.
    RX  : Handles 3-way handshake (responder side).
          Handles NACK frames – reads requested packets from PacketStore
          and bursts them back to the ground station.
          Any attempt to receive new application data is silently dropped
          (satellite does not receive data in this mode).
    """

    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/AudimusCurrentPacketNumber"
        )
        super().__init__(layer)
        self._burst_lock = asyncio.Lock()   # prevents live TX during burst



    async def handle_tx(self, message: bytes):
        """
        Frame and store an outgoing data packet.
        Blocked (queues behind _burst_lock) while a recovery burst is running
        so that burst frames and live frames are never interleaved.
        """
        async with self._burst_lock:
            try:
                self.packet_number += 1
                frame = self._frame(message)
                self.write_packet_number(self.packet_number)
                await self.packet_store.store_packet(self.packet_number, frame)
                return frame
            except Exception as e:
                self.logger.error(f"handle_tx error: {e}")
                self.packet_number -= 1      # roll back on failure
                return None

    def _frame(self, presentation_message):
        msg = Audimus_pb2.Session_Message(
            presentation_message=presentation_message,
            mode=Audimus_pb2.SESSION_MODE.ConnectionlessDownlink,
            packet_number=self.packet_number,
            SYN=False,
            ACK=False
        )
        return msg.SerializeToString()



    async def handle_rx(self, raw):
        """
        Route incoming bytes.
        During handshake  → handshake_rx_queue.
        NACK frame        → trigger burst (fire-and-forget task).
        Anything else     → satellite does not receive application data here,
                            log a warning and drop.
        """
        if self.connecting:
            await self.handshake_rx_queue.put(raw)
            return None

        try:
            frame = Audimus_pb2.Session_Message()
            frame.ParseFromString(raw)
        except Exception as e:
            self.logger.error(f"handle_rx parse error: {e}")
            return None

        # SYN → start handshake
        if frame.SYN:
            self.connecting = True
            asyncio.create_task(
                self.handshake(frame),
                name="audimus_handshake"
            )
            return None

        # NACK → burst missed packets back
        if frame.NACK:
            asyncio.create_task(
                self._burst_missed_packets(list(frame.missing_packets)),
                name="audimus_burst"
            )
            return None

        # Anything else: satellite does not accept new data in this mode
        self.logger.warning(
            "Audimus received unexpected frame in ConnectionlessDownlink "
            f"(mode={frame.mode}, SYN={frame.SYN}, ACK={frame.ACK}) – dropped"
        )
        return None


    async def handshake(self, syn: Audimus_pb2.Session_Message):
        """
        3-way handshake (satellite responder):
          1. Send SYN-ACK
          2. Wait for ACK
          (mode switch is NOT triggered here; the ground station drives that)
        """
        new_mode = syn.mode
        self.connecting = True

        for attempt in range(1, MAX_TRIES + 1):
            try:
                # Step 1 – SYN-ACK
                syn_ack = Audimus_pb2.Session_Message(
                    SYNACK=True,
                    mode=new_mode
                )
                await self.layer.below_tx.put(syn_ack.SerializeToString())
                self.logger.info(f"SYN-ACK sent (attempt {attempt})")

                # Step 2 – wait for ACK
                raw = await asyncio.wait_for(
                    self.handshake_rx_queue.get(),
                    timeout=TIMEOUT
                )
                response = Audimus_pb2.Session_Message()
                response.ParseFromString(raw)

                if response.ACK:
                    self.logger.info("Handshake complete – waiting for NACK")
                    self.connecting = False
                    return

                self.logger.warning(
                    f"Expected ACK, got unexpected frame – retrying"
                )

            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Handshake timeout on attempt {attempt}/{MAX_TRIES}"
                )

        self.logger.error(f"Handshake failed after {MAX_TRIES} attempts")
        self.connecting = False


    async def _burst_missed_packets(self, missing_seqs):
        """
        Recovery sub-protocol (satellite side):
          Acquires the burst lock (blocks live TX), reads each requested packet
          from PacketStore, and sends them all back-to-back.
        """
        if not missing_seqs:
            self.logger.info("NACK received with empty list – nothing to burst")
            return

        self.logger.info(
            f"Bursting {len(missing_seqs)} missed packets: {missing_seqs}"
        )

        async with self._burst_lock:   # block new live TX until burst finishes
            for seq in missing_seqs:
                try:
                    payload = await self.packet_store.get_packet(seq)

                    if payload is None:
                        self.logger.warning(
                            f"Packet seq={seq} not found in store – skipping"
                        )
                        continue

                    # Re-wrap with original seq number so the ground station
                    # can identify which gap each frame fills
                    frame = Audimus_pb2.Session_Message(
                        mode=Audimus_pb2.SESSION_MODE.ConnectionlessDownlink,
                        packet_number=seq,
                        SYN=False,
                        ACK=False
                    )
                    # payload is already a serialised Session_Message stored by
                    # handle_tx; unwrap it to get the presentation_message
                    stored = Audimus_pb2.Session_Message()
                    stored.ParseFromString(payload)
                    frame.presentation_message = stored.presentation_message

                    await self.layer.below_tx.put(frame.SerializeToString())
                    self.logger.debug(f"Burst: sent seq={seq}")

                except Exception as e:
                    self.logger.error(
                        f"Failed to retrieve/send packet seq={seq}: {e}"
                    )

        self.logger.info("Burst complete")


    async def on_exit(self):
        await super().on_exit()
        self.logger.info(
            f"Audimus connectionless downlink exiting. "
            f"Final packet number: {self.packet_number}"
        )
