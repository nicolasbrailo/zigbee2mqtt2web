"""Button handlers for Baticasa home automation."""

import os
import pathlib

from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.logs import build_logger
from zz2m.button_action_service import ButtonActionService
from zz2m.light_helpers import (
    any_light_on,
    light_group_toggle_brightness_pct,
    turn_all_lights_off
)

log = build_logger("BaticasaButtons")

class BaticasaButtons(ButtonActionService):
    def __init__(self, cfg, www):
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        super().__init__(cfg, www, www_path)
        self._cocina_btn_heladera_action_idx = 0
        self.boton_olivia_click_num = 0
        self.boton_olivia_click_off_num = 0
        self.boton_emma_click_num = 0
        self.boton_emma_click_off_num = 0

    def _scene_TV_scene(self):
        self._z2m.get_thing('CocinaCeiling').turn_off()
        self._z2m.get_thing('CocinaCountertop').turn_off()
        self._z2m.get_thing('CocinaFloorlamp').turn_off()
        self._z2m.get_thing('CocinaSink').turn_off()
        self._z2m.get_thing('EntradaCeiling').turn_off()
        self._z2m.get_thing('EntradaColor').turn_off()
        self._z2m.get_thing('TVRoomFloorlampLeft').set_brightness_pct(30)
        self._z2m.get_thing('TVRoomFloorlampLeft').set('color_temp', 454)
        self._z2m.get_thing('TVRoomFloorlampRight').set_brightness_pct(30)
        self._z2m.get_thing('TVRoomFloorlampRight').set('color_temp', 454)
        self._z2m.get_thing('TVRoomSnoopy').set_brightness_pct(30)
        self._z2m.get_thing('EmmaVelador').set_brightness_pct(25)
        self._z2m.get_thing('EmmaVelador').actions['color_rgb'].set_value('F07529')
        self._z2m.get_thing('OliviaVelador').set_brightness_pct(25)
        self._z2m.get_thing('OliviaVelador').actions['color_rgb'].set_value('F07529')
        self._z2m.broadcast_things([
            'CocinaCeiling', 'CocinaCountertop', 'CocinaFloorlamp', 'CocinaSink',
            'EntradaCeiling', 'EntradaColor',
            'TVRoomFloorlampLeft', 'TVRoomFloorlampRight', 'TVRoomSnoopy',
            'EmmaVelador', 'OliviaVelador',
        ])

    def _scene_Cocina_gezellig(self):
        self._z2m.get_thing('CocinaCeiling').set_brightness_pct(25)
        self._z2m.get_thing('CocinaSink').set_brightness_pct(70)
        self._z2m.get_thing('CocinaCountertop').set_brightness_pct(70)
        self._z2m.get_thing('EntradaCeiling').set_brightness_pct(10)
        self._z2m.get_thing('EntradaColor').set_brightness_pct(100)
        self._z2m.get_thing('CocinaFloorlamp').set_brightness_pct(10)
        self._z2m.broadcast_things([
            'CocinaCeiling', 'CocinaSink', 'CocinaCountertop',
            'EntradaCeiling', 'EntradaColor', 'CocinaFloorlamp'
        ])

    def _scene_World_off(self):
        turn_all_lights_off(self._z2m, transition_secs=3)

    def _z2m_cb_BaticuartoWorldOffBtn_action(self, _action):  # pylint: disable=invalid-name
        turn_all_lights_off(self._z2m, transition_secs=3)

    def _z2m_cb_BaticuartoBeladorBtn_action(self, action):  # pylint: disable=invalid-name
        lamp = self._z2m.get_thing('BaticuartoBelador')
        lamp.set_brightness_pct(0 if lamp.is_light_on() else 100)
        lamp.toggle()
        if action == 'on':
            lamp.actions['color_rgb'].set_value('FB1CFF')
        if action == 'off':
            lamp.actions['color_rgb'].set_value('FFFFFF')
        self._z2m.broadcast_thing(lamp)

    def _z2m_cb_EmmaBtn_action(self, action):  # pylint: disable=invalid-name
        if action == 'on':
            lamp = self._z2m.get_thing('EmmaVelador')
            self.boton_emma_click_num += 1
            if self.boton_emma_click_num == 1:
                lamp.set_brightness_pct(100)
                lamp.actions['color_rgb'].set_value('DEDED6')
            elif self.boton_emma_click_num == 2:
                lamp.set_brightness_pct(10)
                lamp.actions['color_rgb'].set_value('F07529')
            else:
                self.boton_emma_click_num = 0
                # Set color to step zero, otherwise on switch-on it will start white and fade to orange
                lamp.actions['color_rgb'].set_value('DEDED6')
                lamp.turn_off()
            lamp.set('transition', 2)
            self._z2m.broadcast_thing(lamp)

        if action == 'off':
            lamp1 = self._z2m.get_thing('EmmaFloorlampColor')
            lamp2 = self._z2m.get_thing('EmmaTriangleLamp')
            self.boton_emma_click_off_num += 1
            if self.boton_emma_click_off_num == 1:
                lamp1.set_brightness_pct(50)
                lamp2.set_brightness_pct(50)
            elif self.boton_emma_click_off_num == 2:
                lamp1.set_brightness_pct(100)
                lamp2.set_brightness_pct(100)
            else:
                self.boton_emma_click_off_num = 0
                lamp1.turn_off()
                lamp2.turn_off()
            lamp1.set('transition', 2)
            lamp2.set('transition', 2)
            self._z2m.broadcast_things([lamp1, lamp2])

    def _z2m_cb_OliviaBtn_action(self, action):  # pylint: disable=invalid-name
        if action == 'on':
            lamp = self._z2m.get_thing('OliviaVelador')
            self.boton_olivia_click_num += 1
            if self.boton_olivia_click_num == 1:
                lamp.set_brightness_pct(100)
                lamp.actions['color_rgb'].set_value('DEDED6')
            elif self.boton_olivia_click_num == 2:
                lamp.set_brightness_pct(10)
                lamp.actions['color_rgb'].set_value('F07529')
            else:
                self.boton_olivia_click_num = 0
                # Set color to step zero, otherwise on switch-on it will start white and fade to orange
                lamp.actions['color_rgb'].set_value('DEDED6')
                lamp.turn_off()
            lamp.set('transition', 2)
            self._z2m.broadcast_thing(lamp)

        if action == 'off':
            lamp1 = self._z2m.get_thing('OliviaFloorlamp')
            lamp2 = self._z2m.get_thing('OliviaSonoslamp')
            self.boton_olivia_click_off_num += 1
            if self.boton_olivia_click_off_num == 1:
                lamp1.set_brightness_pct(50)
                lamp2.set_brightness_pct(50)
            elif self.boton_olivia_click_off_num == 2:
                lamp1.set_brightness_pct(100)
                lamp2.set_brightness_pct(100)
            else:
                self.boton_olivia_click_off_num = 0
                lamp1.turn_off()
                lamp2.turn_off()
            lamp1.set('transition', 2)
            lamp2.set('transition', 2)
            self._z2m.broadcast_things([lamp1, lamp2])

    def _z2m_cb_TVRoomBtn_action(self, action):  # pylint: disable=invalid-name
        if action == 'on_press':
            self._z2m.get_thing('TVRoomFloorlampLeft').set_brightness_pct(100)
            self._z2m.get_thing('TVRoomFloorlampLeft').set('color_temp', 250)
            self._z2m.get_thing('TVRoomFloorlampRight').set_brightness_pct(100)
            self._z2m.get_thing('TVRoomFloorlampRight').set('color_temp', 250)
            self._z2m.get_thing('TVRoomSnoopy').set_brightness_pct(100)
        if action == 'up_press':
            self._z2m.get_thing('TVRoomFloorlampLeft').set_brightness_pct(60)
            self._z2m.get_thing('TVRoomFloorlampLeft').set('color_temp', 370)
            self._z2m.get_thing('TVRoomFloorlampRight').set_brightness_pct(60)
            self._z2m.get_thing('TVRoomFloorlampRight').set('color_temp', 370)
            self._z2m.get_thing('TVRoomSnoopy').set_brightness_pct(60)
        if action == 'down_press':
            self._z2m.get_thing('TVRoomFloorlampLeft').set_brightness_pct(30)
            self._z2m.get_thing('TVRoomFloorlampLeft').set('color_temp', 454)
            self._z2m.get_thing('TVRoomFloorlampRight').set_brightness_pct(30)
            self._z2m.get_thing('TVRoomFloorlampRight').set('color_temp', 454)
            self._z2m.get_thing('TVRoomSnoopy').set_brightness_pct(30)
        if action == 'off_press':
            self._z2m.get_thing('TVRoomFloorlampLeft').turn_off()
            self._z2m.get_thing('TVRoomFloorlampRight').turn_off()
            self._z2m.get_thing('TVRoomSnoopy').turn_off()
        self._z2m.broadcast_things(['TVRoomFloorlampLeft', 'TVRoomFloorlampRight', 'TVRoomSnoopy'])

    def _z2m_cb_CocinaBtnHeladera_action(self, action):  # pylint: disable=invalid-name
        if action == 'toggle':
            kitchen_lights = [
                'CocinaCeiling', 'CocinaSink', 'CocinaCountertop',
                'CocinaFloorlamp', 'EntradaCeiling', 'EntradaColor'
            ]
            group_on = any_light_on(self._z2m, kitchen_lights)
            if not group_on:
                self._cocina_btn_heladera_action_idx = 1
            else:
                self._cocina_btn_heladera_action_idx += 1
            if self._cocina_btn_heladera_action_idx == 1:
                self._z2m.get_thing('CocinaCeiling').set_brightness_pct(20)
                self._z2m.get_thing('CocinaSink').set_brightness_pct(50)
                self._z2m.get_thing('CocinaCountertop').set_brightness_pct(50)
                self._z2m.get_thing('EntradaCeiling').set_brightness_pct(15)
                self._z2m.get_thing('EntradaColor').set_brightness_pct(60)
                self._z2m.get_thing('CocinaFloorlamp').set_brightness_pct(10)
                self._z2m.broadcast_things([
                    'CocinaCeiling', 'CocinaSink', 'CocinaCountertop',
                    'EntradaCeiling', 'EntradaColor', 'CocinaFloorlamp'
                ])
            elif self._cocina_btn_heladera_action_idx == 2:
                self._z2m.get_thing('CocinaCeiling').set_brightness_pct(70)
                self._z2m.get_thing('CocinaSink').set_brightness_pct(80)
                self._z2m.get_thing('CocinaCountertop').set_brightness_pct(80)
                self._z2m.get_thing('EntradaCeiling').set_brightness_pct(50)
                self._z2m.get_thing('EntradaColor').set_brightness_pct(100)
                self._z2m.get_thing('CocinaFloorlamp').set_brightness_pct(30)
                self._z2m.broadcast_things([
                    'CocinaCeiling', 'CocinaSink', 'CocinaCountertop',
                    'EntradaCeiling', 'EntradaColor', 'CocinaFloorlamp'
                ])
            else:
                light_group_toggle_brightness_pct(
                    self._z2m,
                    [
                        ('CocinaCeiling', 90),
                        ('CocinaSink', 90),
                        ('CocinaCountertop', 90),
                        ('EntradaCeiling', 75),
                        ('EntradaColor', 100),
                        ('CocinaFloorlamp', 40)
                    ]
                )
        if action == 'brightness_up_click':
            light_group_toggle_brightness_pct(self._z2m, [('CocinaCeiling', 100)])
        if action == 'brightness_down_click':
            light_group_toggle_brightness_pct(self._z2m, [('CocinaSink', 100), ('CocinaCountertop', 100)])
        if action == 'arrow_right_click':
            light_group_toggle_brightness_pct(self._z2m, [('EntradaCeiling', 100)])
        if action == 'arrow_left_click':
            light_group_toggle_brightness_pct(self._z2m, [('EntradaColor', 100)])


service_runner_with_www(BaticasaButtons)
