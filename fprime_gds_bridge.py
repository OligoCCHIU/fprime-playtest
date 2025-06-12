#!/usr/bin/env python3

import os
import sys
import json
import time
import threading
from fprime_gds.common.pipeline.standard import StandardPipeline
from fprime_gds.executables.cli import StandardPipelineParser
from fprime_gds.common.utils.config_manager import ConfigManager
from fprime_gds.common.data_types.cmd_data import CmdData
from fprime_serial_bridge import FPrimeSerialBridge

class FPrimeGDSBridge:
    def __init__(self, serial_port="/dev/ttyUSB0"):
        self.serial_bridge = FPrimeSerialBridge(serial_port=serial_port)
        self.pipeline = None
        self.running = False

    def command_callback(self, cmd_data):
        """Callback for when a command is received from F' GDS"""
        if not isinstance(cmd_data, CmdData):
            return

        # Convert command to string format
        command_str = f"{cmd_data.get_mnemonic()} {' '.join(str(arg) for arg in cmd_data.get_args())}"
        print(f"Received command: {command_str}")

        # Send command through serial bridge
        self.serial_bridge.send_command(command_str)

    def start(self):
        """Start the GDS bridge"""
        # Start serial bridge
        if not self.serial_bridge.start():
            return False

        # Initialize F' GDS pipeline
        parser = StandardPipelineParser()
        args = parser.parse_args([])  # Use default arguments
        
        # Create pipeline
        self.pipeline = StandardPipeline()
        
        # Get the dictionary and file store paths
        dictionary_path = os.path.join(os.getcwd(), "MathDeployment", "Top")
        file_store_path = os.path.join(os.getcwd(), "build-artifacts", "MathDeployment", "logs")
        
        # Ensure directories exist
        os.makedirs(file_store_path, exist_ok=True)
        
        # Setup pipeline with required arguments
        self.pipeline.setup(args, dictionary_path, file_store_path)
        
        # Register command callback
        self.pipeline.register_command_callback(self.command_callback)
        
        # Start pipeline
        self.pipeline.connect()
        self.running = True
        
        print("F' GDS Bridge started")
        return True

    def stop(self):
        """Stop the GDS bridge"""
        self.running = False
        if self.pipeline:
            self.pipeline.disconnect()
        self.serial_bridge.stop()
        print("F' GDS Bridge stopped")

def main():
    # Create and start the bridge
    bridge = FPrimeGDSBridge()
    if not bridge.start():
        sys.exit(1)

    try:
        # Keep the main thread alive
        while bridge.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bridge...")
    finally:
        bridge.stop()

if __name__ == "__main__":
    main() 