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

    def play(self):
        self.cc.media_controller.play()

    def pause(self):
        self.cc.media_controller.pause()

    def stop(self):
        self.cc.media_controller.stop()

    def mute(self):
        self.cc.set_volume_muted(True)

    def unmute(self):
        self.cc.set_volume_muted(False)

    def volume_up(self):
        self.cc.volume_up()

    def volume_down(self):
        self.cc.volume_down()

    def set_volume(self, vol):
        self.cc.set_volume(vol)

    def get_volume(self):
        try:
            return self.cc.status.volume_level
        except:
            return None

    def get_app(self):
        try:
            return self.cc.status.status_text
        except:
            return None

    def youtube(self, video_id):
        yt = YouTubeController()
        self.cc.register_handler(yt)
        yt.play_video(video_id)

    def thing_types(self):
        return ['media_player']

    def supported_actions(self):
        return ['play', 'pause', 'stop', 'mute', 'unmute', 'volume_up',
                'volume_down', 'set_volume', 'youtube']

    def json_status(self):
        stat = {
                    'name': self.get_pretty_name(),
                    'uuid': self.get_id(),
                    'uri': self.cc.uri,
                    'app': self.get_app(),
                    'volume_level': self.get_volume(),
                    'media': None,
               }

        try:
            self.cc.media_controller.update_status()
            stat['media'] = {
                        'adjusted_current_time': self.cc.media_controller.status.adjusted_current_time,
                        'album_artist': self.cc.media_controller.status.album_artist,
                        'album_name': self.cc.media_controller.status.album_name,
                        'artist': self.cc.media_controller.status.artist,
                        'content_id': self.cc.media_controller.status.content_id,
                        'content_type': self.cc.media_controller.status.content_type,
                        'current_time': self.cc.media_controller.status.current_time,
                        'duration': self.cc.media_controller.status.duration,
                        'images': self.cc.media_controller.status.images,
                        'media_is_generic': self.cc.media_controller.status.media_is_generic,
                        'media_is_movie': self.cc.media_controller.status.media_is_movie,
                        'media_is_musictrack': self.cc.media_controller.status.media_is_musictrack,
                        'media_is_photo': self.cc.media_controller.status.media_is_photo,
                        'media_is_tvshow': self.cc.media_controller.status.media_is_tvshow,
                        'media_metadata': self.cc.media_controller.status.media_metadata,
                        'metadata_type': self.cc.media_controller.status.metadata_type,
                        'playback_rate': self.cc.media_controller.status.playback_rate,
                        'player_is_idle': self.cc.media_controller.status.player_is_idle,
                        'player_is_paused': self.cc.media_controller.status.player_is_paused,
                        'player_is_playing': self.cc.media_controller.status.player_is_playing,
                        'player_state': self.cc.media_controller.status.player_state,
                        'series_title': self.cc.media_controller.status.series_title,
                        'title': self.cc.media_controller.status.title,
                        'volume_level': self.cc.media_controller.status.volume_level,
                        'volume_muted': self.cc.media_controller.status.volume_muted,
                   }
        except:
            pass

        return stat

