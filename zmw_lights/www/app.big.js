class DebouncedRange extends React.Component {
  constructor(props) {
    super(props);

    // Fail early on missing props
    props.min.this_is_a_required_prop;
    props.max.this_is_a_required_prop;
    props.value.this_is_a_required_prop;

    const val = (props.value)? props.value : props.min;
    this.state = {
      changing: false,
      value: val,
    };
  }

  UNSAFE_componentWillReceiveProps(next_props) {
    // Without this, we need to rely on having a key being set for the
    // component to update its state from both parent and internal changes
    // If UNSAFE_componentWillReceiveProps stops working (it may be removed?)
    // then using this element will need to include a key with the current
    // value., Eg:
    // <DebouncedRange
    //       key={`${UNIQ_ELEMENT_NAME}_slider_${parent.state.value}`}
    //       min={$min}
    //       max={$max}
    //       value={parent.state.value} />
    const val = (next_props && next_props.value)? next_props.value : 0;
    this.setState({value: val});
  }

  onChange(value) {
      this.setState({value: value});
  }

  onMouseUp(_) {
      this.setState({changing: false});
      this.props.onChange({target: { value: this.state.value }});
  }

  onMouseDown(_) {
      this.setState({changing: true});
  }

  render() {
    return <input type="range"
             onChange={ (evnt) => this.onChange(evnt.target.value)}
             onMouseUp={ (evnt) => { this.onMouseUp(evnt.target.value) }  }
             onMouseDown={ (evnt) => this.onMouseDown(evnt.target.value) }
             onTouchStart={ (evnt) => this.onMouseDown(evnt.target.value)}
             onTouchEnd={ (evnt) => this.onMouseUp(evnt.target.value)}
             className={this.props.className}
             min={this.props.min}
             max={this.props.max}
             value={this.state.value} />
  }
}
class Light extends React.Component {
  static buildProps(meta, state, api_base_path = '') {
    var props = {
      name: meta.name,
      description: meta.description,
      manufacturer: meta.manufacturer,
      model: meta.model,
      supports_brightness: false,
      brightness_min: 0,
      brightness_max: 0,
      supports_color_temp: false,
      color_temp_min: 0,
      color_temp_max: 0,
      color_temp_presets: [],
      supports_rgb: false,
      user_defined: meta.user_defined,
      api_base_path: api_base_path,
      // Current state from server
      current_state: state.state || false,
      current_brightness: state.brightness || 0,
      current_color_temp: state.color_temp || 0,
      current_color_rgb: state.color_rgb || '',
    }

    for (const action_name of Object.keys(meta.actions)) {
      var desc = meta.actions[action_name].value.meta;
      if (!desc) desc = {};

      if (action_name == 'brightness') {
        props.supports_brightness = true;
        props.brightness_min = desc.value_min;
        props.brightness_max = desc.value_max;
      }

      else if (action_name == 'color_temp') {
        props.supports_color_temp = true;
        props.color_temp_min = desc.value_min;
        props.color_temp_max = desc.value_max;
        props.color_temp_presets = desc.presets;
      }

      else if (action_name == 'color_rgb') {
        props.supports_rgb = true;
      }
    }

    props.has_extra_details = props.supports_color_temp
                              || props.supports_rgb;
    return props;
  }

  constructor(props) {
    super(props);
    this.state = {
      state: props.current_state,
      brightness: props.current_brightness || props.brightness_min,
      color_temp: props.current_color_temp || props.color_temp_min,
      color_rgb: props.current_color_rgb || '',
      details_shown: false,
    };

    /* TODO
    this.props.thing_registry.subscribe_to_state_updates(this.props.name,
      (state) => {
        this.setState(state);
      });
      */
  }

