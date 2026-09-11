"""``python -m llmtone`` — the CLI without a console-script shim.

An installed entry point is a generated executable on the PATH, which is
awkward for the things most likely to drive llmtone: an agent shelling out, an
MCP server, a CI job, a checkout nobody installed at all. Running the module
needs none of that, and behaves identically.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
