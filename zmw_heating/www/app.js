function millisecToNextSlotChg() {
  const now = new Date();
  const qr = Math.floor(now.getMinutes() / 15);
  const nxt_slot_chg_min = (15 * (qr + 1)) % 60;
  const slot_chg = new Date();
  slot_chg.setMinutes(nxt_slot_chg_min);
  slot_chg.setSeconds(0);
  const ms_to_chg = (slot_chg - now);

  if (nxt_slot_chg_min == 0) {
    // If we're rolling over to start of the hour, add one hour
    return ms_to_chg + 60 * 60 * 1000;
  }

  return ms_to_chg;
}

function renderScheduleTable(sched, slotGenerator) {
  const qr_groupped_sched = {};
  for (let hr=0; hr<24; ++hr) {
    qr_groupped_sched[hr] = sched.slice(hr*4,(hr+1)*4);
  }
  return (
    <table className="heating_sched">
    <tbody>
    {Object.keys(qr_groupped_sched).map((hour) => {
      return (<tr key={`table_schedule_${hour}`}>
        {qr_groupped_sched[hour].map((slot) => {
          const slot_t = `${('0' + slot.hour).slice(-2)}:${('0' + slot.minute).slice(-2)}`;
          const sched_slot_class = slot.request_on? 'heating_sched_slotBoilerOn' : 'heating_sched_slotBoilerOff';
          return <td key={`table_schedule_${slot.hour}_${slot.minute}`} className={sched_slot_class}>
                  {slotGenerator(slot)}
                 </td>;
        })}
      </tr>);
    })}
    </tbody>
    </table>
  );
}

class HeatingControls extends React.Component {
  static buildProps(api_base_path = '', state = {}) {
    const props = {
      api_base_path: api_base_path,
    };

    // Optional: pass state data to avoid fetching if already available
    if (state.allow_on !== undefined) props.allow_on = state.allow_on;
    if (state.mqtt_thing_reports_on !== undefined) props.mqtt_thing_reports_on = state.mqtt_thing_reports_on;
    if (state.monitoring_sensors !== undefined) props.monitoring_sensors = state.monitoring_sensors;
    if (state.onRefresh !== undefined) props.onRefresh = state.onRefresh;

    return props;
  }

  constructor(props) {
    super(props);
    this._offNow = this._offNow.bind(this);
    this._refresh = this._refresh.bind(this);

    this.state = {
      allow_on: props.allow_on || null,
      mqtt_thing_reports_on: props.mqtt_thing_reports_on || null,
      monitoring_sensors: props.monitoring_sensors || null,
    };
  }

  componentDidMount() {
    // If no data provided via props, fetch it
    if (!this.props.allow_on && this.props.api_base_path) {
      this._refresh();
    }
  }

  componentDidUpdate(prevProps) {
    // Update internal state if props change
    if (prevProps.allow_on !== this.props.allow_on ||
        prevProps.mqtt_thing_reports_on !== this.props.mqtt_thing_reports_on ||
        prevProps.monitoring_sensors !== this.props.monitoring_sensors) {
      this.setState({
        allow_on: this.props.allow_on,
        mqtt_thing_reports_on: this.props.mqtt_thing_reports_on,
        monitoring_sensors: this.props.monitoring_sensors,
      });
    }
  }

  _refresh() {
    if (this.props.api_base_path) {
      mJsonGet(`${this.props.api_base_path}/svc_state`, state => {
        this.setState({
          allow_on: state.allow_on,
          mqtt_thing_reports_on: state.mqtt_thing_reports_on,
          monitoring_sensors: state.monitoring_sensors,
        });
        if (this.props.onRefresh) {
          this.props.onRefresh();
        }
      });
    }
  }

  _mkBoost(hours) {
    return () => {
      mJsonGet(`${this.props.api_base_path}/boost=${hours}`, this._refresh);
    };
  }

  _offNow() {
    mJsonGet(`${this.props.api_base_path}/off_now`, this._refresh);
  }

