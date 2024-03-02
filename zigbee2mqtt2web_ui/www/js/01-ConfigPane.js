const ConfigPane_MQTT_MaxLogLines = 30;

class ConfigPane extends React.Component {
  constructor(props) {
    super(props);
    this.toggleMqttFeed = this.toggleMqttFeed.bind(this);
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

  toggleMqttFeed() {
    const newMqttFeedShown = !this.state.showingMqttFeed;
    this.maybeSubscribeToMqtt(newMqttFeedShown);
    this.setState({showingMqttFeed: newMqttFeedShown});
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
}
