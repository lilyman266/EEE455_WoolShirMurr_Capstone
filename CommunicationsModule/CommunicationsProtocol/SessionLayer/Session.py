import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from Logger.Logger import LoggerFactory
from CommunicationsModule.Logger.Errors import InvalidSendError
from enum import Enum
import csv
from collections import deque
import os
import struct
import asyncio

class SessionMode(Enum):
    CONNECTIONLESS_DOWNLINK = 0
    CONNECTED_DOWNLINK = 1
    CONNECTED_UPLINK = 2

class Session:
    def __init__(self, context, DLL_rx, DLL_tx, packet_number_path):
        self.below_tx = DLL_tx
        self.below_rx = DLL_rx
        self.packet_number_path = packet_number_path
        self.packet_number = self.read_packet_number()
        self.context = context
        self.packet_store = PacketStore("CommunicationsModule/CommunicationsProtocol/SessionLayer/PacketStore") #saves all packets until acked
        self.packet_tracker = MissingPacketIndex("CommunicationsModule/CommunicationsProtocol/SessionLayer/MissingPacketIndex")

    async def rx(self):
        return await self.below_rx.get()

    async def tx(self, message):
        await self.below_tx.put(message)


    def write_packet_number(self, packet_number):
        with open(self.packet_number_path, "w", encoding="utf-8") as f: f.write(str(packet_number))

    def read_packet_number(self):
        try:
            with open(self.packet_number_path, 'r', encoding='utf-8') as file:
                packet_number = file.read()
                return (int(packet_number))

        except FileNotFoundError:
            print("file not found, writing file")
            self.write_packet_number(0)
            return 0
        except Exception as e:
            print(f"An error occurred: {e}")




#class for ground station to track all missing packet numbers until they are retransmitted
class MissingPacketIndex:
    def __init__(self, filename):
        self.filename = filename
        self.missing = set()
        self._load()

    def _load(self):
        try:
            with open(self.filename, "r") as f:
                for line in f:
                    self.missing.add(int(line.strip()))
        except FileNotFoundError:
            pass

    def _persist(self):
        with open(self.filename, "w") as f:
            for seq in sorted(self.missing):
                f.write(f"{seq}\n")

    def record_drop(self, seq):
        self.missing.add(seq)
        self._persist()

    def get_missing_packets(self):
        return sorted(self.missing)

    def acknowledge(self, seq):
        self.missing.discard(seq)
        self._persist()

#class for Audimus to read/write all packets unti they can be acked.
class PacketStore:
    LOG_FILE = "packets.log"
    IDX_FILE = "packets.idx"

    def __init__(self, directory):
        self.dir = directory
        os.makedirs(self.dir, exist_ok=True)
        self.log_path = os.path.join(self.dir, self.LOG_FILE)
        self.idx_path = os.path.join(self.dir, self.IDX_FILE)

        self.lock = asyncio.Lock()
        self.index = {}

    async def load(self):
        if not os.path.exists(self.idx_path):
            return

        async with self.lock:
            def _load():
                with open(self.idx_path, "r", encoding="utf-8") as f:
                    for line in f:
                        seq, offset, length = map(int, line.split())
                        self.index[seq] = (offset, length)
            await asyncio.to_thread(_load)

    async def _write_index(self):
        def _write():
            tmp = self.idx_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for seq, (offset, length) in sorted(self.index.items()):
                    f.write(f"{seq} {offset} {length}\n")
            os.replace(tmp, self.idx_path)
        await asyncio.to_thread(_write)

    async def store_packet(self, seq: int, payload: bytes):
        async with self.lock:
            def _write_log():
                with open(self.log_path, "ab") as log:
                    offset = log.tell()
                    header = struct.pack("<II", seq, len(payload))
                    log.write(header)
                    log.write(payload)
                    log.flush()
                    os.fsync(log.fileno())
                return offset

            offset = await asyncio.to_thread(_write_log)
            self.index[seq] = (offset, len(payload))
            await self._write_index()

    async def get_packet(self, seq: int):
        async with self.lock:
            entry = self.index.get(seq)
            if not entry:
                return None

            offset, length = entry

            def _read():
                with open(self.log_path, "rb") as log:
                    log.seek(offset)
                    header = log.read(8)
                    pkt_seq, pkt_len = struct.unpack("<II", header)
                    if pkt_seq != seq or pkt_len != length:
                        return None
                    return log.read(pkt_len)

            return await asyncio.to_thread(_read)

    async def acknowledge(self, seq: int):
        async with self.lock:
            if seq in self.index:
                del self.index[seq]
                await self._write_index()









