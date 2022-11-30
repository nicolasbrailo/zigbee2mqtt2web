import logging
logger = logging.getLogger('zigbee2mqtt2flask.thing')

import json
import time
import traceback
from apscheduler.schedulers.background import BackgroundScheduler

from .geo_helper import light_outside
from .geo_helper import late_night

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
            return True
        return x

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

    def light_toggle(self, brightness=None):
        if brightness is None:
            return super().light_toggle()

        if self.is_on == True:
            self.light_off()
        else:
            self.set_brightness(brightness)


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

        return s

    def handle_action(self, action, msg):
        logger.notice("Thing {} action {} implements no handler".format(self.get_id(), action))


class XiaomiContactSensor(BatteryPoweredThing):
    def __init__(self, mqtt_id):
        super().__init__(mqtt_id)
        self.contact = None
        self.temperature = None
        self.voltage = None

    def json_status(self):
        s = super().json_status()
        s.update({'contact': self.contact})
        s.update({'temperature': self.temperature})
        s.update({'voltage': self.voltage})
        return s

    def consume_message(self, topic, msg):
        contact_chg = False
        if 'contact' in msg:
            if self.contact != msg['contact']:
                contact_chg = True
            self.contact = msg['contact']
        if 'temperature' in msg:
            self.temperature = msg['temperature']
        if 'voltage' in msg:
            self.voltage = msg['voltage']

        if contact_chg:
            if self.contact:
                self.on_close()
            else:
                self.on_open()

        return True

    def on_close(self):
        pass

    def on_open(self):
        pass


class DoorOpenSensor(XiaomiContactSensor):
    def __init__(self, mqtt_id, door_open_timeout_secs):
        super().__init__(mqtt_id)
        self.door_open_timeout_secs = door_open_timeout_secs
        self.door_open = None
        self._scheduler = None
        self._bg = None

    def on_close(self):
        if self.door_open is not None and not self.door_open:
            logger.error("Error: duplicated door close event?")

        self.door_open = False

        if self._bg is None:
            logger.error("Error: door warden never started")
        else:
            self._bg.remove()
            self._bg = None

        self._scheduler = None

        self.door_closed()


    def on_open(self):
        if self.door_open:
            logger.error("Error: duplicated door open event?")

        self.door_open = True

        if self._scheduler is not None:
            logger.info("Error: duplicated on_open events?")
            self._scheduler = None

        if self._bg is not None:
            logger.info("Error: duplicated on_open events?")
            self._bg.remove()
            self._bg = None

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        self._bg = self._scheduler.add_job(
                       func=self._door_warden_timeout,
                       trigger="interval",
                       seconds=self.door_open_timeout_secs)

        self.door_opened()

    def _door_warden_timeout(self):
        self.door_open_timeout()


class MultiIkeaMotionSensor(Thing):
    """ A wrapper for Ikea motion sensors. Can wrap multiple motion sensors into one group.
        Will trigger an active event if any sensor is active, and a cleared event when all
        sensors are marked non active. """

    class SensorImpl(BatteryPoweredThing):
        def __init__(self, world, mqtt_id, on_occupant_entered, on_occupant_left):
            super().__init__(mqtt_id)
            logger.info(f"Registering thing {mqtt_id}")
            world.register_thing(self)
            self.on_occupant_entered = on_occupant_entered
            self.on_occupant_left = on_occupant_left
            self.name = mqtt_id
            self.occupied = False

        def consume_message(self, topic, msg):
            if 'occupancy' in msg:
                if msg['occupancy']:
                    self.on_occupant_entered()
                    self.occupied = True
                else:
                    self.on_occupant_left()
                    self.occupied = False
                return True

            return False

        def json_status(self):
            return {'name': self.name, 'active': self.occupied}

    def json_status(self):
        active = False
        sensors_stats = []
        for s in self._sensors:
            if s.occupied:
                active = True
            sensors_stats.append(s.json_status())
        return {'group_active': active, 'sensors_status': sensors_stats}

    def __init__(self, world, mqtt_ids):
        super().__init__('MultiSensor' + '_'.join(mqtt_ids))
        self._sensors = []
        for mqtt_id in mqtt_ids:
            self._sensors.append(MultiIkeaMotionSensor.SensorImpl(world, mqtt_id, self._on_occupant_entered, self._on_occupant_left))

        self._scheduler = BackgroundScheduler()
        self._bg = None
        self._scheduler.start()
        # Ikea motion sensors seem to use 150ish seconds as their refresh period
        self.timeout_secs = 150

    def _on_occupant_entered(self):
        self._maybe_cancel_timeout()
        self._bg = self._scheduler.add_job(func=self._timeout,
                               trigger="interval", seconds=self.timeout_secs)
        self.activity_detected()

    def _on_occupant_left(self):
        for sensor in self._sensors:
            if sensor.occupied:
                return
        # All sensors are marked as cleared
        self._maybe_cancel_timeout()
        self.all_vacant()

    def _maybe_cancel_timeout(self):
        if self._bg is not None:
            self._bg.remove()
            self._bg = None

    def _timeout(self):
        self._maybe_cancel_timeout()
        self.activity_timeout()

    def activity_detected(self):
        pass

    def all_vacant(self):
        pass

    def activity_timeout(self):
        pass