  componentDidUpdate(prevProps) {
    // Only update state from props when props actually change (server state updated)
    if (prevProps.current_state !== this.props.current_state ||
        prevProps.current_brightness !== this.props.current_brightness ||
        prevProps.current_color_temp !== this.props.current_color_temp ||
        prevProps.current_color_rgb !== this.props.current_color_rgb) {
      this.setState({
        state: this.props.current_state,
        brightness: this.props.current_brightness || this.props.brightness_min,
        color_temp: this.props.current_color_temp || this.props.color_temp_min,
        color_rgb: this.props.current_color_rgb || '',
      });
    }
  }

  setLightOn(v) {
    this.setState({ state: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.name}`, `state=${v}`);
  }

  changeBrightness(v) {
    if (v == 0) {
      this.setState({ brightness: 0, state: false });
    } else {
      this.setState({ brightness: v, state: true });
    }
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.name}`, `brightness=${v}`);
  }

  changeColorTemp(v) {
    this.setState({ color_temp: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.name}`, `color_temp=${v}`);
  }

  toggleDetailsPanel() {
    this.setState({ details_shown: !this.state.details_shown });
  }

  changeRGB(v) {
    this.setState({ color_rgb: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.name}`, `color_rgb=${encodeURIComponent(v)}`);
  }

  render() {
    return (
      <div className='thing_div' key={`${this.props.name}_light_div`}>

        <div className="row">
          <div className="col-primary-action">
            <input type="checkbox"
                   checked={this.state.state}
                   value={this.state.state}
                   onChange={(evnt) => this.setLightOn(evnt.target.checked)}
                   key={`${this.props.name}_light_is_on`} />
          </div>

          <div className="col-fixed-fill thing-no-linebreak">
            <div className="row">
              <div className="col-fixed-fill">
              <label className='thing_name' htmlFor={`${this.props.name}_light_is_on`}>
                {this.props.name}
              </label>
              </div>

              { this.render_details_toggle() }
            </div>

            <div className="row">
              { this.render_brightness_select() }
            </div>
          </div>
        </div>

        { this.render_details_panel() }
      </div>
    );
  }

  render_details_toggle() {
    if (!this.props.has_extra_details) return '';
    return <div key={`${this.props.name}_light_details_panel_toggle_div`} className="toggle-details-panel">
             {this.render_details_toggle_link()}
           </div>;
  }

  render_details_toggle_link() {
    if (!this.state.details_shown) {
      return (<a key={`${this.props.name}_light_details_panel_toggle`}
                 onClick={evnt => this.toggleDetailsPanel()}>▼</a>);
    }

    return (<a key={`${this.props.name}_light_details_panel_toggle`}
               onClick={evnt => this.toggleDetailsPanel()} >▲</a>);
  }

  render_details_panel() {
    if (!this.props.has_extra_details) return '';
    if (!this.state.details_shown) return '';
    return (
        <div className="card modal">
          { [this.render_rgb_picker(), this.render_color_temp()] }
        </div>)
  }

  render_brightness_select() {
    if (!this.props.supports_brightness) return '';
    return (
      <DebouncedRange
             onChange={ (evnt) => this.changeBrightness(evnt.target.value) }
             key={`${this.props.name}_light_brightness_slider`}
             min={this.props.brightness_min}
             max={this.props.brightness_max}
             value={this.state.brightness} />
    )
  }

  render_color_temp() {
    if (!this.props.supports_color_temp) return '';
    return (
      <div key={`${this.props.name}_div_color_temp`}>
        <label>Temperature</label>
        <DebouncedRange
               onChange={(evnt) => this.changeColorTemp(evnt.target.value)}
               key={`${this.props.name}_light_color_temp`}
               min={this.props.color_temp_min}
               max={this.props.color_temp_max}
               value={this.state.color_temp} />
        { this.render_color_temp_presets() }
      </div>
    )
  }

  render_color_temp_presets() {
    if (!this.props.color_temp_presets || this.props.color_temp_presets.length == 0) {
      return '';
    }

    var presets = []
    for (const p of this.props.color_temp_presets) {
      presets.push(
        <option
            key={`${this.props.name}_option_color_temp_preset_${p.name}`}
            value={p.value}>
          {p.name}
        </option> 
      )
    }

    return (
      <select
          onChange={(evnt) => this.changeColorTemp(evnt.target.value)}
          key={`${this.props.name}_div_color_temp_presets`}
          value="">
        { presets }
      </select>
    )
  }

