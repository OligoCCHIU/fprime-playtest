#!/bin/bash

# Exit on any error
set -e

# Print commands as they are executed
set -x

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create and activate virtual environment if it doesn't exist
if [ ! -d "$PROJECT_ROOT/fprime-venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_ROOT/fprime-venv"
fi

# Activate virtual environment
source "$PROJECT_ROOT/fprime-venv/bin/activate"

# Clone fprime-gds if it doesn't exist
if [ ! -d "$PROJECT_ROOT/fprime-gds" ]; then
    echo "Cloning fprime-gds..."
    git clone https://github.com/nasa/fprime-gds.git "$PROJECT_ROOT/fprime-gds"
fi

# Install required packages
echo "Installing required packages..."
pip install -r "$PROJECT_ROOT/fprime-gds/requirements.txt"
pip install scapy

echo "Setup complete! The virtual environment is now activated."
echo "You can now run the scripts:"
echo "  python3 scripts/fprime_sender.py <project_path> <deployment_folder>"
echo "  sudo python3 scripts/fprime_receiver.py --dictionary <path_to_dictionary>" 