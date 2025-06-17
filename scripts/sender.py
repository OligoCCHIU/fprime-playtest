#!/usr/bin/env python3
"""
fprime_sender.py

A standalone, command-line tool to send F' commands over a UART/serial interface.
This script uses the fprime-gds libraries to ensure commands are formatted and sent
according to the F' framework specification.
"""

import os
import sys
import logging
import argparse
import struct
import datetime
import threading
import time

# Add SatCat5 Python modules to path
satcat5_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                           'satcat5/src/python')
if os.path.exists(satcat5_path):
    print(f"Adding SatCat5 Python modules to path: {satcat5_path}")
    sys.path.append(satcat5_path)
else:
    print(f"Error: SatCat5 Python modules not found at {satcat5_path}")
    sys.exit(1)

# Import SatCat5 modules
try:
    from satcat5_eth import mac2str
    from satcat5_uart import AsyncSLIPPort
except ImportError as e:
    print(f"Error importing SatCat5 modules: {e}")
    sys.exit(1)

# Add virtual environment site-packages to Python path
venv_site_packages = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                 'fprime-venv/lib/python3.10/site-packages')
if os.path.exists(venv_site_packages):
    print(f"Adding virtual environment site-packages to Python path: {venv_site_packages}")
    sys.path.insert(0, venv_site_packages)
else:
    print(f"Error: Virtual environment site-packages directory not found at {venv_site_packages}")
    sys.exit(1)

try:
    from fprime_gds.common.pipeline.dictionaries import Dictionaries
    from fprime_gds.common.templates.cmd_template import CmdTemplate
    from fprime.common.models.serialize.enum_type import EnumType
    from fprime.common.models.serialize.time_type import TimeType
    from fprime.common.models.serialize.numerical_types import U32Type, F32Type, F64Type
except ImportError as e:
    print(f"Error importing F' modules: {e}")
    print("Please make sure you have activated the virtual environment and installed the required packages.")
    sys.exit(1)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
LOGGER = logging.getLogger("FPrimeSender")

# Ethernet Constants
MAC_BCAST = 6*b'\xFF'  # Broadcast MAC address
ETYPE_FPRIME = b'\x99\x9C'  # Custom EtherType for F' packets
ETYPE_BEAT = b'\x99\x9B'  # EtherType for heartbeat packets

class SerialAdapter:
    """A robust class to manage the serial port connection."""
    def __init__(self, port, baud_rate=921600):
        self.port = port
        self.baud_rate = baud_rate
        # Generate random locally administered MAC (AE:20:xx:xx:xx:xx)
        self.mac_addr = b'\xAE\x20' + os.urandom(4)
        # Create SLIP port
        self.slip_port = AsyncSLIPPort(port, LOGGER, baudrate=baud_rate)
        # Start heartbeat thread
        self._heartbeat_run = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name='Heartbeat')
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()

    def disconnect(self):
        """Disconnect from the serial port."""
        self._heartbeat_run = False
        if self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.0)
        if self.slip_port:
            self.slip_port.close()
            LOGGER.info(f"Disconnected from {self.port}")

    def _heartbeat_loop(self):
        """Send heartbeat packets at regular intervals."""
        while self._heartbeat_run:
            try:
                # Send heartbeat packet
                username = "FPrimeSender"
                payload = struct.pack('>H', len(username)) + username.encode()
                beat_msg = MAC_BCAST + self.mac_addr + ETYPE_BEAT + payload
                self.slip_port.msg_send(beat_msg)
                LOGGER.debug(f"Sent heartbeat: {mac2str(self.mac_addr)}")
            except Exception as e:
                LOGGER.warning(f"Heartbeat failed: {e}")
            time.sleep(1.0)  # Send heartbeat every second

    def send(self, data):
        """Send data over serial with SLIP encoding."""
        try:
            # Format F' command data with length prefix
            LOGGER.info(f"Sending data: {data}")
            cmd_len = struct.pack('>H', len(data))
            payload = cmd_len + data
            
            # Create frame with proper MAC addresses and EtherType
            frame = MAC_BCAST + self.mac_addr + ETYPE_FPRIME + payload
            
            # Send using SLIP port
            self.slip_port.msg_send(frame)
            return True
        except Exception as e:
            LOGGER.error(f"Failed to send data: {e}")
            self.disconnect()
            return False

def get_command_template(dictionaries, command_name):
    """Get the command template for a given command name."""
    # Split the command name into component and command parts
    parts = command_name.split('.')
    if len(parts) != 2:
        return None
    component, command = parts
    full_name = f"{component}.{command}"
    return dictionaries.command_name.get(full_name)

