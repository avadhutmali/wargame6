#!/bin/bash

sudo apt update

# Install python3-venv if not installed
sudo apt install -y python3-venv

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements if file exists
if [ -f "requirements.txt" ]; then
    # pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "No requirements.txt found — skipping dependency install."
fi

# Run your command inside venv
# Change this to the command you want
python play.py