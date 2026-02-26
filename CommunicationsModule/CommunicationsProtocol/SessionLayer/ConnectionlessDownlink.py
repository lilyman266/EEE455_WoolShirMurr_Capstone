import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.Logger.Errors import InvalidSendError
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import Session

class ConnectionlessDownlink(Session):
    def __init__(self, context, DLL_rx, DLL_tx,packet_number_path ):
        self.name = "ConnectionlessDownlink    "
        self.logger = LoggerFactory.get_logger(self.name)
        self.packet_number = self.read_packet_number()
        super().__init__(context, DLL_rx, DLL_tx, packet_number_path)


class GroundStationConnectionlessDownlink(ConnectionlessDownlink):
    def __init__(self, context, DLL_rx, DLL_tx):
        self.packet_number_path = "CommunicationsModule/CommunicationsProtocol/SessionLayer/GroundStationCurrentPacketNumber" #tracks current packet number
        super().__init__(context, DLL_rx, DLL_tx, self.packet_number_path)
        self.context = context

    def frame(self, presentation_message):
        msg = Audimus_pb2.Session_Message()
        msg.message = presentation_message
        msg.mode = Audimus_pb2.SESSION_MODE.ConnectionlessDownLink
        msg.packet_number = self.packet_number

        return msg.SerializeToString()

    def deframe(self, msg):
        message = Audimus_pb2.Session_Message()
        message.ParseFromString(msg)
        self.packet_count(message)
        return message.presentation_message


    #counts, records, saves numbers of missed packets.
    def packet_count(self, message):

        # expected next packet
        expected = self.packet_number + 1

        print(f"Message packet number: {message.packet_number} expected packet number: {expected}")

        if message.packet_number != expected:
            for pkt in range(expected, message.packet_number):
                self.packet_tracker.record_drop(pkt)
                self.logger.info(f"dropped packet number {pkt}")

        # move packet_number forward to the received packet
        self.packet_number = message.packet_number
        self.write_packet_number(self.packet_number)


    async def tx(self, message):
        raise InvalidSendError(
            self,
            f"Cannot send messages in a {self.name} session"
        )

    async def rx(self):
        #receive packet
        msg =  await self.below_rx.get()
        message = self.deframe(msg)
        self.logger.info(message)
        return message

        #count packet number, if missing, record it

    def close_session(self):
        #record all missed packets in storage
        pass


class AudimusConnectionlessDownlink(ConnectionlessDownlink):
    def __init__(self, context, DLL_rx, DLL_tx):
        self.packet_number_path = "CommunicationsModule/CommunicationsProtocol/SessionLayer/AudimusCurrentPacketNumber" #tracks current packet number
        super().__init__(context, DLL_rx, DLL_tx, self.packet_number_path)
        self.context = context

    async def tx(self, message):


        # store the packet until later
        await self.packet_store.store_packet(self.packet_number, message)

        # encode the message
        message = self.frame(message)

        #send the message
        await self.below_tx.put(message)


    async def rx(self):
        # receive packet


        msg = await self.below_rx.get()
        self.logger.info(b"rx: ", msg)
        message = self.deframe(msg)
        self.logger.info(b"rx: ", message)
        return message

    def frame(self, presentation_message):
        # increment packet number
        self.packet_number += 1

        msg = Audimus_pb2.Session_Message()
        msg.presentation_message = presentation_message
        msg.mode = Audimus_pb2.SESSION_MODE.ConnectionlessDownlink
        msg.packet_number = self.packet_number
        self.write_packet_number(self.packet_number)
        return msg.SerializeToString()

    def deframe(self, data_link_message):
        message = Audimus_pb2.Session_Message()
        message.ParseFromString(data_link_message)
        if message.mode != Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
            self.context.set_state(message.mode)

        return message.presentation_message


