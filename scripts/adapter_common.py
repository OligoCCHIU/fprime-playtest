#!/usr/bin/env python3
"""
common.py

Common module for F' serial and Ethernet communication adapters.
This module provides the base classes and utilities shared between
sender and receiver scripts.
"""

import os
import sys
import logging
import struct
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
    from satcat5_eth import mac2str, AsyncEthernetPort
    from satcat5_uart import AsyncSLIPPort
except ImportError as e:
    print(f"Error importing SatCat5 modules: {e}")
    sys.exit(1)

# Add F' virtual environment site-packages to Python path
venv_site_packages = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 'fprime-venv/lib/python3.10/site-packages')
if os.path.exists(venv_site_packages):
    print(f"Adding virtual environment site-packages to Python path: {venv_site_packages}")
    sys.path.insert(0, venv_site_packages)
else:
    print(f"Error: Virtual environment site-packages directory not found at {venv_site_packages}")
    sys.exit(1)

# Import F' modules
try:
    from fprime_gds.common.pipeline.dictionaries import Dictionaries
    from fprime.common.models.serialize.enum_type import EnumType
    from fprime.common.models.serialize.numerical_types import U32Type
except ImportError as e:
    print(f"Error importing F' modules: {e}")
    print("Please make sure you have activated the virtual environment and \
          installed the required packages.")
    sys.exit(1)

# BAUD RATE CONSTANT FOR ARTY A7-100T SATCAT5
BAUD_RATE = 921600
# See: https://github.com/the-aerospace-corporation/satcat5/blob/main/examples/arty_a7/README.md

# Ethernet Constants
MAC_BCAST = 6*b'\xFF'  # Broadcast MAC address
ETYPE_FPRIME = b'\x99\x9C'  # Custom EtherType for F' packets
ETYPE_BEAT = b'\x99\x9B'  # EtherType for heartbeat packets
SATCAT5_CONFIG = b'ZZZZ'  # SatCat5 configuration packet marker

class PortAdapter:
    """Base class for port adapters.
    
    This class provides the common interface for both serial and Ethernet
    communication adapters used in F' command sending and receiving.
    """
    
    def __init__(self, port, baud_rate=BAUD_RATE):
        """Port Adapter Constructor.

        Args:
            port (string): ScaPy interface name
                            i.e., /dev/ttyUSB0 (serial) or eth0 (ethernet)
            baud_rate (int, optional): baud rate of the serial port. Defaults to 921600.
        """
        self.port = port
        self.baud_rate = baud_rate
        
        # Generate random locally administered MAC (AE:20:xx:xx:xx:xx)
        self.mac_addr = b'\xAE\x20' + os.urandom(4)
        self._heartbeat_run = True
        self._heartbeat_thread = None
        self._callback = None
        self._rx_run = True
        self._rx_thread = None

    def set_callback(self, callback):
        """Set callback function for received data.
        
        Args:
            callback (function): Function to call when data is received
        """
        self._callback = callback

    def disconnect(self):
        """Disconnect from the port."""
        self._heartbeat_run = False
        self._rx_run = False
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.0)
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)

    def _heartbeat_loop(self):
        """Send heartbeat packets at regular intervals."""
        while self._heartbeat_run:
            try:
                # Send heartbeat packet
                username = "FPrimeAdapter"
                payload = struct.pack('>H', len(username)) + username.encode()
                beat_msg = MAC_BCAST + self.mac_addr + ETYPE_BEAT + payload
                self.msg_send(beat_msg)
                logging.debug("Sent heartbeat: %s", mac2str(self.mac_addr))
            except Exception as e:
                logging.warning("Heartbeat failed: %s", e)
            time.sleep(1.0)  # Send heartbeat every second

    def msg_send(self, data):
        """Send data over the port. To be implemented by subclasses.
        
        Args:
            data (bytes): Data to send over the port
            
        Returns:
            bool: True if successful, False otherwise
        """
        raise NotImplementedError

    def _rx_loop(self):
        """Main receive loop. To be implemented by subclasses."""
        raise NotImplementedError

class SerialAdapter(PortAdapter):
    """Adapter for serial port communication.
    
    This adapter handles SLIP-encoded serial communication for F' commands.
    """
    
    def __init__(self, port, baud_rate=BAUD_RATE):
        """Serial Adaptor Constructor, child class of PortAdapter.

        Args:
            port (string): ScaPy interface ID string for serial. i.e., /dev/ttyUSB0
            baud_rate (int, optional): baud rate to read data in serial port. Defaults to 921600.
        """
        super().__init__(port, baud_rate)
        # Create SLIP port
        self.slip_port = AsyncSLIPPort(port, logging.getLogger(), baudrate=baud_rate)
        self.slip_port.set_callback(self._handle_data)
        
        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name='Heartbeat')
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()
        
        # Start receive thread
        self._rx_thread = threading.Thread(target=self._rx_loop, name='SerialRx')
        self._rx_thread.daemon = True
        self._rx_thread.start()

    def disconnect(self):
        """Disconnect from the serial port."""
        super().disconnect()
        if self.slip_port:
            self.slip_port.close()
            logging.info("Disconnected from %s", self.port)

    def msg_send(self, data):
        """Send data over serial with SLIP encoding.

        Args:
            data (bytes): message to send over UART

        Returns:
            bool: successfully sent message over UART
        """
        try:
            self.slip_port.msg_send(data)
            return True
        except Exception as e:
            logging.error("Failed to send data: %s", e)
            self.disconnect()
            return False

    def _rx_loop(self):
        """Main loop for serial receive thread."""
        logging.info(f"Starting serial receive loop on {self.port}")
        while self._rx_run:
            time.sleep(0.1)  # Keep thread alive

    def _handle_data(self, data):
        """Handle received data from SLIP port.
        
        Args:
            data (bytes): Received data from SLIP port
        """
        if self._callback:
            self._callback(data)

