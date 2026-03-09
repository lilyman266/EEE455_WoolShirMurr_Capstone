from Logger.Logger import LoggerFactory
from abc import ABC, abstractmethod


class ProtocolLayer:
    def __init__(self, layer_rx, layer_tx, below_rx, below_tx):
        # this layer's tx and rx queues
        self.layer_rx = layer_rx
        self.layer_tx = layer_tx

        # the tx and rx queues of the layer below
        self.below_rx = below_rx
        self.below_tx = below_tx

    async def rx(self):
        while True:

            # grab message from the below layers rx queue
            message = await self.below_rx.get()

            # do the thing to the message
            message = self.process_rx(message)

            # put message into rx queue of this layer
            await self.layer_rx.put(message)


    async def tx(self):
        while True:
            # grab the message from this layer's tx queue
            message = await self.layer_tx.get()

            # do the thing to the message
            message = self.process_tx(message)

            # put message into the tx queue of the layer below
            await self.below_tx.put(message)

    @abstractmethod
    def process_rx(self, message):
        pass

    @abstractmethod
    def process_tx(self, message):
        pass

    @abstractmethod
    def log(self, message):
        pass