  renderHeatingOverrides() {
    let policy_state = "Boiler manager unknown state";
    if (this.state.allow_on == 'Never') {
      policy_state = "Boiler should be off";
    } else if (this.state.allow_on == 'Always') {
      policy_state = "Boiler should be on";
    } else if (this.state.allow_on == 'Rule') {
      policy_state = "Rule controls boiler state";
    }
    return <div className="card heating_cfg_ctrls">
        <div>
          Current status: {policy_state}, boiler reports {this.state.mqtt_thing_reports_on}
        </div>
        <button className="modal-button" onClick={this._mkBoost(1)}>Boost 1 hour</button>
        <button className="modal-button" onClick={this._mkBoost(2)}>Boost 2 hours</button>
        <button className="modal-button" onClick={this._offNow}>Off now</button>
      </div>
  }

  renderMonitoringSensors() {
    if (!this.state.monitoring_sensors) {
      return null;
    }
    return <div className="card heating_cfg_ctrls">
        {Object.entries(this.state.monitoring_sensors).map(([name, value]) => (
          <span key={name} className="bd-dark modal-button">{name}: {value || '?'}</span>
        ))}
      </div>
  }

  render() {
    return <>
      {this.renderHeatingOverrides()}
      {this.renderMonitoringSensors()}
    </>;
  }
}

class HeatingScheduleConfig extends React.Component {
  static buildProps(api_base_path = '', onRefresh = null, onToggleConfig = null, state = {}, renderFunctions = {}) {
    return {
      api_base_path: api_base_path,
      onRefresh: onRefresh,
      onToggleConfig: onToggleConfig,
      configuring: state.configuring || false,
      active_schedule: state.active_schedule || null,
      schedule_template: state.schedule_template || null,
      renderSlot: renderFunctions.renderSlot || null,
      renderTemplateSlot: renderFunctions.renderTemplateSlot || null,
    };
  }

  constructor(props) {
    super(props);
    this._applyTemplate = this._applyTemplate.bind(this);
    this._resetTemplateAlwaysOff = this._resetTemplateAlwaysOff.bind(this);
    this._resetTemplateAlwaysRule = this._resetTemplateAlwaysRule.bind(this);
    this._showLogs = this._showLogs.bind(this);
  }

  _applyTemplate() {
    mJsonGet(`${this.props.api_base_path}/template_apply`, this.props.onRefresh);
  }

  _resetTemplateAlwaysOff() {
    mJsonGet(`${this.props.api_base_path}/template_reset=Never`, this.props.onRefresh);
  }

  _resetTemplateAlwaysRule() {
    mJsonGet(`${this.props.api_base_path}/template_reset=Rule`, this.props.onRefresh);
  }

  _showLogs() {
    window.open('/logs.html', '_self');
  }

  renderConfig() {
    if (!this.props.schedule_template) {
      return null;
    }
    return <div>
        {this.renderTemplateControls()}
        {renderScheduleTable(this.props.schedule_template, this.props.renderTemplateSlot)}
      </div>;
  }

  renderState() {
    if (!this.props.active_schedule) {
      return null;
    }
    return <div>
      {renderScheduleTable(this.props.active_schedule, this.props.renderSlot)}
      {this.renderConfigControls()}
    </div>
  }

  renderConfigControls() {
    return <div className="card heating_cfg_ctrls">
        <button className="modal-button" onClick={this.props.onToggleConfig}>Config</button>
        <button className="modal-button" onClick={this._applyTemplate}>Reset today schedule</button>
        <button className="modal-button" onClick={this._showLogs}>Logs</button>
      </div>
  }

  renderTemplateControls() {
    return <div className="card heating_cfg_ctrls">
        <button className="modal-button" onClick={this.props.onToggleConfig}>Finish Config</button>
        <button className="modal-button" onClick={this._applyTemplate}>Apply template / reset today schedule</button>
        <button className="modal-button" onClick={this._resetTemplateAlwaysOff}>Reset template: Always off</button>
        <button className="modal-button" onClick={this._resetTemplateAlwaysRule}>Reset template: Always rule-based</button>
      </div>
  }

  render() {
    return this.props.configuring ? this.renderConfig() : this.renderState();
  }
}

class MqttHeating extends React.Component {
  static buildProps(api_base_path = '') {
    return {
      key: 'HeatingPane',
      api_base_path: api_base_path,
    };
  }

