"""Compatibility import for the original design-contract tests."""
import sys as _runtime_sys
from pathlib import Path as _RuntimePath
_runtime_sys.path.insert(0, str(_RuntimePath(__file__).resolve().parents[1]/"backend"))
from fintrust.release_contract import *
