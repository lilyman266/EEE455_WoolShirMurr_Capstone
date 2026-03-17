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
        self.packet_number       = self.read_packet_number()
        self.handshake_rx_queue  = asyncio.Queue()
        self.connecting          = False

    async def handle_rx(self, packet: bytes):
        pass

    async def handle_tx(self, message: bytes):
        pass

    async def on_enter(self):
        self.logger.info("Entered ConnectionlessDownlink Mode")

    async def on_exit(self):
        pass



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
        super().__init__(layer)


    async def handle_rx(self, raw: bytes):

        if self.connecting:
            await self.handshake_rx_queue.put(raw)
            return None

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


    # handshake to switch to connected mode
    # 1. Sends syn
    # 2. Waits for syn ack. Syn ack will include current audimus packet_number incase drop occured since last complete rx
    # 3. sends ack then switches to new mode
    async def handshake(self, new_mode: Audimus_pb2.SESSION_MODE):
        self.logger.info(f"Initiating handshake for mode {new_mode}")
        self.connecting = True

        for attempt in range(1, MAX_TRIES + 1):
            try:

                #send ack
                syn = Audimus_pb2.Session_Message(SYN=True, mode=new_mode)
                self.logger.info("first syn swap put")
                await self.layer.swap_put(syn.SerializeToString())

                #wait for syn-ack response
                raw = await asyncio.wait_for(self.handshake_rx_queue.get(), timeout=TIMEOUT)
                syn_ack = Audimus_pb2.Session_Message()
                syn_ack.ParseFromString(raw)
                if not syn_ack.SYNACK:
                    self.logger.warning(
                        f"Expected SYNACK, got unexpected frame (attempt {attempt}) – retrying"
                    )
                    continue
                #log packet number in case drop occured since last complete rx
                self.track_packet(syn_ack.packet_number)

                #send ack
                ack = Audimus_pb2.Session_Message(ACK=True, mode=new_mode)
                await self.layer.put(ack.SerializeToString())
                self.logger.info("handshake complete")

                await self.layer.set_session(new_mode)
                self.connecting = False
                return  # success

            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Timeout waiting for SYN-ACK (attempt {attempt}/{MAX_TRIES})"
                )

        self.logger.error(f"Handshake failed after {MAX_TRIES} attempts,  staying in connectionless downlink for pass")
        self.connecting = False


##############Audimus #####################################################

class AudimusConnectionlessDownlink(ConnectionlessDownlink):
    """ only rx syn for handshake. sends packets oblivious to drops. GS records and will request for retarnsmit it
    connected downlink"""

    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/AudimusCurrentPacketNumber"
        )
        super().__init__(layer)


    async def on_enter(self):
        await self.wait_for_connection()


    async def wait_for_connection(self):
       #put the radio into receive mode
       await self.layer.mode_queue.put(RadioMode.RX)
       self.logger.info("waiting for ground station to reach out")
       await asyncio.sleep(5)
       self.logger.info("Ground station did not reach out, remainder of pass will be done in connectionless downlink")
       # if timer expires, switch back to send mode
       if not self.connecting:
            await self.layer.mode_queue.put(RadioMode.TX)

    async def handle_tx(self, message: bytes) -> bytes | None:
        try:
            self.packet_number += 1
            await self.layer.packet_store.store_packet(self.packet_number, message)
            frame = self.frame(message)
            self.write_packet_number(self.packet_number)
            return frame
        except Exception as e:
            self.logger.error(f"Failed to frame message: {e}")
            self.packet_number -= 1  # roll back
            return None


    def frame(self, presentation_message: bytes) -> bytes:
        msg = Audimus_pb2.Session_Message(
            presentation_message = presentation_message,
            mode = Audimus_pb2.SESSION_MODE.ConnectionlessDownlink,
            packet_number = self.packet_number,
            SYN = False,
        )
        return msg.SerializeToString()


    # if connecting, process handshake
    async def handle_rx(self, raw: bytes):
        if self.connecting:
            await self.handshake_rx_queue.put(raw)
            return None

        try:
            frame =  await self.deframe(raw)

            if frame.SYN:
                self.connecting = True  # set BEFORE spawning task
                asyncio.create_task(self.handshake(frame))
                return None  # no payload for presentation

            #if GS is in wrong mode, send a reset
            if frame.mode == Audimus_pb2.SESSION_MODE.ConnectedUplink:
                self.layer.set_session(Audimus_pb2.SESSION_MODE.ConnectedUplink)

            return frame
        except Exception as e:
            self.logger.error(f"Failed to deframe message: {e}")
            return None



    #syn will trigger handshake
    async def deframe(self, raw: bytes):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)
        return frame



    async def on_exit(self):
        await super().on_exit()

    #three way handshake, sends packet number with ack incase pacekts dropped since last transmission
    async def handshake(self, syn: Audimus_pb2.Session_Message):

        new_mode = syn.mode
        self.logger.info(f"Handshake started for mode {new_mode}")

        for attempt in range(1, MAX_TRIES + 1):
            try:

                syn_ack = Audimus_pb2.Session_Message(SYNACK=True, mode=new_mode, packet_number = self.packet_number )
                await self.layer.swap_put(syn_ack.SerializeToString())


                raw = await asyncio.wait_for(self.handshake_rx_queue.get(), timeout=TIMEOUT)
                response = Audimus_pb2.Session_Message()
                response.ParseFromString(raw)

                if not response.ACK:
                    self.logger.warning(
                        f"Expected ACK, got unexpected frame (attempt {attempt}) – retrying"
                    )
                    continue

                self.logger.info(f"Handshake complete")
                self.connecting = False
                await self.layer.set_session(new_mode)
                return  # success

            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Timeout waiting for ACK (attempt {attempt}/{MAX_TRIES})"
                )

        self.logger.error(f"Handshake failed after {MAX_TRIES} attempts")
        self.connecting = False
