import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from Logger.Errors import InvalidSendError
from enum import Enum

class SessionMode(Enum):
    CONNECTIONLESS_DOWNLINK = 0
    CONNECTED_DOWNLINK = 1
    CONNECTED_UPLINK = 2


class Session:
    def __init__(self, DLL_rx, DLL_tx, file_path):
        self.below_tx = DLL_tx
        self.below_rx = DLL_rx
        self.file_path = file_path
        self.packet_number = self.read_packet_number()



    async def tx(self, message):
        self.logger.info(message)
        await self.below_tx.put(message)



    async def rx(self):
        return await self.below_rx.get()

    def write_packet_number(self, packet_number):
        with open(self.file_path, "w", encoding="utf-8") as f: f.write(str(packet_number))

    def read_packet_number(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                packet_number = file.read()
                return (int(packet_number))

        except FileNotFoundError:
            print("file not found, writing file")
            self.write_packet_number(0)
            return 0
        except Exception as e:
            print(f"An error occurred: {e}")


class ConnectedUplink(Session):
    def __init__(self, DLL_rx, DLL_tx, file_path):
        self.name = "ConnectedUplink"
        self.logger = LoggerFactory.get_logger(self.name)
        super().__init__(DLL_rx, DLL_tx, file_path)

class GroundStationConnectedUplink(ConnectedUplink):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/GroundStationData")


class AudimusConnectedUplink(ConnectedUplink):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/AudimusData")




class ConnectedDownlink(Session):
    def __init__(self, DLL_rx, DLL_tx, file_path):
        self.name = "ConnectedDownlink"
        self.logger = LoggerFactory.get_logger(self.name)
        super().__init__(DLL_rx, DLL_tx, file_path)

class GroundStationConnectedDownlink(ConnectedDownlink):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/GroundStationData")

class AudimusConnectedDownlink(ConnectedDownlink):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/AudimusData")




class ConnectionlessDownlink(Session):
    def __init__(self, DLL_rx, DLL_tx,file_path ):
        self.name = "ConnectionlessDownlink"
        self.logger = LoggerFactory.get_logger(self.name)
        super().__init__(DLL_rx, DLL_tx, file_path)







class GroundStationConnectionlessDownlink(ConnectionlessDownlink):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx, DLL_tx,"CommunicationsModule/CommunicationsProtocol/SessionLayer/GroundStationData")

    def encode(self, presentation_message):
        msg = Audimus_pb2.Application_Message()
        msg.message = presentation_message
        msg.mode = Audimus_pb2.SESSION_MODE.ConnectionlessDownLink
        msg.packet_number = self.packet_number

        return msg.SerializeToString()

    def decode(self, msg):
        message = Audimus_pb2.Application_Message()
        message.ParseFromString(msg)
        return message.message





    async def tx(self, message):
        raise InvalidSendError(
            self,
            f"Cannot send messages in a {self.name} session"
        )

    async def rx(self):

        #receive packet
        return await self.below_rx.get()

        #count packet number, if missing, record it

    def close_session(self):
        #record all missed packets in storage
        pass




class AudimusConnectionlessDownlink(ConnectionlessDownlink):
    def __init__(self, DLL_rx, DLL_tx):
        super().__init__(DLL_rx, DLL_tx, "CommunicationsModule/CommunicationsProtocol/SessionLayer/AudimusData")

    async def tx(self, message):
        raise InvalidSendError(
            self,
            f"Cannot send messages in a {self.name} session"
        )

    async def rx(self):
        # receive packet
        return await self.below_rx.get()




