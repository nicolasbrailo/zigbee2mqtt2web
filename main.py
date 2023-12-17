# This is an example: you probably want to customize this with your network!

import sys
import logging
import json

from zigbee2mqtt2web import Zigbee2Mqtt2Web
from zigbee2mqtt2web_extras.monkeypatching import add_all_known_monkeypatches
from zigbee2mqtt2web_extras.scenes import SceneManager

from zigbee2mqtt2web_extras.sonos import Sonos
from zigbee2mqtt2web_extras.spotify import Spotify

root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root.addHandler(handler)

with open('config.template.json', 'r') as fp:
    CFG = json.loads(fp.read())

zmw = Zigbee2Mqtt2Web(CFG)

def on_net_discovery():
    zmw.registry.register(SceneManager(zmw.registry))
    def example_scene():
        lamp = zmw.registry.get_thing('Light1')
        lamp.set_brightness_pct(100)
        zmw.registry.broadcast_thing(lamp)
    zmw.registry.get_thing('SceneManager').add_scene('Example', 'Turn on one light', example_scene)

    def on_button_press(action):
        if action == 'up_press':
            zmw.registry.get_thing('Light1').set_brightness_pct(40)
            zmw.registry.get_thing('Light2').set_brightness_pct(40)
        elif action == 'down_press':
            zmw.registry.get_thing('Light1').set_brightness_pct(15)
            zmw.registry.get_thing('Light2').set_brightness_pct(15)
        zmw.registry.broadcast_things(['Light1', 'Light2'])

    try:
        zmw.registry.get_thing('ExampleButton')\
            .actions['action'].value.on_change_from_mqtt = on_button_press
    except KeyError:
        # This will fail, unless ExampleButton exists
        pass


add_all_known_monkeypatches(zmw)
zmw.registry.on_mqtt_network_discovered(on_net_discovery)

# Load extras
if 'sonos' in CFG:
    zmw.registry.register(Sonos(CFG['sonos'], zmw.webserver))

if 'spotify' in CFG:
    spotify = Spotify(CFG['spotify'])
    spotify.add_reauth_paths(zmw.webserver)
    zmw.registry.register(spotify)

zmw.start_and_block()
zmw.stop()
