#!/usr/bin/env python3
"""
fprime_receiver.py

A script that receives F' command frames from eth0, unpacks them, and converts them
to F' CLI commands. This allows commands sent over SatCat5 to be executed locally
using the F' CLI.
"""

import os
import sys
import logging
import argparse
import struct
import subprocess
import threading
import time
from scapy.all import sniff, Ether, Raw

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
    from fprime_gds.common.data_types.cmd_data import CmdData
    from fprime.common.models.serialize.time_type import TimeType
    from fprime.common.models.serialize.numerical_types import U32Type
    from fprime_gds.common.utils.config_manager import ConfigManager
except ImportError as e:
    print(f"Error importing F' modules: {e}")
    print("Please make sure you have activated the virtual environment and installed the required packages.")
    sys.exit(1)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
LOGGER = logging.getLogger("FPrimeReceiver")

# Ethernet Constants
ETYPE_FPRIME = 0x999C  # Custom EtherType for F' packets
SATCAT5_CONFIG = b'ZZZZ'  # SatCat5 configuration packet marker

class FPrimeReceiver:
    """Class to handle receiving and processing F' command frames."""
    
    def __init__(self, interface, dictionary_path):
        self.interface = interface
        self.dictionary_path = dictionary_path
        self.dictionaries = Dictionaries()
        self.config = ConfigManager()
        
        # Load dictionaries
        try:
            self.dictionaries.load_dictionaries(dictionary_path, None)
            LOGGER.info("F' Command Dictionary loaded successfully.")
        except Exception as e:
            LOGGER.error(f"Failed to load dictionaries: {e}")
            sys.exit(1)

    def _unpack_command(self, payload):
        """Unpack the F' command from the payload."""
        try:
            # Check for SatCat5 configuration packet
            if payload.startswith(SATCAT5_CONFIG):
                LOGGER.debug("Ignoring SatCat5 configuration packet")
                return None, None

            # First 2 bytes are length
            length = struct.unpack('>H', payload[:2])[0]
            if length + 2 > len(payload):
                LOGGER.error("Invalid payload length")
                return None, None

            # Extract command data
            cmd_data = payload[2:2+length]
            
            # Parse command data
            ptr = 0
            
            # Skip descriptor (4 bytes)
            ptr += 4
            
            # Get opcode
            opcode_obj = U32Type()
            opcode_obj.deserialize(cmd_data, ptr)
            ptr += opcode_obj.getSize()
            opcode = opcode_obj.val
            
            # Get command template from opcode
            if opcode not in self.dictionaries.command_id:
                LOGGER.error(f"Unknown command opcode: {hex(opcode)}")
                return None, None
                
            template = self.dictionaries.command_id[opcode]
            
            # Get remaining data as arguments string
            args_str = cmd_data[ptr:].decode()
            args = args_str.split()
            
            # Format command as component.mnemonic
            command_name = f"{template.get_component()}.{template.get_mnemonic()}"
            LOGGER.info(f"Decoded command: {command_name} (opcode: {hex(opcode)})")
            
            return command_name, args
            
        except Exception as e:
            LOGGER.error(f"Error unpacking command: {e}")
            LOGGER.debug(f"Payload hex: {payload.hex()}")
            return None, None

    def _execute_fprime_cli(self, command_name, arguments=None):
        """Execute the command using fprime-cli."""
        try:
            cmd = ['fprime-cli', 'command-send', command_name]
            if arguments:
                cmd.extend(['--arguments'] + [str(arg) for arg in arguments])
            cmd.extend(['--dictionary', self.dictionary_path])
            
            LOGGER.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                LOGGER.info(f"Command executed successfully: {result.stdout}")
            else:
                LOGGER.error(f"Command failed: {result.stderr}")
        except Exception as e:
            LOGGER.error(f"Error executing command: {e}")

    def _process_packet(self, packet):
        """Process a received packet."""
        if not packet.haslayer(Ether):
            return

        # Check for F' EtherType
        if packet.type != ETYPE_FPRIME:
            return

        # Extract payload
        payload = bytes(packet[Raw].load)
        
        # Log packet details for debugging
        LOGGER.debug(f"Received packet from {packet[Ether].src} to {packet[Ether].dst}")
        LOGGER.debug(f"Payload hex: {payload.hex()}")
        
        # Unpack command
        command_name, arguments = self._unpack_command(payload)
        if command_name:
            LOGGER.info(f"Received command: {command_name}")
            if arguments:
                LOGGER.info(f"Arguments: {arguments}")
            self._execute_fprime_cli(command_name, arguments)

    def start(self):
        """Start listening for packets."""
        LOGGER.info(f"Starting to listen on {self.interface} for F' commands...")
        try:
            # Use scapy's sniff function to capture packets
            sniff(iface=self.interface, 
                  prn=self._process_packet,
                  filter=f"ether proto {ETYPE_FPRIME}",
                  store=0)
        except KeyboardInterrupt:
            LOGGER.info("Stopping packet capture...")
        except Exception as e:
            LOGGER.error(f"Error capturing packets: {e}")

def main():
    """Main function to parse arguments and run the receiver."""
    parser = argparse.ArgumentParser(description='Receive and process F\' commands from eth0')
    parser.add_argument('--interface', default='eth0', help='Network interface to listen on (default: eth0)')
    parser.add_argument('--dictionary', required=True, help='Path to the F\' dictionary XML file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    if args.debug:
        LOGGER.setLevel(logging.DEBUG)

    # Activate virtual environment
    venv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fprime-venv')
    activate_script = os.path.join(venv_path, 'bin', 'activate')
    
    if not os.path.exists(activate_script):
        LOGGER.error(f"Virtual environment not found at {venv_path}")
        sys.exit(1)
    
    # Set environment variables
    os.environ['VIRTUAL_ENV'] = venv_path
    os.environ['PATH'] = os.path.join(venv_path, 'bin') + os.pathsep + os.environ.get('PATH', '')
    os.environ['PYTHONPATH'] = os.path.join(venv_path, 'lib/python3.10/site-packages') + os.pathsep + os.environ.get('PYTHONPATH', '')
    
    LOGGER.info(f"Activated virtual environment at {venv_path}")

    receiver = FPrimeReceiver(args.interface, args.dictionary)
    receiver.start()

if __name__ == "__main__":
    main()