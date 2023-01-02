class ThingRegistry {
  constructor(cache, remote_thing_registry) {
    this._state_update_callbacks = {};

    this.cache = cache;
    this.remote_thing_registry = remote_thing_registry;
    this.full_network_map_metas_cache_key = 'network_map_meta';
    this.network_lights_metas_cache_key = 'things_metas_lights';
    this.network_switches_metas_cache_key = 'things_metas_switches';
    this.network_sensors_metas_cache_key = 'things_metas_sensors';
    this.network_buttons_metas_cache_key = 'things_metas_buttons';
    this.network_mediaplayers_metas_cache_key = 'things_metas_mediaplayers';
    this.network_unknowns_metas_cache_key = 'things_metas_unknowns';
    this.scenes_metas_cache_key = 'things_metas_scenes';

    this.lights = this.cache.cacheGet_ignoreExpire(this.network_lights_metas_cache_key);
    this.switches = this.cache.cacheGet_ignoreExpire(this.network_switches_metas_cache_key);
    this.sensor_things = this.cache.cacheGet_ignoreExpire(this.network_sensors_metas_cache_key);
    this.button_things = this.cache.cacheGet_ignoreExpire(this.network_buttons_metas_cache_key);
    this.mediaplayer_things = this.cache.cacheGet_ignoreExpire(this.network_mediaplayers_metas_cache_key);
    this.unknown_things = this.cache.cacheGet_ignoreExpire(this.network_unknowns_metas_cache_key);
    this.scenes = this.cache.cacheGet_ignoreExpire(this.scenes_metas_cache_key);

    this.probably_needs_network_rebuild = false;
    if (!this.lights) { this.lights = []; this.probably_needs_network_rebuild = true; }
    if (!this.switches) { this.switches = []; this.probably_needs_network_rebuild = true; }
    if (!this.unknown_things) { this.unknown_things = []; this.probably_needs_network_rebuild = true; }
    if (!this.sensor_things) { this.sensor_things = []; this.probably_needs_network_rebuild = true; }
    if (!this.button_things) { this.button_things = []; this.probably_needs_network_rebuild = true; }
    if (!this.mediaplayer_things) { this.mediaplayer_things = []; this.probably_needs_network_rebuild = true; }
    if (!this.scenes) { this.scenes = []; this.probably_needs_network_rebuild = true; }

    remote_thing_registry.subscribe_to_mqtt_stream('ThingRegistry', msg => this._on_mqtt_state_update(msg));
  }

  subscribe_to_state_updates(thing_name, callback) {
    this._state_update_callbacks[thing_name] = callback;
  }

  updateWorldState() {
    this.remote_thing_registry.get_world().then(world_state => {
      const available_callbacks = Object.keys(this._state_update_callbacks);
      for (const thing_state of world_state) {
        for (const thing_name of Object.keys(thing_state)) {
          if (available_callbacks.includes(thing_name)) {
            const callback = this._state_update_callbacks[thing_name];
            callback(reactifyMqttStateUpdate(thing_state[thing_name]));
          }
        }
      }
    });
  }

  set_thing(thing_name, props) {
    return this.remote_thing_registry.set_thing(thing_name, props);
  }

  get_thing_state(thing_name) {
    return this.remote_thing_registry.get_thing_state(thing_name);
  }

  get_thing_action_state(thing_name, action_name) {
    return this.remote_thing_registry.get_thing_action_state(thing_name, action_name);
  }

  request_new_mqtt_networkmap() {
    return this.remote_thing_registry.request_new_mqtt_networkmap();
  }

  _on_mqtt_state_update(msg) {
    const available_callbacks = Object.keys(this._state_update_callbacks);
    for (const thing_name of Object.keys(msg)) {
      if (available_callbacks.includes(thing_name)) {
        const thing_state = msg[thing_name];
        const callback = this._state_update_callbacks[thing_name];
        callback(reactifyMqttStateUpdate(thing_state));
      }
    }
  }

  reloadThings() {
    console.log("Thing registry clearing local storage");
    this.cache.remove(this.full_network_map_metas_cache_key);
    this.cache.remove(this.network_lights_metas_cache_key);
    this.cache.remove(this.network_switches_metas_cache_key);
    this.cache.remove(this.network_sensors_metas_cache_key);
    this.cache.remove(this.network_buttons_metas_cache_key);
    this.cache.remove(this.network_mediaplayers_metas_cache_key);
    this.cache.remove(this.network_unknowns_metas_cache_key);
    this.cache.remove(this.scenes_metas_cache_key);
    // Things will break without the registry, so reload everything
    location.reload(false);
  }

  rebuild_network_map_if_unknown() {
    if (this.probably_needs_network_rebuild) {
      return this.rebuild_network_map();
    }

    var ready = $.Deferred();
    ready.resolve();
    return ready;
  }

  rebuild_network_map() {
    var ready = $.Deferred();
    this.get_all_things_meta().then(all_things => {
      this.lights = [];
      this.switches = [];
      this.sensor_things = [];
      this.button_things = [];
      this.mediaplayer_things = [];
      this.unknown_things = [];
      this.scenes = [];
      for (let thing of all_things) {
        const type = thing.thing_type? thing.thing_type : 'unknown';
        switch (type) {
          case 'light':
            this.lights.push(thing);
            break;
          case 'switch':
            this.switches.push(thing);
            break;
          case 'SceneManager':
            this.scenes.push(thing);
            break;
          case 'sensor':
            this.sensor_things.push(thing);
            break;
          case 'button':
            this.button_things.push(thing);
            break;
          case 'media_player':
            this.mediaplayer_things.push(thing);
            break;
          case 'unknown':  // fallthrough
          default:
            this.unknown_things.push(thing);
            break;
        }
      }

      this.cache.cacheSave(this.network_lights_metas_cache_key, this.lights);
      this.cache.cacheSave(this.network_switches_metas_cache_key, this.switches);
      this.cache.cacheSave(this.network_unknowns_metas_cache_key, this.unknown_things);
      this.cache.cacheSave(this.network_sensors_metas_cache_key, this.sensor_things);
      this.cache.cacheSave(this.network_buttons_metas_cache_key, this.button_things);
      this.cache.cacheSave(this.network_mediaplayers_metas_cache_key, this.mediaplayer_things);
      this.cache.cacheSave(this.scenes_metas_cache_key, this.scenes);
      this.probably_needs_network_rebuild = false;
      ready.resolve();
    });
    return ready;
  }

  get_all_things_meta() {
    var ready = $.Deferred();

    let netmap = this.cache.cacheGet_ignoreExpire(this.full_network_map_metas_cache_key);
    if (netmap != null) {
      ready.resolve(netmap);
      return ready;
    }

    this.uncached_get_all_things_meta(ready).then( netmap => {
      this.cache.cacheSave(this.full_network_map_metas_cache_key, netmap);
      ready.resolve(netmap);
    });

    return ready;
  }

  uncached_get_all_things_meta() {
    var ready = $.Deferred();
    this.remote_thing_registry.ls().then(names => {
      let all_metas = [];
      let meta_rqs = [];
      for (let name of names) {
        let meta_rq = this.remote_thing_registry.get_thing_meta(name)
          .then(meta => all_metas.push(meta));
        meta_rqs.push(meta_rq);
      }
      $.when.apply(null, meta_rqs).done(_ => {
        ready.resolve(all_metas);
      });
    });
    return ready;
  }
}
