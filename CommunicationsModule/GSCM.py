import asyncio
import random
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from CommunicationsModule.CommunicationsProtocol.ApplicationLayer.ApplicationLayer import GroundStationApplicationLayer
from CommunicationsModule.CommunicationsProtocol.PresentationLayer.PresentationLayer import GroundStationPresentationLayer
from CommunicationsModule.CommunicationsProtocol.DataLinkLayer.DataLinkLayer import GroundStationDataLinkLayer
from CommunicationsModule.CommunicationsProtocol.SessionLayer.SessionLayer import GroundStationSessionLayer


async def handle_client(reader, writer):


    #presentation layer queues
    PL_rx = asyncio.Queue()
    PL_tx = asyncio.Queue()

    #session layer queues + state change queue and radio mode change queue
    SL_rx = asyncio.Queue()
    SL_tx = asyncio.Queue()
    session_queue = asyncio.Queue()
    radio_mode_queue = asyncio.Queue()

    #data link layer queues
    DLL_rx = asyncio.Queue()
    DLL_tx = asyncio.Queue()

    #create instances of each layer, pass each layer its own queue and the queue of the level beneath it
    al = GroundStationApplicationLayer(PL_rx, PL_tx, session_queue)
    pl = GroundStationPresentationLayer(PL_rx, PL_tx, SL_rx, SL_tx)
    sl = GroundStationSessionLayer(SL_rx, SL_tx, DLL_rx, DLL_tx, session_queue, radio_mode_queue)
    dll = GroundStationDataLinkLayer(DLL_rx, DLL_tx, reader, writer, radio_mode_queue)

    #run application layer coroutines
    al_tx_handler = asyncio.create_task(al.tx())
    al_rx_handler = asyncio.create_task(al.rx())

    #run presentation layer coroutines
    pl_tx_handler = asyncio.create_task(pl.tx())
    pl_rx_handler = asyncio.create_task(pl.rx())

    # session layer coroutines started internally
    sl_handler = asyncio.create_task(sl.start())

    #run data link layer coroutines
    dll_handler = asyncio.create_task(dll.start())



    task_handlers = [
        al_tx_handler,
        al_rx_handler,
        pl_tx_handler,
        pl_rx_handler,
        sl_handler,
        dll_handler
    ]

    await asyncio.gather(*task_handlers)


async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 8888)
    await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
