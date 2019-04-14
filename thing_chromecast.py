from things import Thing

# https://github.com/balloob/pychromecast
import pychromecast
from pychromecast.controllers.youtube import YouTubeController

class ThingChromecast(Thing):
    @staticmethod
    def set_flask_bindings():
        pass

    @staticmethod
    def scan_network(debug_force_ip=None):
        """ Get all Chromecasts in the network. If debug_force_ip is set
        then the net won't be scanned, only one CC will be returned (useful
        to avoid a long scan wait when debugging) """

        print("Scanning for ChromeCasts")

        if debug_force_ip is not None:
            return [ThingChromecast(pychromecast.Chromecast(debug_force_ip))]

        return [ThingChromecast(cc) for cc in pychromecast.get_chromecasts()]

    def __init__(self, cc_object):
        self.cc = cc_object
        thing_id = str(self.cc.device.uuid)
        pretty_name = self.cc.device.friendly_name
        super().__init__(thing_id, pretty_name)

        cc_object.start()
        print("Found Chromecast {}".format(pretty_name))

    def playpause(self):
        try:
            self.cc.media_controller.update_status()
        except pychromecast.error.UnsupportedNamespace:
            # No media running
            return

        if self.cc.media_controller.is_paused:
            self.cc.media_controller.play()
        elif self.cc.media_controller.is_playing:
            self.cc.media_controller.pause()
        else:
            print("Error: CC {} is not playing nor paused. Status: {}".format(
                        self.get_pretty_name(), self.cc.media_controller.status.player_state))

    def stop(self):
        # A bit more agressive than stop, but stop on its own seems useless:
        # cc will report its state as media still loaded but idle. Easier to kill
        self.cc.quit_app()

    def play_next_in_queue(self):
        try:
            self.cc.media_controller.update_status()
        except pychromecast.error.UnsupportedNamespace:
            # No media running
            return

        self.cc.media_controller.skip()

    def play_prev_in_queue(self):
        try:
            self.cc.media_controller.update_status()
        except pychromecast.error.UnsupportedNamespace:
            # No media running
            return

        self.cc.media_controller.rewind()

    def toggle_mute(self):
        self.cc.set_volume_muted(not self.cc.status.volume_muted)

    def volume_up(self):
        self.cc.volume_up()

    def volume_down(self):
        self.cc.volume_down()

    def set_volume_pct(self, vol):
        self.cc.set_volume(int(vol) / 100)

    def set_playtime(self, t):
        try:
            self.cc.media_controller.update_status()
        except pychromecast.error.UnsupportedNamespace:
            # No media running
            return

        pause_after_seek = self.cc.media_controller.is_paused
        self.cc.media_controller.seek(t)
        if pause_after_seek:
            self.cc.media_controller.pause()


    def youtube(self, video_id):
        yt = YouTubeController()
        self.cc.register_handler(yt)
        yt.play_video(video_id)

    def thing_types(self):
        return ['media_player']

    def supported_actions(self):
        return ['playpause', 'stop', 'play_next_in_queue', 'play_prev_in_queue',
                'toggle_mute', 'volume_up', 'volume_down', 'set_volume_pct',
                'youtube']

    def json_status(self):
        if self.cc.status is None:
            print("Warning: CC {} was disconected?".format(self.get_pretty_name()))
            self.cc.start()

        status = {
                'name': self.get_pretty_name(),
                'uuid': self.get_id(),
                'uri': self.cc.uri,
                'app': self.cc.status.display_name,
                'volume_pct': int(100 * self.cc.status.volume_level),
                'volume_muted': self.cc.status.volume_muted,
                'player_state': 'Idle',
                'media': None,
            }

        try:
            self.cc.media_controller.update_status()
        except pychromecast.error.UnsupportedNamespace:
            # No media running
            return status

        status['player_state'] = self.cc.media_controller.status.player_state
        status['media'] = {
                    'icon': None,
                    'title': self.cc.media_controller.status.title,
                    'duration': self.cc.media_controller.status.duration,
                    'current_time': self.cc.media_controller.status.current_time,
                }

        icons = [img.url for img in self.cc.media_controller.status.images if img is not None]
        try:
            status['media']['icon'] = icons[0]
        except:
            pass

        return status


