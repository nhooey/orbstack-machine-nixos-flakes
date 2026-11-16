"""Load orbstack-machine-nixos-flakes.py as a module for the tests.

The script's file name has hyphens, so it can't be imported by name.
"""

from __future__ import annotations

import importlib.util
import sys
from functools import cache
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).parent.parent
PROVISION_SCRIPT_PATH = PROJECT_ROOT / "orbstack-machine-nixos-flakes.py"
MODULE_NAME = "orbstack_nixos_provision"


@cache
def load() -> ModuleType:
    """Return the provisioning script as a module, loading it once."""
    spec = importlib.util.spec_from_file_location(MODULE_NAME, PROVISION_SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module
