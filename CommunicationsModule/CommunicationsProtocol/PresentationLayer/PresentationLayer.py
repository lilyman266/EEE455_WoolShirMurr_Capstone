from CommunicationsModule.CommunicationsProtocol import ProtocolLayer
import CommunicationsModule.Audimus_pb2 as Audimus_pb2

from Logger.Logger import LoggerFactory
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

KEY_FILE = "CommunicationsModule/CommunicationsProtocol/PresentationLayer/master_key" #preload before launch
KEY_SIZE = 32  # 256 bits for AES-256-GCM
SALT_SIZE = 4
NONCE_SIZE =12
SENDER_IDENTITY = 1

class PresentationLayer(ProtocolLayer.ProtocolLayer):
    def __init__(self, PL_rx, PL_tx, SL_rx, SL_tx, data_file):
        super().__init__(PL_rx, PL_tx, SL_rx, SL_tx)
        self.name           = "Presentation Layer"
        self.key_epoch      = 0
        self.data_file      = data_file
        self.session_number = self.read_session_number()
        self.logger         = LoggerFactory.get_logger(self.name)
        self.master_key     = self.load_master_key(KEY_FILE)
        self.aesgcm         = AESGCM(self.master_key)
        self.nonce_salt     = os.urandom(SALT_SIZE)
        self.nonce_count    = 0

    def on_exit(self):
        self.update_session_number(self.session_number)

    def load_master_key(self, path):
        with open(path, "rb") as f:
            key = f.read().strip()
        if len(key) != KEY_SIZE:
            raise ValueError(f"Invalid key length: expected {KEY_SIZE}, got {len(key)}")
        return key

    def get_nonce(self):
        self.nonce_count += 1
        return self.nonce_salt + self.nonce_count.to_bytes(8, byteorder="big")


    def process_tx(self, message):
        return self.frame(message)

    def frame(self, message):
        msg = Audimus_pb2.Presentation_Message()
        msg.key_epoch          = self.key_epoch
        msg.session_number     = self.session_number
        msg.application_message = self.encrypt(message)
        return msg.SerializeToString()

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = self.get_nonce()
        aad = f"{SENDER_IDENTITY}".encode("utf-8")

        try:
            cipher = self.aesgcm.encrypt(nonce, plaintext, aad)
        except ValueError:
            self.logger.warning(f"message: {plaintext} too short for encryption")
            return b''

        return nonce + cipher


    def process_rx(self, message):
        message = self.deframe(message)
        return message

    def deframe(self, message):
        pl_message = Audimus_pb2.Presentation_Message()
        pl_message.ParseFromString(message)

        # Always decrypt using the session number in the packet
        try:
            plaintext = self.decrypt(pl_message.application_message,pl_message.session_number)
        except ValueError:
            self.logger.warning(f"message: {message} too short for decryption")
            return b''


        if pl_message.session_number > self.session_number:
            self.update_session_number(pl_message.session_number)

        return plaintext

    def decrypt(self, payload: bytes, session_number: int) -> bytes:

        if len(payload) < NONCE_SIZE:
            raise ValueError(f"Payload too short: {len(payload)} bytes")



        nonce = payload[:NONCE_SIZE]
        ciphertext_with_tag = payload[NONCE_SIZE:]
        associated_data = f"{SENDER_IDENTITY}".encode("utf-8")

        plaintext = self.aesgcm.decrypt(nonce, ciphertext_with_tag, associated_data)
        return plaintext

    def read_session_number(self):
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return int(f.read().strip()) + 1
        except FileNotFoundError:
            self.update_session_number(0)
            return 0
        except Exception as e:
            self.logger.error(f"read_session_number error: {e}")
            raise

    def update_session_number(self, new_session_number):
        self.session_number = new_session_number
        with open(self.data_file, "w", encoding="utf-8") as f:
            f.write(str(new_session_number))



class GroundStationPresentationLayer(PresentationLayer):
    def __init__(self, PL_rx,PL_tx, SL_rx, SL_tx):
        super().__init__(PL_rx, PL_tx, SL_rx, SL_tx, "CommunicationsModule/CommunicationsProtocol/PresentationLayer/GroundStationData")


class AudimusPresentationLayer(PresentationLayer):
    def __init__(self, PL_rx,PL_tx, SL_rx, SL_tx):
        super().__init__(PL_rx, PL_tx, SL_rx, SL_tx, "CommunicationsModule/CommunicationsProtocol/PresentationLayer/AudimusData")





