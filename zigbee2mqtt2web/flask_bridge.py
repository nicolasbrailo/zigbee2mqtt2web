""" All web routing logic """

from flask import Flask
from flask import redirect
from flask import request as FlaskRequest
from flask import send_from_directory
from flask import url_for
from flask_socketio import SocketIO

import dataclasses
import json
import os
import subprocess
from multiprocessing import Process

import logging
logger = logging.getLogger(__name__)


def _validate(cfg):
    ok_cfg = {
        'host': cfg['server_listen_host'] if (
            'server_listen_host' in cfg) else '0.0.0.0',
        'port': cfg['server_listen_port'],
        'http_port': cfg['httponly_listen_port'] if 'httponly_listen_port' in cfg else None,
        'server_systemd_name': cfg['server_systemd_name'],
        'socketio_topic': cfg['mqtt_socketio_topic'],
        'ui_local_path': None,
        'ui_uri_prefix': '/www',
        'www_extra_local_path': None,
        'www_extra_uri_prefix': None,
        'ssl': None,
    }

    if 'ui_local_path' in cfg:
        ok_cfg['ui_local_path'] = cfg['ui_local_path']
        if not os.path.isdir(ok_cfg['ui_local_path']):
            raise RuntimeError(
                f"Can't access UI web path {ok_cfg['ui_local_path']}")

    missing_prefix = 'www_extra_local_path' in cfg and 'www_extra_uri_prefix' not in cfg
    missing_path = 'www_extra_local_path' not in cfg and 'www_extra_uri_prefix' in cfg
    if missing_prefix or missing_path:
        raise RuntimeError(
            'Options www_extra_local_path and www_extra_uri_prefix must '
            'both be None, or both be configured')

    if 'www_extra_local_path' in cfg:
        ok_cfg['www_extra_uri_prefix'] = cfg['www_extra_uri_prefix']
        ok_cfg['www_extra_local_path'] = cfg['www_extra_local_path']
        if not os.path.isdir(ok_cfg['www_extra_local_path']):
            raise RuntimeError(
                f"Can't access extra web path {ok_cfg['www_extra_local_path']}")
        if cfg['www_extra_uri_prefix'] == ok_cfg['ui_uri_prefix']:
            raise RuntimeError(
                f"www extra URI prefix ({ok_cfg['www_extra_uri_prefix']}) can't be "
                f"the same as www UI URI prefix ({ok_cfg['ui_uri_prefix']})")

    if 'www_https' in cfg:
        if cfg['www_https'] == "" or cfg['www_https'] == "adhoc":
            ok_cfg['ssl'] = 'adhoc'
        else:
            crt = os.path.join(cfg['www_https'], 'zmw.cert')
            if not os.path.isfile(crt):
                raise FileNotFoundError(
                    f"SSL/HTTPS mode enabled, but can't find {crt} (hint: use `make ssl`")

            key = os.path.join(cfg['www_https'], 'zmw.key')
            if not os.path.isfile(key):
                raise FileNotFoundError(
                    f"SSL/HTTPS mode enabled, but can't find {key} (hint: use `make ssl`")

            ok_cfg['ssl'] = (crt, key)

    return ok_cfg


