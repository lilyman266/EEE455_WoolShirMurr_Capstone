import asyncio
import random
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from CommunicationsModule.CommunicationsProtocol.ApplicationLayer.ApplicationLayer import GroundStationApplicationLayer
from CommunicationsModule.CommunicationsProtocol.PresentationLayer.PresentationLayer import GroundStationPresentationLayer
from CommunicationsModule.CommunicationsProtocol.DataLinkLayer.DataLinkLayer import GroundStationDataLinkLayer
from CommunicationsModule.CommunicationsProtocol.SessionLayer.SessionLayer import GroundStationSessionLayer


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")


async def app_rx(AL_rx):
    while True:
        message = await AL_rx.get()


async def app_tx(AL_tx, sl ):

  # For reading from the command line
    loop = asyncio.get_running_loop()
    print("Enter messages (type 'exit' to quit):")
    while True:
        line = await loop.run_in_executor(None,input,"> ")
        if line.lower() == "exit":
            break



# For reading from a file
   #  for line in read_lines("CommunicationsModule/TestTXGroundStation"):
        match line:
            case "connected uplink mode":
                await sl.session.handshake(Audimus_pb2.SESSION_MODE.ConnectedUplink)
            case "connected downlink mode":
                 await sl.session.handshake(Audimus_pb2.SESSION_MODE.ConnectedDownlink)
            case "connectionless downlink mode":
                await sl.session_queue.put(Audimus_pb2.SESSION_MODE.ConnectionlessDownlink)
            case _ :
                await AL_tx.put(line)
        #await asyncio.sleep(1)

#write to SDR sending file
async def file_tx(SDR_tx):
    pass

#write to SDR receiving file
async def file_Rx(SDR_rx):
    pass

#sends to Audimus with tcp
async def tcp_tx(writer, SDR_tx):
    while True:
        msg = (await SDR_tx.get())

        writer.write(msg)          # msg must be bytes
        await writer.drain()

#receives from Audimus with tcp
async def tcp_rx(reader, SDR_rx):
    while True:
        msg = await reader.read(1024)
        if random.randint(0,10) >10 :
            print("dropped a packet")
            continue
        if msg == b"":  # connection closed
            break
        await SDR_rx.put(msg)



async def handle_client(reader, writer):
    # application layer queues
    AL_rx = asyncio.Queue()
    AL_tx = asyncio.Queue()

    #presentation layer queues
    PL_rx = asyncio.Queue()
    PL_tx = asyncio.Queue()

    #session layer queues + state change queue
    SL_rx = asyncio.Queue()
    SL_tx = asyncio.Queue()
    SL_SC = asyncio.Queue()

    #data link layer queues
    DLL_rx = asyncio.Queue()
    DLL_tx = asyncio.Queue()

    #SDR_queue
    SDR_rx = asyncio.Queue()
    SDR_tx = asyncio.Queue()

    #create instances of each layer, pass each layer its own queue and the queue of the level beneath it
    al = GroundStationApplicationLayer(AL_rx, AL_tx, PL_rx, PL_tx)
    pl = GroundStationPresentationLayer(PL_rx, PL_tx, SL_rx, SL_tx)
    sl = GroundStationSessionLayer(SL_rx, SL_tx, DLL_rx, DLL_tx, SL_SC)
    dll = GroundStationDataLinkLayer(DLL_rx, DLL_tx, SDR_rx, SDR_tx)

    #run tcp rx and tx coroutines
    sat_rx = asyncio.create_task(tcp_rx(reader, SDR_rx))
    sat_tx = asyncio.create_task(tcp_tx(writer, SDR_tx))



    #run application layer coroutines
    al_tx_handler = asyncio.create_task(al.tx())
    al_rx_handler = asyncio.create_task(al.rx())

    #run presentation layer coroutines
    pl_tx_handler = asyncio.create_task(pl.tx())
    pl_rx_handler = asyncio.create_task(pl.rx())

    # session layer coroutines started internally
    sl_handler = asyncio.create_task(sl.start())

    #run data link layer coroutines
    dll_tx_handler = asyncio.create_task(dll.tx())
    dll_rx_handler = asyncio.create_task(dll.rx())

    # run application rx and tx coroutines
    AL_rx = asyncio.create_task(app_rx(AL_rx))
    AL_tx = asyncio.create_task(app_tx(AL_tx, sl))

    # wait for responses

async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)
    await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
