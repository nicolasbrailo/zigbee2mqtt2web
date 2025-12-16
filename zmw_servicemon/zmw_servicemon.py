"""Service monitoring and status tracking."""

import pathlib
import os
import json
import subprocess

from ansi2html import Ansi2HTMLConverter
from flask import abort

from zzmw_lib.zmw_mqtt_mon import ZmwMqttServiceMonitor
from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.logs import build_logger

from journal_monitor import JournalMonitor

log = build_logger("ZmwServicemon")


class ZmwServicemon(ZmwMqttServiceMonitor):
    """ Monitor other z2m2w services running on this host """

    def __init__(self, cfg, www):
        # Initialize journal monitor (exclude own service to prevent error loops)
        self._journal_monitor = JournalMonitor(
            max_errors=cfg['error_history_len'],
            rate_limit_window_mins=cfg['rate_limit_window_mins'],
            on_error_logged=self._on_service_logged_err,
            own_service_name="zmw_servicemon"
        )

        super().__init__(cfg)

        www.register_www_dir(os.path.join(pathlib.Path(__file__).parent.resolve(), 'www'))
        www.serve_url('/ls', lambda: json.dumps(dict(sorted(self.get_known_services().items())), default=str))
        www.serve_url('/systemd_status', self.systemd_status)
        www.serve_url('/recent_errors', lambda: json.dumps(self._journal_monitor.get_recent_errors(), default=str))
        www.serve_url('/recent_errors_clear', self._journal_monitor.clear_recent_errors)
        def _log_error():
            log.error("Hola!")
            try:
                raise ValueError(42)
            except:
                log.error("Exception", exc_info=True)
            return ""
        www.serve_url('/recent_errors_test_new', _log_error)

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

    def on_new_svc_discovered(self, svc_name, svc_meta):
        """ Called by ZmwMqttServiceMonitor when a new service is discovered. Not guaranteed that service is alive. """
        journal_name = svc_meta.get('systemd_name', svc_name)
        log.info("New service '%s' with journal '%s' discovered", svc_name, journal_name)
        self._journal_monitor.monitor_unit(journal_name)

    def _on_service_logged_err(self, err):
        # TODO: Forward to Telegram
        pass

    def stop(self):
        """Stop the service and journal monitor"""
        self._journal_monitor.stop()
        super().stop()

service_runner_with_www(ZmwServicemon)
