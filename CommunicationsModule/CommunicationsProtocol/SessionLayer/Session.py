from enum import Enum
import csv
from collections import deque
import os
import struct
import asyncio


class Session:
    def __init__(self, layer):
        self.layer = layer


    async def handle_rx(self, packet):
        """Process incoming packet from layer RX loop"""
        return packet

    async def handle_tx(self, message):
        """Process outgoing message before sending"""
        return message

    async def on_enter(self):
        """Called when session becomes active"""
        pass

    async def on_exit(self):
        """Called when session is replaced"""
        pass

    def write_packet_number(self, packet_number):
        """writes current packet number over different sessions"""
        with open(self.packet_number_path, "w", encoding="utf-8") as f: f.write(str(packet_number))

    def read_packet_number(self):
        """reads current packet number over different sessions"""
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


