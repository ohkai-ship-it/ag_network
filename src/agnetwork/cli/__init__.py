"""CLI package for AG Network.

This package provides a modular CLI structure with commands split by domain.
The main Typer app is created in app.py and commands are registered from each module.

Backward Compatibility:
    The old import `from agnetwork.cli import app` remains valid since we re-export
    the app from this __init__.py.
"""

# Import app first (creates the Typer instance)
# Import command modules to register commands with the app
# Order matters: modules that create sub-apps must be imported before
# modules that might depend on them
import agnetwork.cli.commands_crm  # noqa: F401, E402
import agnetwork.cli.commands_memory  # noqa: F401, E402
import agnetwork.cli.commands_pipeline  # noqa: F401, E402
import agnetwork.cli.commands_research  # noqa: F401, E402
import agnetwork.cli.commands_sequence  # noqa: F401, E402
import agnetwork.cli.commands_skills  # noqa: F401, E402
import agnetwork.cli.commands_workspace  # noqa: F401, E402
from agnetwork.cli.app import app

__all__ = ["app"]
