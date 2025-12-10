class Switch extends React.Component {
  static buildProps(thing_registry, meta) {
    return {
      thing_registry: thing_registry,
      name: meta.name,
      description: meta.description,
      manufacturer: meta.manufacturer,
      model: meta.model,
      user_defined: meta.user_defined,
    }
  }

  constructor(props, thing_registry) {
    super(props);
    this.state = {
      state: false,
    };

    props.thing_registry.get_thing_state(props.name).then( state => {
      this.setState(state);
    });
  }

  setSwitchOn(v) {
    this.setState({ state: v });
    this.props.thing_registry.set_thing(this.props.name, `state=${v}`)
  }

  render() {
    return (
      <div className='thing_div' key={`${this.props.name}_switch_div`}>

        <div className="row">
          <div className="col-primary-action">
            <input type="checkbox"
                   checked={this.state.state}
                   value={this.state.state}
                   onChange={(evnt) => this.setSwitchOn(evnt.target.checked)}
                   key={`${this.props.name}_switch_is_on`} />
          </div>

          <div className="col-fixed-fill">
            <label className='thing_name' htmlFor={`${this.props.name}_switch_is_on`}>
              {this.props.name}
            </label>
          </div>
        </div>
      </div>
    );
  }
}