class MotionActivatedNightLight(MultiIkeaMotionSensor):
    def __init__(self, lat, lon, late_night_start_hr, world, sensor_mqtt_ids, light):
        super().__init__(world, sensor_mqtt_ids)
        self.light = light
        self.light_on_because_activity = False
        self.lat = lat
        self.lon = lon
        self.late_night_start_hr = late_night_start_hr
        self.off_during_daylight = True
        self.high_brightness_pct = 40
        self.low_brightness_pct = 5

    def always_off_during_daylight(self, v):
        self.off_during_daylight = v

    def activity_detected(self):
        # Only trigger if the light wasn't on before (eg manually)
        if self.light.is_on:
            return

        if self.off_during_daylight and light_outside(self.lat, self.lon):
            return

        logger.info("MotionActivatedLight on activity_detected")
        brightness = self.high_brightness_pct
        if late_night(self.lat, self.lon, self.late_night_start_hr):
            brightness = self.low_brightness_pct

        self.light_on_because_activity = True
        self.light.set_brightness(brightness)

    def all_vacant(self):
        logger.info("MotionActivatedLight on all_vacant")
        if self.light_on_because_activity:
            self.light_on_because_activity = False
            self.light.light_off()

    def activity_timeout(self):
        logger.info("MotionActivatedLight on timeout")
        self.all_vacant()


class MultiThing:
    def __init__(self, group_id, typeofthing, mqtt_ids, mqtt_broadcaster):
        self.typeofthing = typeofthing
        self.group_id = group_id
        self.things = []
        for mqtt_id in mqtt_ids:
            try:
                self.things.append(typeofthing(mqtt_id, mqtt_broadcaster))
            except TypeError as ex:
                print("Can't build thing of type {}, bad ctor".format(str(typeofthing)))
                raise ex

    def get_id(self):
        return self.group_id

    def __getattr__(self, name):
        def funcwrapper(*args, **kwargs):
            last_ex = None
            last_res = None
            first_call = True
            for obj in self.things:
                # Try to find method on this sub-thing; all sub things should be the same type, so fail all calls if this fails
                f = None
                try:
                    f = getattr(obj, name)
                except AttributeError as ex:
                    print("Thing {}: Method {}.{} doesn't exist".format(self.group_id, self.typeofthing, name))
                    raise ex
                except TypeError as ex:
                    print("Thing {}: Can't call {}.{} for the supplied args".format(self.group_id, self.typeofthing, name))
                    raise ex

                # Invoke method on sub-thing. If one fails, continue executing and raise error on last one.
                this_res = None
                try:
                    this_res = f(*args, **kwargs)
                except Exception as ex:
                    print("Thing {}: Exception on {}.{} for sub-thing {}".format(self.group_id, self.typeofthing, name, obj.get_id()))
                    print(traceback.format_exc())
                    last_ex = ex

                # All ret vals should be the same, otherwise we don't know how to wrap this. Default to returning
                # whatever was last + printing an error
                if first_call:
                    first_call = False
                else:
                    if last_res != this_res:
                        pass
                    last_res = this_res

            # If there were errors, pick an arbitrary exception to raise
            if last_ex is not None:
                raise last_ex

            # If there were no errors, pick an arbitrary value to return. Hopefully all values are the same
            return last_res

        # Pretend everything is fine if we don't wrap any objects
        if len(self.things) == 0:
            return None

        # Requested a function-like member, wrap it
        if callable(getattr(self.things[0], name)):
            return funcwrapper

        # Requested a variable-like member, read all of them in case there are side-effects and return the last
        val = None
        for obj in self.things:
            val = getattr(obj, name)
        return val


def any_light_on(world, lst):
    for name in lst:
        if world.get_thing_by_name(name).is_on:
            return True
    return False

def light_group_toggle(world, grp):
    things = [name for name,_ in grp]
    if any_light_on(world, things):
        for name,brightness in grp:
            world.get_thing_by_name(name).light_off()
    else:
        for name,brightness in grp:
            world.get_thing_by_name(name).set_brightness(brightness)


