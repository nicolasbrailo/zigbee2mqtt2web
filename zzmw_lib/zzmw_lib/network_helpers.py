"""Network utility functions shared across services."""
import os
import socket


def get_lan_ip():
    """
    Get LAN IP by checking which interface would route to an external host.

    This creates a UDP socket and "connects" to an external IP (no data is sent),
    then checks which local IP was selected for the connection.

    Returns:
        str: The LAN IP address, or None if it cannot be determined
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def is_port_available(host, port):
    """
    Check if a port is available for binding.

    Args:
        host: The host address to check
        port: The port number to check

    Returns:
        bool: True if the port is available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False


def find_available_port(host, start_port, end_port):
    """
    Find an available port in the given range.

    Args:
        host: The host address to bind to
        start_port: Start of port range (inclusive)
        end_port: End of port range (inclusive)

    Returns:
        int: An available port, or 0 if none found (let OS assign)
    """
    for port in range(start_port, end_port + 1):
        if is_port_available(host, port):
            return port
    return 0


def is_safe_path(basedir, path, follow_symlinks=False):
    """
    Validates that a file path is safe and within the allowed base directory.

    Prevents path traversal attacks by resolving the full path and verifying
    it stays within the base directory.

    Args:
        basedir: The allowed base directory (must be absolute)
        path: The requested file path (relative to basedir)
        follow_symlinks: False means that symlinks outside of the basedir are allowed, use with caution

    Returns:
        The safe absolute path if valid

    Raises:
        ValueError: If the path escapes the base directory
    """
    if follow_symlinks:
        basedir = os.path.realpath(basedir)
        matchpath = os.path.realpath(os.path.join(basedir, path))
    else:
        basedir = os.path.abspath(basedir)
        matchpath = os.path.abspath(os.path.join(basedir, path))

    # Check if the resolved path is within the base directory
    if not matchpath.startswith(basedir + os.sep) and matchpath != basedir:
        raise ValueError(f"Path traversal attempt detected: {path}")

    return matchpath
