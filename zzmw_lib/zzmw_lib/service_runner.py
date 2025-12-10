import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time

from inotify_simple import INotify, flags
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


log = build_logger("ServiceRunner")

def _get_config():
    with open('config.json', 'r') as fp:
        cfg = json.loads(fp.read())

    def _reload_on_cfg_change():
        inotify = INotify()
        inotify.add_watch("config.json", flags.MODIFY)
        for ev in inotify.read():
            log.info("Config file config.json has changed, will reload service (by shutting it down!)")
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)
            log.critical("Sent SIGTERM, if you're seeing this something is broken...")

    cfg_checker = threading.Thread(target=_reload_on_cfg_change, daemon=True)
    cfg_checker.start()
    return cfg


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


def get_this_service_logs():
    """Return logs from the last 24 hours, newest first, as a flask tuple-response"""
    pid = os.getpid()
    try:
        result = subprocess.run([
                'journalctl',
                f'_PID={pid}',
                '--since', '24 hours ago',
                '-r',  # reverse order (newest first)
                '-o', 'json'  # JSON output, one object per line
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
    except subprocess.TimeoutExpired:
        log.error("journalctl command timed out after 5 seconds")
        return {"error": "Log retrieval timed out"}, 504
    except FileNotFoundError:
        log.error("journalctl command not found")
        return {"error": "journalctl not available"}, 503

    if result.returncode != 0:
        log.error("journalctl failed with exit code %d: %s", result.returncode, result.stderr)
        return {"error": "Failed to retrieve logs"}, 500

    logs = []
    for line in result.stdout.strip().split('\n'):
        # Skip flask log lines for user requests, they are too noisy
        if line and not 'werkzeug/_internal.py' in line:
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("Failed to parse log line: %s", line[:100])
                continue

    return {"logs": logs, "count": len(logs)}


def service_runner_with_www(AppClass):
    """
    Run a service application with embedded Flask web server.

    Loads config.json, sets up Flask server with www directory serving,
    instantiates the service class with Flask app, and runs both with
    proper signal handling for graceful shutdown.

    Args:
        AppClass: Service class to instantiate. Must have __init__(cfg, www)
                  where www is the Flask app with additional methods:
                  - serve_url(path, view_func, methods=['GET'])
                  - register_www_dir(wwwdir, prefix='/')
                  - public_url_base (http://host:port)

    The Flask app runs in a background thread while the main thread
    runs the service's loop_forever().
    """
    # Import in helper method, so that services that don't need flask doesn't have to install a dep
    from flask import Flask
    from flask import send_from_directory, abort, redirect, url_for
    from werkzeug.serving import make_server, WSGIRequestHandler

    # Custom request handler that skips the timestamp in logs
    class CustomRequestHandler(WSGIRequestHandler):
        def log_date_time_string(self):
            return ""  # Return empty string to skip timestamp

    cfg = _get_config()
    flaskapp = Flask(AppClass.__name__)
    wwwserver = make_server(cfg['http_host'], cfg['http_port'], flaskapp, request_handler=CustomRequestHandler)

    flaskapp.public_url_base = f"http://{cfg['http_host']}:{cfg['http_port']}"
    def serve_url(url_path, view_func, methods=['GET']):
        return flaskapp.add_url_rule(rule=url_path,
                                     endpoint=url_path,
                                     view_func=view_func,
                                     methods=methods)
    def url_cb_ret_none(url_path, view_func, methods=['GET', 'PUT']):
        def wrapper(*a, **kw):
            r = view_func(*a, **kw)
            if r is not None:
                raise ValueError(f'Callback with expected None return actually returned a value: {str(r)}')
            return {}
        return flaskapp.add_url_rule(rule=url_path,
                                     endpoint=url_path,
                                     view_func=wrapper,
                                     methods=methods)

    def register_www_dir(wwwdir, prefix='/'):
        def srv(filename):
            try:
                safe_path = is_safe_path(wwwdir, filename)
            except ValueError as e:
                log.warning(f"Path traversal attempt blocked: {filename}")
                abort(400, description="Invalid file path.")

            if not os.path.isfile(safe_path):
                abort(404, description=f"File {filename} not found")

            try:
                return send_from_directory(wwwdir, filename)
            except Exception as e:
                log.error(f"Error serving file {filename}: {e}")
                return {"error": "Internal server error"}, 500

        if prefix[-1] != '/' and prefix[0] != '/':
            raise ValueError(f"URL prefix needs to start and end with a '/'. Recevied '{prefix}'")
        flaskapp.serve_url(f'{prefix}', lambda: redirect(f'{prefix}index.html'))
        flaskapp.serve_url(f'{prefix}<path:filename>', srv)
        return flaskapp.public_url_base

    def _www_serve_bg():
        t = threading.Thread(target=wwwserver.serve_forever)
        t.start()

    flaskapp.serve_url = serve_url
    flaskapp.url_cb_ret_none = url_cb_ret_none
    flaskapp.register_www_dir = register_www_dir
    flaskapp.serve_url('/svc_logs', get_this_service_logs)
    flaskapp.startup_automatically = True
    flaskapp.setup_complete = _www_serve_bg

    app = AppClass(cfg, flaskapp)

    def signal_handler(sig, frame):
        log.info("Shutdown requested by signal, stop app...")
        wwwserver.shutdown()
        app.stop()
        log.info("Clean exit")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if flaskapp.startup_automatically:
        # User may override this when the app is instanciated
        flaskapp.setup_complete()
    app.loop_forever()
    t.join()