def get_command_help_string(template):
    """Get a help string for a command template."""
    if not template:
        return "Command not found."
    
    help_str = f"\n{template.get_full_name()} (Opcode: {hex(template.get_id())})\n"
    help_str += f"  Description: {template.get_description() or '--no description--'}\n"
    
    if not template.get_args():
        help_str += "  Takes 0 arguments."
        return help_str

    help_str += f"  Arguments ({len(template.get_args())}):\n"
    for arg_name, arg_desc, arg_type in template.get_args():
        type_name = arg_type.__name__ if hasattr(arg_type, '__name__') else str(arg_type)
        if isinstance(arg_type, type) and issubclass(arg_type, EnumType):
            enum_members = f"Members: {list(arg_type.keys())}"
            help_str += f"  {arg_name}: {arg_desc} ({type_name}) {enum_members}\n"
        else:
            help_str += f"  {arg_name}: {arg_desc} ({type_name})\n"
    
    return help_str

def format_command_data(template, args):
    """Format command data according to F' specification."""
    # Command descriptor (0x5A5A5A5A)
    descriptor = U32Type(0x5A5A5A5A).serialize()
    
    # Command opcode
    opcode = U32Type(template.get_id()).serialize()
    
    # Get template arguments
    template_args = template.get_args()
    if len(args) != len(template_args):
        raise ValueError(f"Argument count mismatch. Expected {len(template_args)}, got {len(args)}")
    
    # Just join all arguments with spaces and encode
    arg_str = " ".join(args)
    arg_data = arg_str.encode()
    
    return descriptor + opcode + arg_data

def main():
    """Main function to parse arguments and run the commander."""
    parser = argparse.ArgumentParser(description='Send F\' commands over serial')
    parser.add_argument('project_path', help='Path to the F\' project directory')
    parser.add_argument('deployment_folder', help='Name of the deployment folder')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=921600, help='Baud rate (default: 921600)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Set logging level based on debug flag
    if args.debug:
        LOGGER.setLevel(logging.DEBUG)
    
    # Initialize F' GDS components
    dictionaries = Dictionaries()
    
    # Load dictionaries
    dictionary_path = os.path.join(args.project_path, f"build-artifacts/Linux/{args.deployment_folder}/dict/{args.deployment_folder}TopologyAppDictionary.xml")
    if not os.path.exists(dictionary_path):
        LOGGER.error(f"Dictionary file not found at {dictionary_path}")
        sys.exit(1)
    
    try:
        dictionaries.load_dictionaries(dictionary_path, None)
        LOGGER.info("F' Command Dictionary loaded successfully.")
    except Exception as e:
        LOGGER.error(f"Failed to load dictionaries: {e}")
        sys.exit(1)

    # Initialize serial adapter
    adapter = SerialAdapter(args.port, args.baud)

    LOGGER.info("Ready. Type 'list' for commands, 'help <command_name>', or 'exit'.")

    try:
        # Main command loop
        while True:
            user_input = input("F' > ").strip()
            if not user_input:
                continue

            parts = user_input.split()
            command_name = parts[0]
            cmd_args = parts[1:]

            if command_name.lower() == "exit":
                break
            
            if command_name.lower() == "list":
                LOGGER.info("Available Commands:")
                for name in sorted(dictionaries.command_name.keys()):
                    print(f"  - {name}")
                continue

            if command_name.lower() == "help":
                if not cmd_args:
                    LOGGER.warning("Usage: help <command_name>")
                    continue
                template = get_command_template(dictionaries, cmd_args[0])
                print(get_command_help_string(template))
                continue

            # Prepare and send the command
            template = get_command_template(dictionaries, command_name)
            if not template:
                LOGGER.error(f"Command '{command_name}' not found.")
                continue

            if len(cmd_args) != len(template.get_args()):
                LOGGER.error(f"Argument count mismatch for '{command_name}'.")
                print(get_command_help_string(template))
                continue
            
            try:
                # Format command data
                binary_data = format_command_data(template, cmd_args)
                
                LOGGER.info(f"Sending: {command_name} with args {cmd_args}")
                if adapter.send(binary_data):
                    LOGGER.info(f"Sent {len(binary_data)} bytes successfully.")
                else:
                    LOGGER.error("Failed to send command.")
            except Exception as e:
                LOGGER.error(f"Error processing command: {e}")
                print(get_command_help_string(template))

    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        adapter.disconnect()
        LOGGER.info("Application terminated.")

if __name__ == "__main__":
    main()