from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from Logger.Logger import LoggerFactory

class PresentationLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, PL_rx,PL_tx, SL_rx, SL_tx, data_file):
        super().__init__(PL_rx,PL_tx, SL_rx, SL_tx)
        self.name = "Presentation Layer"
        self.key_epoch = 0
        self.data_file = data_file
        self.session_number = self.read_session_number()
        self.logger = LoggerFactory.get_logger(self.name)


    def process_rx(self, message):
        message = self.deframe(message)
        return message

    def process_tx(self, message):
        message = self.frame(message)
        self.logger.info(str(message))
        return message


    def frame(self, message):
        #create the pl_level header
        msg = Audimus_pb2.Presentation_Message()
        msg.key_epoch = self.key_epoch
        msg.session_number = self.session_number
        msg.application_message = message
        return msg.SerializeToString()

    def deframe(self, message):
        pl_message = Audimus_pb2.Presentation_Message()
        pl_message.ParseFromString(message)
        if pl_message.session_number > self.session_number:
            self.update_session_number(pl_message.session_number)
        return pl_message.application_message


    def encrypt(self, message):
        pass

    def dencrypt(self, message):
        pass

    def authenticate(self, message):
        pass

    def read_session_number(self):
        try:
            with open(self.data_file, 'r', encoding='utf-8') as file:
                session_number = file.read()
                return (int(session_number) + 1)

        except FileNotFoundError:
            print("file not found, writing file")
            self.update_session_number(0)
            return 0
        except Exception as e:
            print(f"An error occurred: {e}")


    def update_session_number(self, new_session_number):
        self.session_number = new_session_number
        with open(self.data_file, "w", encoding="utf-8") as f: f.write(str(new_session_number))





class GroundStationPresentationLayer(PresentationLayer):
    def __init__(self, PL_rx,PL_tx, SL_rx, SL_tx):
        super().__init__(PL_rx, PL_tx, SL_rx, SL_tx, "CommunicationsModule/CommunicationsProtocol/PresentationLayer/GroundStationData")



class AudimusPresentationLayer(PresentationLayer):
    def __init__(self, PL_rx,PL_tx, SL_rx, SL_tx):
        super().__init__(PL_rx, PL_tx, SL_rx, SL_tx, "CommunicationsModule/CommunicationsProtocol/PresentationLayer/AudimusData")





