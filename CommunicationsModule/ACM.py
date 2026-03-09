import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from CommunicationsModule.CommunicationsProtocol.ApplicationLayer.ApplicationLayer import AudimusApplicationLayer
from CommunicationsModule.CommunicationsProtocol.PresentationLayer.PresentationLayer import AudimusPresentationLayer
from CommunicationsModule.CommunicationsProtocol.DataLinkLayer.DataLinkLayer import AudimusDataLinkLayer
from CommunicationsModule.CommunicationsProtocol.SessionLayer.SessionLayer import AudimusSessionLayer


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")

async def app_rx(AL_rx):
    while True:
        message = await AL_rx.get()

async def app_tx(AL_tx):
    for line in read_lines("CommunicationsModule/TestTXAudimus"):
        await AL_tx.put(line)
        await asyncio.sleep(1)


async def tcp_tx(writer, SDR_tx):
    while True:
        msg = await SDR_tx.get()      # wait for outgoing message
        writer.write(msg)               # send it
        await writer.drain()            # flush


async def tcp_rx(reader, SDR_rx):
    while True:
        msg = await reader.read(1024)   # wait for incoming data
        if not msg:
            break                       # server closed connection
        await SDR_rx.put(msg)         # push into RX queue


async def run_client(host, port):
    reader, writer = await asyncio.open_connection(host, port)

    #Application layer queues
    AL_rx = asyncio.Queue()
    AL_tx = asyncio.Queue()

    # presentation layer queues
    PL_rx = asyncio.Queue()
    PL_tx = asyncio.Queue()

    # session layer queues
    SL_rx = asyncio.Queue()
    SL_tx = asyncio.Queue()

    #session state change queue
    SL_sc = asyncio.Queue()

    # data link layer queues
    DLL_rx = asyncio.Queue()
    DLL_tx = asyncio.Queue()

    # SDR_queue
    SDR_rx = asyncio.Queue()
    SDR_tx = asyncio.Queue()

    # create instances of each layer
    al = AudimusApplicationLayer(AL_rx, AL_tx,PL_rx,PL_tx)
    pl = AudimusPresentationLayer(PL_rx, PL_tx, SL_rx, SL_tx)
    sl = AudimusSessionLayer(SL_rx, SL_tx, DLL_rx, DLL_tx, SL_sc)
    dll = AudimusDataLinkLayer(DLL_rx, DLL_tx, SDR_rx, SDR_tx)

    # run application rx and tx coroutines
    AL_rx_handler = asyncio.create_task(app_rx(AL_rx))
    AL_tx_handler = asyncio.create_task(app_tx(AL_tx))

    # run application layer coroutines
    al_tx_handler = asyncio.create_task(al.tx())
    al_rx_handler = asyncio.create_task(al.rx())

    #run satellite rx and tx coroutines
    rx = asyncio.create_task(tcp_rx(reader, SDR_rx))
    tx = asyncio.create_task(tcp_tx(writer, SDR_tx))

    # run presentation layer coroutines
    pl_tx_handler = asyncio.create_task(pl.tx())
    pl_rx_handler = asyncio.create_task(pl.rx())

    # session layer coroutines started internally
    # session layer coroutines started internally
    sl_handler = asyncio.create_task(sl.start())

    # run data link layer coroutines
    dll_tx_handler = asyncio.create_task(dll.tx())
    dll_rx_handler = asyncio.create_task(dll.rx())


    await asyncio.gather(tx, rx)


async def main():
    await run_client("127.0.0.1", 8888)


if __name__ == "__main__":
    asyncio.run(main())
