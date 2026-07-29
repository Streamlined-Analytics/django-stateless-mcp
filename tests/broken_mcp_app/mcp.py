"""A deliberately broken mcp.py: its own import fails.

ModuleNotFoundError is the sharpest case for the startup-failure guarantee,
because it is the same exception class autodiscovery suppresses for apps
that simply have no mcp module.
"""

import does_not_exist_xyz  # type: ignore[import-not-found]  # noqa: F401
