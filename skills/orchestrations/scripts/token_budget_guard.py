#!/usr/bin/env python3
"""Compatibility entrypoint: exact-session cumulative ledger, no default hard cap."""
import runpy
import sys
from pathlib import Path

scripts = Path.home() / '.codex/skills/context-handoff/scripts'
sys.path.insert(0, str(scripts))
runpy.run_path(str(scripts / 'ledger.py'), run_name='__main__')
