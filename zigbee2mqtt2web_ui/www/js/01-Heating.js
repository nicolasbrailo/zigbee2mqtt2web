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

    const app_visibility = new VisibilityCallback();
    app_visibility.app_became_visible = this.refresh;

    this.state = {
      thing: null,
      hour_schedule: null,
      refreshId: null,
      app_visibility,
    };

    this.refresh();
  }

  refresh() {
    console.log("Refresshing boiler state...");
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

  render() {
    if (!this.state.hour_schedule) {
      return "Loading...";
    }

    return <div>
      {this.render_controls()}
      {this.render_schedule_table()}
    </div>
  }

  render_controls() {
    return <div className="card">
        <div>
          Current status: should be {this.state.thing.should_be_on? "on" : "off"}, boiler reports {this.state.thing.mqtt_thing_reports_on}
        </div>
        <button className="modal-button" onClick={this._mkBoost(1)}>Boost 1 hour</button>
        <button className="modal-button" onClick={this._mkBoost(2)}>Boost 2 hours</button>
        <button className="modal-button" onClick={this._offNow}>Off now</button>
      </div>
  }

  render_schedule_table() {
    return (
      <table className="heating_sched">
      <tbody>
      {Object.keys(this.state.hour_schedule).map((hour, _) => {
        return (<tr key={`table_schedule_${hour}`}>
          {Object.keys(this.state.hour_schedule[hour]).map((quarter,v) => {
            const slot_t = this.state.hour_schedule[hour][quarter][0];
            const slot = this.state.hour_schedule[hour][quarter][1];
            const sched_slot_class = slot.should_be_on? 'heating_sched_slot_on' : 'heating_sched_slot_off';
            return <td key={`table_schedule_${hour}_${quarter}`} className={sched_slot_class}>
              <button className="modal-button" onClick={this._mkCallbackSlotClick(slot.hour, slot.minute)}>
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
}
