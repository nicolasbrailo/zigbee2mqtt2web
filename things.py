import json

class Thing(object):
    def __init__(self, thing_id, pretty_name):
        self.thing_id = thing_id
        self.pretty_name = pretty_name

    def get_id(self):
        return self.thing_id

    def get_pretty_name(self):
        return self.pretty_name

    def describe_capabilities(self):
        return {'thing_types': self.thing_types(),
                'supported_actions': self.supported_actions()}

    def json_status(self):
        raise Exception("Subclass responsibility")

    def thing_types(self):
        raise Exception("Subclass responsibility")

    def supported_actions(self):
        raise Exception("Subclass responsibility")


class MqttThing(Thing):
    def __init__(self, mqtt_id, pretty_name):
        super().__init__(mqtt_id, pretty_name)
        self.link_quality = None

    def thing_types(self):
        return ['mqtt']

    def supported_actions(self):
        return []

    def json_status(self):
        return {'link_quality': self.link_quality}
        
    def consume_message(self, topic, msg):
        """ Return True if message was understood """

        if 'linkquality' in msg:
            self.link_quality = msg['linkquality']
            return True
        return False


class BatteryPoweredThing(MqttThing):
    def __init__(self, mqtt_id, pretty_name):
        super().__init__(mqtt_id, pretty_name)
        self.battery_level = None

    def thing_types(self):
        s = super().thing_types()
        s.extend(['battery_powered'])
        return s

    def json_status(self):
        s = super().json_status()
        s.update({'battery_level': self.battery_level})
        return s
        
    def consume_message(self, topic, msg):
        x = super().consume_message(topic, msg)
        if 'battery' in msg:
            self.battery_level = msg['battery']
        return x or 'battery' in msg

class Lamp(MqttThing):
    def __init__(self, mqtt_id, pretty_name, mqtt_broadcaster):
        super().__init__(mqtt_id, pretty_name)
        self.is_on = None
        self.mqtt_broadcaster = mqtt_broadcaster

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

    def consume_message(self, topic, msg):
        if topic.lower().endswith('/config'):
            # Received tconfig when 1st connecting. No use for it so far:
            # since everything is setup by hand the capabilities of each device
            # are already known
            self.config = msg
            return True

        s = super().consume_message(topic, msg)

        if 'state' in msg:
            self.is_on = (msg['state'] == 'ON')
            return True

        return s

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
        topic = self.get_id() + '/set'
        self.mqtt_broadcaster.broadcast(topic, json.dumps(self.mqtt_status()))


class DimmableLamp(Lamp):
    def __init__(self, mqtt_id, pretty_name, mqtt_broadcaster):
        super().__init__(mqtt_id, pretty_name, mqtt_broadcaster)
        self.brightness = None # 0-100, phys => 0-255
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

    def consume_message(self, topic, msg):
        s = super().consume_message(topic, msg)

        if 'brightness' in msg:
            new_brightness = int(int(msg['brightness']) / 255 * 100)
            if self.brightness is not None and \
                    abs(new_brightness - self.brightness) <= 1:
                # Probably a rounding error between float/int, ignore
                pass
            else:
                self.brightness = new_brightness
            return True

        return s

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

from color_lamp_rgb_converter import rgb_to_xy
class ColorDimmableLamp(DimmableLamp):
    def __init__(self, mqtt_id, pretty_name, mqtt_broadcaster):
        super().__init__(mqtt_id, pretty_name, mqtt_broadcaster)
        self.rgb = None

    def thing_types(self):
        s = super().thing_types()
        s.extend(['color'])
        return s

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['set_rgb'])
        return s

    def mqtt_status(self):
        s = super().mqtt_status()
        if self.rgb is not None:
            xy = rgb_to_xy(self.rgb)
            s['color'] = {'x': xy[0], 'y': xy[1]}
        return s

    def json_status(self):
        s = super().json_status()
        if self.rgb:
            r,g,b = self.rgb
            html_triple = format(r<<16 | g<<8 | b, '06x')
            s['rgb'] = html_triple
        else:
            s['rgb'] = None
        return s

    def consume_message(self, topic, msg):
        s = super().consume_message(topic, msg)

        if 'color' in msg:
            # TODO: XY to RGB not supported
            return True

        return s

    def set_rgb(self, html_rgb_triple):
        self.rgb = bytes.fromhex(html_rgb_triple)
        self.broadcast_new_state()


class Button(BatteryPoweredThing):
    def __init__(self, mqtt_id, pretty_name):
        super().__init__(mqtt_id, pretty_name)

    def thing_types(self):
        s = super().thing_types()
        s.extend(['button'])
        return s

    def consume_message(self, topic, msg):
        if topic.lower().endswith('/config'):
            # Received thing config when 1st connecting. No use for it so far:
            # since everything is setup by hand the capabilities of each device
            # are already known
            self.config = msg
            return True

        s = super().consume_message(topic, msg)

        if 'action' in msg:
            self.handle_action(msg['action'], msg)
            return True

        return False

    def handle_action(self, action, msg):
        print(self.pretty_name, ": default handler for action ", action)


