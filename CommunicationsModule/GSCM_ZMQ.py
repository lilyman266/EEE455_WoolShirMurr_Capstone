import asyncio
import random
import CommunicationsModule.Audimus_pb2 as Audimus_pb2
from CommunicationsModule.CommunicationsProtocol.ApplicationLayer.ApplicationLayer import GroundStationApplicationLayer
from CommunicationsModule.CommunicationsProtocol.PresentationLayer.PresentationLayer import GroundStationPresentationLayer
from CommunicationsModule.CommunicationsProtocol.DataLinkLayer.DataLinkLayer import GroundStationDataLinkLayer
from CommunicationsModule.CommunicationsProtocol.SessionLayer.SessionLayer import GroundStationSessionLayer



async def handle_client(reader=1, writer=2):

    # presentation layer queues
    PL_rx = asyncio.Queue()
    PL_tx = asyncio.Queue()

    # session layer queues + state change queue
    SL_rx = asyncio.Queue()
    SL_tx = asyncio.Queue()
    SL_SC = asyncio.Queue()

    # data link layer queues
    DLL_rx = asyncio.Queue()
    DLL_tx = asyncio.Queue()

    # SDR_queue
    SDR_rx = asyncio.Queue()
    SDR_tx = asyncio.Queue()

    # create instances of each layer, pass each layer its own queue and the queue of the level beneath it
    dll = GroundStationDataLinkLayer(DLL_rx, DLL_tx, SDR_rx, SDR_tx, reader, writer)
    sl = GroundStationSessionLayer(SL_rx, SL_tx, DLL_rx, DLL_tx, SL_SC)
    pl = GroundStationPresentationLayer(PL_rx, PL_tx, SL_rx, SL_tx)
    al = GroundStationApplicationLayer(PL_rx, PL_tx, sl)

    # run application layer coroutines
    al_tx_handler = asyncio.create_task(al.tx_command_line())
    al_rx_handler = asyncio.create_task(al.rx())

    # run presentation layer coroutines
    pl_tx_handler = asyncio.create_task(pl.tx())
    pl_rx_handler = asyncio.create_task(pl.rx())

    # session layer coroutines started internally
    sl_handler = asyncio.create_task(sl.start())

    # run data link layer coroutines
    dll_tx_handler = asyncio.create_task(dll.tx_zmq())
    dll_rx_handler = asyncio.create_task(dll.rx_zmq())

    task_handlers = [
        al_tx_handler,
        al_rx_handler,
        pl_tx_handler,
        pl_rx_handler,
        sl_handler,
        dll_tx_handler,
        dll_rx_handler,
    ]

    await asyncio.gather(*task_handlers)


async def main():
    await handle_client()


if __name__ == "__main__":
    asyncio.run(main())