class EthernetAdapter(PortAdapter):
    """Adapter for Ethernet port communication.
    
    This adapter handles Ethernet communication for F' commands.
    """
    
    def __init__(self, interface, baud_rate=BAUD_RATE):
        """EthernetAdapter Constructor, child of PortAdapter.

        Args:
            interface (string): ScaPy interface ID string for ethernet. i.e., eth0
            baud_rate (int, optional): baud rate to read data in eth port. Defaults to BAUD_RATE=921600.
        """
        super().__init__(interface, baud_rate)
        # Create Ethernet port
        self.eth_port = AsyncEthernetPort("FPrimeAdapter", interface, logging.getLogger())
        self.eth_port.set_callback(self._handle_data)
        
        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name='Heartbeat')
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()
        
        # Start receive thread
        self._rx_thread = threading.Thread(target=self._rx_loop, name='EthRx')
        self._rx_thread.daemon = True
        self._rx_thread.start()

    def disconnect(self):
        """Disconnect from the Ethernet port."""
        super().disconnect()
        if self.eth_port:
            self.eth_port.close()
            logging.info("Disconnected from %s", self.port)

    def msg_send(self, data):
        """Send data over ethernet.

        Args:
            data (bytes): message to send over ethernet

        Returns:
            bool: successfully sent message over ethernet
        """
        try:
            self.eth_port.msg_send(data)
            return True
        except Exception as e:
            logging.error("Failed to send data: %s", e)
            self.disconnect()
            return False

    def _rx_loop(self):
        """Main loop for Ethernet receive thread."""
        logging.info(f"Starting Ethernet receive loop on {self.port}")
        while self._rx_run:
            time.sleep(0.1)  # Keep thread alive

    def _handle_data(self, data):
        """Handle received data from Ethernet port.
        
        Args:
            data (bytes): Received data from Ethernet port
        """
        if self._callback:
            self._callback(data)

def create_adapter(port_type, port, baud_rate=BAUD_RATE):
    """Create the appropriate adapter based on port type.

    Args:
        port_type (string): describes method of communication, either serial or ethernet.
        port (string): ScaPy interface name, i.e., /dev/ttyUSB0 (serial) or eth0 (ethernet)
        baud_rate (int, optional): baud rate to send data over serial. Defaults to BAUD_RATE.

    Raises:
        ValueError: only supported interface types are ethernet or serial

    Returns:
        PortAdapter: PortAdapter child class
    """
    if port_type.lower() == 'serial':
        return SerialAdapter(port, baud_rate)
    elif port_type.lower() == 'ethernet':
        return EthernetAdapter(port, baud_rate)
    else:
        raise ValueError(f"Unsupported port type: {port_type}")

def setup_logging(debug=False):
    """Setup logging configuration.
    
    Args:
        debug (bool, optional): Enable debug logging. Defaults to False.
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")

def load_dictionaries(dictionary_path):
    """Load F' command dictionaries from XML file.
    
    Args:
        dictionary_path (string): Path to the F' dictionary XML file
        
    Returns:
        Dictionaries: Loaded F' dictionaries object
        
    Raises:
        FileNotFoundError: If dictionary file doesn't exist
        Exception: If dictionary loading fails
    """
    if not os.path.exists(dictionary_path):
        raise FileNotFoundError(f"Dictionary file not found at {dictionary_path}")
    
    dictionaries = Dictionaries()
    dictionaries.load_dictionaries(dictionary_path, None)
    logging.info("F' Command Dictionary loaded successfully.")
    return dictionaries

def get_command_template(dictionaries, command_name):
    """Get the command template for a given command name.

    Args:
        dictionaries (Dictionaries): dictionary type defined by F' Dictionaries
        command_name (string): F' command to run, consists of <component>.<mnemonic>

    Returns:
        CmdTemplate: Command template object or None if not found
    """
    # Split the command name into component and mnemonic parts
    parts = command_name.split('.')
    if len(parts) != 2:
        return None
    component, mnemonic = parts
    full_name = f"{component}.{mnemonic}"
    return dictionaries.command_name.get(full_name)

def get_command_help_string(template):
    """Get a help string for a command template.

    Args:
        template (CmdTemplate): F' command to receive more information about

    Returns:
        str: F' command information, i.e. <component>.<mnemonic> <arg1> <arg2> ... <argn>
    """
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
    """Format command data according to F' specification.

    Args:
        template (CmdTemplate): F' command in <component>.<mnemonic> form
        args (list): arguments for the corresponding F' command, if any

    Raises:
        ValueError: args mismatch

    Returns:
        bytes: formatted command in binary form
    """
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