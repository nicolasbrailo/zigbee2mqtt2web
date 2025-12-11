"""Service monitoring and status tracking."""

import pathlib
import os
import json
import subprocess
from datetime import datetime

from ansi2html import Ansi2HTMLConverter
from flask import abort

from zzmw_lib.zmw_mqtt_service import ZmwMqttServiceNoCommands
from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.logs import build_logger

from journal_monitor import JournalMonitor

log = build_logger("ZmwServicemon")

class ZmwServicemon(ZmwMqttServiceNoCommands):
    """ Monitor other z2m2w services running on this host """

    def __init__(self, cfg, www):
        super().__init__(cfg, svc_deps=[])
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)
        self._services = {}

        # Initialize journal monitor (exclude own service to prevent error loops)
        self._journal_monitor = JournalMonitor(
            max_errors=cfg['error_history_len'],
            rate_limit_window_mins=cfg['rate_limit_window_mins'],
            on_error_logged=self._on_service_logged_err,
            own_service_name="zmw_servicemon"
        )

        www.serve_url('/ls', self.known_services)
        www.serve_url('/systemd_status', self.systemd_status)
        www.serve_url('/recent_errors', self.recent_errors)

    def known_services(self):
        """Return JSON list of all known services and their metadata."""
        return json.dumps(dict(sorted(self._services.items())), default=str)

    def systemd_status(self):
        """Execute services_status.sh script and return HTML-formatted systemd status."""
        status_script = os.path.join(os.getcwd(), '../services_status.sh')
        if not os.path.isfile(status_script):
            script_dir = pathlib.Path(__file__).parent.resolve()
            status_script = script_dir.parent / 'services_status.sh'
            if not status_script.is_file():
                return abort(500, description=f"Can't find status script at {status_script}")
        cmd = str(status_script)
        syslogcmd = subprocess.run(cmd.split(), stdout=subprocess.PIPE, text=True, check=True).stdout
        conv = Ansi2HTMLConverter(inline=True, scheme='ansi2html')
        return conv.convert(syslogcmd, full=False)

    def recent_errors(self):
        """Return JSON list of recent errors from the journal monitor."""
        return json.dumps(self._journal_monitor.get_recent_errors(), default=str)

    def _on_service_logged_err(self, err):
        # TODO: Forward to Telegram
        pass

    def _on_service_updown(self, up, svc_meta):
        """ Hack an MqttServiceClient to work as a global service monitor; an MqttServiceClient is meant to
        declare its dependencies statically, at startup time. This service will monitor all deps, adding them
        to the list of known services as they come online. """
        super()._on_service_updown(up, svc_meta)
        if svc_meta is None or 'name' not in svc_meta:
            # Weird message published in the bus, ignore
            return

        svc_name = svc_meta['name']
        self._services[svc_name] = svc_meta
        self._services[svc_name]['alive'] = up
        if up:
            self._services[svc_name]['last_seen'] = datetime.now()
        self._journal_monitor.monitor_unit(svc_meta.get('systemd_name', svc_name))

    def on_dep_became_stale(self, name):
        if name not in self._services:
            # Service we never seen going up?
            self._services[name] = {
                    'name': name,
                    'last_seen': None,
            }
        self._services[name]['alive'] = False

    def stop(self):
        """Stop the service and journal monitor"""
        self._journal_monitor.stop()
        super().stop()

service_runner_with_www(ZmwServicemon)