  constructor(props) {
    super(props);
    this.refresh = this.refresh.bind(this);
    this._toggleConfig = this._toggleConfig.bind(this);
    this._renderSlot = this._renderSlot.bind(this);
    this._renderTemplateSlot = this._renderTemplateSlot.bind(this);

    const app_visibility = new VisibilityCallback();
    app_visibility.app_became_visible = this.refresh;

    this.state = {
      configuring: false,
      active_schedule: null,
      schedule_template: null,
      allow_on: null,
      mqtt_thing_reports_on: null,
      monitoring_sensors: null,
      refreshId: null,
      app_visibility,
    };
  }

  refresh() {
    if (this.state.refreshId) {
      // Calling clearTimeout with an invalid id doesn't throw an error
      clearTimeout(this.state.refreshId);
    }

    if (this.state.configuring) {
      console.log("Configuring: will refresh schedule");
      mJsonGet(`${this.props.api_base_path}/template_schedule`, tmpl_state => {
        this.setState({schedule_template: tmpl_state.template});
      });
      return;
    }

    console.log("Refreshing boiler state...");
    mJsonGet(`${this.props.api_base_path}/svc_state`, state => {
      this.setState({active_schedule: state.active_schedule,
                     allow_on: state.allow_on,
                     mqtt_thing_reports_on: state.mqtt_thing_reports_on,
                     monitoring_sensors: state.monitoring_sensors,
                     refreshId: setInterval(this.refresh, millisecToNextSlotChg())});
    });
  }

  _toggleConfig() {
    this.setState({configuring: !this.state.configuring});
  }

  render() {
    return this.state.configuring? this.renderConfig() : this.renderState();
  }

  renderConfig() {
    if (!this.state.schedule_template) {
      this.refresh();
      return "Loading configuration...";
    }
    return <div>
      <HeatingScheduleConfig
        configuring={true}
        schedule_template={this.state.schedule_template}
        renderTemplateSlot={this._renderTemplateSlot}
        api_base_path={this.props.api_base_path}
        onRefresh={this.refresh}
        onToggleConfig={this._toggleConfig}
      />
    </div>;
  }

  renderState() {
    if (!this.state.active_schedule) {
      this.refresh();
      return "Loading...";
    }

    return <div>
      <HeatingControls
        allow_on={this.state.allow_on}
        mqtt_thing_reports_on={this.state.mqtt_thing_reports_on}
        monitoring_sensors={this.state.monitoring_sensors}
        api_base_path={this.props.api_base_path}
        onRefresh={this.refresh}
      />
      <HeatingScheduleConfig
        configuring={false}
        active_schedule={this.state.active_schedule}
        renderSlot={this._renderSlot}
        api_base_path={this.props.api_base_path}
        onRefresh={this.refresh}
        onToggleConfig={this._toggleConfig}
      />
    </div>
  }

  _renderSlot(slot) {
    const slot_name = `${('0' + slot.hour).slice(-2)}:${('0' + slot.minute).slice(-2)}`;
    const cb = () => {
      console.log("User toggling slot", slot_name);
      mJsonGet(`${this.props.api_base_path}/slot_toggle=${slot_name}`, this.refresh)
    };

    let descr = "Error";
    if (slot.allow_on == 'Never') {
      descr = `Off: ${slot.reason}`
    } else if (slot.allow_on == 'Always') {
      descr = `On: ${slot.reason}`
    } else if (slot.allow_on == 'Rule' && slot.request_on) {
      descr = `On: Rule ${slot.reason}`
    } else if (slot.allow_on == 'Rule' && !slot.request_on) {
      descr = `Off: Rule ${slot.reason}`
    }

    return <button className="modal-button" onClick={cb}>
             {slot_name}<wbr/> {descr}
           </button>
  }

  _renderTemplateSlot(slot) {
    const slot_name = `${('0' + slot.hour).slice(-2)}:${('0' + slot.minute).slice(-2)}`;
    const cb = (evt) => {
      const selected = evt.nativeEvent.target.value;
      console.log("Uset setting template", slot_name, selected);
      mJsonGet(`${this.props.api_base_path}/template_slot_set=${slot.hour},${slot.minute},${selected}`, this.refresh)
    };

    return <div>
            {slot_name}<wbr/> {slot.reason}
            <select key="`table_schedule_${slot.hour}_${slot.minute}_opt`"
                    defaultValue={slot.allow_on}
                    onChange={cb}>
              <option value="Always">Always on</option>
              <option value="Never">Always off</option>
              <option value="Rule">Follow rule</option>
            </select>
      </div>
  }
}
