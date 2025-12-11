from .zmw_mqtt_base import ZmwMqttBase

class ZmwMqttNullSvc(ZmwMqttBase):
    """ An ZmwMqttNullSvc publishes metadata (like http for the service, and its systemdname) but doesn't have
    any behaviour: it doesn't depend on any other services, and it doesn't publish any data over mqtt. The
    service still has access to mqtt (eg for Z2M) through this client. """

    def get_service_mqtt_topic(self):
        return None


