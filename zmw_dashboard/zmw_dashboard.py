""" Dashboard - unified UI for different mqtt services """
import os
import pathlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from zzmw_lib.zmw_mqtt_mon import ZmwMqttServiceMonitor
from zzmw_lib.service_runner import service_runner
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
    def __init__(self, cfg, www, sched):
        # These are the minimum dep list that we know we'll need; there may be more, and we'll proxy all known
        # services, but we need at least these to have a healthy service running.
        min_deps = ["ZmwLights", "ZmwSpeakerAnnounce", "ZmwContactmon", "ZmwHeating", "ZmwReolinkDoorbell",
                    "ZmwSensormon"]
        super().__init__(cfg, sched, svc_deps=min_deps)

        self._scenes_svc = cfg["scenes_service_name"]
        self._user_defined_links = cfg.get("user_defined_links", [])
        _validate_user_defined_links(self._user_defined_links)
        self._svc_proxy = None
        self._www = www

        # Endpoints to prefetch for the dashboard init batch request
        self._prefetch_endpoints = [
            "/svc_alerts",
            "/ZmwLights/get_lights",
            "/Scenes/ls_scenes",
            "/ZmwSensormon/sensors/measuring/temperature",
            "/ZmwLights/z2m/get_known_things_hash",
        ]

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
            if svc_name == "ZmwDashboard":
                continue  # Don't proxy requests to ourselves
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
        self._www.serve_url('/prefetch', self.get_prefetch_data)
        self._www.setup_complete()

    def _get_user_defined_links(self):
        return self._user_defined_links

    def _fetch_prefetch_endpoint(self, endpoint):
        """Fetch a single prefetch endpoint."""
        # Handle local endpoint
        if endpoint == "/svc_alerts":
            return self.get_service_alerts()

        # Parse proxied endpoint: /ServiceName/path/to/resource
        parts = endpoint.split('/', 2)  # ['', 'ServiceName', 'path/to/resource']
        if len(parts) < 3:
            log.warning("Invalid prefetch endpoint format: %s", endpoint)
            return None

        service_name = parts[1]
        path = '/' + parts[2]

        services = self._svc_proxy.get_proxied_services()
        if service_name not in services:
            log.warning("Prefetch endpoint references unknown service: %s", service_name)
            return None

        service_url = services[service_name]
        try:
            resp = requests.get(f"{service_url}{path}", timeout=2, verify=False)
            if resp.status_code == 200:
                return resp.json()
            log.debug("Prefetch %s returned status %d", endpoint, resp.status_code)
        except Exception:  # pylint: disable=broad-exception-caught
            log.debug("Failed to prefetch %s", endpoint, exc_info=True)
        return None

    def get_prefetch_data(self):
        """Fetch all prefetch endpoints concurrently and return as a dict."""
        if self._svc_proxy is None:
            return {}

        result = {}
        with ThreadPoolExecutor(max_workers=len(self._prefetch_endpoints)) as executor:
            futures = {executor.submit(self._fetch_prefetch_endpoint, ep): ep
                       for ep in self._prefetch_endpoints}
            for future in as_completed(futures):
                endpoint = futures[future]
                try:
                    data = future.result()
                    if data is not None:
                        result[endpoint] = data
                except Exception:  # pylint: disable=broad-exception-caught
                    result[endpoint] = None
                    log.debug("Failed to get prefetch result for %s", endpoint, exc_info=True)
        return result

    def _fetch_service_alerts(self, svc_name, svc_url):
        """Fetch alerts from a single service."""
        try:
            resp = requests.get(f"{svc_url}/svc_alerts", timeout=2, verify=False)
            if resp.status_code == 200:
                return [(svc_name, alert) for alert in resp.json()]
        except Exception:  # pylint: disable=broad-exception-caught
            log.debug("Failed to get alerts from %s", svc_name, exc_info=True)
        return []

    def get_service_alerts(self):
        """Aggregate alerts from all proxied services."""
        if self._svc_proxy is None:
            return ["Service proxy not running yet..."]
        alerts = []
        services = list(self._svc_proxy.get_proxied_services().items())
        if not services:
            return []
        with ThreadPoolExecutor(max_workers=len(services)) as executor:
            futures = {executor.submit(self._fetch_service_alerts, name, url): name
                       for name, url in services}
            for future in as_completed(futures):
                for svc_name, alert in future.result():
                    alerts.append(f"{svc_name}: {alert}")
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

service_runner(ZmwDashboard)
