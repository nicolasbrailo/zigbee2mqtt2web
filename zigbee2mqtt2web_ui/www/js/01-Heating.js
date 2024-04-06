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

class Heating extends React.Component {
  static buildProps(thing_registry) {
    return {
      thing_registry,
      key: 'HeatingPane',
    };
  }

  constructor(props) {
    super(props);
    this.refresh = this.refresh.bind(this);
    this._offNow = this._offNow.bind(this);
    this._toggleConfig = this._toggleConfig.bind(this);
    this._showLogs = this._showLogs.bind(this);
    this._applyTemplate = this._applyTemplate.bind(this);
    this._resetTemplateAlwaysOff = this._resetTemplateAlwaysOff.bind(this);
    this._resetTemplateAlwaysRule = this._resetTemplateAlwaysRule.bind(this);
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
      this.props.thing_registry.get_thing_action_state('Heating', 'template_schedule').then(tmpl_state => {
        this.setState({schedule_template: JSON.parse(tmpl_state).template});
      });
      return;
    }

    console.log("Refreshing boiler state...");
    this.props.thing_registry.get_thing_state('Heating').then(state => {
      this.setState({active_schedule: state.active_schedule,
                     allow_on: state.allow_on,
                     mqtt_thing_reports_on: state.mqtt_thing_reports_on,
                     refreshId: setInterval(this.refresh, millisecToNextSlotChg())});
    });
  }

  _mkBoost(hours) {
    return () => {
      this.props.thing_registry.set_thing('Heating', `boost=${hours}`).then(()=>{this.refresh()});
    };
  }

  _offNow() {
    this.props.thing_registry.set_thing('Heating', 'off_now').then(()=>{this.refresh()});
  }

  _applyTemplate() {
    this.props.thing_registry.set_thing('Heating', 'template_apply').then(()=>{this.refresh()});
  }

  _resetTemplateAlwaysOff() {
    this.props.thing_registry.set_thing('Heating', 'template_reset=Never').then(()=>{this.refresh()});
  }

  _resetTemplateAlwaysRule() {
    this.props.thing_registry.set_thing('Heating', 'template_reset=Rule').then(()=>{this.refresh()});
  }

  _toggleConfig() {
    this.setState({configuring: !this.state.configuring});
  }

  _showLogs() {
    this.props.thing_registry.get_thing_action_state('Heating', 'log_url').then((url) => {
      window.open(url, '_blank')
    });
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
        {this.renderTemplateControls()}
        {renderScheduleTable(this.state.schedule_template, this._renderTemplateSlot)}
      </div>;
  }

  renderState() {
    if (!this.state.active_schedule) {
      this.refresh();
      return "Loading...";
    }

    return <div>
      {this.renderHeatingOverrides()}
      {renderScheduleTable(this.state.active_schedule, this._renderSlot)}
      {this.renderConfigControls()}
    </div>
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

  renderConfigControls() {
    return <div className="card heating_cfg_ctrls">
        <button className="modal-button" onClick={this._toggleConfig}>Config</button>
        <button className="modal-button" onClick={this._applyTemplate}>Reset today schedule</button>
        <button className="modal-button" onClick={this._showLogs}>Logs</button>
      </div>
  }

  renderTemplateControls() {
    return <div className="card heating_cfg_ctrls">
        <button className="modal-button" onClick={this._toggleConfig}>Finish Config</button>
        <button className="modal-button" onClick={this._applyTemplate}>Apply template / reset today schedule</button>
        <button className="modal-button" onClick={this._resetTemplateAlwaysOff}>Reset template: Always off</button>
        <button className="modal-button" onClick={this._resetTemplateAlwaysRule}>Reset template: Always rule-based</button>
        <button className="modal-button" onClick={this._showLogs}>Logs</button>
      </div>
  }

  _renderSlot(slot) {
    const slot_name = `${('0' + slot.hour).slice(-2)}:${('0' + slot.minute).slice(-2)}`;
    const cb = () => {
      console.log("User toggling slot", slot_name);
      const slotSet = `slot_toggle=${slot_name}`;
      this.props.thing_registry.set_thing('Heating', slotSet).then(()=>{this.refresh()});
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
      const slotSet = `template_slot_set=${slot.hour},${slot.minute},${selected}`;
      this.props.thing_registry.set_thing('Heating', slotSet).then(()=>{this.refresh()});
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
