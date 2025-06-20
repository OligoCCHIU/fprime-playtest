#!/usr/bin/env python3
"""
telemetry.py

A telemetry script that handles both spacecraft downlink and ground station reception.
This script can operate in two modes:
1. Spacecraft mode: Pulls channel data and sends it through SatCat5 communication
2. Ground station mode: Receives telemetry data and updates the ground station

The script uses the F' GDS infrastructure for telemetry processing and the common
adapter module for communication.
"""

import os
import sys
import logging
import argparse
import struct
import time
import json
from typing import List, Dict, Any, Optional

# Import common functionality
from common import (
    create_adapter, setup_logging, load_dictionaries, BAUD_RATE,
    ETYPE_FPRIME, SATCAT5_CONFIG
)

# Import F' modules for telemetry processing
try:
    from fprime_gds.common.data_types.ch_data import ChData
    from fprime_gds.common.decoders.ch_decoder import ChDecoder
    from fprime_gds.common.models.common.channel_telemetry import Channel
    from fprime.common.models.serialize.time_type import TimeType
    from fprime.common.models.serialize.numerical_types import U32Type
    from fprime_gds.common.utils.config_manager import ConfigManager
except ImportError as e:
    print("Error importing F' telemetry modules: %s", e)
    print("Please make sure you have activated the virtual environment and installed the required packages.")
    sys.exit(1)

# Configure basic logging
LOGGER = logging.getLogger("FPrimeTelemetry")

# Telemetry EtherType for SatCat5
ETYPE_TELEMETRY = b'\x99\x9D'  # Custom EtherType for telemetry packets

