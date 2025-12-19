""" Dashboard - unified UI for different mqtt services """
import os
import pathlib
import threading

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from zzmw_lib.zmw_mqtt_mon import ZmwMqttServiceMonitor
from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.logs import build_logger
from service_magic_proxy import ServiceMagicProxy

log = build_logger("ZmwDashboard")


def _validate_user_defined_links(links):
    """Validate that user_defined_links has the correct format."""
    if not isinstance(links, list):
        raise ValueError("user_defined_links must be a list")
    for i, link in enumerate(links):
        if not isinstance(link, dict):
            raise ValueError(f"user_defined_links[{i}] must be a dict")
        required_keys = {"label", "url", "icon"}
        missing = required_keys - set(link.keys())
        if missing:
            raise ValueError(f"user_defined_links[{i}] missing keys: {missing}")


class ZmwDashboard(ZmwMqttServiceMonitor):
    """Dashboard service that aggregates other services with generic proxying."""
    def __init__(self, cfg, www):
        # These are the minimum dep list that we know we'll need; there may be more, and we'll proxy all known
        # services, but we need at least these to have a healthy service running.
        min_deps = ["ZmwLights", "ZmwSpeakerAnnounce", "ZmwContactmon", "ZmwHeating", "ZmwReolinkDoorbell",
                    "ZmwSensormon"]
        super().__init__(cfg, svc_deps=min_deps)

        self._scenes_svc = cfg["scenes_service_name"]
        self._user_defined_links = cfg.get("user_defined_links", [])
        _validate_user_defined_links(self._user_defined_links)
        self._svc_proxy = None
        self._www = www

        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_www_base = self._www.register_www_dir(www_path, '/')
        # We'll call www.setup_complete when the service is ready, otherwise we'll try to setup routes after
        # the service may have started.
        self._www.startup_automatically = False

    def on_all_service_deps_running(self):
        # Delay startup: we may still be processing messages from known services that are not full deps, eg if our
        # list of deps is [a,b] and the published list of running services is [a,b,c], this method will be called
        # before c is registered. By delaying startup, we can get the full list of services registered first even
        # if the are not explicitly declared deps.
        threading.Timer(1.0, self._setup_service_proxies).start()

    def _setup_service_proxies(self):
        proxies = {}
        for svc_name, svc_meta in self.get_known_services().items():
            if "www" not in svc_meta or svc_meta["www"] is None:
                log.error("Service %s doesn't have a www service, can't proxy", svc_name)
                continue
            proxies[svc_name] = svc_meta["www"]
            if svc_name == self._scenes_svc:
                # This is a service with an alias, expose it in two endpoints
                proxies['Scenes'] = svc_meta["www"]
        self._svc_proxy = ServiceMagicProxy(proxies, self._www)
        log.info("Proxy routes registered, starting dashboard www")
        self._www.serve_url('/get_proxied_services', self._svc_proxy.get_proxied_services)
        self._www.serve_url('/get_user_defined_links', self._get_user_defined_links)
        self._www.setup_complete()

    def _get_user_defined_links(self):
        return self._user_defined_links

    def get_service_alerts(self):
        """Aggregate alerts from all proxied services."""
        if self._svc_proxy is None:
            return ["Service proxy not running yet..."]
        alerts = []
        for svc_name, svc_url in self._svc_proxy.get_proxied_services().items():
            try:
                resp = requests.get(f"{svc_url}/svc_alerts", timeout=2, verify=False)
                if resp.status_code == 200:
                    svc_alerts = resp.json()
                    for alert in svc_alerts:
                        alerts.append(f"{svc_name}: {alert}")
            except Exception:  # pylint: disable=broad-exception-caught
                log.debug("Failed to get alerts from %s", svc_name, exc_info=True)
        return alerts

    def on_startup_fail_missing_deps(self, deps):
        log.critical("Some dependencies are missing, functionality may be broken in the dashboard: %s", deps)
        # Try to continue with whatever deps we have
        self.on_all_service_deps_running()

    def on_service_announced_meta(self, name, svc_meta):
        """ Notify the service proxy of every meta announcement: if the url for a service changes, the proxy needs to
        know (and possibly restart the proxy) """
        if self._svc_proxy is None:
            # Not setup yet, so it's safe to ignore new services
            return
        self._svc_proxy.on_service_announced_meta(name, svc_meta.get("www"))

    def on_new_svc_discovered(self, svc_name, svc_meta):
        """ We'll proxy all known services on startup. If a new service comes up after we've started, let the
        service proxy know, it may decide to restart to proxy a new service. If the proxy is null, we haven't
        started yet so it's safe to ignore announcements. """
        if self._svc_proxy is not None:
            self._svc_proxy.on_service_announced_meta(svc_name, svc_meta.get("www"))

service_runner_with_www(ZmwDashboard)
