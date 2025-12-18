"""HTTP-only asset server for Sonos speaker compatibility.

Sonos speakers cannot fetch audio from HTTPS servers with self-signed certificates.
This module provides a secondary HTTP-only Flask server to serve TTS assets
that Sonos can access, while the main service may run on HTTPS.
"""
import os
import threading

from flask import Flask, send_from_directory, abort
from werkzeug.serving import make_server, WSGIRequestHandler

from zzmw_lib.logs import build_logger
from zzmw_lib.network_helpers import get_lan_ip, find_available_port, is_safe_path

log = build_logger("HttpAssetServer")


class HttpAssetServer:
    """HTTP-only server for serving TTS assets to Sonos speakers."""

    def __init__(self, tts_assets_path, http_host=None):
        """
        Initialize the HTTP asset server.

        Args:
            tts_assets_path: Path to the directory containing TTS audio files
            http_host: Host to bind to (auto-detected if None)
        """
        self._tts_assets_path = tts_assets_path
        self._host = http_host or get_lan_ip() or '0.0.0.0'
        self._server = None
        self._thread = None
        self._public_url_base = None

    def start(self):
        """Start the HTTP asset server in a background thread."""
        class _QuietRequestHandler(WSGIRequestHandler):
            def log_request(self, *args, **kwargs):
                pass  # Suppress request logging

        app = Flask("HttpAssetServer")
        port = find_available_port(self._host, 4301, 4399)

        # Register the TTS assets route
        @app.route('/tts/<path:filename>')
        def serve_tts(filename):
            try:
                safe_path = is_safe_path(self._tts_assets_path, filename)
            except ValueError:
                log.warning("Path traversal attempt blocked: %s", filename)
                abort(400, description="Invalid file path")

            if not os.path.isfile(safe_path):
                abort(404, description=f"File {filename} not found")

            return send_from_directory(self._tts_assets_path, filename)

        # Create HTTP-only server (no ssl_context)
        self._server = make_server(
            self._host,
            port,
            app,
            request_handler=_QuietRequestHandler,
            ssl_context=None
        )

        actual_port = self._server.server_port
        self._public_url_base = f"http://{self._host}:{actual_port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def shutdown(self):
        """Shutdown the HTTP asset server."""
        if self._server:
            log.info("Shutting down HTTP asset server")
            self._server.shutdown()

    @property
    def public_tts_base(self):
        """Return the public URL base for TTS assets (e.g., http://192.168.1.10:4301/tts)."""
        if self._public_url_base is None:
            raise RuntimeError("Server not started yet")
        return f"{self._public_url_base}/tts"
