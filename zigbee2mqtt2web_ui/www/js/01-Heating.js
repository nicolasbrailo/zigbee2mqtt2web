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


function renderTemplateScheduleTable(sched, slotClickCbFactory) {
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
          const sched_slot_class = slot.should_be_on? 'heating_sched_slot_on' : 'heating_sched_slot_off';
          return <td key={`table_schedule_${slot.hour}_${slot.minute}`} className={sched_slot_class}>
            {slot_t}<wbr/> Current: {slot.reason}
            <select key="`table_schedule_${slot.hour}_${slot.minute}_opt`"
                    defaultValue={slot.should_be_on? "on" : "off"}
                    onChange={slotClickCbFactory(slot.hour, slot.minute)}>
              <option value="on">Always on</option>
              <option value="off">Always off</option>
            </select>
          </td>;
        })}
      </tr>);
    })}
    </tbody>
    </table>
  );
}

function renderScheduleTable(sched, slotClickCbFactory) {
  return (
    <table className="heating_sched">
    <tbody>
    {Object.keys(sched).map((hour, _) => {
      return (<tr key={`table_schedule_${hour}`}>
        {Object.keys(sched[hour]).map((quarter,v) => {
          const slot_t = sched[hour][quarter][0];
          const slot = sched[hour][quarter][1];
          const sched_slot_class = slot.should_be_on? 'heating_sched_slot_on' : 'heating_sched_slot_off';
          return <td key={`table_schedule_${hour}_${quarter}`} className={sched_slot_class}>
            <button className="modal-button" onClick={slotClickCbFactory(slot.hour, slot.minute)}>
            {slot_t}<wbr/> {slot.reason}
            </button>
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
    this._offNow = this._offNow.bind(this);
    this.refresh = this.refresh.bind(this);
    this._mkCallbackSlotClick = this._mkCallbackSlotClick.bind(this);
    this._mkCallbackTemplateSlotClick = this._mkCallbackTemplateSlotClick.bind(this);
    this._toggleConfig = this._toggleConfig.bind(this);
    this._showLogs = this._showLogs.bind(this);
    this._applyTemplate = this._applyTemplate.bind(this);

    const app_visibility = new VisibilityCallback();
    app_visibility.app_became_visible = this.refresh;

    this.state = {
      configuring: false,
      thing: null,
      hour_schedule: null,
      schedule_template: null,
      refreshId: null,
      app_visibility,
    };

    this.refresh();
  }

  refresh() {
    if (this.state.configuring) {
      console.log("Skip state refresh: configuring");
      return;
    }

    console.log("Refreshing boiler state...");
    if (this.state.refreshId) {
      clearTimeout(this.state.refreshId);
    }

    this.props.thing_registry.get_thing_state('Heating').then(state => {
      const hour_schedule = {}
      for (let hr=0; hr<24; ++hr) {
        hour_schedule[hr] = Object.entries(state.schedule).slice(hr*4,(hr+1)*4);
      }
      console.log("Updated. Will refresh state again in ", millisecToNextSlotChg()/1000, "seconds");
      this.setState({hour_schedule,
                     thing: state,
                     refreshId: setInterval(this.refresh, millisecToNextSlotChg())});
    });
  }

  refreshTemplate() {
    thing_registry.get_thing_action_state('Heating', 'template_schedule').then(tmpl_state => {
      this.setState({schedule_template: JSON.parse(tmpl_state).template});
    });
  }

  refreshActiveOrTemplate() {
    if (this.state.configuring) {
      return this.refreshTemplate();
    }
    return this.refresh();
  }

  _mkCallbackSlotClick(hour, minute) {
    return () => {
      const slotSet = `slot_toggle=${hour}:${minute}`;
      this.props.thing_registry.set_thing('Heating', slotSet).then(()=>{this.refresh()});
    };
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
    this.props.thing_registry.set_thing('Heating', 'template_apply').then(()=>{this.refreshActiveOrTemplate()});
  }

  _toggleConfig() {
    if (!this.state.configuring) {
      this.refreshTemplate();
    }
    this.setState({configuring: !this.state.configuring});
  }

  _showLogs() {
    thing_registry.get_thing_action_state('Heating', 'log_url').then((url) => {
      window.open(url, '_blank')
    });
  }

  render() {
    if (this.state.configuring) {
      return this.renderConfig();
    }

    if (!this.state.hour_schedule) {
      return "Loading...";
    }

    return <div>
      {this.renderHeatingOverrides()}
      {renderScheduleTable(this.state.hour_schedule, this._mkCallbackSlotClick)}
      {this.renderConfigControls()}
    </div>
  }

  renderHeatingOverrides() {
    return <div className="card heating_cfg_ctrls">
        <div>
          Current status: should be {this.state.thing.should_be_on? "on" : "off"}, boiler reports {this.state.thing.mqtt_thing_reports_on}
        </div>
        <button className="modal-button" onClick={this._mkBoost(1)}>Boost 1 hour</button>
        <button className="modal-button" onClick={this._mkBoost(2)}>Boost 2 hours</button>
        <button className="modal-button" onClick={this._offNow}>Off now</button>
      </div>
  }

  renderConfigControls() {
    return <div className="card heating_cfg_ctrls">
        <button className="modal-button" onClick={this._toggleConfig}>Config</button>
        <button className="modal-button" onClick={this._applyTemplate}>Apply template / reset today schedule</button>
        <button className="modal-button" onClick={this._showLogs}>Logs</button>
      </div>
  }


  _mkCallbackTemplateSlotClick(hour, minute) {
    return (evt) => {
      const selected = evt.nativeEvent.target.value;
      console.log("Uset setting template", `${hour}:${minute}`, selected);
      const slotSet = `template_slot_set=${hour},${minute},${selected}`;
      this.props.thing_registry.set_thing('Heating', slotSet).then(()=>{this.refreshTemplate()});
    };
  }

  renderConfig() {
    if (!this.state.schedule_template) {
      return "Loading configuration...";
    }

    return <div>
        {this.renderConfigControls()}
        {renderTemplateScheduleTable(this.state.schedule_template, this._mkCallbackTemplateSlotClick)}
      </div>;
  }
}
