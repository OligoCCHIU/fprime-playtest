#!/usr/bin/env python3
"""
fprime_receiver.py

A script that receives F' command frames from either serial or Ethernet interfaces,
unpacks them, and converts them to F' CLI commands. This allows commands sent over
SatCat5 to be executed locally using the F' CLI.
"""

import os
import sys
import logging
import argparse
import struct
import subprocess
import time

# Import common functionality
from adapter_common import (
    create_adapter, setup_logging, load_dictionaries, SATCAT5_CONFIG, U32Type, BAUD_RATE
)

# Configure basic logging
LOGGER = logging.getLogger("FPrimeReceiver")

class FPrimeReceiver:
    """Class to handle receiving and processing F' command frames."""
    
    def __init__(self, port_type, port, dictionary_path, baud_rate=BAUD_RATE):
        """Initialize FPrimeReceiver.
        
        Args:
            port_type (string): Type of port (serial or ethernet)
            port (string): Port name (e.g., /dev/ttyUSB0 or eth0)
            dictionary_path (string): Path to F' dictionary XML file
            baud_rate (int, optional): Baud rate for serial. Defaults to 921600.
        """
        self.port_type = port_type
        self.port = port
        self.dictionary_path = dictionary_path
        
        # Load dictionaries
        try:
            self.dictionaries = load_dictionaries(dictionary_path)
        except Exception as e:
            LOGGER.error("Failed to load dictionaries: %s", e)
            sys.exit(1)

        # Create port adapter
        try:
            self.adapter = create_adapter(port_type, port, baud_rate)
            self.adapter.set_callback(self._process_data)
        except Exception as e:
            LOGGER.error("Failed to initialize port: %s", e)
            sys.exit(1)

    def _unpack_command(self, payload):
        """Unpack the F' command from the payload.
        
        Args:
            payload (bytes): Raw payload data
            
        Returns:
            tuple: (command_name, arguments) or (None, None) if failed
        """
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
                LOGGER.error("Unknown command opcode: %s", hex(opcode))
                return None, None
                
            template = self.dictionaries.command_id[opcode]
            
            # Get remaining data as arguments string
            args_str = cmd_data[ptr:].decode()
            args = args_str.split()
            
            # Format command as component.mnemonic
            command_name = f"{template.get_component()}.{template.get_mnemonic()}"
            LOGGER.info("Decoded command: %s (opcode: %s)", command_name, hex(opcode))
            
            return command_name, args
            
        except Exception as e:
            LOGGER.error("Error unpacking command: %s", e)
            LOGGER.debug("Payload hex: %s", payload.hex())
            return None, None

    def _execute_fprime_cli(self, command_name, arguments=None):
        """Execute the command using fprime-cli.
        
        Args:
            command_name (string): F' command name (component.mnemonic)
            arguments (list, optional): Command arguments. Defaults to None.
        """
        try:
            cmd = ['fprime-cli', 'command-send', command_name]
            if arguments:
                cmd.extend(['--arguments'] + [str(arg) for arg in arguments])
            cmd.extend(['--dictionary', self.dictionary_path])
            
            LOGGER.info("Executing: %s", ' '.join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                LOGGER.info("Command executed successfully: %s", result.stdout)
            else:
                LOGGER.error("Command failed: %s", result.stderr)
        except Exception as e:
            LOGGER.error("Error executing command: %s", e)

    def _process_data(self, data):
        """Process received data.
        
        Args:
            data (bytes): Received data from port
        """
        # Log packet details for debugging
        LOGGER.debug("Received data: %s", data.hex())
        
        # Unpack command
        command_name, arguments = self._unpack_command(data)
        if command_name:
            LOGGER.info("Received command: %s", command_name)
            if arguments:
                LOGGER.info("Arguments: %s", arguments)
            self._execute_fprime_cli(command_name, arguments)

    def start(self):
        """Start listening for data."""
        LOGGER.info("Starting to listen on %s (%s) for F' commands...", self.port, self.port_type)
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            LOGGER.info("Stopping...")
        finally:
            self.adapter.disconnect()

def main():
    """Main function to parse arguments and run the receiver."""
    parser = argparse.ArgumentParser(description='Receive and process F\' commands from serial or Ethernet')
    parser.add_argument('deployment_folder', help='Name of the deployment folder')
    parser.add_argument('--port-type', choices=['serial', 'ethernet'], default='ethernet',
                      help='Type of port to use (default: ethernet)')
    parser.add_argument('--port', default='eth0',
                      help='Port name (default: eth0 for Ethernet, /dev/ttyUSB0 for serial)')
    parser.add_argument('--baud', type=int, default=BAUD_RATE,
                      help='Baud rate for serial port (default: 921600)')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.debug)

    # Activate virtual environment
    venv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fprime-venv')
    activate_script = os.path.join(venv_path, 'bin', 'activate')
    
    if not os.path.exists(activate_script):
        LOGGER.error("Virtual environment not found at %s", venv_path)
        sys.exit(1)
    
    # Set environment variables
    os.environ['VIRTUAL_ENV'] = venv_path
    os.environ['PATH'] = os.path.join(venv_path, 'bin') + os.pathsep + os.environ.get('PATH', '')
    os.environ['PYTHONPATH'] = os.path.join(venv_path, 'lib/python3.10/site-packages') + os.pathsep + os.environ.get('PYTHONPATH', '')
    
    LOGGER.info("Activated virtual environment at %s", venv_path)
    
    dictionary_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f"build-artifacts/Linux/{args.deployment_folder}/dict/{args.deployment_folder}TopologyAppDictionary.xml")

    receiver = FPrimeReceiver(args.port_type, args.port, dictionary_path, args.baud)
    receiver.start()

if __name__ == "__main__":
    main()