#!/usr/bin/env python
"""Launcher script for Updates Manager Tool."""
import sys
from pathlib import Path

# Add the tool directory to path
tool_dir = Path(__file__).parent
if str(tool_dir) not in sys.path:
    sys.path.insert(0, str(tool_dir))

from app.main import main

if __name__ == "__main__":
    main()
