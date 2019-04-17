from things import Thing

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

class ThingSpotify(Thing):

    class TokenNeedsRefresh(Exception):
        def __init__(self, url):
            self.refresh_url = url

    @staticmethod
    def _get_spotify_scopes():
        return 'app-remote-control user-read-playback-state user-modify-playback-state user-read-currently-playing'

    @staticmethod
    def get_cached_token(cfg):
        """ Call get_cached_token to try and receive a cached auth token. Will throw TokenNeedsRefresh
        if token is invalid. Goto url in exception.refresh_url to get a new token from Spotify (user
        will need to do that manually: it requires user approval """
        auth = SpotifyOAuth(cfg['spotify_client_id'], cfg['spotify_client_secret'],
                                cfg['spotify_redirect_uri'], scope=ThingSpotify._get_spotify_scopes(),
                                cache_path=cfg['spotipy_cache'])

        tok = auth.get_cached_token()
        if tok:
            return tok['access_token']

        raise ThingSpotify.TokenNeedsRefresh(auth.get_authorize_url())

    @staticmethod
    def update_token_from_url(cfg, refresh_redir_url):
        """ If get_cached_token failed, call get_token_from_redir_url with the result of the url
        redirect that comes from calling the new authorize url """
        auth = SpotifyOAuth(cfg['spotify_client_id'], cfg['spotify_client_secret'],
                                cfg['spotify_redirect_uri'], scope=ThingSpotify._get_spotify_scopes(),
                                cache_path=cfg['spotipy_cache'])

        code = auth.parse_response_code(refresh_redir_url)
        tok = auth.get_access_token(code)
        if code is None or tok is None:
            return ThingSpotify.get_cached_token()

        return tok['access_token']


    def __init__(self, tok):
        super().__init__("Spotify", "Spotify")
        self._sp = Spotify(auth=tok)
        self.unmuted_vol_pct = 0

    def supported_actions(self):
        return ['playpause', 'stop', 'play_next_in_queue', 'play_prev_in_queue',
                'toggle_mute', 'volume_up', 'volume_down', 'set_volume_pct',
                'play_in_device']

    def playpause(self):
        if self._is_active():
            self._sp.pause_playback()
        else:
            self._sp.start_playback()

    def stop(self):
        self._sp.pause_playback()

    def play_next_in_queue(self):
        self._sp.next_track()
    
    def play_prev_in_queue(self):
        # First 'prev' just moves playtime back to 0
        self._sp.previous_track()
        self._sp.previous_track()

    def set_playtime(self, t):
        if not self._is_active():
            return

        self._sp.seek_track(t * 1000)

    def volume_up(self):
        if not self._is_active():
            return

        vol = self._get_volume_pct() + 10
        if vol > 100:
            vol = 100
        self.set_volume_pct(vol)

    def volume_down(self):
        if not self._is_active():
            return

        vol = self._get_volume_pct() - 10
        if vol < 0:
            vol = 0
        self.set_volume_pct(vol)

    def set_volume_pct(self, pct):
        if not self._is_active():
            return
        self._sp.volume(pct)

    def toggle_mute(self):
        if not self._is_active():
            return
        vol = self._get_volume_pct()
        if vol == 0:
            self.set_volume_pct(self.unmuted_vol_pct)
        else:
            self.unmuted_vol_pct = vol
            self.set_volume_pct(0)

    def play_in_device(self, dev_name):
        devs = self._sp.devices()['devices']
        for dev in devs:
            if dev['name'] == dev_name:
                self._sp.transfer_playback(dev['id'])
                return

        raise KeyError("Spotify knows no device called {}".format(dev_name))

    def _get_available_devices(self):
        return [x['name'] for x in self._sp.devices()['devices']]

    def _get_active_device(self):
        l = [x for x in self._sp.devices()['devices'] if x['is_active'] == True]

        if len(l) == 0:
            return None

        assert(len(l) == 1)
        return l[0]

    def _get_volume_pct(self):
        dev = self._get_active_device()
        if dev is None:
            return 0
        return dev['volume_percent']

    def _is_active(self):
        track = self._sp.current_user_playing_track()
        return (track is not None) and track['is_playing']

    def json_status(self):
        vol = self._get_volume_pct()
        dev = self._get_active_device()
        status = {
                'name': self.get_pretty_name(),
                'uuid': self.get_id(),
                'uri': None,
                'active_device': dev['name'] if dev is not None else None,
                'available_devices': self._get_available_devices(),
                'app': None,
                'volume_pct': vol,
                'volume_muted': (vol == 0),
                'player_state': 'Playing' if self._is_active() else 'Idle',
                'media': None,
                }
        
        track = self._sp.current_user_playing_track()
        if track is None:
            return status

        # Get all cover images sorted by image size
        imgs = [(img['height'] * img['width'], img['url'])
                    for img in track['item']['album']['images']]
        imgs.sort()

        # Pick an image that's at least 300*300 (or the biggest, if all are smaller)
        selected_img = None
        for img in imgs:
            area, selected_img = img
            if area >= 90000:
                break

        status['media'] = {
                    'icon': selected_img,
                    'title': track['item']['name'],
                    'duration': track['item']['duration_ms'] / 1000,
                    'current_time': track['progress_ms'] / 1000,
                    'spotify_metadata': {
                        'artist': ', '.join([x['name'] for x in track['item']['album']['artists']]),
                        'album_link': track['item']['album']['external_urls']['spotify'],
                        'album_name': track['item']['album']['name'],
                        'track_count': track['item']['album']['total_tracks'],
                        'current_track': track['item']['track_number'],
                    }
                }

        return status


