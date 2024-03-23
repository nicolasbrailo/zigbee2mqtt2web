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

    const sched = {};
    for (let hr=0; hr < 24; ++hr) {
      for (let qr=0; qr < 4; ++qr) {
        const k = ("0" + hr).slice(-2) + ":" + ("0" + qr*15).slice(-2);
        sched[k] = {hour: hr, minute: qr*15, should_be_on: false, reason: "Default"};
      }
    }

    this.state = {
      schedule: null,
      hour_schedule: null,
    };

    this.refresh();
  }

  refresh() {
    this.props.thing_registry.get_thing_state('Heating').then(state => {
      const hour_schedule = {}
      for (let hr=0; hr<24; ++hr) {
        hour_schedule[hr] = Object.entries(state.schedule).slice(hr*4,(hr+1)*4);
      }
      this.setState({hour_schedule, schedule: state.schedule});
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
    return <div>
      {this.render_controls()}
      {this.render_schedule_table()}
    </div>
  }

  render_controls() {
    return <div className="card">
        <button className="modal-button" onClick={this._mkBoost(1)}>Boost 1 hour</button>
        <button className="modal-button" onClick={this._mkBoost(2)}>Boost 2 hours</button>
        <button className="modal-button" onClick={this._offNow}>Off now</button>
      </div>
  }

  render_schedule_table() {
    if (!this.state.hour_schedule) {
      return "Loading schedule...";
    }

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
              {slot_t} {slot.reason}
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
