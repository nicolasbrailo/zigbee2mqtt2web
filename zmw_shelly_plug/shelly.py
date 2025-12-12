from requests import post
from requests.exceptions import RequestException
from requests.auth import HTTPDigestAuth
from json.decoder import JSONDecodeError

# Docs https://shelly-api-docs.shelly.cloud/gen2/0.14/Devices/ShellyPlusPlugUK/
# Some code stolen from https://github.com/Jan200101/ShellyPy


class ShellyGen2:
    def __init__(self, host, port = "80", login={}, timeout=5):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._credentials = (login.get("username", ""), login.get("password", ""))
        self._payload_id = 1

        self._last_status = None
        self._last_cfg = None

    def post(self, endpoint, values = None):
        url = "http://{}:{}/rpc".format(self._host, self._port)

        self._payload_id += 1
        payload_id = self._payload_id
        payload = {
            "jsonrpc": "2.0",
            "id": payload_id,
            "method": endpoint,
        }

        if values:
            payload["params"] = values

        credentials = None
        try:
            credentials = auth=HTTPDigestAuth('admin', self._credentials[1])
        except IndexError:
            pass

        response = post(url, auth=credentials, json=payload, timeout=self._timeout)
        if response.status_code == 401:
            raise PermissionError()
        elif response.status_code == 404:
            raise LookupError("{endpoint} not found")

        try:
            response_data = response.json()
        except JSONDecodeError:
            raise ValueError("Unexpected response: can't decode JSON")

        if "error" in response_data:
            error_code = response_data["error"].get("code", None)
            error_message = response_data["error"].get("message", "")

            if error_code == 401:
                raise PermissionError(error_message)
            elif error_code == 404:
                raise LookupError(error_message)
            else:
                raise ValueError("{}: {}".format(error_code, error_message))

        if response_data["id"] != payload_id:
            raise KeyError("invalid payload id was returned")

        return response_data.get("result", {})

    def test_invoke(self, method):
        res = self.post(method)
        return json.dumps(res, indent=2)

class ShellyPlug(ShellyGen2):
    def __init__(self, host, *args, **kwargs):
        super().__init__(host, *args, **kwargs)
        self._host = host
        self._stats = None
        self._device_cfg = {}
        self.update_device_config()

    def update_device_config(self):
        try:
            self._device_cfg = self.post("Switch.GetConfig", {"id": 0})
        except (RequestException, PermissionError, LookupError, ValueError, KeyError):
            self._device_cfg = {}
        if "name" not in self._device_cfg:
            self._device_cfg["name"] = self._host

    def get_name(self):
        return self._device_cfg["name"]

    def get_stats(self):
        stats = self.post("Shelly.GetStatus")
        switch = stats.get("switch:0", {})
        sys_stats = stats.get("sys", {})
        wifi = stats.get("wifi", {})

        self._stats = {
            "device_name": self.get_name(),
            "powered_on": switch.get("output"),
            "active_power_watts": switch.get("apower"),
            "voltage_volts": switch.get("voltage"),
            "current_amps": switch.get("current"),
            "temperature_c": switch.get("temperature", {}).get("tC"),
            "lifetime_energy_use_watt_hour": switch.get("aenergy", {}).get("total"),
            "last_minute_energy_use_watt_hour": switch.get("aenergy", {}).get("by_minute", [None])[0],
            "device_current_time": sys_stats.get("time"),
            "device_uptime": sys_stats.get("uptime"),
            "device_ip": wifi.get("sta_ip"),
        }
        return self._stats
