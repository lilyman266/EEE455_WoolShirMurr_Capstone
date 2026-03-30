
import asyncio
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from CommunicationsModule.CommunicationsProtocol.ApplicationLayer.ApplicationLayer import AudimusApplicationLayer
from CommunicationsModule.CommunicationsProtocol.PresentationLayer.PresentationLayer import AudimusPresentationLayer
from CommunicationsModule.CommunicationsProtocol.DataLinkLayer.DataLinkLayer import AudimusDataLinkLayer
from CommunicationsModule.CommunicationsProtocol.SessionLayer.SessionLayer import AudimusSessionLayer



async def run_client(host, port):
    reader, writer = await asyncio.open_connection(host, port)


    # presentation layer queues
    PL_rx = asyncio.Queue()
    PL_tx = asyncio.Queue()

    # session layer queues
    SL_rx = asyncio.Queue()
    SL_tx = asyncio.Queue()

    #session state change queue
    session_queue = asyncio.Queue()

    # raido mode state change queue
    radio_mode_queue = asyncio.Queue()

    #audimus presentation layer to AROS session queue
    aros_sim_queue = asyncio.Queue()

    # data link layer queues
    DLL_rx = asyncio.Queue()
    DLL_tx = asyncio.Queue()

    # SDR_queue
    SDR_rx = asyncio.Queue()
    SDR_tx = asyncio.Queue()

    # create instances of each layer
    al = AudimusApplicationLayer(PL_rx, PL_tx, aros_sim_queue)
    pl = AudimusPresentationLayer(PL_rx, PL_tx, SL_rx, SL_tx)
    dll = AudimusDataLinkLayer(DLL_rx, DLL_tx, reader, writer)
    sl = AudimusSessionLayer(SL_rx, SL_tx, DLL_rx, DLL_tx, dll, session_queue, aros_sim_queue)


    # run application layer coroutines
    sim_handler = asyncio.create_task(al.AROS_sim())
    state_handler = asyncio.create_task(al.state_watcher())



    # run presentation layer coroutines
    pl_tx_handler = asyncio.create_task(pl.tx())
    pl_rx_handler = asyncio.create_task(pl.rx())

    # session layer coroutines started internally
    sl_handler = asyncio.create_task(sl.start())


    #run data link layer coroutines
    dll_handler = asyncio.create_task(dll.tx_tcp())
    dll_handler = asyncio.create_task(dll.rx_tcp())



    task_handlers = [
        sim_handler,
        state_handler,
        pl_tx_handler,
        pl_rx_handler,
        sl_handler,
        dll_handler,
    ]

    await asyncio.gather(*task_handlers)


async def main():
    await run_client("127.0.0.1", 8888)


if __name__ == "__main__":
    asyncio.run(main())
