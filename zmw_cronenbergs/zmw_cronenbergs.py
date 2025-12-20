"""Cronenberg service for scheduled home automation tasks."""
import json
import os
import pathlib
from datetime import datetime
from collections import deque

from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.zmw_mqtt_service import ZmwMqttServiceNoCommands
from zzmw_lib.logs import build_logger

from zz2m.z2mproxy import Z2MProxy
from zz2m.light_helpers import turn_all_lights_off

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = build_logger("ZmwCronenbergs")


class ZmwCronenbergs(ZmwMqttServiceNoCommands):
    """
    Scheduled tasks service. Runs calendar-based automation like:
    - Turning off lights at specific times
    - Sending notifications about scheduled events
    """

    def __init__(self, cfg, www):
        super().__init__(cfg, svc_deps=['ZmwTelegram'])
        self._z2m = Z2MProxy(cfg, self)

        self._light_check_history = deque(maxlen=10)

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)
        www.serve_url('/stats', self._get_stats)
        www.serve_url('/mock_auto_lights_off', self._mock_auto_lights_off)

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

        # Schedule automatic lights off if configured
        if 'auto_lights_off' in cfg and cfg['auto_lights_off']['enable']:
            day_of_week = cfg['auto_lights_off']['day_of_week']
            time_parts = cfg['auto_lights_off']['time'].split(':')
            hour, minute = int(time_parts[0]), int(time_parts[1])
            log.info(f"Scheduling light check for {day_of_week} at {hour:02d}:{minute:02d}")
            self._scheduler.add_job(
                self._check_and_turn_off_lights,
                trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, second=0),
                id='auto_lights_off'
            )

        self._vacations_mode = 'vacations_mode' in cfg and cfg['vacations_mode']['enable']
        if self._vacations_mode:
            log.info("Vacations mode enabled, scheduling light effects")
            for job_name in ['late_afternoon', 'evening', 'night']:
                time_parts = cfg['vacations_mode'][job_name].split(':')
                hour, minute = int(time_parts[0]), int(time_parts[1])
                method = getattr(self, f'_vacations_mode_{job_name}')
                self._scheduler.add_job(
                    method,
                    trigger=CronTrigger(hour=hour, minute=minute, second=0),
                    id=f'vacations_mode_{job_name}'
                )

        self._speaker_announce = cfg.get('speaker_announce', [])
        for idx, announce in enumerate(self._speaker_announce):
            time_parts = announce['time'].split(':')
            hour, minute = int(time_parts[0]), int(time_parts[1])
            log.info(f"Scheduling speaker announce '{announce['msg']}' at {hour:02d}:{minute:02d}")
            self._scheduler.add_job(
                lambda lang=announce['lang'], msg=announce['msg'], vol=announce['vol']: self._on_speaker_announce_cron(lang, msg, vol),
                trigger=CronTrigger(hour=hour, minute=minute, second=0),
                id=f'speaker_announce_{idx}'
            )

    def _get_stats(self):
        stats = {
            "light_check_history": list(self._light_check_history),
            "vacations_mode": self._vacations_mode,
            "speaker_announce": self._speaker_announce,
        }
        return json.dumps(stats, default=str)

    def get_service_alerts(self):
        if self._vacations_mode:
            return ["Vacations mode is enabled! Expect random light effects."]
        return []

    def _mock_auto_lights_off(self):
        self._light_check_history.append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'lights_forgotten': True,
            'lights_left_on': ["Light1", "Light3"],
        })
        self._light_check_history.append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'lights_forgotten': False,
            'lights_left_on': [],
        })
        self._light_check_history.append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'lights_forgotten': True,
            'lights_left_on': ["Light1", "Light2", "Light3"],
        })
        return "OK"

    def _check_and_turn_off_lights(self):
        """
        Check which lights are on, turn them off, and send a notification.
        """
        lights_on = self._z2m.get_things_if(lambda t: t.thing_type == 'light' and t.is_light_on())

        self._light_check_history.append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'lights_forgotten': len(lights_on) > 0,
            'lights_left_on': [l.name for l in lights_on] if len(lights_on) > 0 else []
        })

        if len(lights_on) == 0:
            log.info("Light checker: no lights forgot on, nothing to do")
            return

        turn_all_lights_off(self._z2m)
        names = ", ".join([l.name for l in lights_on])
        msg = f'Someone forgot the lights on. Will turn off {names}'
        self.message_svc("ZmwTelegram", "send_text", {'msg': msg})
        log.info(msg)

    def _vacations_mode_late_afternoon(self):
        # TODO: Implement late afternoon light effects
        pass

    def _vacations_mode_evening(self):
        # TODO: Implement evening light effects
        pass

    def _vacations_mode_night(self):
        turn_all_lights_off(self._z2m)
        msg = f'Home going to sleep! Will turn off all lights. Night night.'
        self.message_svc("ZmwTelegram", "send_text", {'msg': msg})
        log.info(msg)

    def _on_speaker_announce_cron(self, lang, msg, vol):
        # TODO: Implement speaker announcement
        pass


service_runner_with_www(ZmwCronenbergs)
