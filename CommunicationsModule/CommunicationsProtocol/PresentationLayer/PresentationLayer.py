from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from Logger.Logger import LoggerFactory
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64
import json
import asyncio

KEY_FILE = "CommunicationsModule/CommunicationsProtocol/PresentationLayer/master_key" #preload before launch
KEY_SIZE = 32  # 256 bits for AES-256-GCM
SALT_SIZE = 4

class PresentationLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, PL_rx,PL_tx, SL_rx, SL_tx, data_file):
        super().__init__(PL_rx,PL_tx, SL_rx, SL_tx)
        self.name = "Presentation Layer"
        self.key_epoch = 0
        self.data_file = data_file
        self.session_number = self.read_session_number()
        self.logger = LoggerFactory.get_logger(self.name)
        self.master_key = self.load_master_key(KEY_FILE)
        self.aesgcm = AESGCM(self.master_key)
        self.nonce_salt = os.urandom(SALT_SIZE)
        self.nonce_count = 0


    def on_exit(self):
        self.update_session_number(self.session_number)

    def load_master_key(self, path) :
        with open(path, "rb") as f:
            key = f.read().strip()
        if len(key) != KEY_SIZE:
            raise ValueError("Invalid key length after hex decode")
        return key

    def get_nonce(self):
        #returns a 12 byte nonce, uses a 4 byte salt
        return self.nonce_salt + self.nonce_count.to_bytes(8, byteorder="big")





    def process_rx(self, message):

        message = self.deframe(message)

        return message

    def process_tx(self, message):

        message = self.frame(message)


        return message


    def frame(self, message):
        msg = Audimus_pb2.Presentation_Message()
        msg.key_epoch = self.key_epoch
        msg.session_number = self.session_number
        msg.application_message = self.encrypt(message)
        return msg.SerializeToString()

    def deframe(self, message):
        pl_message = Audimus_pb2.Presentation_Message()
        pl_message.ParseFromString(message)
        if pl_message.session_number > self.session_number:
            self.update_session_number(pl_message.session_number)
        plaintext = self.decrypt(pl_message.application_message)
        return plaintext


    def encrypt(self, plaintext):
        nonce = self.get_nonce()
        associated_data = (str(self.session_number)).encode("utf-8")
        cipher = self.aesgcm.encrypt(nonce, plaintext, associated_data)
        return nonce + cipher

    def decrypt(self, payload):
        nonce = payload[:12]
        cipher = payload[12:]
        associated_data = (str(self.session_number)).encode("utf-8")

        try:
            plain_text = self.aesgcm.decrypt(nonce, cipher, associated_data)
            return plain_text
        except:
            self.logger.info("Decryption/auth failure")
            raise

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





