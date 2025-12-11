""" Dashboard - unified UI for different mqtt services """
import json
import os
import pathlib

from zzmw_lib.zmw_mqtt_service import ZmwMqttServiceNoCommands
from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.logs import build_logger
from service_magic_proxy import ServiceMagicProxy

log = build_logger("ZmwDashboard")


class ZmwDashboard(ZmwMqttServiceNoCommands):
    """Dashboard service that aggregates other services with generic proxying."""
    def __init__(self, cfg, www):
        super().__init__(cfg, svc_deps=[
                "ZmwLights", "ZmwSpeakerAnnounce", "ZmwContactmon",
                "ZmwHeating", "ZmwReolinkDoorbell", "ZmwSensormon",
                "BaticasaButtons"])

        self._svc_proxy = None
        self._www = www

        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_www_base = self._www.register_www_dir(www_path, '/')
        # We'll call www.setup_complete when the service is ready, otherwise we'll try to setup routes after
        # the service may have started.
        self._www.startup_automatically = False

    def on_all_service_deps_running(self):
        proxies = {}
        for svc_name, svc_meta in self.get_known_services().items():
            if "www" not in svc_meta or svc_meta["www"] is None:
                log.error("Service %s doesn't have a www service, can't proxy", svc_name)
                continue
            proxies[svc_name] = svc_meta["www"]
        self._svc_proxy = ServiceMagicProxy(proxies, self._www)
        log.info("Proxy routes registered, starting dashboard www")
        self._www.serve_url('/get_proxied_services', self._svc_proxy.get_proxied_services)
        self._www.setup_complete()

    def on_startup_fail_missing_deps(self, deps):
        log.critical("Some dependencies are missing, functionality may be broken in the dashboard: %s", deps)
        # Try to continue with whatever deps we have
        self.on_all_service_deps_running()

    def on_service_announced_meta(self, svc_name, meta):
        if self._svc_proxy is None:
            # Not setup yet, so it's safe to ignore new services
            return
        self._svc_proxy.on_service_announced_meta(svc_name, meta.get("www"))

service_runner_with_www(ZmwDashboard)
