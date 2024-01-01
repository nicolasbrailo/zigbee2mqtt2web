""" Main door monitor: monitors a contact sensor, and when an open-door even is triggered it will
start a leaving routine (turn on lights for a period of time) and make an announcement over
speakers """

import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from zigbee2mqtt2web_extras.utils.geo_helper import light_outside

import logging
logger = logging.getLogger('MainDoorMonitor')


def _validate_cfg(cfg):
    # Check we have must-have keys
    cfg['contact_sensor_name']  # pylint: disable=pointless-statement
    cfg['on_contact_action_name']  # pylint: disable=pointless-statement
    cfg['lat_lon']  # pylint: disable=pointless-statement

    if (cfg['sonos_name'] is None) != (cfg['chime_url'] is None):
        raise KeyError(
            'MainDoorMonitor bad config: sonos_name and chime_url must be both null or both'
            'non-null')

    if 'skip_chime_timeout_secs' not in cfg:
        cfg['skip_chime_timeout_secs'] = 300

    if 'leaving_routine_timeout_secs' not in cfg:
        cfg['leaving_routine_timeout_secs'] = 180
    return cfg


class MainDoorMonitor:
    """ When a contact sensor opens, will play a chime on Sonos and activate a set of lights for a
    period of time """

    def __init__(self, zmw, cfg):
        self.cfg = _validate_cfg(cfg)
        self._zmw = zmw
        self._play_door_open_chime = True
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        self._skip_chime_bg = None
        self._leaving_routine_bg = None
        self.active_managed_lamps = []

        thing = zmw.registry.get_thing(self.cfg['contact_sensor_name'])
        thing.actions[self.cfg['on_contact_action_name']
                      ].value.on_change_from_mqtt = self._on_state_report

    def _on_state_report(self, has_contact):
        if has_contact:
            logger.info(
                '%s: main door closed',
                self.cfg['contact_sensor_name'])
        else:
            if not light_outside(self.cfg['lat_lon']):
                logger.info(
                    '%s: main door open and is dark out, trigger leaving routine',
                    self.cfg['contact_sensor_name'])
                self.trigger_leaving_routine()
            else:
                logger.info(
                    '%s: main door open',
                    self.cfg['contact_sensor_name'])
            self._door_open_announce_and_block()

    def _door_open_announce_and_block(self):
        if self._play_door_open_chime is True:
            logger.info('Door open, announcing...')
            self._zmw.registry.get_thing(
                self.cfg['sonos_name']).play_announcement(
                self.cfg['chime_url'], timeout_secs=20)
        else:
            logger.info("Door open, but we're skipping announcing...")

    def skip_next_door_open_chime(self):
        """ If the next open-door event happens within a timeout, the speaker announcement will be
        skipped """
        logger.info('Door chime will skip on door-open event for %s seconds',
                    self.cfg["skip_chime_timeout_secs"])
        self._play_door_open_chime = False

        def restore_door_open_chime():
            logger.info('Door chime will play on next door-open event')
            self._play_door_open_chime = True
            self._skip_chime_bg = None

        if self._skip_chime_bg is not None:
            logger.info(
                '(We were already skipping chimes, adding more timeout)')
            self._skip_chime_bg.remove()

        self._skip_chime_bg = self._scheduler.add_job(
            func=restore_door_open_chime,
            next_run_time=datetime.datetime.now() +
            datetime.timedelta(
                seconds=self.cfg['skip_chime_timeout_secs']))

    def trigger_leaving_routine(self):
        """ Force the leaving routine to start (ie turn on lights for some time) """
        logger.info('Starting leaving routine')

        if self._leaving_routine_bg is not None:
            logger.info(
                '(Leaving routine already active: adding more timeout)')
            self._leaving_routine_bg.remove()
        else:
            # Only rebuild the active_managed_lamps list when a new leaving
            # routine is triggered, to avoid inconsistencies
            for thing_name, pct in self.cfg['managed_lamps']:
                thing = self._zmw.registry.get_thing(thing_name)
                if thing.is_light_on():
                    logger.info(
                        "Light %s is already on, won't use it for leaving routine",
                        thing_name)
                else:
                    logger.info(
                        "Light %s is managed by the leaving routine",
                        thing_name)
                    thing.set_brightness_pct(pct)
                    self.active_managed_lamps.append(thing_name)
            self._zmw.registry.broadcast_things(self.active_managed_lamps)

        def leaving_routine_timeout():
            logger.info('Leaving routine complete, shutdown managed devices')
            for thing_name in self.active_managed_lamps:
                self._zmw.registry.get_thing(thing_name).turn_off()
            self._zmw.registry.broadcast_things(self.active_managed_lamps)
            self.active_managed_lamps = []
            self._leaving_routine_bg = None

        self._leaving_routine_bg = self._scheduler.add_job(
            func=leaving_routine_timeout,
            next_run_time=datetime.datetime.now() +
            datetime.timedelta(
                seconds=self.cfg['leaving_routine_timeout_secs']))
