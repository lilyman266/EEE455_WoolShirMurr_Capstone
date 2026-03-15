from Logger.Logger import LoggerFactory
import asyncio
import os
import struct
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectionlessDownlink import GroundStationConnectionlessDownlink,AudimusConnectionlessDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedDownlink import GroundStationConnectedDownlink,AudimusConnectedDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedUplink import GroundStationConnectedUplink, AudimusConnectedUplink
from CommunicationsModule.Logger.Errors import StateChangeError as SessionChangeError
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
import json




class SessionLayer:
    def __init__(self, sl_rx, sl_tx, dll_rx, dll_tx, session_queue):
        self.below_rx      = dll_rx
        self.below_tx      = dll_tx
        self.layer_rx      = sl_rx
        self.layer_tx      = sl_tx
        self.mode          = None
        self.session       = None
        self.name          = "Session Layer"
        self.logger        = LoggerFactory.get_logger(self.name)
        self.session_queue = session_queue
        self._tasks        = []
        self._session_lock = asyncio.Lock()


    async def start(self):
        """Spawn the three worker tasks."""
        self._tasks = [
            asyncio.create_task(self.state_watcher(), name="state_watcher"),
            asyncio.create_task(self.rx(),            name="session_rx"),
            asyncio.create_task(self.tx(),            name="session_tx"),
        ]

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


    async def rx(self):
        while True:
            packet = await self.below_rx.get()
            self.logger.info(f"rx: {packet}")
            async with self._session_lock:
                session = self.session

            if session is None:
                self.logger.warning("Packet dropped - no active session")
                continue

            message = await session.handle_rx(packet)

            if message is not None:
                await self.layer_rx.put(message)


    async def tx(self):
        while True:

            message = await self.layer_tx.get()

            async with self._session_lock:
                session = self.session

            if session is None:
                self.logger.warning("Message dropped - no active session")
                continue


            packet = await session.handle_tx(message)

            if packet is not None:
                await self.below_tx.put(packet)


    async def set_session(self, new_mode: Audimus_pb2.SESSION_MODE):

        # teardown the current session
        if self.session:
            await self.session.on_exit()

        async with self._session_lock:
            self.session = await self.get_session(new_mode)
            self.mode = new_mode


            #start the next session
            await self.session.on_enter()


    async def get_session(self, new_mode):
        pass


##################Ground Station ###############################################

class GroundStationSessionLayer(SessionLayer):

    def __init__(self, layer_rx, layer_tx, dll_rx, dll_tx, sl_sc):
        super().__init__(layer_rx, layer_tx, dll_rx, dll_tx, sl_sc)
        self.packet_tracker = MissingPacketIndex()  #tracks dropped packets for retransmission
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )



    async def start(self):
        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
        await super().start()

    async def get_session(self, new_mode):
        match new_mode:
            case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                return GroundStationConnectionlessDownlink(self)
            case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                return GroundStationConnectedUplink(self)
            case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                return GroundStationConnectedDownlink(self)
            case _:
                return None

    #reads from state queue, evaluates if session needs to be changed.
    async def state_watcher(self):
        while True:

            new_mode = await self.session_queue.get()
            # don't need to switch if you're allready in the mode
            if self.mode is not None and int(self.mode) == int(new_mode):
                self.logger.info(f"Already in mode: {new_mode}")
                continue

            #if no mode, automatically switch to connectionless downlink
            if self.mode == None:
                await self.set_session(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
                continue

            #prevent switching directly between connected uplink and connected downlink
            if  (self.mode == Audimus_pb2.SESSION_MODE.ConnectedUplink and new_mode == Audimus_pb2.SESSION_MODE.ConnectedDownlink
                or (self.mode == Audimus_pb2.SESSION_MODE.ConnectedDownlink and new_mode == Audimus_pb2.SESSION_MODE.ConnectedUplink)):
                self.logger.warning(f"switching between connected sessions is not supported. switch to connectionless downlink first")
                continue

            #if there are no packets to retransmit
            if new_mode == Audimus_pb2.SESSION_MODE.ConnectedDownlink:

                if not self.packet_tracker.has_missing_packets():
                    self.logger.info(f"no packets awaiting retransmission. staying in connectionless downlink mode")
                    continue

            match self.mode:

                # switching from connectionless downlink to a connected mode
                case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                    await self.session.handshake(new_mode)
                    continue

                #if we are in connected uplink mode, can only switch to connected downlink
                case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                    await self.session.teardown()
                    continue

                # if we are in connected downlink mode, can only switch to connected downlink
                case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                    await self.session.teardown()
                    continue




################## Audimus ###############################################

class AudimusSessionLayer(SessionLayer):

    def __init__(self, layer_rx, layer_tx, dll_rx, dll_tx, sl_sq):
        super().__init__(layer_rx, layer_tx, dll_rx, dll_tx, sl_sq)
        self.packet_store = PacketStore()  # saves all packets until acked
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )

    async def start(self):
        await self.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
        await super().start()


    async def get_session(self, new_mode):
        match new_mode:
            case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                return AudimusConnectionlessDownlink(self)
            case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                return AudimusConnectedUplink(self)
            case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                return AudimusConnectedDownlink(self)
            case _:
                return None


    # reads from state queue, evaluates if session needs to be changed.
    async def state_watcher(self):
        while True:
            new_mode = await self.session_queue.get()
            await self.set_session(new_mode)


