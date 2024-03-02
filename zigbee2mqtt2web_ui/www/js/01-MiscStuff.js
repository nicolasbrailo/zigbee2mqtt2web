const ConfigPane_LowBatteryLimit = 20;

class MiscStuff extends React.Component {
  static buildProps(thing_registry, thingsPane) {
    const maybeUsrBtns = thing_registry.unknown_things.filter((thing) => { return thing.name=='UIUserButtons'; } );
    const zmwActions = (maybeUsrBtns.length > 0)? Object.values(maybeUsrBtns[0].actions) : [];
    const userButtons = zmwActions.map((a) => { return {url: a.name, descr: a.description}; })
                                  .filter((a) => {return a.url != 'get'});
    return {
      key: 'MiscStuffPane',
      thing_registry: thing_registry,
      thingsPane: thingsPane,
      userButtons,
    };
  }

  constructor(props) {
    super(props);

    this._toggleExpandOpts = this._toggleExpandOpts.bind(this);
    this._reloadThings = this._reloadThings.bind(this);
    this._zigbeeNetMapAskConfirm = this._zigbeeNetMapAskConfirm.bind(this);
    this._zigbeeNetMap = this._zigbeeNetMap.bind(this);

    this.state = {
      showingExpandedOptions: false,
      askConfirmZigbeeNetmap: false,
    };
  }

  _toggleExpandOpts() {
    this.setState({showingExpandedOptions: !this.state.showingExpandedOptions});
  }

  _reloadThings() {
    this.props.thing_registry.reloadThings();
  }

  _zigbeeNetMapAskConfirm() {
    this.setState({askConfirmZigbeeNetmap: true});
  }

  _zigbeeNetMap() {
    this.props.thing_registry.request_new_mqtt_networkmap().done(_ => {
      console.log("New networkmap may be available");
    });
    this.setState({askConfirmZigbeeNetmap: false});
    window.open('mqtt_networkmap.html');
  }

  render() {
    const btns = [];
    btns.push(<li key="show_sensors_history"><button className="modal-button" onClick={this.TODO}>Sensors history</button></li>);

    if (this.state.showingExpandedOptions) {
      btns.push(<li key="reorder"><button className="modal-button" onClick={this.props.thingsPane.onReorderThings.toggle}>Reorder things</button></li>);
      btns.push(<li key="reload"><button className="modal-button" onClick={this._reloadThings}>Reload things</button></li>);
      btns.push(<li key="showHidden"><button className="modal-button" onClick={this.props.thingsPane.showHiddenThings.toggle}>Show hidden things</button></li>);
      btns.push(<li key="syslog"><button className="modal-button" onClick={() => window.open('/syslog/500')}>Syslog</button></li>);
      btns.push(<li key="mqtt"><button className="modal-button" onClick={this.TODO}>Show MQTT feed</button></li>);

      if (this.state.askConfirmZigbeeNetmap) {
        btns.push(<li key="netmap"><button className="modal-button" onClick={this._zigbeeNetMap}>ZigBee netmap: will take a long time, click here to launch</button></li>);
      } else {
        btns.push(<li key="netmap"><button className="modal-button" onClick={this._zigbeeNetMapAskConfirm}>ZigBee netmap</button></li>);
      }
    }

    for (let btn of this.props.userButtons) {
      btns.push(<li key={btn.url}><button className="modal-button" onClick={() => window.open(btn.url)}>{btn.descr}</button></li>);
    }

    btns.push(<li key="toggle_expand_options"><button className="modal-button" onClick={this._toggleExpandOpts}>...</button></li>);
    return <div id="MiscStuffPane" className="card" key="MiscStuffPaneDiv">
             <ul>{btns}</ul>
             {this.renderLowBatteryList()}
           </div>;
    /*
     * Fold these two here?
    console.log("X");
  ReactDOM.createRoot(document.querySelector('#sensors_history')).render([
    React.createElement(SensorsHistoryPane, SensorsHistoryPane.buildProps(thing_registry, INTERESTING_PLOT_METRICS)),
  ]);

  ReactDOM.createRoot(document.querySelector('#config')).render([
    React.createElement(ConfigPane, ConfigPane.buildProps(thing_registry, remote_thing_registry, thingsPaneProps)),
  ]);
  */
  }

  renderLowBatteryList() {
    const batThings = this.props.thing_registry.battery_powered_things_state;
    // TODO: This gets populated after load?
    const lowBatThings = {};
    let needsRender = false;
    for (const thingName of Object.keys(batThings)) {
      const bat = batThings[thingName];
      if (bat && bat < ConfigPane_LowBatteryLimit) {
        lowBatThings[thingName] = bat;
        needsRender = true;
      }
    }

    if (!needsRender) {
      return '';
    }

    let low_bat = [];
    for (const thingName of Object.keys(lowBatThings)) {
      low_bat.push(
        <li key={`ConfigPane_lowBattery_${thingName}_li`}>
          <label>{thingName}: {lowBatThings[thingName]}%</label>
        </li>
      );
    }

    return (<div id="ConfigPane_low_battery" className="container is-small">
        Things with low battery:
        <ul>{low_bat}</ul>
      </div>);
  }
}

