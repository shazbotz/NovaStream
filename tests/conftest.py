"""Shared pytest fixtures.

Deliberately minimal in the bootstrap phase - fixtures that construct a
full wired application (config -> providers -> services) get added
alongside the first feature plugin in Phase 3, when there's real behavior
worth testing end-to-end. For now, unit tests construct exactly the
collaborators each test needs, directly.
"""

import sys
from pathlib import Path

# Allow `pytest` to find the package without an editable install, so the
# test suite works immediately after cloning, before `pip install -e .`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
