from apscheduler.schedulers.background import BackgroundScheduler
from zigbee2mqtt2web_extras.light_helpers import which_lights_are_on_in_the_house
from zigbee2mqtt2web_extras.utils.geo_helper import todays_redshift_steps

from datetime import datetime, timedelta

import logging
log = logging.getLogger(__name__)


class Cronenberg:
    def __init__(self, zmw, latlon):
        self._zmw = zmw
        self._latlon = latlon

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

        self._redshift_lights = ['Comedor']

        #self._scheduler.add_job(self._vacation_mode_start, trigger='cron', day_of_week='mon-sun', hour=18, minute=14)
        #self._scheduler.add_job(self._vacation_mode_night, trigger='cron', day_of_week='mon-sun', hour=21, minute=34)
        #self._scheduler.add_job(self._vacation_mode_sleep, trigger='cron', day_of_week='mon-sun', hour=22, minute=16)
        # Schedule redshift everyday (or now, if we're restarting the app)
        self._scheduler.add_job(self._refresh_redshift_crons, trigger='cron', hour=6, next_run_time=datetime.now())
        self.redshifting = False

    def _refresh_redshift_crons(self):
        self.redshifting = False
        def _gen_step(pct):
            def _apply_step():
                self.redshifting = True
                log.info("Applying redshift step to %s percent", pct)
                for light_name in self._redshift_lights:
                    thing = self._zmw.registry.get_thing(light_name)
                    vmin = thing.actions['color_temp'].value.meta['value_min']
                    vmax = thing.actions['color_temp'].value.meta['value_max']
                    color_temp = ((vmax - vmin) * (int(pct)/100)) + vmin
                    thing.set('color_temp', color_temp)
                self._zmw.registry.broadcast_things(self._redshift_lights)
            return _apply_step

        for step_t,pct in todays_redshift_steps(self._latlon):
            self._scheduler.add_job(
               func=_gen_step(pct),
               trigger="date",
               run_date=step_t)

    def _vacation_mode_start(self):
        self._zmw.registry.get_thing('SceneManager').actions['Gezellig'].apply_scene()
        self._zmw.announce_system_event({
            'event': 'vacation_mode_start',
        })
    def _vacation_mode_night(self):
        self._zmw.registry.get_thing('SceneManager').actions['a dormir'].apply_scene()
        self._zmw.announce_system_event({
            'event': 'vacation_mode_night',
        })
    def _vacation_mode_sleep(self):
        self._zmw.registry.get_thing('SceneManager').actions['World off'].apply_scene()
        self._zmw.announce_system_event({
            'event': 'vacation_mode_sleep',
        })