class FlaskBridge:
    """ Creates a bridge from a thing-registry to a Flask instance """

    def __init__(self, cfg, thing_registry):
        self._cfg = _validate(cfg)

        # Holder for a graphvizmap last message; since this message takes so
        # long to complete, it's likely the user may lose it
        self._last_graphvizmap = None

        self._flask = Flask(self._cfg['server_systemd_name'])
        self._http_only_flask_proc = None
        if self._cfg['http_port'] is None:
            self._http_only_flask = None
        else:
            httpName = self._cfg['server_systemd_name'] + '_httponly'
            self._http_only_flask = Flask(httpName)

        # If websockets break, try this instead:
        #
        # self._flask_socketio = SocketIO(self._flask, async_mode='threading')
        #
        # websockets with gevent/eventlet are very brittle and can break after
        # any update. threading mode claims to be less performant, which I
        # guess is true, there isn't anything more performant than not doing
        # anything...
        self._flask_socketio = SocketIO(self._flask)

        self._registry = thing_registry
        self._registry.on_mqtt_network_discovered(self._register_socket_fwds)

        # Register URL rules
        if self._cfg['ui_local_path'] is not None:
            self.add_url_rule(
                f"{self._cfg['ui_uri_prefix']}/<path:urlpath>",
                lambda urlpath: send_from_directory(
                    self._cfg['ui_local_path'],
                    urlpath))

            def default_redir():
                return redirect(url_for(
                    f"{self._cfg['ui_uri_prefix']}/<path:urlpath>",
                    urlpath='index.html'))
            self.add_url_rule(f"{self._cfg['ui_uri_prefix']}/", default_redir)
            self.add_url_rule('/', default_redir)

        if self._cfg['www_extra_local_path'] is not None:
            self.add_url_rule(
                f"/{self._cfg['www_extra_uri_prefix']}/<path:urlpath>",
                lambda urlpath: send_from_directory(
                    self._cfg['www_extra_local_path'],
                    urlpath))

        def get_thing_names():
            return self._registry.get_thing_names()
        self._thing_get('/ls', get_thing_names)
        self._thing_get('/get_thing_names', get_thing_names)

        def get_all_known_thing_names():
            return self._registry.get_all_known_thing_names()
        self._thing_get('/get_all_known_things', get_all_known_thing_names)

        def get_thing_names_supporting_action(action):
            return self._registry.get_thing_names_with_actions([action])
        self._thing_get(
            '/get_thing_names_supporting/<action>',
            get_thing_names_supporting_action)

        def get_thing_meta(thing_name):
            thing = self._registry.get_thing(thing_name)
            return dataclasses.asdict(thing)
        self._thing_get('/meta/<thing_name>', get_thing_meta)

        def get_thing_action_meta(thing_name, prop_name):
            act = self._registry.get_thing(thing_name).actions[prop_name]
            return dataclasses.asdict(act)
        self._thing_get(
            '/meta/<thing_name>/<prop_name>',
            get_thing_action_meta)

        def get_thing_state(thing_name):
            return self._registry.get_thing(thing_name).get_json_state()
        self._thing_get('/get/<thing_name>', get_thing_state)

        def get_world():
            return self._registry.get_world()
        self._thing_get('/get_world', get_world)

        def get_prop_from_thing(thing_name, prop_name):
            return self._registry.get_thing(thing_name).get(prop_name)
        self._thing_get('/get/<thing_name>/<prop_name>', get_prop_from_thing)

        def set_prop_of_thing(thing_name):
            if FlaskRequest.form is None or len(
                    list(FlaskRequest.form.items())) == 0:
                raise RuntimeError('Set prop requires at least one PUT value')

            # Validate all k,v's are valid and exist before applying any. Note
            # values may be empty or non existent
            for key, val in FlaskRequest.form.items():
                if key is None or len(key) == 0:
                    raise RuntimeError(
                        f'Invalid set of PUT values f{key}:f{val}')

            for key, val in FlaskRequest.form.items():
                self._registry.get_thing(thing_name).set(key, val)

            # Propagate changes
            self._registry.broadcast_thing(thing_name)
            return True
        self._thing_put('/set/<thing_name>', set_prop_of_thing)

        def start_mqtt_networkmap():
            self._registry.start_mqtt_networkmap()
            return True
        self._thing_put(
            '/mqtt_networkmap/start_mapping',
            start_mqtt_networkmap)

        def cached_mqtt_networkmap():
            return self._last_graphvizmap
        self._thing_get('/mqtt_networkmap', cached_mqtt_networkmap)

        def syslog(num_lines):
            cmd = '/usr/bin/journalctl' \
                f' --unit={self._cfg["server_systemd_name"]}' \
                f' -n {num_lines}' \
                  ' --no-pager --reverse --output=cat'
            syslogcmd = subprocess.run(
                cmd.split(), stdout=subprocess.PIPE, text=True, check=True)
            return f'<pre>{syslogcmd.stdout}</pre>'
        self.add_url_rule('/syslog/<num_lines>', syslog)

    def _thing_get(self, url, cb_view):
        return self._thing_url(url, cb_view, ['GET'])

    def _thing_put(self, url, cb_view):
        return self._thing_url(url, cb_view, ['PUT'])

    def _thing_url(self, url, cb_view, methods):
        def wrapped_cb(*k, **kv):
            try:
                res = cb_view(*k, **kv)

                def jsonify_non_serializable(data):
                    return f'[non-serializable {type(data).__qualname__}]'
                return json.dumps(res, default=jsonify_non_serializable)
            except KeyError as ex:
                logger.info(
                    'User requested non-existing thing. %s', ex, exc_info=True)
                return str(ex), 404
            except AttributeError as ex:
                logger.info(
                    'User requested non-existing action for existing thing. %s',
                    ex,
                    exc_info=True)
                return str(ex), 415
            except ValueError as ex:
                logger.info(
                    'User attempted to set an invalid value for an action %s',
                    ex,
                    exc_info=True)
                return str(ex), 422
            except RuntimeError as ex:
                logger.info(
                    'User request error %s', ex, exc_info=True)
                return str(ex), 400
        self._flask.add_url_rule(
            rule=url,
            endpoint=url,
            view_func=wrapped_cb,
            methods=methods)

    def add_url_rule(self, url, view_func, methods=None):
        """ Adds a rule directly to the underlying flask instance """
        if methods is None:
            methods = ['GET']
        return self._flask.add_url_rule(
            rule=url,
            endpoint=url,
            view_func=view_func,
            methods=methods)

    def add_asset_url_rule(self, url, view_func, methods=None):
        """ Same as add_url_rule, but will ensure requests are accepted over http or
        over https; this is useful when using https mode with a self-signed cert """
        if self._http_only_flask_proc is not None:
            raise RuntimeError(
                "Can't add a new http-only asset rule after the http server has started")

        if methods is None:
            methods = ['GET']

        self.add_url_rule(url, view_func, methods)

        return self._http_only_flask.add_url_rule(
            rule=url,
            endpoint=url,
            view_func=view_func,
            methods=methods)

    def start(self):
        """ Start Flask, socket.io and http-only Flask """
        self._start_http_server()
        logger.info(
            'zigbee2mqtt2flask active on [%s]:%d',
            self._cfg["host"],
            self._cfg["port"])
        kw = {
            "host": self._cfg["host"],
            "port": self._cfg["port"],
            # werkzeug may not be recommended, but it's the only server
            # that works reliably in a RPi and doesn't cause a mess with
            # dependencies. It also seems to be performant enough for this app
            "allow_unsafe_werkzeug": True,
            "debug": False,
        }
        if self._cfg['ssl']:
            kw['ssl_context'] = self._cfg['ssl']
        try:
            self._flask_socketio.run(self._flask, **kw)
        except TypeError as ex:
            if 'ssl_context' in kw:
                logger.info(
                    "Can't start flask, are you sure ssl is installed?",
                    exc_info=True)
                exit(0)
            raise ex

        if self._http_only_flask_proc is not None:
            # At this point, the logger won't work (http_only is forking and may close the fd
            # before we get here), so logging anything may result in an
            # exception
            self._http_only_flask_proc.kill()
            self._http_only_flask_proc.join(timeout=10)
            if self._http_only_flask_proc.exitcode is None:
                logger.info(
                    'zigbee2mqtt2flask http-only failed to shut down, terminating...')
                self._http_only_flask_proc.terminate()

    def _start_http_server(self):
        """ https probably won't work for all use cases, as using self-signed certs will
        run into security warnings. This means for LAN use cases, some actions may only
        be possible with http only (eg Sonos picking up a static asset for playback).

        Note this extra http server is started as a new process, and there is no interaction
        possible with it once it starts (eg no new routes may be added)
        """

        if self._http_only_flask is None:
            return

        logger.info(
            'zigbee2mqtt2flask starting http-only subprocess [%s]:%d',
            self._cfg["host"],
            self._cfg["http_port"])

        # If things act up, try with different fork mechanisms
        # eg multiprocessing.set_start_method('spawn')

        kw = {
            "host": self._cfg["host"],
            "port": self._cfg["http_port"],
            "debug": False,
        }
        self._http_only_flask_proc = Process(
            target=self._http_only_flask.run,
            name="ZMW_Flask_httponly",
            kwargs=kw)
        self._http_only_flask_proc.start()

    def _register_socket_fwds(self):
        logger.info('FlaskBridge: register socket forwarder for mqtt messages')

        def make_socketio_forwarder(thing):
            def forward(_topic, msg):
                self._flask_socketio.emit(
                    self._cfg["socketio_topic"], {thing.name: msg})
            return forward

        for name in self._registry.get_thing_names():
            thing = self._registry.get_thing(name)
            if thing.is_zigbee_mqtt:
                self._registry.cb_for_mqtt_topic(
                    thing.name, make_socketio_forwarder(thing))
                self._registry.cb_for_mqtt_topic(
                    thing.address, make_socketio_forwarder(thing))

        # Register a handler for MQTT graphviz maps (by just forwarding them)
        def _on_graphvizmap_complete(_topic, msg):
            self._last_graphvizmap = msg
            self._flask_socketio.emit('mqtt_networkmap', msg)
        self._registry.cb_for_mqtt_topic(
            'bridge/response/networkmap',
            _on_graphvizmap_complete)