############################### packet index and packet tracker ######################################


class MissingPacketIndex:
    """class for ground station to track all missing packet numbers until they are retransmitted"""
    def __init__(self):
        self.packet_index = "CommunicationsModule/CommunicationsProtocol/SessionLayer/PacketStore/GS_packet_tracker"
        self.missing = set()
        self._load()

    def _load(self):
        try:
            with open(self.packet_index, "r") as f:
                for line in f:
                    self.missing.add(int(line.strip()))
        except FileNotFoundError:
            pass

    def _persist(self):
        with open(self.packet_index, "w") as f:
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

    def has_missing_packets(self):
        return bool(self.missing)





import os
import json
import asyncio


class PacketStore:
    """
    Async-safe class to store, retrieve, and acknowledge packets
    from a communications protocol session layer.
    Packets are persisted to a JSON index file.
    """

    STORE_PATH = (
        "CommunicationsModule/CommunicationsProtocol"
        "/SessionLayer/PacketStore/packets.idx"
    )

    def __init__(self):

        self._lock = asyncio.Lock()

        os.makedirs(os.path.dirname(self.STORE_PATH), exist_ok=True)

        if not os.path.exists(self.STORE_PATH):
            self._write_store({})

        self._store = self._read_store()


    def _read_store(self) -> dict:
        try:
            with open(self.STORE_PATH, "r") as f:
                data = json.load(f)
            return {int(k): bytes.fromhex(v) for k, v in data.items()}
        except Exception as e:
            print(f"Error reading store: {e}")  # <-- Add this to see what is failing
            return {}

    def _write_store(self, store: dict) -> None:
        """Serialise and write the packet store dict to the index file."""
        # bytes are not JSON serialisable, so store as hex strings
        serialisable = {str(k): v.hex() for k, v in store.items()}
        with open(self.STORE_PATH, "w") as f:
            json.dump(serialisable, f, indent=4)


    async def store_packet(self, seq_number: int, payload: bytes) -> None:
        if seq_number in self._store:
            raise ValueError(
                f"Packet with seq_number {seq_number} already exists in the store."
            )
        self._store[seq_number] = payload
        self._write_store(self._store)

    async def get_packet(self, seq_number: int):
        return self._store[seq_number]

    async def acknowledge(self, seq_number: int) -> None:
        """
        Acknowledge and remove a packet from the store.

        Args:
            seq_number (int): The sequence number of the packet to acknowledge.

        Raises:
            TypeError: If seq_number is not an int.
            KeyError:  If no packet with the given sequence number exists.
        """
        if not isinstance(seq_number, int):
            raise TypeError(
                f"seq_number must be an int, got {type(seq_number).__name__}"
            )


        if seq_number not in self._store:
            raise KeyError(
                f"No packet with seq_number {seq_number} found in the store."
            )

        del self._store[seq_number]
        self._write_store(self._store)