class TelemetryPacket:
    """Class to handle telemetry packet formatting and parsing."""
    
    def __init__(self):
        """Initialize TelemetryPacket."""
        self.config = ConfigManager()
    
    def format_telemetry_packet(self, channel_data: List[ChData]) -> bytes:
        """Format telemetry data into a packet for transmission.
            Args:
                channel_data (List[ChData]): List of channel data objects
                
            Returns:
                bytes: Formatted telemetry packet
        """
        # Packet format:
        # - Length (2 bytes)
        # - Packet type (1 byte) - 0x01 for telemetry
        # - Timestamp (8 bytes) - Unix timestamp
        # - Channel count (2 bytes)
        # - For each channel:
        #   - Channel ID (4 bytes)
        #   - Channel value length (2 bytes)
        #   - Channel value (variable)
        
        packet_type = 0x01  # Telemetry packet
        timestamp = int(time.time())
        channel_count = len(channel_data)
        
        # Start building packet
        packet = struct.pack('>H', 0)  # Placeholder for length
        packet += struct.pack('>B', packet_type)
        packet += struct.pack('>Q', timestamp)
        packet += struct.pack('>H', channel_count)
        
        # Add each channel
        for ch_data in channel_data:
            channel_id = ch_data.id
            value_obj = ch_data.get_val_obj()
            
            if value_obj is None:
                # Skip channels with no value
                continue
                
            # Serialize the value
            value_bytes = value_obj.serialize()
            value_length = len(value_bytes)
            
            packet += struct.pack('>I', channel_id)
            packet += struct.pack('>H', value_length)
            packet += value_bytes
        
        # Update length field
        packet_length = len(packet) - 2  # Exclude the length field itself
        packet = struct.pack('>H', packet_length) + packet[2:]
        
        return packet
    
    def parse_telemetry_packet(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse a telemetry packet received from the spacecraft.
        
        Args:
            data (bytes): Raw telemetry packet data
            
        Returns:
            Dict[str, Any]: Parsed telemetry data or None if parsing fails
        """
        try:
            if len(data) < 13:  # Minimum packet size
                return None
                
            ptr = 0
            
            # Parse header
            length = struct.unpack('>H', data[ptr:ptr+2])[0]
            ptr += 2
            
            packet_type = struct.unpack('>B', data[ptr:ptr+1])[0]
            ptr += 1
            
            if packet_type != 0x01:  # Not a telemetry packet
                return None
                
            timestamp = struct.unpack('>Q', data[ptr:ptr+8])[0]
            ptr += 8
            
            channel_count = struct.unpack('>H', data[ptr:ptr+2])[0]
            ptr += 2
            
            channels = []
            
            # Parse each channel
            for _ in range(channel_count):
                if ptr + 6 > len(data):
                    break
                    
                channel_id = struct.unpack('>I', data[ptr:ptr+4])[0]
                ptr += 4
                
                value_length = struct.unpack('>H', data[ptr:ptr+2])[0]
                ptr += 2
                
                if ptr + value_length > len(data):
                    break
                    
                value_bytes = data[ptr:ptr+value_length]
                ptr += value_length
                
                channels.append({
                    'id': channel_id,
                    'value_bytes': value_bytes,
                    'timestamp': timestamp
                })
            
            return {
                'timestamp': timestamp,
                'channels': channels
            }
            
        except Exception as e:
            LOGGER.error("Error parsing telemetry packet: %s", e)
            return None

class SpacecraftTelemetry:
    """Class to handle spacecraft-side telemetry downlink."""
    
    def __init__(self, port_type: str, port: str, dictionary_path: str, 
                 baud_rate: int = BAUD_RATE, channel_filter: Optional[List[str]] = None):
        """Initialize SpacecraftTelemetry.
        
        Args:
            port_type (str): Type of port (serial or ethernet)
            port (str): Port name (e.g., /dev/ttyUSB0 or eth0)
            dictionary_path (str): Path to F' dictionary XML file
            baud_rate (int, optional): Baud rate for serial. Defaults to BAUD_RATE.
            channel_filter (List[str], optional): List of channel names to include. Defaults to None.
        """
        self.port_type = port_type
        self.port = port
        self.dictionary_path = dictionary_path
        self.channel_filter = channel_filter or []
        
        # Load dictionaries
        try:
            self.dictionaries = load_dictionaries(dictionary_path)
            LOGGER.info("F' Telemetry Dictionary loaded successfully.")
        except Exception as e:
            LOGGER.error("Failed to load dictionaries: %s", e)
            sys.exit(1)
        
        # Create port adapter
        try:
            self.adapter = create_adapter(port_type, port, baud_rate)
        except Exception as e:
            LOGGER.error("Failed to initialize port: %s", e)
            sys.exit(1)
        
        # Initialize telemetry packet formatter
        self.packet_formatter = TelemetryPacket()
        
        # Get channel templates
        self.channel_templates = {}
        if self.channel_filter:
            for channel_name in self.channel_filter:
                if channel_name in self.dictionaries.channel_name:
                    template = self.dictionaries.channel_name[channel_name]
                    self.channel_templates[template.get_id()] = template
        else:
            # Include all channels
            for channel_id, template in self.dictionaries.channel_id.items():
                self.channel_templates[channel_id] = template
    
    def create_sample_telemetry(self) -> List[ChData]:
        """Create sample telemetry data for demonstration.
        
        Returns:
            List[ChData]: List of sample channel data
        """
        channel_data = []
        current_time = time.time()
        
        for channel_id, template in self.channel_templates.items():
            # Create sample values based on channel type
            try:
                # This is a simplified example - in practice, you'd get real values
                # from your F' components or sensors
                if 'U32' in str(template.get_type()):
                    from fprime.common.models.serialize.numerical_types import U32Type
                    value_obj = U32Type(int(current_time) % 1000)
                elif 'F32' in str(template.get_type()):
                    from fprime.common.models.serialize.numerical_types import F32Type
                    value_obj = F32Type(float(current_time) % 100.0)
                else:
                    # Default to U32 for unknown types
                    from fprime.common.models.serialize.numerical_types import U32Type
                    value_obj = U32Type(0)
                
                # Create ChData object
                ch_data = ChData(value_obj, TimeType(), template)
                channel_data.append(ch_data)
                
            except Exception as e:
                LOGGER.warning("Failed to create sample data for channel %s: %s", 
                              template.get_full_name(), e)
        
        return channel_data
    
    def send_telemetry(self, channel_data: List[ChData]) -> bool:
        """Send telemetry data over the communication link.
        
        Args:
            channel_data (List[ChData]): List of channel data to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Format telemetry packet
            packet = self.packet_formatter.format_telemetry_packet(channel_data)
            
            # Add SatCat5 framing
            framed_packet = ETYPE_TELEMETRY + packet
            
            LOGGER.info("Sending telemetry packet with %d channels", len(channel_data))
            LOGGER.debug("Packet size: %d bytes", len(framed_packet))
            
            # Send over adapter
            return self.adapter.msg_send(framed_packet)
            
        except Exception as e:
            LOGGER.error("Error sending telemetry: %s", e)
            return False
    
    def run(self, interval: float = 1.0):
        """Run the spacecraft telemetry downlink.
        
        Args:
            interval (float): Interval between telemetry transmissions in seconds
        """
        LOGGER.info("Starting spacecraft telemetry downlink on %s (%s)", self.port, self.port_type)
        LOGGER.info("Transmitting %d channels every %.1f seconds", len(self.channel_templates), interval)
        
        try:
            while True:
                # Create sample telemetry data
                channel_data = self.create_sample_telemetry()
                
                # Send telemetry
                if self.send_telemetry(channel_data):
                    LOGGER.info("Sent telemetry packet successfully")
                else:
                    LOGGER.error("Failed to send telemetry packet")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            LOGGER.info("Stopping spacecraft telemetry...")
        finally:
            self.adapter.disconnect()

class GroundStationTelemetry:
    """Class to handle ground station telemetry reception and processing."""
    
    def __init__(self, port_type: str, port: str, dictionary_path: str, 
                 baud_rate: int = BAUD_RATE, gds_address: str = "127.0.0.1", 
                 gds_port: int = 50050):
        """Initialize GroundStationTelemetry.
        
        Args:
            port_type (str): Type of port (serial or ethernet)
            port (str): Port name (e.g., /dev/ttyUSB0 or eth0)
            dictionary_path (str): Path to F' dictionary XML file
            baud_rate (int, optional): Baud rate for serial. Defaults to BAUD_RATE.
            gds_address (str, optional): GDS server address. Defaults to "127.0.0.1".
            gds_port (int, optional): GDS server port. Defaults to 50050.
        """
        self.port_type = port_type
        self.port = port
        self.dictionary_path = dictionary_path
        self.gds_address = gds_address
        self.gds_port = gds_port
        
        # Load dictionaries
        try:
            self.dictionaries = load_dictionaries(dictionary_path)
            LOGGER.info("F' Telemetry Dictionary loaded successfully.")
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
        
        # Initialize telemetry packet parser
        self.packet_parser = TelemetryPacket()
        
        # Initialize channel decoder for ground system integration
        self.channel_decoder = ChDecoder(self.dictionaries.channel_id, ConfigManager())
        
        # Initialize GDS connection
        self.gds_connected = False
        self._connect_to_gds()
    
    def _connect_to_gds(self):
        """Connect to the F' GDS server."""
        try:
            from fprime_gds.common.communication.ground import TCPGround
            self.gds_handler = TCPGround(self.gds_address, self.gds_port)
            if self.gds_handler.open():
                self.gds_connected = True
                LOGGER.info("Connected to GDS at %s:%d", self.gds_address, self.gds_port)
            else:
                LOGGER.warning("Failed to connect to GDS at %s:%d", self.gds_address, self.gds_port)
        except Exception as e:
            LOGGER.warning("Could not connect to GDS: %s", e)
    
    def _process_data(self, data: bytes):
        """Process received telemetry data.
        
        Args:
            data (bytes): Received data from port
        """
        LOGGER.debug("Received data: %s", data.hex())
        
        # Check for SatCat5 configuration packet
        if data.startswith(SATCAT5_CONFIG):
            LOGGER.debug("Ignoring SatCat5 configuration packet")
            return
        
        # Check for telemetry packet
        if len(data) >= 2 and data[:2] == ETYPE_TELEMETRY:
            telemetry_data = data[2:]  # Remove EtherType
            self._process_telemetry_packet(telemetry_data)
    
    def _process_telemetry_packet(self, data: bytes):
        """Process a telemetry packet.
        
        Args:
            data (bytes): Telemetry packet data
        """
        parsed_data = self.packet_parser.parse_telemetry_packet(data)
        if not parsed_data:
            LOGGER.warning("Failed to parse telemetry packet")
            return
        
        LOGGER.info("Received telemetry packet with %d channels", len(parsed_data['channels']))
        
        # Process each channel
        for channel_info in parsed_data['channels']:
            self._process_channel(channel_info)
    
    def _process_channel(self, channel_info: Dict[str, Any]):
        """Process a single channel update.
        
        Args:
            channel_info (Dict[str, Any]): Channel information
        """
        channel_id = channel_info['id']
        value_bytes = channel_info['value_bytes']
        timestamp = channel_info['timestamp']
        
        # Get channel template
        if channel_id not in self.dictionaries.channel_id:
            LOGGER.warning("Unknown channel ID: %d", channel_id)
            return
        
        template = self.dictionaries.channel_id[channel_id]
        channel_name = template.get_full_name()
        
        try:
            # Create ChData object for ground system
            ch_data = self._create_ch_data(template, value_bytes, timestamp)
            
            # Update ground system
            self._update_ground_system(ch_data)
            
            LOGGER.info("Updated channel %s: %s", channel_name, ch_data.get_display_text())
            
        except Exception as e:
            LOGGER.error("Error processing channel %s: %s", channel_name, e)
    
    def _create_ch_data(self, template, value_bytes: bytes, timestamp: float) -> ChData:
        """Create a ChData object from received data.
        
        Args:
            template: Channel template
            value_bytes (bytes): Serialized channel value
            timestamp (float): Unix timestamp
            
        Returns:
            ChData: Channel data object
        """
        # Create time object
        time_obj = TimeType()
        time_obj.setTime(timestamp)
        
        # Deserialize value
        value_type = template.get_type()
        value_obj = value_type()
        value_obj.deserialize(value_bytes, 0)
        
        # Create ChData
        return ChData(value_obj, time_obj, template)
    
    def _update_ground_system(self, ch_data: ChData):
        """Update the ground system with new telemetry data.
        
        Args:
            ch_data (ChData): Channel data to update
        """
        if not self.gds_connected:
            LOGGER.debug("GDS not connected, skipping ground system update")
            return
        
        try:
            # Send to GDS through the channel decoder
            self.channel_decoder.send_to_all(ch_data)
            LOGGER.debug("Sent channel %s to GDS", ch_data.template.get_full_name())
        except Exception as e:
            LOGGER.error("Error updating ground system: %s", e)
    
    def run(self):
        """Run the ground station telemetry reception."""
        LOGGER.info("Starting ground station telemetry reception on %s (%s)", self.port, self.port_type)
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            LOGGER.info("Stopping ground station telemetry...")
        finally:
            if self.gds_connected:
                self.gds_handler.close()
            self.adapter.disconnect()

def main():
    """Main function to parse arguments and run the telemetry system."""
    parser = argparse.ArgumentParser(description='F\' Telemetry System')
    parser.add_argument('mode', choices=['spacecraft', 'ground'], 
                      help='Operation mode: spacecraft (downlink) or ground (reception)')
    parser.add_argument('--port-type', choices=['serial', 'ethernet'], default='serial',
                      help='Type of port to use (default: serial)')
    parser.add_argument('--port', default='/dev/ttyUSB0',
                      help='Port name (default: /dev/ttyUSB0 for serial, eth0 for Ethernet)')
    parser.add_argument('--baud', type=int, default=BAUD_RATE,
                      help='Baud rate for serial port (default: 921600)')
    parser.add_argument('--dictionary', required=True,
                      help='Path to the F\' dictionary XML file')
    parser.add_argument('--channels', nargs='*',
                      help='List of channel names to include (spacecraft mode only)')
    parser.add_argument('--interval', type=float, default=1.0,
                      help='Telemetry transmission interval in seconds (spacecraft mode only)')
    parser.add_argument('--gds-address', default='127.0.0.1',
                      help='GDS server address (ground mode only)')
    parser.add_argument('--gds-port', type=int, default=50050,
                      help='GDS server port (ground mode only)')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.debug)

    if args.mode == 'spacecraft':
        # Spacecraft mode
        telemetry = SpacecraftTelemetry(
            args.port_type, args.port, args.dictionary, args.baud, args.channels
        )
        telemetry.run(args.interval)
    else:
        # Ground mode
        telemetry = GroundStationTelemetry(
            args.port_type, args.port, args.dictionary, args.baud,
            args.gds_address, args.gds_port
        )
        telemetry.run()

if __name__ == "__main__":
    main() 