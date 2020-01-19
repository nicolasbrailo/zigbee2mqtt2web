import logging
logger = logging.getLogger('zigbee2mqtt2flask.thing')

import json
import time

class Thing(object):
    def __init__(self, thing_id):
        self.thing_id = thing_id

    def get_id(self):
        return self.thing_id

    def json_status(self):
        raise Exception("Subclass responsibility")

    def supported_actions(self):
        return ['json_status']


class MqttThing(Thing):
    def __init__(self, mqtt_id):
        super().__init__(mqtt_id)
        self.link_quality = None

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['mqtt_status'])
        return s

    def mqtt_status(self):
        return self.json_status()

    def json_status(self):
        return {'link_quality': self.link_quality}
        
    def consume_message(self, topic, msg):
        """ Return True if message was understood """

        if 'linkquality' in msg:
            self.link_quality = msg['linkquality']
            return True
        return False


class BatteryPoweredThing(MqttThing):
    def __init__(self, mqtt_id):
        super().__init__(mqtt_id)
        self.battery_level = None

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
    def __init__(self, mqtt_id, mqtt_broadcaster):
        super().__init__(mqtt_id)
        self.is_on = None
        self.mqtt_broadcaster = mqtt_broadcaster

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['light_on', 'light_off', 'light_toggle'])
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

    def light_on(self, broadcast_update=True):
        self.is_on = True
        if broadcast_update:
            self.broadcast_new_state()

    def light_off(self, broadcast_update=True):
        self.is_on = False
        if broadcast_update:
            self.broadcast_new_state()

    def light_toggle(self):
        if self.is_on == True:
            self.light_off()
        else:
            # If is_on was None (unknown) assume it was off
            self.light_on()

    def broadcast_new_state(self, transition_time=None):
        topic = self.get_id() + '/set'
        cmd = self.mqtt_status()
        if transition_time is not None:
            cmd['transition'] = transition_time
        self.mqtt_broadcaster.broadcast(topic, json.dumps(cmd))


class DimmableLamp(Lamp):
    def __init__(self, mqtt_id, mqtt_broadcaster):
        super().__init__(mqtt_id, mqtt_broadcaster)
        self.brightness = None # 0-100, phys => 0-255
        self.brightness_change_delta_pct = 20

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['set_brightness', 'brightness_up', 'brightness_down'])
        return s

    def mqtt_status(self):
        s = super().mqtt_status()
        if s['state'] == 'ON' and self.brightness is not None:
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

    def set_brightness(self, pct, broadcast_update=True):
        pct = int(pct)
        if pct < 0 or pct > 100:
            raise Exception('Unexpected brightness %: {} (should be 0-100)'.format(pct))

        self.brightness = pct

        if self.brightness == 0:
            self.light_off(broadcast_update=False)
        else:
            self.light_on(broadcast_update=False)

        if broadcast_update:
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

from .color_lamp_rgb_converter import rgb_to_xy
class ColorDimmableLamp(DimmableLamp):
    def __init__(self, mqtt_id, mqtt_broadcaster):
        super().__init__(mqtt_id, mqtt_broadcaster)
        self.rgb = None

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['set_rgb'])
        return s

    def mqtt_status(self):
        s = super().mqtt_status()
        if self.rgb is not None:
            try:
                xy = rgb_to_xy(self.rgb)
                s['color'] = {'x': xy[0], 'y': xy[1]}
            except ZeroDivisionError:
                logger.error("Lamp {} ignoring invalid color {}".format(self.get_id(), self.rgb))
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

    def set_rgb(self, html_rgb_triple, broadcast_update=True):
        self.rgb = bytes.fromhex(html_rgb_triple)
        if broadcast_update:
            self.broadcast_new_state()

class ColorTempDimmableLamp(DimmableLamp):
    def __init__(self, mqtt_id, mqtt_broadcaster):
        super().__init__(mqtt_id, mqtt_broadcaster)
        self.color_temp = None

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['set_color_temp'])
        return s

    def mqtt_status(self):
        s = super().mqtt_status()
        if self.color_temp is not None:
            # Lamps seem to dislike setting temperature and color. First set one, then the other
            topic = self.get_id() + '/set'
            self.mqtt_broadcaster.broadcast(topic, json.dumps(s))
            # Reset msg
            s = {}
            s['color_temp'] = self.color_temp
            time.sleep(1)
        return s

    def json_status(self):
        s = super().json_status()
        s['color_temp'] = self.color_temp
        return s

    def consume_message(self, topic, msg):
        s = super().consume_message(topic, msg)

        if 'color_temp' in msg:
            self.set_color_temp(msg['color_temp'], False)
            return True

        return s

    def set_color_temp(self, color_temp, broadcast_update=True):
        try:
            self.color_temp = int(color_temp)
        except:
            self.color_temp = 0

        if broadcast_update:
            self.broadcast_new_state()


class Button(BatteryPoweredThing):
    def __init__(self, mqtt_id):
        super().__init__(mqtt_id)

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
        logger.notice("Thing {} action {} implements no handler".format(self.get_id(), action))


