import CommunicationsModule.Audimus_pb2 as Audimus_pb2
import asyncio
import enum

class RadioMode(enum.Enum):
    RX = "rx"
    TX = "tx"

TIMER = 10

class Session:
    def __init__(self, layer):
        self.layer = layer

    async def reset(self):
        self.logger.warning(f"Received reset. Going back to connectionless downlink")
        await self.layer.set_session(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
        return

    async def handle_rx(self, packet):
        return packet

    async def handle_tx(self, message):
        return message

    async def on_enter(self):
        self.logger.info(f"Entered {self.name} mode")
        asyncio.create_task(self.activity_timer())

    async def activity_timer(self):
            # put the radio into receive mode
            self.logger.info(f"starting activity timer for {TIMER}")
            await asyncio.sleep(TIMER)
            self.logger.info("No activity detected, switching to Connectionless Downlink Mode")
            # if timer expires, go to connectionless downlink
            asyncio.create_task(self.layer.set_session(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink))

    async def on_exit(self):
        pass

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
        print(msg)
        await self.layer.put(msg)
        await self.layer.put(msg)
        await self.layer.swap_put(msg)


