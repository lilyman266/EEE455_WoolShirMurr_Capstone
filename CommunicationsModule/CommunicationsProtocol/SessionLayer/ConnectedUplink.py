import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session, SessionMode


MAX_RETRIES = 5
TIMEOUT = 0.7

class ConnectedUplink(Session):
    def __init__(self, DLL_rx, DLL_tx, file_path):
        super().__init__(DLL_rx, DLL_tx, file_path)
        self.name = "ConnectedUplink"
        self.logger = LoggerFactory.get_logger(self.name)

    async def rx(self):
        message = self.below_rx.get()
        return message


    async def tx(self, message):
        msg = self.frame(message)
        await self.below_tx.put(msg)

    def frame(self, presentation_message):
        msg = Audimus_pb2.Session_Message()
        msg.presentation_message = presentation_message
        msg.mode = Audimus_pb2.SESSION_MODE.ConnectedUplink
        msg.packet_number = self.packet_number
        self.write_packet_number(self.packet_number)
        return msg.SerializeToString()

    async def tear_down(self):
        pass


class GroundStationConnectedUplink(ConnectedUplink):
    def __init__(self, DLL_rx, DLL_tx, session_queue):
        super().__init__(DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/GroundStationData")
        self.session_queue = session_queue

    async def handshake(self):

        for attempt in range(1, MAX_RETRIES + 1):
            # Send SYN
            syn_msg = Audimus_pb2.Session_Message(
                presentation_message = b'SYN',
                SYN=True,
                mode = Audimus_pb2.ConnectedUplink
            )
            await self.below_tx.put(syn_msg.SerializeToString())

            try:
                # Wait for SYN-ACK
                raw = await asyncio.wait_for(self.below_rx.get(), timeout=TIMEOUT)
                response = Audimus_pb2.Session_Message()
                response.ParseFromString(raw)

                if response.SYN and response.ACK:
                    # Send final ACK
                    ack_msg = Audimus_pb2.Session_Message(
                        ACK=True
                    )
                    await self.below_tx.put(ack_msg.SerializeToString())
                    self.logger.info("Connection Established")
                    return True

            except asyncio.TimeoutError:
                pass


        self.logger.info("Handshake failed")
        await self.session_queue.put(SessionMode.CONNECTIONLESS_DOWNLINK)
        return False

class AudimusConnectedUplink(ConnectedUplink):
    def __init__(self, DLL_rx, DLL_tx, session_queue):
        super().__init__(DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/AudimusData")
        self.session_queue = session_queue


    async def handshake(self):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Wait for SYN
                raw = await asyncio.wait_for(self.below_rx.get(), timeout=TIMEOUT)

                message = Audimus_pb2.Session_Message()
                message.ParseFromString(raw)

                if message.SYN and not message.ACK:

                    # Send SYN-ACK
                    syn_ack = Audimus_pb2.Session_Message(
                        presentation_message=b'SYN-ACK',
                        SYN=True,
                        ACK=True,
                    )
                    await self.below_tx.put(syn_ack.SerializeToString())

                    try:
                        # Wait for final ACK
                        raw_ack = await asyncio.wait_for(
                            self.below_rx.get(),
                            timeout=TIMEOUT
                        )

                        final_msg = Audimus_pb2.Session_Message()
                        final_msg.ParseFromString(raw_ack)

                        if final_msg.ACK and not final_msg.SYN:
                            self.logger.info("Received ACK — Connection Established")
                            return True

                    except asyncio.TimeoutError:
                        await self.session_queue.put(SessionMode.CONNECTIONLESS_DOWNLINK)
            except asyncio.TimeoutError:
                # No SYN received this round
                continue
        self.logger.info("Server handshake failed")
        return False



    async def rx(self):
        message = await self.below_rx.get()
        self.logger.info("rx: {message}")
        message = self.deframe(message)
        return message

    async def deframe(self, data_link_message):
        message = Audimus_pb2.Session_Message()
        message.ParseFromString(data_link_message)
        match message.mode:
            case 1:
                await self.session_queue.put(SessionMode.CONNECTED_DOWNLINK)
            case 2:
                await self.session_queue.put(SessionMode.CONNECTED_UPLINK)
            case _:
                pass
        return message.message


