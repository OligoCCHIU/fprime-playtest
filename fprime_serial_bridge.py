#!/usr/bin/env python3

import serial
import struct
import time
import threading
import socket
import json
import sys
import os

# Protocol constants
PROTOCOL_TEXT = 0x999c
PROTOCOL_HEARTBEAT = 0x999b
PROTOCOL_DATA = 0x999d

class FPrimeSerialBridge:
    def __init__(self, serial_port="/dev/ttyUSB0", baud_rate=115200):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.serial = None
        self.running = False
        self.heartbeat_thread = None

    def connect_serial(self):
        """Connect to the serial port"""
        try:
            self.serial = serial.Serial(
                port=self.serial_port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            print(f"Connected to {self.serial_port}")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to {self.serial_port}: {e}")
            return False

    def send_packet(self, protocol_type, data):
        """Send a packet with the specified protocol type and data"""
        if not self.serial:
            print("Serial port not connected")
            return False

        try:
            # Calculate packet length (protocol type + data length)
            packet_len = len(data) + 4  # 4 bytes for protocol type
            
            # Create packet header
            header = struct.pack(">HH", packet_len, protocol_type)
            
            # Send the packet
            self.serial.write(header)
            self.serial.write(data)
            self.serial.flush()
            return True
        except Exception as e:
            print(f"Error sending packet: {e}")
            return False

    def send_command(self, command):
        """Send a command through the serial port"""
        # Convert command to bytes if it's a string
        if isinstance(command, str):
            command = command.encode('utf-8')
        
        return self.send_packet(PROTOCOL_TEXT, command)

    def send_heartbeat(self):
        """Send a heartbeat packet"""
        return self.send_packet(PROTOCOL_HEARTBEAT, b'')

    def heartbeat_loop(self):
        """Continuously send heartbeat packets"""
        while self.running:
            self.send_heartbeat()
            time.sleep(1)

    def start(self):
        """Start the bridge"""
        if not self.connect_serial():
            return False

        self.running = True
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

        print("F' Serial Bridge started")
        return True

    def stop(self):
        """Stop the bridge"""
        self.running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join()
        if self.serial:
            self.serial.close()
        print("F' Serial Bridge stopped")

def main():
    # Create and start the bridge
    bridge = FPrimeSerialBridge()
    if not bridge.start():
        sys.exit(1)

    try:
        # Main loop to read commands from stdin
        while True:
            command = input("Enter command (or 'quit' to exit): ")
            if command.lower() == 'quit':
                break
            
            # Send the command
            if bridge.send_command(command):
                print(f"Command sent: {command}")
            else:
                print("Failed to send command")

    except KeyboardInterrupt:
        print("\nStopping bridge...")
    finally:
        bridge.stop()

if __name__ == "__main__":
    main() 