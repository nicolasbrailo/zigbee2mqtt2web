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
