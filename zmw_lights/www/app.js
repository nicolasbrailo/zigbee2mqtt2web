function filterMeta(meta) {
  const filtered = {
    description: meta.description,
    model: meta.model,
    name: meta.name,
    real_name: meta.real_name,
    thing_type: meta.thing_type,
    thing_id: meta.thing_id,
    address: meta.address,
    actions: {},
  };

  const actionNames = ['brightness', 'color_rgb', 'color_temp', 'effect', 'state'];
  for (const actionName of actionNames) {
    if (meta.actions && meta.actions[actionName]) {
      filtered.actions[actionName] = meta.actions[actionName];
    }
  }

  return filtered;
}

async function getLightsMeta(api_base_path, lights) {
  // Fetch metadata for all lights in parallel
  const metaPromises = lights.map((light) => {
    return new Promise((resolve) => {
      mJsonGet(`${api_base_path}/z2m/meta/${light.thing_name}`, (meta) => {
        resolve({ name: light.thing_name, meta: filterMeta(meta) });
      });
    });
  });

  const metaResults = await Promise.all(metaPromises);
  const metaByName = {};
  for (const result of metaResults) {
    metaByName[result.name] = result.meta;
  }
  return metaByName;
}

function getPrefixGroups(lightNames) {
  // Get valid prefixes for a name (split at uppercase letters, min 3 chars)
  function getValidPrefixes(name) {
    const prefixes = [];
    for (let i = 1; i < name.length; i++) {
      if (name[i] >= 'A' && name[i] <= 'Z') {
        const prefix = name.substring(0, i);
        if (prefix.length >= 3) {
          prefixes.push(prefix);
        }
      }
    }
    if (name.length >= 3) {
      prefixes.push(name);
    }
    return prefixes;
  }

  // Count occurrences of each prefix
  const prefixCounts = {};
  for (const name of lightNames) {
    for (const prefix of getValidPrefixes(name)) {
      prefixCounts[prefix] = (prefixCounts[prefix] || 0) + 1;
    }
  }

  // For each light, find the prefix with the most lights (>= 2)
  const groups = {};
  const assigned = new Set();

  for (const name of lightNames) {
    let bestPrefix = null;
    let bestCount = 1;

    for (const prefix of getValidPrefixes(name)) {
      if (prefixCounts[prefix] > bestCount) {
        bestPrefix = prefix;
        bestCount = prefixCounts[prefix];
      }
    }

    if (bestPrefix) {
      if (!groups[bestPrefix]) {
        groups[bestPrefix] = [];
      }
      groups[bestPrefix].push(name);
      assigned.add(name);
    }
  }

  // Put unassigned lights in "Others"
  const others = lightNames.filter(name => !assigned.has(name));
  if (others.length > 0) {
    groups['Others'] = others;
  }

  return groups;
}

function groupLightsByPrefix(lights) {
  const lightNames = lights.map(light => light.thing_name);
  const groupsByName = getPrefixGroups(lightNames);

  // Convert name groups to light object groups
  const lightsByName = {};
  for (const light of lights) {
    lightsByName[light.thing_name] = light;
  }

  const groups = {};
  const sortedPrefixes = Object.keys(groupsByName).sort((a, b) => a.localeCompare(b));
  for (const prefix of sortedPrefixes) {
    groups[prefix] = groupsByName[prefix]
      .map(name => lightsByName[name])
      .sort((a, b) => a.thing_name.localeCompare(b.thing_name));
  }

  return groups;
}

class DebouncedRange extends React.Component {
  // "Smart" range that will let you update the UI, but will only fire a change event once the user
  // releases the element. This is to avoid spamming changes that may need to travel over the network
  constructor(props) {
    super(props);
    this.state = {
      changing: false,
      value: props.value ?? props.min ?? 0,
    };
  }

  componentDidUpdate(prevProps) {
    if (prevProps.value !== this.props.value && !this.state.changing) {
      this.setState({ value: this.props.value ?? 0 });
    }
  }

  onChange(value) {
    this.setState({ value: value });
  }

  onMouseUp(_) {
    this.setState({ changing: false });
    this.props.onChange({ target: { value: this.state.value } });
  }

  onMouseDown(_) {
    this.setState({ changing: true });
  }

  render() {
    return (
      <input
        type="range"
        onChange={(e) => this.onChange(e.target.value)}
        onMouseUp={(e) => this.onMouseUp(e.target.value)}
        onMouseDown={(e) => this.onMouseDown(e.target.value)}
        onTouchStart={(e) => this.onMouseDown(e.target.value)}
        onTouchEnd={(e) => this.onMouseUp(e.target.value)}
        className={this.props.className}
        min={this.props.min}
        max={this.props.max}
        value={this.state.value}
      />
    );
  }
}

