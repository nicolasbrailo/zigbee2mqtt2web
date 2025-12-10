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

class ThingsPane extends React.Component {
  static buildProps(local_storage, things) {
    // Expose state through props... surely that's the intended purpose, right?
    const cbObjReorderThings = {
      toggle: null,
    };

    const cbShowHiddenThings = {
      toggle: null,
    }

    return {
      key: 'global_thing_list',
      things: things,
      local_storage: local_storage,
      onReorderThings: cbObjReorderThings,
      showHiddenThings: cbShowHiddenThings,
    };
  }

  _getOrderedThings(props) {
    // Create default order for list
    let default_things_order = [];
    for (const elm of props.things) {
      default_things_order.push(elm.props.name);
    }

    // Try to fetch from cache
    let cached_things_order = this.props.local_storage.get('ThingsPane.things_order', default_things_order);
    const set_existing_things = new Set(default_things_order);
    const set_cached_things_order = new Set(cached_things_order);
    let order_changed = false;

    // If non existing things are in the order, delete them
    for (const [idx,elm] of cached_things_order.entries()) {
      if (!set_existing_things.has(elm)) {
        delete cached_things_order[idx];
        order_changed = true;
      }
    }
    cached_things_order = cached_things_order.filter(x => x != null);

    // If things are missing from the order, add them to the end
    for (const elm of default_things_order) {
      if (!set_cached_things_order.has(elm)) {
        cached_things_order.push(elm);
        order_changed = true;
      }
    }

    if (order_changed) {
      this.props.local_storage.save('ThingsPane.things_order', cached_things_order);
    }

    return cached_things_order;
  }

  constructor(props) {
    super(props);

    this.props.onReorderThings.toggle = () => {
      this.setState({reordering: !this.state.reordering});
    };

    this.props.showHiddenThings.toggle = () => {
      this.setState({showHiddenThings: !this.state.showHiddenThings});
    };

    const things_lookup = {};
    for (const elm of props.things) {
      things_lookup[elm.props.name] = elm;
    }

    this.state = {
      things_lookup: things_lookup,
      things_order: this._getOrderedThings(props),
      reordering: false,
      showHiddenThings: false,
      visibleGroup: null,
    };
  }

  reorder(idx, delta) {
    if ((idx + delta < 0) || (idx + delta >= this.state.things_order.length)) {
      return;
    }
    let new_order = this.state.things_order;
    const tmp = new_order[idx];
    new_order[idx] = new_order[idx+delta];
    new_order[idx+delta] = tmp;

    this.props.local_storage.save('ThingsPane.things_order', new_order);
    this.setState({things_order: new_order});
  }

  render() {
    if (this.state.reordering) return this.render_reordering();
    return <div key="global_thing_list_pane">
             {this._buildList()}
           </div>
  }

  _buildList() {
    const groupedThingList = new Map();
    groupedThingList.set(null, []);
    let current_group = null;
    for (const thing_name of this.state.things_order) {
      const thing = this.state.things_lookup[thing_name];

      let group = null;
      if (thing.props.user_defined) group = thing.props.user_defined.ui_group;
      if (group === undefined) group = null;
      if (group != current_group) {
        current_group = group;
        if (!groupedThingList.has(current_group)) {
          groupedThingList.set(current_group, []);
        }
      }

      const ui_hide = thing.props.user_defined && thing.props.user_defined.ui_hide;
      const classNames = (!this.state.showHiddenThings && ui_hide)? 'is-hidden' : '';
      groupedThingList.get(current_group).push(
        <li className={classNames} key={`${thing.props.name}_thing_li`}>
          {thing}
        </li>)
    }

    const groupList = [];
    const visibleGroup = (() => {
      if (this.state.visibleGroup) return this.state.visibleGroup;
      const groups = Array.from(groupedThingList.entries());
      if (groups.length == 0) return null;
      return groups[0][0];
    })();

    for (const e of groupedThingList.entries()) {
      const group = e[0];
      if (!group) continue; // We'll add null-group at the bottom

      const thinglist = e[1];
      const visible = (!this.state.showHiddenThings && group != null && group != visibleGroup)? 'is-hidden' : '';
      const expandGroupCtrl = (
        <div onClick={_ => this.setState({visibleGroup: group})} className="is-full-width text-dark bd-primary is-small is-a-bit-rounded">
          <b>{group}</b>
        </div>)
      groupList.push(
        <div className="card" key={`${group}_thing_pane_group`}>
        {expandGroupCtrl}
        <ul className={visible} key={`${group}_thing_pane_group_ul`}>
          {thinglist}
        </ul>
        </div>);
    }

    if (groupedThingList.get(null).length > 0) {
      groupList.push(
        <div className="card" key={`nullgroup_thing_pane_group`}>
        <ul key={`nullgroup_thing_pane_group_ul`}>
          {groupedThingList.get(null)}
        </ul>
        </div>);
    }

    return groupList;
  }

  render_reordering() {
    const thing_list = this.state.things_order.map((thing_name, idx) => {
      const thing = this.state.things_lookup[thing_name];
      const reorder_up = () => {
        return (idx == 0)?
                  '▲' :
                  <a className="thing-list-reorder-link" onClick={evnt => this.reorder(idx, -1)}>▲</a>
      }
      const reorder_down = () => {
        return (idx == this.state.things_order.length-1)?
                  '▼' :
                  <a className="thing-list-reorder-link" onClick={evnt => this.reorder(idx, +1)}>▼</a>
      }
      return <li key={`${thing.props.name}_thing_reorder_li`}>
        <div className="thing_div row"
             key={`${thing.props.name}_reorder_div`}>
          <div className="col-primary-action">
            { reorder_down() }
            { reorder_up() }
          </div>
          <div className="col-fixed-fill">
            <h3>{thing.props.name}</h3>
          </div>
        </div>
      </li>
    });

    return <ul key="global_thing_list_pane">
             {thing_list}
           </ul>
  }
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
  ReactDOM.createRoot(document.querySelector('#app_root')).render([
    React.createElement(SensorsHistoryPane, SensorsHistoryPane.buildProps(thing_registry)),
  ]);
}

function loadHeating() {
  ReactDOM.createRoot(document.querySelector('#app_root')).render([
    React.createElement(Heating, Heating.buildProps(thing_registry)),
  ]);
}

thing_registry.rebuild_network_map_if_unknown().then(_ => {
  if (document.location.href.includes('www/sensors.html')) {
    loadSensors();
  } else if (document.location.href.includes('www/heating.html')) {
    loadHeating();
  } else if (document.location.href.includes('www/devel.html')) {
    loadHeating();
  } else {
    loadMainApp();
  }
});

thing_registry.updateWorldState();
m$('global_loading').classList.add('app-finished-loading');
m$('global_loading').classList.remove('app-loading');
