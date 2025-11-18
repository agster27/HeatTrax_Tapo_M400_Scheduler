#!/usr/bin/env python3
"""
Simple script to start the web server for manual testing.
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_manager import ConfigManager
from web_server import WebServer

# Use the example config
config_path = 'config.example.yaml'

# Create config manager
config_manager = ConfigManager(config_path)

# Create web server
web_server = WebServer(config_manager)

print("=" * 80)
print("Starting HeatTrax Web UI for testing...")
print("=" * 80)
print(f"URL: http://127.0.0.1:4328")
print("Press Ctrl+C to stop")
print("=" * 80)

# Run the web server
try:
    web_server.run(host='127.0.0.1', port=4328, debug=False)
except KeyboardInterrupt:
    print("\nShutting down...")
