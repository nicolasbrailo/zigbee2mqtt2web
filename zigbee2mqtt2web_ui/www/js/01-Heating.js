class Heating extends React.Component {
  static buildProps(thing_registry) {
    return {
      thing_registry,
      key: 'HeatingPane',
    };
  }

  constructor(props) {
    super(props);
    this.render = this.render.bind(this);

    const sched = {};
    for (let hr=0; hr < 24; ++hr) {
      for (let qr=0; qr < 4; ++qr) {
        const k = ("0" + hr).slice(-2) + ":" + ("0" + qr*15).slice(-2);
        sched[k] = {hour: hr, minute: qr*15, should_be_on: false, reason: "Default"};
      }
    }

    props.thing_registry.get_thing_state('Heating').then(state => {
      const hour_schedule = {}
      for (let hr=0; hr<24; ++hr) {
        hour_schedule[hr] = Object.entries(state.schedule).slice(hr*4,(hr+1)*4);
      }
      this.setState({hour_schedule, schedule: state.schedule});
    });

    this.state = {
      schedule: null,
      hour_schedule: null,
    };
  }

  _mkCallbackSlotClick(hour, quarter) {
    return () => {
      console.log(hour, quarter);
      this.state.hour_schedule[hour][quarter][1].should_be_on = !this.state.hour_schedule[hour][quarter][1].should_be_on;
      this.state.hour_schedule[hour][quarter][1].reason = "User change";
      this.setState({hour_schedule: this.state.hour_schedule});
    };
  }

  _mkBoost(hours) {
    return () => {
      console.log(hours);
      this.props.thing_registry.set_thing('Heating', `boost=${hours}`);
    };
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
              <button className="modal-button" onClick={this._mkCallbackSlotClick(hour, quarter)}>
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
