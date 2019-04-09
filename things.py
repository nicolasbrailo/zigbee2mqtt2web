import json

class Thing(object):
    def __init__(self, pretty_name):
        self.pretty_name = pretty_name
        self.link_quality = None

    def describe_capabilities(self):
        return {'thing_types': self.thing_types(),
                'supported_actions': self.supported_actions()}

    def thing_types(self):
        return []

    def supported_actions(self):
        return []

    def json_status(self):
        return {'link_quality': self.link_quality}
        
    def on_message(self, topic, msg):
        if 'linkquality' in msg:
            self.link_quality = msg['linkquality']


class BatteryPoweredThing(Thing):
    def __init__(self, pretty_name):
        super().__init__(pretty_name)
        self.battery_level = None

    def thing_types(self):
        s = super().thing_types()
        s.extend(['battery_powered'])
        return s

    def json_status(self):
        s = super().json_status()
        s.update({'battery_level': self.battery_level})
        return s
        
    def on_message(self, topic, msg):
        super().on_message(topic, msg)
        if 'battery' in msg:
            self.battery_level = msg['battery']

class Lamp(Thing):
    def __init__(self, pretty_name, mqtt):
        super().__init__(pretty_name)
        self.is_on = None
        self.mqtt = mqtt

    def thing_types(self):
        s = super().thing_types()
        s.extend(['lamp'])
        return s

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['turn_on', 'turn_off', 'toggle'])
        return s

    def json_status(self):
        s = super().json_status()
        s['is_on'] = self.is_on
        return s

    def mqtt_status(self):
        return {'state': 'ON' if self.is_on else 'OFF'}

    def on_message(self, topic, msg):
        super().on_message(topic, msg)

        if topic.lower().endswith('/config'):
            # Received tconfig when 1st connecting. No use for it so far:
            # since everything is setup by hand the capabilities of each device
            # are already known
            self.config = msg

        if 'state' in msg:
            self.is_on = (msg['state'] == 'ON')

    def turn_on(self, broadcast_update=True):
        self.is_on = True
        self.broadcast_new_state()

    def turn_off(self, broadcast_update=True):
        self.is_on = False
        self.broadcast_new_state()

    def toggle(self):
        if self.is_on == True:
            self.turn_off()
        else:
            # If is_on was None (unknown) assume it was off
            self.turn_on()

    def broadcast_new_state(self):
        self.mqtt.send_message_to_thing(self.pretty_name, json.dumps(self.mqtt_status()))


class DimmableLamp(Lamp):
    def __init__(self, pretty_name, mqtt):
        super().__init__(pretty_name, mqtt)
        self.brightness = None # 0-100, mqtt => 0-255
        self.brightness_change_delta_pct = 20

    def thing_types(self):
        s = super().thing_types()
        s.extend(['dimmable'])
        return s

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['set_brightness', 'brightness_up', 'brightness_down'])
        return s

    def mqtt_status(self):
        s = super().mqtt_status()
        if self.brightness is not None:
            s['brightness'] = int(self.brightness / 100.0 * 255)
        return s

    def json_status(self):
        s = super().json_status()
        if self.brightness is not None:
            s['brightness'] = self.brightness
        else:
            s['brightness'] = None
        return s

    def on_message(self, topic, msg):
        super().on_message(topic, msg)

        if 'brightness' in msg:
            self.brightness = int(int(msg['brightness']) / 255 * 100)

    def set_brightness(self, pct):
        if pct < 0 or pct > 100:
            raise Exception('Unexpected brightness %: {} (should be 0-100)'.format(pct))

        self.brightness = pct

        if self.brightness == 0:
            self.turn_off(broadcast_update=False)
        else:
            self.turn_on(broadcast_update=False)

        self.broadcast_new_state()

    def brightness_up(self):
        self._chg_brightness(+1)

    def brightness_down(self):
        self._chg_brightness(-1)

    def _chg_brightness(self, direction):
        if self.brightness is None:
            self.brightness = 0

        new_brightness = self.brightness + int(direction * self.brightness_change_delta_pct)
        if new_brightness > 100:
            new_brightness = 100
        if new_brightness < 0:
            new_brightness = 0

        self.set_brightness(new_brightness)


class Button(BatteryPoweredThing):
    def __init__(self, pretty_name):
        super().__init__(pretty_name)

    def thing_types(self):
        s = super().thing_types()
        s.extend(['button'])
        return s

    def on_message(self, topic, msg):
        super().on_message(topic, msg)

        if topic.lower().endswith('/config'):
            # Received thing config when 1st connecting. No use for it so far:
            # since everything is setup by hand the capabilities of each device
            # are already known
            self.config = msg
            return

        if 'action' in msg:
            self.handle_action(msg['action'], msg)
            return

        print("RCV UNKNOWN BUTTON MSG: ", topic, msg)

    def handle_action(self, action, msg):
        print(self.pretty_name, ": default handler for action ", action)