  render_rgb_picker() {
    if (!this.props.supports_rgb) return '';
    return (
      <div key={`${this.props.name}_div_color_picker`}>
        <label>Lamp color</label>
        <input type="color"
               onChange={(evt) => this.changeRGB(evt.target.value)}
               key={`${this.props.name}_light_rgb`}
               value={this.state.color_rgb} />
      </div>
    )
  }
}
class ThingsPane extends React.Component {
  static buildProps(local_storage, things, onResetOrder, onToggleReorder) {
    return {
      key: 'global_thing_list',
      things: things,
      local_storage: local_storage,
      onResetOrder: onResetOrder,
      onToggleReorder: onToggleReorder,
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

  static getDerivedStateFromProps(props, state) {
    // Rebuild things_lookup whenever props.things changes
    const things_lookup = {};
    for (const elm of props.things) {
      things_lookup[elm.props.name] = elm;
    }
    return { things_lookup };
  }

  constructor(props) {
    super(props);

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

  toggleReordering() {
    this.setState({reordering: !this.state.reordering});
  }

  toggleShowHidden() {
    this.setState({showHiddenThings: !this.state.showHiddenThings});
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
        <div className="light-group-collapsed" key={`${group}_thing_pane_group`}>
        {expandGroupCtrl}
        <ul className={visible} key={`${group}_thing_pane_group_ul`}>
          {thinglist}
        </ul>
        </div>);
    }

    if (groupedThingList.get(null).length > 0) {
      groupList.push(
        <div className="light-group-expanded" key={`nullgroup_thing_pane_group`}>
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

    return <div key="global_thing_list_pane">
             <button onClick={() => this.toggleReordering()}>
               Done
             </button>
             <ul key="global_thing_list_ul">
               {thing_list}
             </ul>
           </div>
  }
}

class MqttLights extends React.Component {
  static buildProps(api_base_path = '') {
    return {
      key: 'MqttLights',
      local_storage: new LocalStorageManager(),
      api_base_path: api_base_path,
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      lights: null,
      thingsPaneKey: 0,
      autoGrouping: props.local_storage.get('autoGrouping', true),
      configExpanded: false,
    };
    this.thingsPaneRef = React.createRef();
  }

  analyzeGroups(lights) {
    console.log('=== Starting group analysis ===');
    console.log('Light names:', lights.map(l => l.meta.name));

    // Extract possible prefixes from each name
    const extractPrefix = (name) => {
      // Match sequences like "TVRoom" (all-caps followed by capitalized word)
      // Examples: "TVRoomSnoopy" -> "TVRoom", "TVRoomFloorlampLeft" -> "TVRoom"
      const capsWordMatch = name.match(/^([A-Z]{2,}[A-Z][a-z]+)/);
      if (capsWordMatch) {
        console.log(`    extractPrefix("${name}") caps+word match: ${capsWordMatch[1]}`);
        return capsWordMatch[1];
      }

      // Match simple camelCase: get the first word before another uppercase letter
      // Examples: "OliviaFloorlamp" -> "Olivia", "EmmaVelador" -> "Emma"
      const camelMatch = name.match(/^([A-Z][a-z]+)/);
      if (camelMatch) {
        console.log(`    extractPrefix("${name}") camelCase match: ${camelMatch[1]}`);
        return camelMatch[1];
      }

      // Fallback: match all letters until non-letter
      const fallbackMatch = name.match(/^([A-Za-z]+)/);
      const result = fallbackMatch ? fallbackMatch[1] : null;
      console.log(`    extractPrefix("${name}") fallback: ${result}`);
      return result;
    };

    // Count prefix occurrences
    const prefixCounts = {};
    const nameToPrefixes = {};

    for (const light of lights) {
      const name = light.meta.name;
      const prefix = extractPrefix(name);
      console.log(`  ${name} -> prefix: ${prefix}`);
      if (prefix && prefix.length >= 3) {
        prefixCounts[prefix] = (prefixCounts[prefix] || 0) + 1;
        nameToPrefixes[name] = prefix;
      }
    }

    console.log('Prefix counts:', prefixCounts);

    // Assign groups (only if prefix appears 2+ times)
    const groups = {};
    for (const light of lights) {
      const name = light.meta.name;
      const prefix = nameToPrefixes[name];
      if (prefix && prefixCounts[prefix] >= 2) {
        groups[name] = prefix;
        console.log(`  ${name} assigned to group: ${prefix}`);
      } else {
        groups[name] = null;
        console.log(`  ${name} not grouped (prefix: ${prefix}, count: ${prefixCounts[prefix] || 0})`);
      }
    }

    console.log('Final groups:', groups);
    return groups;
  }

  applyGrouping(lights, enabled) {
    console.log(`=== applyGrouping called, enabled: ${enabled} ===`);

    if (!enabled) {
      console.log('Removing all grouping');
      // Remove grouping
      for (const light of lights) {
        if (!light.meta.user_defined) light.meta.user_defined = {};
        light.meta.user_defined.ui_group = undefined;
      }
      return lights;
    }

    // Apply auto-grouping
    const groups = this.analyzeGroups(lights);
    console.log('Applying grouping to lights...');
    for (const light of lights) {
      if (!light.meta.user_defined) light.meta.user_defined = {};
      light.meta.user_defined.ui_group = groups[light.meta.name];
      console.log(`  ${light.meta.name}.ui_group = ${light.meta.user_defined.ui_group}`);
    }
    console.log('=== Grouping applied ===');
    return lights;
  }

  applyGroupingNow() {
    // Toggle grouping state
    const newValue = !this.state.autoGrouping;
    this.props.local_storage.save('autoGrouping', newValue);
    this.setState({ autoGrouping: newValue });

    // Clear cached metadata and order to force recalculation
    this.props.local_storage.remove('things_meta');
    this.props.local_storage.remove('things_hash');
    this.props.local_storage.remove('ThingsPane.things_order');

    // Reload lights with new grouping setting
    this.fetchLights();
  }

  resetOrder() {
    if (!this.state.lights) return;

    // Sort by group first, then alphabetically (grouping already applied to metadata)
    const sorted_lights = [...this.state.lights].sort((a, b) => {
      const groupA = a.meta.user_defined?.ui_group || '';
      const groupB = b.meta.user_defined?.ui_group || '';

      if (groupA && groupB) {
        if (groupA !== groupB) {
          return groupA.localeCompare(groupB);
        }
        return a.meta.name.localeCompare(b.meta.name);
      }

      if (groupA && !groupB) return -1;
      if (!groupA && groupB) return 1;

      return a.meta.name.localeCompare(b.meta.name);
    });

    const sorted_names = sorted_lights.map(light => light.meta.name);

    // Save to local storage
    this.props.local_storage.save('ThingsPane.things_order', sorted_names);

    // Force ThingsPane to re-mount by changing its key
    this.setState({ thingsPaneKey: this.state.thingsPaneKey + 1 });
  }

  fetchLights(force_reload = false) {
    mJsonGet(`${this.props.api_base_path}/z2m/get_known_things_hash`, (server_hash) => {
      const cached_hash = this.props.local_storage.cacheGet('things_hash');
      const cached_meta = this.props.local_storage.cacheGet('things_meta');
      const hash_changed = cached_hash !== server_hash;

      // Always fetch current state with /get_lights
      mJsonGet(`${this.props.api_base_path}/get_lights`, async (lights_list) => {
        // If hash changed or no cached metadata, fetch metadata for all lights
        if (hash_changed || !cached_meta) {
          const lights_with_meta = await Promise.all(
            lights_list.map(light =>
              new Promise(resolve => {
                mJsonGet(`${this.props.api_base_path}/z2m/meta/${light.thing_name}`, (meta) => {
                  resolve({ state: light, meta: meta });
                });
              })
            )
          );

          // Apply grouping if enabled
          console.log('Applying grouping during fetch, autoGrouping:', this.state.autoGrouping);
          this.applyGrouping(lights_with_meta, this.state.autoGrouping);

          // Cache the metadata WITH grouping applied, using thing_name as key
          const meta_by_name = {};
          for (const light of lights_with_meta) {
            meta_by_name[light.state.thing_name] = light.meta;
          }
          this.props.local_storage.cacheSave('things_meta', meta_by_name);
          this.props.local_storage.cacheSave('things_hash', server_hash);

          this.setState({ lights: lights_with_meta });
        } else {
          // Use cached metadata, only fetched fresh state
          const lights_with_meta = lights_list.map(light => ({
            state: light,
            meta: cached_meta[light.thing_name]
          }));
          // Grouping is already in cached meta, no need to reapply
          this.setState({ lights: lights_with_meta });
        }
      });
    });
  }

  async componentDidMount() {
    this.fetchLights();
  }

  on_app_became_visible() {
    this.fetchLights(true);
  }

  componentWillUnmount() {
  }

  fetchStats() {
    mJsonGet(`${this.props.api_base_path}/get_lights`, (res) => {
      this.setState({ lights: res });
    });
  }

  render() {
    if (!this.state.lights) {
      return ( <div className="app-loading">Loading...</div> );
    }

    console.log('=== MqttLights.render() ===');
    console.log('autoGrouping state:', this.state.autoGrouping);

    // Grouping is already applied in the cached data, just sort
    const sorted_lights = [...this.state.lights].sort((a, b) => {
      const groupA = a.meta.user_defined?.ui_group || '';
      const groupB = b.meta.user_defined?.ui_group || '';

      // If both have groups, sort by group then name
      if (groupA && groupB) {
        if (groupA !== groupB) {
          return groupA.localeCompare(groupB);
        }
        return a.meta.name.localeCompare(b.meta.name);
      }

      // Items with groups come before items without
      if (groupA && !groupB) return -1;
      if (!groupA && groupB) return 1;

      // Both without groups, sort alphabetically
      return a.meta.name.localeCompare(b.meta.name);
    });

    // Create Light components from the fetched lights
    const light_components = sorted_lights.map(light => {
      const props = Light.buildProps(light.meta, light.state, this.props.api_base_path);
      return React.createElement(Light, props);
    });

    // Create and render ThingsPane with the Light components
    const thingsPaneProps = ThingsPane.buildProps(
      this.props.local_storage,
      light_components,
      () => this.resetOrder(),
      () => this.thingsPaneRef.current && this.thingsPaneRef.current.toggleReordering()
    );
    // Use thingsPaneKey to force re-mount when order is reset
    thingsPaneProps.key = `ThingsPane_${this.state.thingsPaneKey}`;
    thingsPaneProps.ref = this.thingsPaneRef;
    const thingsPane = React.createElement(ThingsPane, thingsPaneProps);

    return (
      <div>
        {thingsPane}
        <div className="config-section">
          <div
            className="config-toggle"
            onClick={() => this.setState({ configExpanded: !this.state.configExpanded })}>
            Config {this.state.configExpanded ? '▲' : '▼'}
          </div>
          {this.state.configExpanded && (
            <div className="config-panel">
              <button className="modal-button" onClick={() => this.thingsPaneRef.current && this.thingsPaneRef.current.toggleReordering()}>
                Reorder
              </button>
              <button className="modal-button" onClick={() => this.resetOrder()}>
                Reset order
              </button>
              <button className="modal-button" onClick={() => this.fetchLights(true)}>
                Refresh things
              </button>
              <button className="modal-button" onClick={() => this.applyGroupingNow()}>
                {this.state.autoGrouping ? 'Disable grouping' : 'Enable grouping'}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }
}
