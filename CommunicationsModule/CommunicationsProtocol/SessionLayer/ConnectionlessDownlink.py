import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.Logger.Errors import InvalidSendError
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session, SessionMode

import asyncio


MAX_TRIES = 5
TIMEOUT = 5

class ConnectionlessDownlink(Session):
    """ Base class for connectionless downlink sessions"""

    def __init__(self, layer):
        super().__init__(layer)
        self.layer = layer
        self.name = "ConnectionlessDownlink"
        self.logger = LoggerFactory.get_logger(self.name)
        self.packet_number = self.read_packet_number()
        self.handshake_rx_queue = asyncio.Queue()
        self.connecting = False


    async def handle_rx(self, packet: bytes):
        pass


    async def handle_tx(self, message: bytes):
        pass

    async def on_enter(self):
        self.logger.info(f"{self.name} entered")

    async def on_exit(self):
        pass


class GroundStationConnectionlessDownlink(ConnectionlessDownlink):
    """
    RX: Receives data frames from Audimus, deframes, tracks dropped packets.
    TX: Sends SYN requests to Audimus to initiate connected sessions. Error if sends other message. .
    """

    def __init__(self, layer):
        self.packet_number_path = ("CommunicationsModule/CommunicationsProtocol/SessionLayer/PacketStore/GroundStationCurrentPacketNumber")
        super().__init__(layer)  # reads packet_number via read_packet_number()


    async def handle_rx(self, data_link_message):
        """Deframe incoming packet.Returns none if frame is malformed. If handshake is in progress, use special queue"""

        if self.connecting:
            await self.handshake_rx_queue.put(data_link_message)
            return None

        try:
            return self.deframe(data_link_message)
        except Exception as e:
            self.logger.error(f"Failed to deframe packet: {e}")
            return None

    def deframe(self, data_link_message):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(data_link_message)
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


    async def handle_tx(self, message):
        """Ground station does not send data in connectionless downlink mode. Only syn request"""
        try:
            frame = self.frame_syn(message)
            self.logger.info(f"Sending SYN request")
            return frame
        except Exception as e:
            self.logger.error(f"Failed to frame SYN: {e}")
            return None



    async def on_exit(self):
        await super().on_exit()
        self.logger.info(
            f"GroundStation connectionless downlink exiting. "
            f"Final packet number: {self.packet_number}"
        )

    async def handshake(self, new_mode:Audimus_pb2.SESSION_MODE):
        """sends Syn, expects SYNACK, responds with ACK. Cancels if timer expires"""
        self.logger.info(f"initiating handshake for{new_mode}")
        self.connecting = True

        for attempt in range(MAX_TRIES):
            try:
                syn = Audimus_pb2.Session_Message(SYN = True, mode = new_mode)
                await self.layer.below_tx.put(syn.SerializeToString())


                #wait for SYN-ACK
                raw = await asyncio.wait_for(self.handshake_rx_queue.get(), timeout= TIMEOUT)
                syn_ack = Audimus_pb2.Session_Message()
                syn_ack.ParseFromString(raw)
                if not syn_ack.SYNACK:
                    break

                else:
                    #send ack
                    ack = Audimus_pb2.Session_Message(ACK = True, mode = new_mode)
                    await self.layer.below_tx.put(ack.SerializeToString())

                    #switch modes
                    await self.layer.session_queue.put(new_mode)
                    break

            except asyncio.TimeoutError:
                self.logger.error(f"handshake failed after {MAX_TRIES} attempts")
        self.connecting = False







class AudimusConnectionlessDownlink(ConnectionlessDownlink):

    def __init__(self, layer):
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/AudimusCurrentPacketNumber"
        )
        super().__init__(layer)  # reads packet_number via read_packet_number()


    async def handle_tx(self, message: bytes) -> bytes | None:
        """Frame outgoing data and send to ground station. Increments and persists packet number on every transmission.
        """
        try:
            self.packet_number += 1
            frame = self.frame(message)
            self.write_packet_number(self.packet_number)
            await self.packet_store.store_packet(self.packet_number, frame)
            return frame
        except Exception as e:
            self.logger.error(f"Failed to frame message: {e}")
            self.packet_number -= 1  # roll back on failure
            return None

    def frame(self, presentation_message):
        msg = Audimus_pb2.Session_Message()
        msg.presentation_message = presentation_message
        msg.mode = Audimus_pb2.SESSION_MODE.ConnectionlessDownlink
        msg.packet_number = self.packet_number
        msg.SYN = False
        return msg.SerializeToString()


    async def handle_rx(self, raw):
        """Receive messages from ground station. SYN frames trigger a session mode transition.
         Returns presentation payload, or None if it was a control frame only.
         If handshake is in progress, use special queue"""
        if self.connecting:
            await self.handshake_rx_queue.put(raw)
            return None
        try:
            return await self.deframe(raw)
        except Exception as e:
            self.logger.error(f"Failed to deframe message: {e}")
            return None

    async def deframe(self, raw):
        frame = Audimus_pb2.Session_Message()
        frame.ParseFromString(raw)

        if frame.SYN:
            self.Connecting = True
            asyncio.create_task(self.handshake(frame))
            return None  # SYN frames have no payload for presentation

        return frame.presentation_message

    async def handshake(self, syn: Audimus_pb2.Session_Message):
        """
        Executes the full 3-way handshake from the satellite side.
        Called by handle_rx when a SYN frame is detected.
        Stays in connectionless mode until final ACK is confirmed.
        Switches mode via session_queue only on success.
        """
        new_mode = syn.mode
        self.connecting = True
        for attempt in range(MAX_TRIES):
            try:

                # send syn ack
                syn_ack = Audimus_pb2.Session_Message(SYNACK = True, mode = new_mode)
                await self.layer.below_tx.put(syn_ack.SerializeToString())
                self.logger.info(f"SYN-ACK sent (attempt {attempt})")

                # wait for ack
                raw = await asyncio.wait_for(
                    self.handshake_rx_queue.get(),
                    timeout=TIMEOUT
                )
                response = Audimus_pb2.Session_Message()
                response.ParseFromString(raw)

                if response.ACK:
                    # switch modes
                    self.logger.info(f"Handshake complete - requesting mode {new_mode}")
                    await self.layer.session_queue.put(new_mode)
                    self.connecting = False
                    return  # success


            except asyncio.TimeoutError:
                self.logger.warning(f"Handshake timeout waiting for ACK ")


        # all retries exhausted - notify ground station
        self.logger.error(f"Handshake failed after {MAX_TRIES} attempts - ")
        self.connecting = False


    async def on_exit(self):
        await super().on_exit()  # saves packet number
        self.logger.info(
            f"Audimus connectionless downlink exiting. "
            f"Final packet number: {self.packet_number}"
        )
