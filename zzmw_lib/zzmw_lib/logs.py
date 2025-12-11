import os
import logging

from systemd.journal import JournalHandler

def build_logger(name, lvl=logging.DEBUG):
    """
    Create a logger configured for systemd journal or console output.

    Automatically detects if running under systemd (via INVOCATION_ID env var) and
    configures appropriate handlers. Ensures third-party library logs are filtered
    at INFO level while allowing app logs at DEBUG level.

    Args:
        name: Logger name (typically the service/module name)
        lvl: Log level for this logger (default: logging.DEBUG)

    Returns:
        Configured logging.Logger instance
    """
    # Configure root logger ONCE with proper handler/formatter for third-party libs
    root = logging.getLogger()
    if not root.handlers:  # Only configure if not already done
        if os.getenv("INVOCATION_ID"):
            # Running under systemd
            root_handler = JournalHandler()
            root_handler.setFormatter(logging.Formatter('%(message)s'))
        else:
            # Running standalone
            root_handler = logging.StreamHandler()
            root_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

        root_handler.setLevel(logging.DEBUG)
        root.addHandler(root_handler)
        root.setLevel(logging.INFO)  # Root stays at INFO to filter third-party noise

    # Create isolated logger for your app code
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    log.handlers.clear()

    # Same handler setup as root, but isolated
    if os.getenv("INVOCATION_ID"):
        # We're running under systemd, don't bother with stdout
        handler = JournalHandler()
        handler.setLevel(lvl)
        handler.setFormatter(logging.Formatter('%(message)s'))
        log.addHandler(handler)
    else:
        handler = logging.StreamHandler()
        handler.setLevel(lvl)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        log.addHandler(handler)

    return log


