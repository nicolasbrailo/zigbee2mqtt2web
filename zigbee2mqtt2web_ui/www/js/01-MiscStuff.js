const ConfigPane_LowBatteryLimit = 20;
const ConfigPane_MQTT_MaxLogLines = 30;

class MiscStuff extends React.Component {
  static buildProps(thing_registry, remote_thing_registry, thingsPane) {
    const maybeUsrBtns = thing_registry.unknown_things.filter((thing) => { return thing.name=='UIUserButtons'; } );
    const zmwActions = (maybeUsrBtns.length > 0)? Object.values(maybeUsrBtns[0].actions) : [];
    const userButtons = zmwActions.map((a) => { return {url: a.name, descr: a.description}; })
                                  .filter((a) => {return a.url != 'get'});
    return {
      key: 'MiscStuffPane',
      thing_registry,
      remote_thing_registry,
      thingsPane,
      userButtons,
    };
  }

  constructor(props) {
    super(props);

    this._toggleExpandOpts = this._toggleExpandOpts.bind(this);
    this._reloadThings = this._reloadThings.bind(this);
    this._zigbeeNetMapAskConfirm = this._zigbeeNetMapAskConfirm.bind(this);
    this._zigbeeNetMap = this._zigbeeNetMap.bind(this);
    this._toggleMqttFeed = this._toggleMqttFeed.bind(this);
    this.renderMqttFeed = this.renderMqttFeed.bind(this);

    this.state = {
      showingExpandedOptions: false,
      askConfirmZigbeeNetmap: false,
      showMqttFeed: false,
      mqttLog: [],
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
    this.props.thing_registry.request_new_mqtt_networkmap().then(_ => {
      console.log("New networkmap may be available");
    });
    this.setState({askConfirmZigbeeNetmap: false});
    window.open('mqtt_networkmap.html');
  }

  _toggleMqttFeed() {
    const newMqttFeedShown = !this.state.showMqttFeed;
    this.maybeSubscribeToMqtt(newMqttFeedShown);
    this.setState({showMqttFeed: !this.state.showMqttFeed});
  }

  render() {
    const btns = [];
    btns.push(<li key="show_sensors_history"><button className="modal-button" onClick={this.TODO}>Sensors history</button></li>);

    if (this.state.showingExpandedOptions) {
      btns.push(<li key="reorder"><button className="modal-button" onClick={this.props.thingsPane.onReorderThings.toggle}>Reorder things</button></li>);
      btns.push(<li key="reload"><button className="modal-button" onClick={this._reloadThings}>Reload things</button></li>);
      btns.push(<li key="showHidden"><button className="modal-button" onClick={this.props.thingsPane.showHiddenThings.toggle}>Show hidden things</button></li>);
      btns.push(<li key="syslog"><button className="modal-button" onClick={() => window.open('/syslog/500')}>Syslog</button></li>);
      btns.push(<li key="mqtt"><button className="modal-button" onClick={this._toggleMqttFeed}>Show MQTT feed</button></li>);

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
             {this.renderMqttFeed()}
           </div>;
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

  renderMqttFeed() {
    if (!this.state.showMqttFeed) {
      return '';
    }

    return <div className="card container" id="ConfigPane_mqtt_feed" key="ConfigPane_mqtt_feed">
             <ul>
               { this.state.mqttLog.map( (logLine,logIdx) =>
                 <li key={`{mqttlog_${logIdx}}`}>{logLine}</li>) }
             </ul>
           </div>
  }

  maybeSubscribeToMqtt(shouldSubscribe) {
    const alreadyActive = (shouldSubscribe && this.state.showMqttFeed);
    const alreadyInactive = (!shouldSubscribe && !this.state.showMqttFeed);
    if (alreadyActive || alreadyInactive) {
      return;
    }

    const appendMsg = (msg) => {
      const time = new Date();
      const hrs= ('0'+time.getHours()).slice(-2);
      const mins = ('0'+time.getMinutes()).slice(-2);
      const secs = ('0'+time.getSeconds()).slice(-2);
      const msgTime = `${hrs}:${mins}:${secs}`;

      let newLog = this.state.mqttLog;
      newLog.push(`${msgTime}: ${JSON.stringify(msg)}`);

      if (newLog.length > ConfigPane_MQTT_MaxLogLines) {
        newLog = newLog.slice(1);
      }

      this.setState({mqttLog: newLog});
    };

    if (shouldSubscribe) {
      appendMsg("MQTT feed started");
      this.props.remote_thing_registry.subscribe_to_mqtt_stream(
        "ConfigPane", msg => appendMsg(msg));
    } else {
      this.props.remote_thing_registry.unsubscribe_to_mqtt_stream("ConfigPane");
      appendMsg("MQTT feed stopped");
    }
  }

}

