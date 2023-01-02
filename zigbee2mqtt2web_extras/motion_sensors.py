""" Extras to describe the behaviour of motion sensors """

from apscheduler.schedulers.background import BackgroundScheduler

from .geo_helper import light_outside
from .geo_helper import late_night

import logging
logger = logging.getLogger(__name__)


class MultiMotionSensor:
    """ Wraps multiple motion sensors and exposes two callbacks:
    * When any of the sensors first transitions from inactive to active
    * When all of the sensors transition from active to inactive
    """

    def __init__(self, registry, sensor_names, timeout_secs=None):
        self._registry = registry
        self._sensor_names = sensor_names
        self._active = False

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        self._bg_job = None
        # Ikea motion sensors seem to use 180ish seconds as their refresh period
        # so that's a reasonable default
        self._timeout_secs = 200 if timeout_secs is None else timeout_secs

        def build_cb(sensor_name):
            def callback(occupied):
                return self._on_activity(sensor_name, occupied)
            return callback

        for sensor_name in self._sensor_names:
            registry.get_thing(sensor_name).actions['occupancy'] \
                    .value.on_change_from_mqtt = build_cb(sensor_name)

    def _on_activity(self, sensor_name, occupied):
        if occupied:
            if not self._active:
                logger.debug('Register activity on %s', sensor_name)
                self._active = True
                self._start_watchdog()
                self.on_activity_detected()
            else:
                logger.debug(
                    'Register activity on %s, multiple sensors active',
                    sensor_name)
                self._pet_watchdog()
        else:
            if self._active:
                if self.all_sensors_clear():
                    logger.debug(
                        'Cleared activity on %s and all sensors clear',
                        sensor_name)
                    self._active = False
                    self._stop_watchdog()
                    self.on_activity_cleared()
                else:
                    logger.debug(
                        'Cleared activity on %s, but other sensors are active',
                        sensor_name)
            else:
                # A sensor may send periodic 'no one is here' pings, so we can
                # just ignore these
                logger.debug(
                    'Cleared activity on %s but no longer active '
                    '(sensor reported after timeout of %d seconds?)',
                    sensor_name,
                    self._timeout_secs)

    def _start_watchdog(self):
        """ Called when first active, to start up a timer that will detect a
        timeout (eg the all-clear message was posted by the sensor, but it got
        lost in transit """
        if self._bg_job is not None:
            logger.warning(
                'Error: starting watchdog, but another watchdog is already active')
            self._bg_job.remove()

        self._bg_job = self._scheduler.add_job(
            func=self._watchdog_timeout,
            trigger="interval",
            seconds=self._timeout_secs)

    def _stop_watchdog(self):
        """ Called when all sensors have reported cleared, and there is no
        need for a watchdog anymore """
        self._bg_job.remove()
        self._bg_job = None

    def _pet_watchdog(self):
        """ Called when a new wrapped sensor reports as active, so that the
        timeout gets pushed to the maximum possible timeout (of the latest
        active sensor """
        self._stop_watchdog()
        self._start_watchdog()

    def _watchdog_timeout(self):
        logger.warning(
            'Error: sensor timeout %s',
            ','.join(
                self._sensor_names))
        self._active = False
        self._stop_watchdog()
        self.on_timeout()

    def all_sensors_clear(self):
        """ True if none of the sensors register activity """
        for name in self._sensor_names:
            occupancy = self._registry.get_thing(name).get('occupancy')
            if occupancy:
                return False
        return True

    def on_activity_detected(self):
        """ Called when activity is first detected on any of the wrapped sensors """
        logger.debug(
            'MultiSensor active. You should override this and do something useful')

    def on_activity_cleared(self):
        """ Called when all of the wrapped sensors no longer report active """
        logger.debug(
            'MultiSensor cleared. You should override this and do something useful')

    def on_timeout(self):
        """ Called when the group becomes active, but there is all-clear received after
        the configured timeout """
        logger.debug(
            'MultiSensor timeout. You should override this and do something useful')


class MotionActivatedNightLight:
    """ Takes control of $light when $motion_sensor becomes active. It will manage
    the light (only if the user hasn't explicitly set a value for this light) when
    it's dark outside, and when there is motion detected in a MultiMotionSensor """

    def __init__(self, registry, motion_sensor, light, latlon):
        if isinstance(motion_sensor, type([])):
            motion_sensor = MultiMotionSensor(registry, motion_sensor)

        if isinstance(light, str):
            light = registry.get_thing(light)

        motion_sensor.on_activity_detected = self._on_activity_detected
        motion_sensor.on_activity_cleared = self._on_activity_cleared
        motion_sensor.on_timeout = self._on_timeout
        self.sensor = motion_sensor

        self._light_on_because_activity = False
        self._light = light
        self._registry = registry

        # Used to determine if it's light outside or not
        self._latlon = latlon

        self._cfg = {
            # Turn on to enable this light even during daytime
            'off_during_daylight': True,
            # Manage this light only while early in the night, not late
            'off_during_late_night': False,
            # Brightness level during evening
            'high_brightness_pct': 40,
            # Brightness level during late night
            'low_brightness_pct': 5,
            # After this time, the light will turn on with its dimmest setting
            'late_night_start_hr': 23,
        }

    def managing_light(self):
        """ True if the managed light is on because of movement """
        return self._light_on_because_activity

    def configure(self, key, value):
        """ Hackish way of configuring """
        self._cfg[key] = value

    def _on_activity_detected(self):
        if self._light.is_light_on():
            logger.debug(
                'MotionActivatedNightLight activity detected, but light is managed by user')
            # This light is being managed by the user, ignore
            return

        if self._cfg['off_during_daylight'] and light_outside(self._latlon):
            logger.debug(
                'MotionActivatedNightLight activity detected, but there is light outside')
            return

        is_late_night = late_night(
            self._latlon, self._cfg['late_night_start_hr'])
        if self._cfg['off_during_late_night'] and is_late_night:
            logger.debug(
                'MotionActivatedNightLight activity detected, but it\'s late '
                'and we don\'t manage the light at late night')
            return

        logger.debug(
            'MotionActivatedNightLight activity detected, will turn on %s',
            self._light.name)
        brightness = self._cfg['high_brightness_pct']
        if is_late_night:
            brightness = self._cfg['low_brightness_pct']

        self._light_on_because_activity = True
        self._light.set_brightness_pct(brightness)
        self._registry.broadcast_thing(self._light)

    def _on_activity_cleared(self):
        if not self._light_on_because_activity:
            logger.debug(
                'MotionActivatedNightLight cleared for %s but not managing light',
                self._light.name)
        else:
            logger.debug(
                'MotionActivatedNightLight cleared and managing light, will turn off %s',
                self._light.name)
            self._light_on_because_activity = False
            self._light.turn_off()
            self._registry.broadcast_thing(self._light)

    def _on_timeout(self):
        logger.warning(
            'MotionActivatedNightLight timeout for %s',
            self._light.name)
        self._on_activity_cleared()
