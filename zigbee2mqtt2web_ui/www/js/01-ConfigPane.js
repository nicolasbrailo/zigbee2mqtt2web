const ConfigPane_MQTT_MaxLogLines = 30;
const ConfigPane_LowBatteryLimit = 20;

class ConfigPane extends React.Component {
  static buildProps(thing_registry, remote_thing_registry, thingsPane) {
    return {
      key: 'global_config',
      thing_registry: thing_registry,
      remote_thing_registry: remote_thing_registry,
      thingsPane: thingsPane,
    };
  }

  constructor(props) {
    super(props);
    this.reorderThings = this.reorderThings.bind(this);
    this.reloadThings = this.reloadThings.bind(this);
    this.showHiddenThings = this.showHiddenThings.bind(this);
    this.toggleExpanded = this.toggleExpanded.bind(this);
    this.toggleMqttFeed = this.toggleMqttFeed.bind(this);
    this.showMqttMapConfirm = this.showMqttMapConfirm.bind(this);
    this.renderLowBatteryList = this.renderLowBatteryList.bind(this);
    this.userRequestedMqttNetworkmapRefresh = this.userRequestedMqttNetworkmapRefresh.bind(this);

    this.state = {
      expanded: false,
      showingMqttFeed: false,
      showMqttMapConfirm: false,
      newMqttMapAvailable: false,
      mqttLog: [],
      thingsWithLowBattery: [],
    };
  }

  maybeSubscribeToMqtt(shouldSubscribe) {
    const alreadyActive = (shouldSubscribe && this.state.showingMqttFeed);
    const alreadyInactive = (!shouldSubscribe && !this.state.showingMqttFeed);
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

  reorderThings() {
    this.props.thingsPane.onReorderThings.toggle();
  }

  reloadThings() {
    // Reload and triggers page refresh
    this.props.thing_registry.reloadThings();
  }

  showHiddenThings() {
    this.props.thingsPane.showHiddenThings.toggle();
  }

  toggleExpanded() {
    const newExpanded = !this.state.expanded;

    const newMqttFeedShown = newExpanded && this.state.showingMqttFeed;
    this.maybeSubscribeToMqtt(newMqttFeedShown);

    this.setState({
      expanded: newExpanded,
      showingMqttFeed: newMqttFeedShown,
    });
  }

  toggleMqttFeed() {
    const newMqttFeedShown = !this.state.showingMqttFeed;
    this.maybeSubscribeToMqtt(newMqttFeedShown);
    this.setState({showingMqttFeed: newMqttFeedShown});
  }

  showMqttMapConfirm() {
    this.setState({showMqttMapConfirm: !this.state.showMqttMapConfirm});
  }

  userRequestedMqttNetworkmapRefresh() {
    this.setState({mqttNetworkmapRequestInProgress: true});
    this.props.thing_registry.request_new_mqtt_networkmap().done( _ => {
      console.log("New networkmap may be available");
      this.setState({showMqttMapConfirm: false, newMqttMapAvailable: true});
    });
  }

  render() {
    if (this.state.expanded) {
      return this.render_expanded();
    }
    return this.render_minimized();
  }

  renderLowBatteryList() {
    const batThings = this.props.thing_registry.battery_powered_things_state;
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

    return (<div id="ConfigPane_low_battery" className="container">
        Things with low battery:
        <ul>{low_bat}</ul>
      </div>);
  }

  render_minimized() {
    return (<div id="ConfigPane_config_options">
                <button className="modal-button" onClick={this.toggleExpanded}>Options</button>
            </div>)
  }

  render_expanded() {
    return (<div key="ConfigPane_config_options" id="ConfigPane_config_options" className="modal">
              <button className="modal-button" onClick={this.toggleExpanded}>X</button>
              <ul key="ConfigPane_config_options">
                <li><button onClick={this.reorderThings}>Reorder things</button></li>
                <li><button onClick={this.reloadThings}>Reload things</button></li>
                <li><button onClick={this.showHiddenThings}>List hidden / broken things</button></li>
                <li>{this.renderMqttNetworkMapOptions()}</li>
                <li>
                  <button onClick={this.toggleMqttFeed}>Show MQTT message feed</button>
                  {this.render_mqtt_feed()}
                </li>
                <li><button id="syslogOpenNewWindow"
                            onClick={() => window.open('/syslog/500')}>
                      Syslog
                    </button></li>
              </ul>
              {this.renderLowBatteryList()}
            </div>)
  }

  render_mqtt_feed() {
    if (!this.state.showingMqttFeed) return '';
    return <div className="card container" id="ConfigPane_mqtt_feed" key="ConfigPane_mqtt_feed">
             <ul>
               { this.state.mqttLog.map( (logLine,logIdx) =>
                 <li key={`{mqttlog_${logIdx}}`}>{logLine}</li>) }
             </ul>
           </div>
  }

  renderMqttNetworkMapOptions() {
    if (!this.state.showMqttMapConfirm) {
      return <button onClick={this.showMqttMapConfirm}>Show MQTT network</button>
    }

    const networkmapOpenNewWindow = <button
          id="openNetworkmapNewWindow" onClick={() => {
              window.open('mqtt_networkmap.html');
          }}>Load MQTT network map from cache</button>

    if (this.state.newMqttMapAvailable) {
      return (<div className="container card">
          <div className="row">
            <button className="modal-button" onClick={this.showMqttMapConfirm}>X</button>
            { networkmapOpenNewWindow }
          </div>
        </div>)
    }

    if (this.state.mqttNetworkmapRequestInProgress) {
      return (<div className="container card">
          <div className="row">
            <button className="modal-button" onClick={this.showMqttMapConfirm}>X</button>
          </div>
          <div className="row">
            <label>
              A request for a new networkmap is in progress. If you miss the reply
              (eg by closing this window) you can request the cached map next time.
            </label>
          </div>
          <div className="row">
            <button disabled>MQTT network map request in progress</button>
            { networkmapOpenNewWindow }
          </div>
        </div>)
    }

    return (<div className="container card">
        <div className="row">
          <button className="modal-button" onClick={this.showMqttMapConfirm}>X</button>
        </div>
        <div className="row">
          <label>
            Caution: this may make your network unresponsive for a few minutes.
            The response may take a few minutes to arrive too. Alternatively,
            you can try getting the cached networkmap.
          </label>
        </div>
        <div className="row">
          <button onClick={this.userRequestedMqttNetworkmapRefresh}>Request MQTT network map</button>
          { networkmapOpenNewWindow }
        </div>
      </div>)
  }
}
