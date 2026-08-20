#!/usr/bin/env python3
"""Thin wrapper — prefer: python -m tradelab.cli paper"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradelab.cli import main

if __name__ == "__main__":
    main(["paper", "--strategy", "momentum", "--bars", "400", "--no-journal"])
