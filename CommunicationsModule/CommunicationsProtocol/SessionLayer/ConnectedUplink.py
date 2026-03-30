import asyncio
import time

import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session


ATTEMPTS = 5
TIMEOUT = 1


class ConnectedUplink(Session):
    """routes flagged messages to internal queues for processing
    teardown is three step handshake"""

    def __init__(self, layer):
        super().__init__(layer)
        self.name          = "ConnectedUplink"
        self.logger        = LoggerFactory.get_logger(self.name)
        self.ack_queue     = asyncio.Queue()
        self.fin_ack_queue = asyncio.Queue()
        self.fin_queue     = asyncio.Queue()
        self.tx_seq        = 0
        self.last_rx_seq   = 0


    #ACK, fin, fin-ack handled at layers below. Only data is passed upward. Fin triggers change in mode
    async def handle_rx(self, raw):
        self.activity_timer.reset()
        try:

            frame = Audimus_pb2.Session_Message()
            frame.ParseFromString(raw)

            self.logger.info(
                f"handle_rx self={id(self)} queue={id(self.ack_queue)} "
                f"ACK={frame.ACK} FIN={frame.FIN} seq={frame.packet_number}"
            )



            # if we get a syn message for this mode, respond with a SYNACK.
            if frame.SYN:
                ack = self.build_syn_ack()
                await self.layer.swap_put(ack)
                return None


            # if fin ack, put it in the queue
            if frame.FIN and frame.ACK:
                await self.fin_ack_queue.put(frame)
                return None

            # if FIN, send a fin ack and switch to idle mode
            if frame.FIN:
                print("got fin")
                print(frame)
                fin_ack = self.build_fin_ack(frame.mode)
                await self.layer.swap_put(fin_ack)

                await self.layer.set_session(frame.mode)
                return None

            # if we get a data ack
            if frame.ACK and not frame.DATA:
                self.logger.debug(f"ACK received for seq={frame.packet_number}")
                await self.ack_queue.put(frame)
                return None

            if frame.mode:
                if frame.mode != Audimus_pb2.SESSION_MODE.ConnectedUplink:
                    await self.layer.set_session(frame.mode)
                    return None
                if frame.mode == Audimus_pb2.SESSION_MODE.ConnectedUplink:
                    return None

            # if we get data
            ack = self.build_ack(frame.packet_number)
            await self.layer.swap_put(ack)
            self.logger.info(f"ACK sent for seq={frame.packet_number}")

            # if we get a duplicate
            if frame.packet_number <= self.last_rx_seq:
                self.logger.warning(
                    f"Duplicate/old packet received seq={frame.packet_number}, "
                    f"last_rx_seq={self.last_rx_seq}; payload dropped after ACK"
                )
                return None

            # if packets are out of order
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

            self.tx_seq += 1
            seq   = self.tx_seq
            frame = self.frame(message, seq)

            for attempt in range(ATTEMPTS):
                await self.layer.swap_put(frame)
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

            self.logger.error(f"Packet seq={seq} failed after {ATTEMPTS} attempts")
            return None




    def frame(self, presentation_message, seq) -> bytes:
        msg = Audimus_pb2.Session_Message(
            presentation_message=presentation_message,
            packet_number=seq,
        )
        return msg.SerializeToString()

    def build_ack(self, seq: int) -> bytes:
        ack = Audimus_pb2.Session_Message(
            packet_number=seq,
            ACK=True,
        )
        return ack.SerializeToString()

    def build_fin(self, new_mode):
        fin = Audimus_pb2.Session_Message(
            FIN = True,
            mode = new_mode
        )
        return fin.SerializeToString()

    def build_fin_ack(self, mode) -> bytes:
        fin_ack = Audimus_pb2.Session_Message(
            FIN = True,
            ACK=True,
            mode = mode
        )
        return fin_ack.SerializeToString()

    def build_syn_ack(self):
        syn_ack = Audimus_pb2.Session_Message(
            SYN=True,
            ACK=True,
        )
        return syn_ack.SerializeToString()


############################################ Ground Station ##########################################

class GroundStationConnectedUplink(ConnectedUplink):

    def __init__(self, layer):
        super().__init__(layer)

    async def switch_mode(self, new_mode):
        """teardown connection"""
        fin = self.build_fin(new_mode)
        for attempt in range(ATTEMPTS):
            await self.layer.swap_put(fin)
            try:
                await asyncio.wait_for(self.fin_ack_queue.get(), timeout=TIMEOUT)
                print("got from fin_ack_queue")
                await self.layer.set_session(new_mode)
                return

            except asyncio.TimeoutError:
                self.logger.warning(f"ACK timeout, retrying FIN for {new_mode}...")
        self.logger.info(f"Attempts exhausted, no response from Satellite, switching to {new_mode}")
        self.layer.set_session(new_mode)



############################################ Audimus ##########################################


class AudimusConnectedUplink(ConnectedUplink):

    def __init__(self, layer):
        super().__init__(layer)



