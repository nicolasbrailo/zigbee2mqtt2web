import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time

from flask import Flask
from flask import send_from_directory, abort, redirect, url_for
from werkzeug.serving import make_server, WSGIRequestHandler

from inotify_simple import INotify, flags
from systemd.journal import JournalHandler

from .zmw_mqtt_base import ZmwMqttBase
from .logs import build_logger

log = build_logger("ServiceRunner")


def _get_lan_ip():
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


def _get_http_host(cfg):
    """
    Get the HTTP host to bind to.

    If cfg['http_host'] exists and is not None, use it.
    Otherwise, try to auto-detect the LAN IP.
    If detection fails, fall back to '0.0.0.0'.

    Returns:
        str: The host address to bind to
    """
    if cfg.get('http_host') is not None:
        return cfg['http_host']

    lan_ip = _get_lan_ip()
    if lan_ip is not None:
        return lan_ip

    log.error("Could not determine LAN IP, falling back to 0.0.0.0. Service discovery will break.")
    return '0.0.0.0'


def _get_port(cfg, host):
    """
    Get a port for the HTTP server.

    If cfg['http_port'] exists and is not None, use it.
    Otherwise, try to find a free port in range 4201-4299.
    If no port in range is available, fall back to OS-assigned port.

    Returns:
        int: The port number to use
    """
    if cfg.get('http_port') is not None:
        return cfg['http_port']

    # Try to find a free port in the preferred range
    for port in range(4201, 4300):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            continue

    # Fall back to OS-assigned port
    log.warning("No free port found in range 4201-4299, falling back to OS-assigned port")
    return 0

def _get_systemd_name(cls):
    # Assume that systemd name is going to be FooBar -> foo_bar
    # TODO: Check also path to src, and verify it exists in journald so error is printed here instead when trying to monitor
    return ''.join(f'_{c.lower()}' if c.isupper() and i > 0 else c.lower() for i, c in enumerate(cls.__name__))

def _monkeypatch_service_meta(cls, wwwurl):
    # Add get_service_meta to the class before instantiation (in case it's abstract)
    if getattr(getattr(cls, 'get_service_meta', None), '__isabstractmethod__', False):
        def _get_service_meta(self):
            return {
                "name": cls.__name__,
                "systemd_name": _get_systemd_name(cls),
                "mqtt_topic": self.get_service_mqtt_topic(),
                "www": wwwurl,
            }
        cls.get_service_meta = _get_service_meta
        # Clear from abstract methods set so ABC allows instantiation
        cls.__abstractmethods__ = cls.__abstractmethods__ - {'get_service_meta'}


def _get_config():
    """ Will open config.json for this service. If the config file doesn't exist, returns an empty map. Will kill the
    running service if the config changes, or if a new config file is created after the service has been started with
    no config file, so the service will have a chance to reload. """
    config_exists = os.path.exists('config.json')

    if config_exists:
        with open('config.json', 'r') as fp:
            cfg = json.loads(fp.read())
    else:
        log.info("Config file config.json not found, using empty config")
        cfg = {}

    def _reload_on_cfg_change():
        inotify = INotify()
        if config_exists:
            inotify.add_watch("config.json", flags.MODIFY)
        else:
            inotify.add_watch(".", flags.CREATE)
        for ev in inotify.read():
            if not config_exists and ev.name != "config.json":
                continue
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
    # Custom request handler that skips the timestamp in logs
    class CustomRequestHandler(WSGIRequestHandler):
        def log_date_time_string(self):
            return ""  # Return empty string to skip timestamp

    cfg = _get_config()
    flaskapp = Flask(AppClass.__name__)
    http_host = _get_http_host(cfg)
    wwwserver = make_server(http_host,
                            _get_port(cfg, http_host),
                            flaskapp, request_handler=CustomRequestHandler)
    flaskapp.public_url_base = f"http://{http_host}:{wwwserver.server_port}"
    log.info("Will serve www requests to %s", flaskapp.public_url_base)

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

    www_thread = threading.Thread(target=wwwserver.serve_forever)
    def _www_serve_bg():
        www_thread.start()

    flaskapp.serve_url = serve_url
    flaskapp.url_cb_ret_none = url_cb_ret_none
    flaskapp.register_www_dir = register_www_dir
    flaskapp.startup_automatically = True
    flaskapp.setup_complete = _www_serve_bg

    _lib_www_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www')
    # Add an endpoint to retrieve logs for this service
    flaskapp.serve_url('/svc_logs', get_this_service_logs)
    flaskapp.serve_url('/svc_logs.html', lambda: send_from_directory(_lib_www_path, 'svc_logs.html'))
    # Add endpoints for common www things
    flaskapp.serve_url('/zmw.css', lambda: send_from_directory(_lib_www_path, 'build/zmw.css'))
    flaskapp.serve_url('/zmw.js', lambda: send_from_directory(_lib_www_path, 'build/zmw.js'))

    if not issubclass(AppClass, ZmwMqttBase):
        raise ValueError("Don't know how to run app '%s', this runner is meant to be used with ZmwMqttServices", AppClass.__name__)

    _monkeypatch_service_meta(AppClass, flaskapp.public_url_base)
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
    www_thread.join()
