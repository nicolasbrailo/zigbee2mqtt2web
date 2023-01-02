""" Wraps a Spotipy client in a Zigbee2Mqtt2Web thing """

from spotipy.oauth2 import SpotifyOauthError
from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify as Spotipy
from spotipy import SpotifyException


from apscheduler.schedulers.background import BackgroundScheduler

from zigbee2mqtt2web import Zigbee2MqttAction
from .phony import PhonyZMWThing

import logging
logger = logging.getLogger(__name__)

_SCHEDULER = BackgroundScheduler()
_SCHEDULER.start()

# A token is valid for an hour, so we refresh every 45 minutes
_SPOTIFY_SECS_BETWEEN_TOK_REFRESH = 60 * 45


def _config_spotipy_logger(use_debug_log):
    if not use_debug_log:
        logging.getLogger('spotipy.*').setLevel(logging.INFO)
        logging.getLogger('spotipy.client').setLevel(logging.INFO)
        logging.getLogger('spotipy.oauth2').setLevel(logging.INFO)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)


def _get_spotify_scopes():
    return 'app-remote-control user-read-playback-state ' \
           'user-modify-playback-state user-read-currently-playing'


def _get_auth_obj(cfg):
    return SpotifyOAuth(cfg['client_id'],
                        cfg['client_secret'],
                        cfg['redirect_uri'],
                        scope=_get_spotify_scopes(),
                        cache_path=cfg['spotipy_cache'])


def _get_valid_auth_obj(cfg):
    oauth = _get_auth_obj(cfg)
    tok = None if oauth is None else oauth.get_cached_token()
    if tok is None or 'access_token' not in tok or 'refresh_token' not in tok:
        raise RuntimeError('Spotify has no cached token, needs reauth')
    return oauth