class ZmwLight extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      state: props.light.state,
      brightness: props.light.brightness,
      color_temp: props.light.color_temp,
      color_rgb: props.light.color_rgb || '#ffffff',
      effect: props.light.effect,
    };
  }

  componentDidUpdate(prevProps) {
    if (prevProps.light !== this.props.light) {
      this.setState({
        state: this.props.light.state,
        brightness: this.props.light.brightness,
        color_temp: this.props.light.color_temp,
        color_rgb: this.props.light.color_rgb || '#ffffff',
        effect: this.props.light.effect,
      });
    }
  }

  onStateChange(e) {
    const v = e.target.checked;
    this.setState({ state: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.light.thing_name}`, `state=${v}`);
  }

  onBrightnessChange(e) {
    const v = e.target.value;
    if (v == 0) {
      this.setState({ brightness: 0, state: false });
    } else {
      this.setState({ brightness: v, state: true });
    }
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.light.thing_name}`, `brightness=${v}`);
  }

  onColorTempChange(e) {
    const v = e.target.value;
    this.setState({ color_temp: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.light.thing_name}`, `color_temp=${v}`);
  }

  onColorRgbChange(e) {
    const v = e.target.value;
    this.setState({ color_rgb: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.light.thing_name}`, `color_rgb=${v}`);
  }

  onEffectChange(e) {
    const v = e.target.value;
    this.setState({ effect: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.light.thing_name}`, `effect=${v}`);
  }

  renderColorTemp() {
    const meta = this.props.meta;
    if (!meta.actions.color_temp) {
      return null;
    }

    const colorTempMeta = meta.actions.color_temp.value.meta;
    const presets = colorTempMeta.presets || [];

    return (
      <div>
      <label>Temperature</label>
      <DebouncedRange
        min={colorTempMeta.value_min}
        max={colorTempMeta.value_max}
        value={this.state.color_temp}
        onChange={(e) => this.onColorTempChange(e)}
      />
      <select value={this.state.color_temp} onChange={(e) => this.onColorTempChange(e)}>
        {presets.map((preset) => (
          <option key={preset.name} value={preset.value}>{preset.name}</option>
        ))}
      </select>
      </div>
    );
  }

  renderColorRgb() {
    const meta = this.props.meta;
    if (!meta.actions.color_rgb) {
      return null;
    }

    return (
      <div>
      <label>RGB</label>
      <input
        type="color"
        value={this.state.color_rgb}
        onChange={(e) => this.onColorRgbChange(e)}
      />
      </div>
    );
  }

  renderEffect() {
    const meta = this.props.meta;
    if (!meta.actions.effect) {
      return null;
    }

    const effectValues = meta.actions.effect.value.meta.values || [];

    return (
      <div>
      <label>Effect</label>
      <select value={this.state.effect || ''} onChange={(e) => this.onEffectChange(e)}>
        <option value="">None</option>
        {effectValues.map((effect) => (
          <option key={effect} value={effect}>{effect}</option>
        ))}
      </select>
      </div>
    );
  }

  renderExtraCfgs() {
    const meta = this.props.meta;
    if (!(meta.actions.color_temp || meta.actions.color_rgb || meta.actions.effect)) {
      return null;
    }

    return (
      <details className="light_details">
        <summary>⚙</summary>
        {meta.name} ({meta.description} / {meta.model})
        {this.renderColorTemp()}
        {this.renderColorRgb()}
        {this.renderEffect()}
      </details>
    );
  }


  render() {
    const light = this.props.light;
    const meta = this.props.meta;
    const displayName = light.thing_name.startsWith(this.props.prefix)
      ? light.thing_name.slice(this.props.prefix.length)
      : light.thing_name;
    return (
      <li>
        <input
          id={`${light.thing_name}_light_is_on`}
          type="checkbox"
          value="true"
          checked={this.state.state}
          onChange={(e) => this.onStateChange(e)}
        />
        <label htmlFor={`${light.thing_name}_light_is_on`}>{displayName}</label>
        <DebouncedRange
          min={0}
          max={254}
          value={this.state.brightness}
          onChange={(e) => this.onBrightnessChange(e)}
        />
        {this.renderExtraCfgs()}
      </li>
    );
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
    };
  }

  async componentDidMount() {
    this.fetchLights();
  }

  on_app_became_visible() {
    this.fetchLights();
  }

  setLightsState(lights, meta) {
    const groups = groupLightsByPrefix(lights);
    this.setState({ lights: lights, groups: groups, meta: meta });
  }

  clearCache() {
    const storage = this.props.local_storage;
    storage.remove('zmw_lights_hash');
    storage.remove('lights_meta');
    this.fetchLights();
  }

  fetchLights() {
    const storage = this.props.local_storage;
    const cachedHash = storage.get('zmw_lights_hash', null);

    // Always fetch lights state
    mJsonGet(`${this.props.api_base_path}/get_lights`, async (lights) => {
      // Check hash to decide if we need to fetch metadata
      mJsonGet(`${this.props.api_base_path}/z2m/get_known_things_hash`, async (serverHash) => {
        const cachedMeta = storage.cacheGet('lights_meta');

        if (cachedHash && cachedHash === serverHash && cachedMeta) {
          // Hash matches and we have cached metadata, use it
          this.setLightsState(lights, cachedMeta);
          return;
        }

        // Hash doesn't match or no cache, fetch metadata
        const metaByName = await getLightsMeta(this.props.api_base_path, lights);
        storage.save('zmw_lights_hash', serverHash);
        storage.cacheSave('lights_meta', metaByName);
        this.setLightsState(lights, metaByName);
      });
    });
  }

  render() {
    if (!this.state.lights) {
      return ( <div className="app-loading">Loading...</div> );
    }

    return (
      <div id="zmw_lights">
        {Object.entries(this.state.groups).map(([prefix, lights]) => (
          <details key={prefix}>
            <summary>{prefix}</summary>
            <ul>
              {lights.map((light) => (
                <ZmwLight key={light.thing_name} light={light} meta={this.state.meta[light.thing_name]} prefix={prefix} api_base_path={this.props.api_base_path} />
              ))}
            </ul>
          </details>
        ))}
        { this.props.runningStandaloneApp && (
          <button onClick={() => this.clearCache()}>Clear cache</button>)}
      </div>
    );
  }
}

class StandaloneMqttLights extends MqttLights {
  static buildProps(api_base_path = '') {
    const p = super.buildProps();
    p.runningStandaloneApp = true;
    return p;
  }
}
