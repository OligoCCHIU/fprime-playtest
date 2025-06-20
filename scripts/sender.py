#!/usr/bin/env python3
"""
sender.py

A standalone, command-line tool to send F' commands over a UART/serial interface.
This script uses the fprime-gds libraries to ensure commands are formatted and sent
according to the F' framework specification.
"""

import os
import sys
import logging
import argparse

# Import common functionality
from adapter_common import (
    create_adapter, setup_logging, load_dictionaries, get_command_template,
    get_command_help_string, format_command_data, BAUD_RATE
)

# Configure basic logging
LOGGER = logging.getLogger("FPrimeSender")

def main():
    """Main function to parse arguments and run the commander."""
    parser = argparse.ArgumentParser(description='Send F\' commands over serial or Ethernet')
    parser.add_argument('project_path', help='Path to the F\' project directory')
    parser.add_argument('deployment_folder', help='Name of the deployment folder')
    parser.add_argument('--port-type', choices=['serial', 'ethernet'], default='serial',
                      help='Type of port to use (default: serial)')
    parser.add_argument('--port', default='/dev/ttyUSB0',
                      help='Port name (default: /dev/ttyUSB0 for serial, eth0 for Ethernet)')
    parser.add_argument('--baud', type=int, default=BAUD_RATE,
                      help='Baud rate for serial port (default: 921600)')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.debug)
    
    # Initialize F' GDS components
    dictionary_path = os.path.join(args.project_path, f"build-artifacts/Linux/{args.deployment_folder}/dict/{args.deployment_folder}TopologyAppDictionary.xml")
    
    try:
        dictionaries = load_dictionaries(dictionary_path)
    except Exception as e:
        LOGGER.error("Failed to load dictionaries: %s", e)
        sys.exit(1)

    # Initialize port adapter
    try:
        adapter = create_adapter(args.port_type, args.port, args.baud)
    except Exception as e:
        LOGGER.error("Failed to initialize port: %s", e)
        sys.exit(1)

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
                LOGGER.error("Command '%s' not found.", command_name)
                continue

            if len(cmd_args) != len(template.get_args()):
                LOGGER.error("Argument count mismatch for '%s'.", command_name)
                print(get_command_help_string(template))
                continue
            
            try:
                # Format command data
                binary_data = format_command_data(template, cmd_args)
                
                LOGGER.info("Sending: %s with args %s", command_name, cmd_args)
                if adapter.msg_send(binary_data):
                    LOGGER.info("Sent %d bytes successfully.", len(binary_data))
                else:
                    LOGGER.error("Failed to send command.")
            except Exception as e:
                LOGGER.error("Error processing command: %s", e)
                print(get_command_help_string(template))

    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        adapter.disconnect()
        LOGGER.info("Application terminated.")

if __name__ == "__main__":
    main()
