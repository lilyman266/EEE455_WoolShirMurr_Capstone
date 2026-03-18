
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Idle import GroundStationIdle, AudimusIdle
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectionlessDownlink import GroundStationConnectionlessDownlink,AudimusConnectionlessDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedDownlink import GroundStationConnectedDownlink,AudimusConnectedDownlink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.ConnectedUplink import GroundStationConnectedUplink, AudimusConnectedUplink
from CommunicationsModule.CommunicationsProtocol.SessionLayer.Session import RadioMode
from Logger.Logger import LoggerFactory

import CommunicationsModule.Audimus_pb2 as Audimus_pb2
import asyncio
import json
import os


class SessionLayer:
    def __init__(self, sl_rx, sl_tx, dll_rx, dll_tx, session_queue, mode_queue):
        self.below_rx      = dll_rx
        self.below_tx      = dll_tx
        self.layer_rx      = sl_rx
        self.layer_tx      = sl_tx
        self.session_queue = session_queue
        self.mode_queue = mode_queue
        self.mode          = None
        self.session       = None
        self.name          = "Session Layer"
        self.logger        = LoggerFactory.get_logger(self.name)
        self._tasks        = []
        self._session_lock = asyncio.Lock()


    async def start(self):
        """Spawn the three worker tasks."""
        self._tasks = [
            asyncio.create_task(self.state_watcher(), name="state_watcher"),
            asyncio.create_task(self.rx(),             name="session_rx"),
            asyncio.create_task(self.tx(),            name="session_tx"),
        ]
        await self.set_session(Audimus_pb2.SESSION_MODE.Idle)

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


    async def rx(self):
        while True:

            packet = await self.below_rx.get()
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


    async def dll_radio_switch(self, new_mode):
        await self.mode_queue.put(new_mode)

    # all tx to the data link layer goes through here
    async def swap_put(self, message):
        await self.mode_queue.put(RadioMode.TX)
        await asyncio.sleep(0.001)
        await self.below_tx.put(message)
        await asyncio.sleep(0.001)
        await self.mode_queue.put(RadioMode.RX)
        await asyncio.sleep(0.001)



    async def put(self, message):
        await self.mode_queue.put(RadioMode.TX)
        await asyncio.sleep(0.001)
        await self.below_tx.put(message)


    async def mode_put(self, mode: RadioMode):
        await self.mode_queue.put(mode)







##################Ground Station ###############################################

class GroundStationSessionLayer(SessionLayer):

    def __init__(self, layer_rx, layer_tx, dll_rx, dll_tx, sl_sc, rm_sq):
        super().__init__(layer_rx, layer_tx, dll_rx, dll_tx, sl_sc, rm_sq)
        self.packet_tracker = MissingPacketIndex()  #tracks dropped packets for retransmission
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )


    async def get_session(self, new_mode):
        match new_mode:
            case Audimus_pb2.SESSION_MODE.Idle:
                return GroundStationIdle(self)
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


            match self.mode:
                ###########################switch from idle to connected uplink, connected downlink, or connectionless downlink
                    case Audimus_pb2.SESSION_MODE.Idle:
                        match new_mode:
                            case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                                await self.session.handshake(new_mode)
                            case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                                await self.session.handshake(new_mode)
                            case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                                await self.session.downlink()
                        continue

                ###########################from connected uplink
                    #if we are in connected uplink mode, can only switch to idle
                    case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                        match new_mode:
                            case Audimus_pb2.Idle:
                                await self.session.teardown()
                            case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                                self.logger.info(f"cannot switch directly between connected downlink and connectd uplink, switch to idle first")
                            case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                                self.logger.info(f"cannot switch directly between connected downlink and connectionless downlink, switch to idle first")

                    ###########################from connected downlink
                    case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                        match new_mode:
                            case Audimus_pb2.Idle:
                                await self.session.teardown()
                            case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                                self.logger.info(
                                    f"cannot switch directly between connected downlink and connectd uplink, switch to idle first")
                            case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                                self.logger.info(
                                    f"cannot switch directly between connected downlink and connectionless downlink, switch to idle first")


                    ###########################from connected downlink
                    case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                        self.logger.info(f"cannot switch from connectionless downlink mode. Wait for next pass")


