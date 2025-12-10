// MQTT state update may contain null fields, which are not suitable for React:
// they turn controled fields to un-controlled fields, or otherwise change how
// react sees these fields. This helper will filter out the null fields from an
// MQTT state update.
function reactifyMqttStateUpdate(state_update) {
  let react_state_update = {};
  for (let state_key of Object.keys(state_update)) {
    const val = state_update[state_key];
    if (val !== null) {
      react_state_update[state_key] = val;

      // Switches and lights have a bool-ish flag for state
      if (state_key == 'state') {
        const is_str = !!val.toLowerCase;
        if (is_str && ['0', 'false', 'off'].includes(val.toLowerCase())) {
          react_state_update[state_key] = false;
        }
      }
    }
  }
  return react_state_update;
}

class Zigbee2Mqtt2Flask2js {
  constructor(ui_display_error) {
    this.socket = null;
    this.netmap_socket = null;
    this._z2m_www_base = 'z2m'
    this._on_mqtt_message_cb = {};
    this._ui_display_error = ui_display_error;
  }

  _get(url) {
    if (url[0] != "/") {
      url = '/' + url;
    }

    var ready = mDeferred();
    mAjax({
        url: `${this._z2m_www_base}${url}`,
        cache: false,
        type: 'get',
        dataType: 'json',
        success: ready.resolve,
        error: (err) => {
          const msg = `Set error ${err.status} ${err.statusText}: ${err.responseText}`;
          console.log(msg);
          this._ui_display_error(msg);
          ready.reject();
        },
    });
    return ready;
  }

  _put(url, val) {
    var ready = mDeferred();
    mAjax({
        url: url,
        cache: false,
        type: 'put',
        data: val,
        dataType: 'json',
        success: ready.resolve,
        error: (err) => {
          const msg = `Error: ${err.statusText}, ${err.responseText}\nError ${err.status} on ${err.responseURL}`;
          console.log(msg, err);
          this._ui_display_error(msg);
          ready.reject();
        },
    });
    return ready;
  }

  ls() {
    return this._get('/ls');
  }

  get_world() {
    return this._get('/get_world');
  }

  get_known_things_hash() {
    return this._get('/get_known_things_hash');
  }

  get_thing_meta(thing_name) {
    return this._get(`/meta/${thing_name}`);
  }

  get_thing_action_meta(thing_name, action_name) {
    return this._get(`/meta/${thing_name}/${action_name}`);
  }

  get_thing_state(thing_name) {
    var ready = mDeferred();
    this._get(`/get/${thing_name}`).then(new_state => {
      ready.resolve(reactifyMqttStateUpdate(new_state));
    });
    return ready;
  }

  get_thing_action_state(thing_name, action_name) {
    return this._get(`/get/${thing_name}/${action_name}`);
  }

  set_thing(thing_name, state) {
    return this._put(`/set/${thing_name}`, state);
  }

  subscribe_to_mqtt_stream(callback_id, callback) {
    if (Object.keys(this._on_mqtt_message_cb).length == 0) {
      this._start_mqtt_stream();
    }
    this._on_mqtt_message_cb[callback_id] = callback;
  }

  unsubscribe_to_mqtt_stream(callback_id) {
    delete this._on_mqtt_message_cb[callback_id];
    if (Object.keys(this._on_mqtt_message_cb).length == 0) {
      this.stop_mqtt_stream();
    }
  }

  get_cached_mqtt_networkmap() {
    return this._get('/mqtt_networkmap');
  }

  request_new_mqtt_networkmap() {
    var ready = mDeferred();
    if (!this.netmap_socket) {
      console.log("Requesting new network map");
      this.netmap_socket = io.connect('http://' + document.domain + ':' + location.port);
      this.netmap_socket.onAny(console.log);
      this.netmap_socket.on('mqtt_networkmap', (msg) => {
        console.log("Received network map update");
        this.netmap_socket = null;
        ready.resolve(msg);
      });
      this.netmap_socket.on('disconnect', () => {
        this.netmap_socket = null;
        ready.resolve(null);
      });
      this._put('/mqtt_networkmap/start_mapping', null);
    } else {
      ready.reject('Netmap request in progress');
    }
    return ready;
  }

  _start_mqtt_stream(on_message) {
    if (typeof(io) != "undefined") {
      this._sockIoReady();
    } else {
      const dynEnableSockIO = false;
      if (!dynEnableSockIO) {
        console.log("SockIO not enabled, no Z2M2W data stream");
      } else {
        var script = document.createElement('script');
        script.src = '/www/extjsdeps/socket.io.js';
        document.head.appendChild(script);
        const self = this;
        script.onload = () => { self._sockIoReady(); };
      }
    }
  }

  _sockIoReady() {
    const forward_msg = (msg) => {
      console.log("Received mqtt_thing_msg ", msg);
      for (const cb_id of Object.keys(this._on_mqtt_message_cb)) {
        this._on_mqtt_message_cb[cb_id](msg);
      }
    };

    const sock_url = document.location.protocol + '//' + document.location.host;
    console.log(`SockIO ready, connecting to websocket at ${sock_url}`)
    this.socket = io.connect(sock_url);
    //this.socket.onAny(console.log);
    this.socket.on('mqtt_thing_msg', forward_msg);
    this.socket.on('mqtt_networkmap', forward_msg);
    this.socket.on('connect', () => {
      const msg = "Connected to server";
      console.log(msg);
      forward_msg(msg);
    });
    this.socket.on('disconnect', () => {
      const msg = "Disconnected! Will try reconnecting.";
      console.log(msg);
      forward_msg(msg);
    });
  }

  stop_mqtt_stream() {
    this.socket.destroy();
    this.socket = null;
  }
}
