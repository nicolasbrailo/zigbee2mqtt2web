from abc import ABC, abstractmethod
from datetime import datetime

from .zmw_mqtt_service import ZmwMqttServiceNoCommands

class ZmwMqttServiceMonitor(ZmwMqttServiceNoCommands):
    def __init__(self, cfg, svc_deps=[]):
        self._all_services_ever_seen = {}
        super().__init__(cfg, svc_deps)

    def _on_service_updown(self, up, svc_meta):
        """ Hack an MqttServiceClient to work as a global service monitor; an MqttServiceClient is meant to
        declare its dependencies statically, at startup time. This service will monitor all deps, adding them
        to the list of known services as they come online. """
        if svc_meta is None or 'name' not in svc_meta:
            # Weird message published in the bus, ignore
            return

        svc_name = svc_meta['name']
        new_svc = svc_name not in self._all_services_ever_seen
        self._all_services_ever_seen[svc_name] = svc_meta
        self._all_services_ever_seen[svc_name]['alive'] = up
        if up:
            self._all_services_ever_seen[svc_name]['last_seen'] = datetime.now()
        if new_svc:
            self.on_new_svc_discovered(svc_name, svc_meta)

        # Delay parent processing; when all deps are complete, it will fire events notifying that all deps are known
        # and if we do this before we register the service here, we will have a mismatch in the list of known services
        super()._on_service_updown(up, svc_meta)

    def on_dep_became_stale(self, name):
        if name in self._all_services_ever_seen:
            self._all_services_ever_seen[name]['alive'] = False
            return
        # Service we never seen going up? Maybe this service booted up after this one, and missed the
        # annoucement message
        self._all_services_ever_seen[name] = {
            'name': name,
            'last_seen': None,
            'alive': False,
        }
        self.on_new_svc_discovered(name, self._all_services_ever_seen[name])

    def get_known_services(self):
        """ Override list of known services: ZmwMqttServiceNoCommands only keeps a list of requested deps, but we need
        to monitor ALL services, dep or not. """
        return self._all_services_ever_seen

    @abstractmethod
    def on_new_svc_discovered(self, svc_name, svc_meta):
        """ Called when a new service is first seen. Service may or may not be alive. """