################## Audimus ###############################################

class AudimusSessionLayer(SessionLayer):

    def __init__(self, layer_rx, layer_tx, dll_rx, dll_tx, session_queue, mode_queue, aros_sq):
        super().__init__(layer_rx, layer_tx, dll_rx, dll_tx, session_queue, mode_queue)
        self.packet_store = PacketStore()  # saves all packets until acked
        self.aros_session_queue = aros_sq
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/GroundStationCurrentPacketNumber"
        )


    async def get_session(self, new_mode):
        match new_mode:
            case Audimus_pb2.SESSION_MODE.Idle:
                return AudimusIdle(self)
            case Audimus_pb2.SESSION_MODE.ConnectionlessDownlink:
                return AudimusConnectionlessDownlink(self)
            case Audimus_pb2.SESSION_MODE.ConnectedUplink:
                return AudimusConnectedUplink(self)
            case Audimus_pb2.SESSION_MODE.ConnectedDownlink:
                return AudimusConnectedDownlink(self)
            case _:
                return None


    # reads from state queue, evaluates if session needs to be changed. send new session mode to audimus sim
    async def state_watcher(self):
        while True:
            new_mode = await self.session_queue.get()
            await self.set_session(new_mode)



    async def set_session(self, new_mode: Audimus_pb2.SESSION_MODE):

        # teardown the current session
        if self.session:
            await self.session.on_exit()

        async with self._session_lock:
            self.session = await self.get_session(new_mode)
            self.mode = new_mode

            #start the next session
            await self.session.on_enter()
            await self.aros_session_queue.put(new_mode)


############################### packet index and packet tracker ######################################


class MissingPacketIndex:
    """class for the ground station to track all missing packet numbers"""
    def __init__(self):
        self.packet_index = "CommunicationsModule/CommunicationsProtocol/SessionLayer/PacketStore/GS_packet_tracker"
        self.packet_number_path = (
            "CommunicationsModule/CommunicationsProtocol"
            "/SessionLayer/PacketStore/AudimusCurrentPacketNumber"
        )
        self.missing = set()
        self.load()

    def load(self):
        try:
            with open(self.packet_index, "r") as f:
                for line in f:
                    self.missing.add(int(line.strip()))
        except FileNotFoundError:
            pass

    def persist(self):
        with open(self.packet_index, "w") as f:
            for seq in sorted(self.missing):
                f.write(f"{seq}\n")

    def record_drop(self, seq):
        self.missing.add(seq)
        self.persist()

    def get_missing_packets(self):
        return sorted(self.missing)

    def acknowledge(self, seq):
        self.missing.discard(seq)
        self.persist()

    def has_missing_packets(self):
        return bool(self.missing)




class PacketStore:
    """class for Audimus to store all data untill it is acked.
     - Stored by connectionless downlink
     - retrieved and acknowledged by connected downlink
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


    def _read_store(self):
        try:
            with open(self.STORE_PATH, "r") as f:
                data = json.load(f)
            return {int(k): bytes.fromhex(v) for k, v in data.items()}
        except Exception as e:
            print(f"Error reading store: {e}")  # <-- Add this to see what is failing
            return {}

    def _write_store(self, store: dict) -> None:
        """Serialise and write the packet store dict to the index file."""
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

    async def empty_store(self) -> None:
        self._store= {}
        self._write_store(self._store)

    async def get_packet(self, seq_number: int):
        try:
            return self._store[seq_number]
        except KeyError:
            return None

    async def acknowledge(self, seq_number: int) -> None:
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



