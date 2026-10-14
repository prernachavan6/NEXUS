#!/usr/bin/env python3
"""
NEXUS E-Commerce — Server Launcher
Executes the Python Flask backend and serves the frontend on port 5000.
"""

import os
import sys

DIRECTORY = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIRECTORY)

if __name__ == '__main__':
    from app import run_server
    run_server()
