const showGlobalError = (msg) => {
  m$('global_error_msg').innerText = msg;
  m$('global_error_ui').classList.remove('no-error');
};
m$('global_error_ui_ack').onclick = () => {
  m$('global_error_msg').innerText = '';
  m$('global_error_ui').classList.add('no-error');
};

window.remote_thing_registry = new Zigbee2Mqtt2Flask2js(showGlobalError);
window.local_storage = new LocalStorageManager();
window.thing_registry = new ThingRegistry(local_storage, remote_thing_registry);

const app_visibility = new VisibilityCallback();
app_visibility.app_became_visible = () => {
  console.log("App became visible, will refresh state")
  thing_registry.updateWorldState();
}

function loadMainApp() {
  let things = [];

  for (const meta of thing_registry.lights) {
    const props = Light.buildProps(thing_registry, meta);
    things.push(React.createElement(Light, props));
  }

  for (const meta of thing_registry.switches) {
    const props = Switch.buildProps(thing_registry, meta);
    things.push(React.createElement(Switch, props));
  }

  const thingsPaneProps = ThingsPane.buildProps(local_storage, things);
  ReactDOM.createRoot(document.querySelector('#things_root')).render(
    React.createElement(ThingsPane, thingsPaneProps)
  );

  ReactDOM.createRoot(document.querySelector('#others_root')).render([
    React.createElement(ScenesPane, {key: 'scenes_list', thing_registry: thing_registry, scenes: thing_registry.scenes[0]}),
    React.createElement(SensorsPane, SensorsPane.buildProps(thing_registry)),
    React.createElement(MediaPlayerList, MediaPlayerList.buildProps(thing_registry)),
    React.createElement(MiscStuff, MiscStuff.buildProps(thing_registry, remote_thing_registry, thingsPaneProps)),
  ]);
}


function loadSensors() {
  ReactDOM.createRoot(document.querySelector('#sensors_root')).render([
    React.createElement(SensorsHistoryPane, SensorsHistoryPane.buildProps(thing_registry)),
  ]);
}


thing_registry.rebuild_network_map_if_unknown().then(_ => {
  if (document.location.href.includes('www/sensors.html')) {
    loadSensors();
  } else {
    loadMainApp();
  }
});

thing_registry.updateWorldState();
m$('global_loading').classList.add('app-finished-loading');
m$('global_loading').classList.remove('app-loading');
