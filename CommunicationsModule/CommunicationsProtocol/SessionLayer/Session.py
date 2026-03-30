import CommunicationsModule.Audimus_pb2 as Audimus_pb2
import asyncio
import enum

class RadioMode(enum.Enum):
    RX = "rx"
    TX = "tx"


SESSION_TIMER = 30

class Session:
    def __init__(self, layer):
        self.layer = layer
        self.activity_timer = ActivityTimer(timeout = SESSION_TIMER, callback = self.on_timeout)

    async def on_timeout(self):
        self.logger.warning("No RX in 2 minutes — switching to ConnectionlessDownlink")
        await self.layer.set_session(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)

    async def handle_rx(self, packet):
        return packet

    async def handle_tx(self, message):
        return message

    async def on_enter(self):
        self.logger.info(f"Entered {self.name} mode")
        self.activity_timer.start()


    async def on_exit(self):
        await self.activity_timer.stop()

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

    #frames message for mode burst
    def frame_mode(self, new_mode):
        msg = Audimus_pb2.Session_Message(mode=new_mode)
        return msg.SerializeToString()

    async def transmit_mode(self, new_mode):
        msg = self.frame_mode(new_mode)
        await self.layer.put(msg)
        await self.layer.put(msg)
        await self.layer.put(msg)


############################### timer class #########################################################

class ActivityTimer:
    def __init__(self, timeout: float, callback):
        self.timeout  = timeout
        self.callback = callback
        self._task    = None
        self._event   = asyncio.Event()

    def start(self):
        self._event.clear()
        self._task = asyncio.create_task(self.run(), name="activity_timer")

    def reset(self):
        """Call this on every RX."""
        self._event.set()

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run(self):
        try:
            while True:
                self._event.clear()
                try:
                    await asyncio.wait_for(
                        self._event.wait(),
                        timeout=self.timeout
                    )
                    # event was set → RX occurred → reset and wait again
                except asyncio.TimeoutError:
                    # no RX in `timeout` seconds → fire callback
                    await self.callback()
                    return
        except asyncio.CancelledError:
            pass