#!/usr/bin/env python3
"""Appinfra CLI entry point."""

import sys
from pathlib import Path

# Ensure local source takes precedence over installed package
sys.path.insert(0, str(Path(__file__).parent))

from appinfra.cli.cli import main

if __name__ == "__main__":
    main()