def _build_user_reauth_html(cfg):
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
                    document.getElementById("set_new_code_link").href = "{}" + code;
                }} else {{
                    document.getElementById("invalid_code").style.visibility = "visible";
                    document.getElementById("valid_code").style.visibility = "hidden";
                }}
            }}
        </script>
    """

    return html.format(
        _get_auth_obj(cfg).get_authorize_url(),
        cfg['set_reauth_code_url_path'])


def _refresh_access_tok(cfg):
    oauth = _get_valid_auth_obj(cfg)
    refresh_tok = oauth.get_cached_token()['refresh_token']
    new_tok = oauth.refresh_access_token(refresh_tok)
    if new_tok is None:
        raise RuntimeError('Refresh token failed')
    logger.debug('Spotify token refresh succeeded')


def _new_spotipy(cfg):
    oauth = _get_valid_auth_obj(cfg).get_cached_token()
    return Spotipy(auth=oauth['access_token'])


def _action_get_is_authenticated(_spotipy):
    return True


def _action_get_is_playing(spotipy):
    track = spotipy.current_user_playing_track()
    return (track is not None) and track['is_playing']


def _action_stop(spotipy, _):
    try:
        spotipy.pause_playback()
    except SpotifyException:
        # Most likely the stream was stopped
        pass


def _action_toggle_play(spotipy, _):
    if _action_get_is_playing(spotipy):
        _action_stop(spotipy, _)
    else:
        spotipy.start_playback()


def _action_set_next_or_prev(spotipy, val):
    val = int(val)
    for _ in range(0, val):
        spotipy.next_track()
    for _ in range(val, 0):
        spotipy.previous_track()


def _action_get_volume_pct(spotipy):
    active_devices = [device for device in spotipy.devices()['devices']
                      if device['is_active']]
    if len(active_devices) == 0:
        return None
    return active_devices[0]['volume_percent']


def _action_set_volume_pct(spotipy, volume):
    try:
        spotipy.volume(int(volume))
    except SpotifyException as ex:
        # Some devices don't support volume set
        if ex.http_status == 403:
            raise RuntimeError('Setting volume not allowed by Spotify') from ex
        raise ex


def _action_media_info(spotipy):
    # Get all cover images sorted by image size
    def pick_album_cover(track):
        imgs = []
        try:
            imgs = sorted([(img['height'] * img['width'], img['url'])
                           for img in track['item']['album']['images']])
        except KeyError:
            pass

        # Pick an image that's at least 300*300 (or the biggest, if all are
        # smaller)
        selected_img = None
        for img in imgs:
            area, selected_img = img
            if area >= 90000:
                break
        return selected_img

    track = spotipy.current_user_playing_track()
    if track is None or track['item'] is None:
        return {}
    return {
        'icon': pick_album_cover(track),
        'title': track['item']['name'],
        'duration': track['item']['duration_ms'] / 1000,
        'current_time': track['progress_ms'] / 1000,
        'artist': ', '.join([x['name'] for x in track['item']['album']['artists']]),
        'album_link': track['item']['album']['external_urls']['spotify'],
        'album_name': track['item']['album']['name'],
        'track_count': track['item']['album']['total_tracks'],
        'current_track': track['item']['track_number'],
    }


def _action_media_player_state(spotipy):
    return {
        'is_authenticated': _action_get_is_authenticated(spotipy),
        'volume': _action_get_volume_pct(spotipy),
        'media_info': _action_media_info(spotipy),
    }


def _new_zmw_action(
        name,
        description,
        on_tok_expired,
        getter=None,
        setter=None):
    def _catch_spotify_deauth(base_func):
        """ Detect if Spotify has an expired token """

        def wrap(self, *a, **kw):
            try:
                return base_func(self, *a, **kw)
            except SpotifyException as ex:
                if ex.http_status != 401:  # If exc == deauth
                    raise ex
                logger.info(
                    'Spotify access token expired, will try to renew and retry')
                self._cb_on_token_expired()  # pylint: disable=protected-access
                return base_func(self, *a, **kw)

        return wrap

    class _SpotifyAction:
        def __init__(self, cb_on_token_expired, getter=None, setter=None):
            assert(getter is not None or setter is not None)
            self._sp = None
            self._cb_on_token_expired = cb_on_token_expired
            self._getter = getter
            self._setter = setter

        def update_spotipy_instance(self, spotipy):
            """ Updates the underlying object when the auth token changes """
            self._sp = spotipy

        @_catch_spotify_deauth
        def get(self):
            """ Invoke an action if the auth token is valid """
            if self._sp is None:
                return None
            return self._getter(self._sp)

        @_catch_spotify_deauth
        def set(self, val):
            """ Invoke a set action if the auth token is valid """
            if self._sp is None:
                return None
            return self._setter(self._sp, val)

    return {name: Zigbee2MqttAction(
        name=name,
        description=description,
        can_set=(setter is not None),
        can_get=(getter is not None),
        value=_SpotifyAction(on_tok_expired, getter, setter))}


class _SpotifyGetPlayerStateAction:
    """ GetPlayerState is special: we want to return something even if the spotipy
    instance is not authenticated """

    def __init__(self, reauth_url):
        self._sp = None
        self._reauth_url = reauth_url

    def update_spotipy_instance(self, spotipy):
        """ Update instance if auth token changes """
        self._sp = spotipy

    def get(self):
        """ If not authenticated, return a URL to do the auth """
        if self._sp is None:
            return {
                'is_authenticated': False,
                'reauth_url': self._reauth_url,
                'volume': 0,
                'media_info': None,
            }
        return _action_media_player_state(self._sp)


def _build_actions_map(cb_on_token_expired, cfg):
    actions = {}
    actions.update(_new_zmw_action(
        'is_playing',
        'True if there is an active stream',
        cb_on_token_expired,
        getter=_action_get_is_playing))
    actions.update(_new_zmw_action(
        'is_authenticated',
        'True if Spotify thing is enabled and can perform actions',
        cb_on_token_expired,
        getter=_action_get_is_authenticated))
    actions.update(_new_zmw_action(
        'relative_jump_to_track',
        'Jumps backwards/forwards to the next/previous N track',
        cb_on_token_expired,
        setter=_action_set_next_or_prev))
    actions.update(_new_zmw_action(
        'stop',
        'Stops playback, if active',
        cb_on_token_expired,
        setter=_action_stop))
    actions.update(_new_zmw_action(
        'toggle_play',
        'Pauses or resumes playback',
        cb_on_token_expired,
        setter=_action_toggle_play))
    actions.update(_new_zmw_action(
        'volume',
        'Manages volume for active playback',
        cb_on_token_expired,
        setter=_action_set_volume_pct,
        getter=_action_get_volume_pct))
    actions.update(_new_zmw_action(
        'media_info',
        'Info for currently playing media',
        cb_on_token_expired,
        getter=_action_media_info))

    actions['media_player_state'] = Zigbee2MqttAction(
        name='media_player_state',
        description='get_json_state() is disabled for this object, as it needs remote access '
        'and may be very slow. Use this action instead to retrieve the full state',
        can_set=False,
        can_get=True,
        value=_SpotifyGetPlayerStateAction(
            cfg['start_reauth_url_path']))

    return actions


class Spotify(PhonyZMWThing):
    """ Wraps a Spotipy client in a ZMW thing """

    def __init__(self, cfg):
        super().__init__(
            name="Spotify",
            description="Wrapper over Spotify for ZMW",
            thing_type="media_player",
        )
        self._cfg = cfg
        self._spotify = None
        self.actions = _build_actions_map(self._refresh_access_tok, self._cfg)

        # After all actions are built, refresh their access token
        self._refresh_access_tok()

        _SCHEDULER.add_job(
            func=self._refresh_access_tok,
            trigger="interval",
            seconds=_SPOTIFY_SECS_BETWEEN_TOK_REFRESH)
        _config_spotipy_logger(use_debug_log=cfg['debug_log'])

    def add_reauth_paths(self, webserver):
        """ Adds paths to reatuh to a flask instance """
        webserver.add_url_rule(
            self._cfg['start_reauth_url_path'],
            lambda: _build_user_reauth_html(self._cfg))
        webserver.add_url_rule(
            self._cfg['set_reauth_code_url_path'] + '/<code>',
            self._complete_reauth)

    def _complete_reauth(self, code):
        logger.info("Starting Spotify reauth")
        try:
            _get_auth_obj(self._cfg).get_access_token(code)
            _get_valid_auth_obj(self._cfg)
        except SpotifyOauthError as ex:
            return str(ex), 400
        except RuntimeError as ex:
            return str(ex), 400

        self._refresh_access_tok()
        return "Code accepted"

    def _refresh_access_tok(self):
        logger.info("Starting Spotify access token refresh")
        try:
            _refresh_access_tok(self._cfg)
            spotipy = _new_spotipy(self._cfg)
            for _action_name, action in self.actions.items():
                action.value.update_spotipy_instance(spotipy)
        except RuntimeError:
            logging.error(
                'Failed to authenticate Spotify, needs reauth',
                exc_info=True)
            for _action_name, action in self.actions.items():
                action.value.update_spotipy_instance(None)
