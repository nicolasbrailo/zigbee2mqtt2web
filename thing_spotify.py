from things import Thing

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

class _ThingSpotifyDummy(Thing):
    """ Dummy Spotify thing used when no auth token is valid """

    def __init__(self):
        super().__init__("Spotify", "Spotify")

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['playpause', 'stop', 'play_next_in_queue', 'play_prev_in_queue',
                'toggle_mute', 'volume_up', 'volume_down', 'set_volume_pct',
                'play_in_device', 'auth_token_refresh', 'set_new_auth_code'])
        return s

    def playpause(self):
        pass

    def stop(self):
        pass

    def play_next_in_queue(self):
        pass

    def play_prev_in_queue(self):
        pass

    def set_playtime(self, t):
        pass

    def volume_up(self):
        pass

    def volume_down(self):
        pass

    def set_volume_pct(self, pct):
        pass

    def toggle_mute(self):
        pass

    def play_in_device(self, dev_name):
        pass

    def json_status(self):
        err_solve = "<a href='/thing/{}/auth_token_refresh' target='blank'>Refresh authentication data</a>"
        return {
                'error': 'Not authenticated',
                'error_html_details': err_solve.format(self.get_pretty_name()),
                'name': self.get_pretty_name(),
                'uuid': self.get_id(),
                'uri': None,
                'active_device': None,
                'available_devices': None,
                'app': None,
                'volume_pct': 0,
                'volume_muted': True,
                'player_state': None,
                'media': None,
                }


class _ThingSpotifyImpl(_ThingSpotifyDummy):
    def __init__(self, tok):
        super().__init__()
        self._sp = Spotify(auth=tok)
        self.unmuted_vol_pct = 0

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

        self._sp.seek_track(int(t) * 1000)

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
        self._sp.volume(int(pct))

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



class ThingSpotify(Thing):
    @staticmethod
    def _get_spotify_scopes():
        return 'app-remote-control user-read-playback-state user-modify-playback-state user-read-currently-playing'

    @staticmethod
    def _get_auth_obj(cfg):
        return SpotifyOAuth(cfg['spotify_client_id'], 
                            cfg['spotify_client_secret'],
                            cfg['spotify_redirect_uri'],
                            scope=ThingSpotify._get_spotify_scopes(),
                            cache_path=cfg['spotipy_cache'])

    @staticmethod
    def _get_cached_token(cfg):
        """ Call to try and receive a cached auth token. Will return
        None if there is no valid token. If so, goto refresh_url to get a new token
        from Spotify (user will need to do that manually: it requires user approval) """
        tok = ThingSpotify._get_auth_obj(cfg).get_cached_token()
        if tok:
            return tok['access_token']
        else:
            return None

    @staticmethod
    def _update_token_from_url_code(cfg, code):
        """ If get_cached_token failed, call get_token_from_redir_url with the result of the url
        redirect that comes from calling the new authorize url """
        tok = ThingSpotify._get_auth_obj(cfg).get_access_token(code)
        if tok:
            return tok['access_token']

        # Check if there's a cached token we can use
        return ThingSpotify._get_auth_obj(cfg).get_access_token(code)


    def __init__(self, cfg):
        super().__init__("Spotify", "Spotify")
        self.cfg = cfg

        tok = ThingSpotify._get_cached_token(cfg)
        if tok is None:
            self.impl = _ThingSpotifyDummy()
            print("Spotify token needs a refresh! User will need to manually update token.")
        else:
            self.impl = _ThingSpotifyImpl(tok)

    def supported_actions(self):
        return self.impl.supported_actions()

    def auth_token_refresh(self):
        """ A bit hackish, but works: returns an HTML view to let a user manually
        update the auth token for spotify """
        html = """
            <h1>Spotify Auth Update</h1>
            <ol>
                <li>Goto <a href="{}" target="blank">this page</a>.
                    If asked, accept the permission request from Spotify.</li>
                <li>If approved, you'll be redirected to another page. Copy the URL of this new page.</li>
                <li>
                    Paste the URL here: <input type="text" id="redir_url" onChange="validateCode()"/>
                    <div id="invalid_code" style="display: inline">
                        That looks like an invalid code! Please try again.
                    </div>
                </li>
                <li id="valid_code">
                    That looks like a valid code! <a href="#" id="set_new_code_link">Update Spotify token.</a>
                </li>
            </ol>

            <script>
                document.getElementById("valid_code").style.visibility = "hidden";
                document.getElementById("invalid_code").style.visibility = "hidden";

                function validateCode() {{
                    var url = document.getElementById("redir_url").value;
                    var sep = "?code=";
                    var code = url.substr(url.indexOf(sep) + sep.length)
                    console.log("Code = ", code);

                    if (code.length > 10) {{
                        document.getElementById("invalid_code").style.visibility = "hidden";
                        document.getElementById("valid_code").style.visibility = "visible";
                        document.getElementById("set_new_code_link").href = "set_new_auth_code/" + code;
                    }} else {{
                        document.getElementById("invalid_code").style.visibility = "visible";
                        document.getElementById("valid_code").style.visibility = "hidden";
                    }}
                }}
            </script>
        """
        return html.format(ThingSpotify._get_auth_obj(self.cfg).get_authorize_url())

    def set_new_auth_code(self, code):
        try:
            tok = ThingSpotify._update_token_from_url_code(self.cfg, code)
            if tok is None:
                return "Sorry, token doesn't seem valid"
            else:
                self.impl = _ThingSpotifyImpl(tok)
                return "Updated!"
        except Exception as ex:
            print(ex)
            return str(ex)

    def playpause(self):
        return self.impl.playpause()

    def stop(self):
        return self.impl.stop()

    def play_next_in_queue(self):
        return self.impl.play_next_in_queue()

    def play_prev_in_queue(self):
        return self.impl.play_prev_in_queue()

    def set_playtime(self, t):
        return self.impl.set_playtime(t)

    def volume_up(self):
        return self.impl.volume_up()

    def volume_down(self):
        return self.impl.volume_down()

    def set_volume_pct(self, pct):
        return self.impl.set_volume_pct(pct)

    def toggle_mute(self):
        return self.impl.toggle_mute()

    def play_in_device(self, dev_name):
        return self.impl.play_in_device(dev_name)

    def json_status(self):
        return self.impl.json_status()

