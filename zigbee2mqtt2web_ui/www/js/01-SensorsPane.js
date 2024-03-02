class SensorsPane extends React.Component {
  // static SensorMetrics = ['temperature', 'humidity', 'voc_index', 'pm25', 'occupancy', 'contact'];
  static SensorMetrics = ['temperature', 'humidity', 'voc_index', 'pm25'];

  static prettyMetricName(metric) {
    switch (metric) {
      case 'temperature': return '';
      case 'humidity': return '';
      case 'voc_index': return 'co2';
      case 'pm25': return 'pm25';
      case 'update_time': return '@';
      case 'contact': return 'Closed';
      case 'occupancy': return 'Occupancy';
      default: return metric;
    }
  }

  static prettyMetricUnit(metric) {
    switch (metric) {
      case 'temperature': return '°C';
      case 'humidity': return '%RH';
      case 'voc_index': return '';
      case 'pm25': return '';
      case 'update_time': return '';
      case 'contact': return '';
      case 'occupancy': return '';
      default: return metric;
    }
  }

  static extraStyleFor(metric, value) {
    const base = !value?
                    'is-hidden' :
                    'pull-right is-small';
    switch (metric) {
      case 'pm25':
      case 'update_time':
      case 'contact':
      case 'occupancy': return base + ' hide-xs hide-sm';
      default: return base;
    }
  }

  static getSensorMetrics(thing) {
    let metrics = [];
    for (const thing_action_name of Object.keys(thing.actions)) {
      if (SensorsPane.SensorMetrics.includes(thing_action_name)) {
        metrics.push(thing_action_name);
      }
    }
    return metrics;
  }

  static buildProps(thing_registry) {
    let sensors = {};

    for (const sensor of thing_registry.sensor_things) {
      let metric_vals = {};
      for (const metric of SensorsPane.getSensorMetrics(sensor)) {
        if (!sensors[sensor.name]) {
          sensors[sensor.name] = {};
        }

        sensors[sensor.name][metric] = sensor.actions[metric].value._current;
      }
    }

    let all_known_metrics = SensorsPane.SensorMetrics;
    all_known_metrics.push('update_time');

    return {key: 'sensor_pane_component',
            sensors: sensors,
            sensor_names: Object.keys(sensors),
            all_known_metrics: all_known_metrics,
            thing_registry: thing_registry};
  }

  constructor(props) {
    super(props);

    this.state = {sensors: props.sensors};
    for (const sensor_name of this.props.sensor_names) {
      props.thing_registry.subscribe_to_state_updates(sensor_name, (sensor_state) => {
        this._updateSensor(sensor_name, sensor_state);
      });
    }
  }

  _updateSensor(sensor_name, new_sensor_state) {
    let new_state = this.state.sensors;
    const updated_metrics = Object.keys(new_sensor_state);
    for (const metric of this.props.all_known_metrics) {
      if (updated_metrics.includes(metric)) {
        let val = new_sensor_state[metric];
        if (val === true) val = 'Y';
        if (val === false) val = 'N';
        new_state[sensor_name][metric] = val;
      } else {
        new_state[sensor_name][metric] = null;
      }
    }

    const time = new Date();
    const hrs= ('0'+time.getHours()).slice(-2);
    const mins = ('0'+time.getMinutes()).slice(-2);
    //const secs = ('0'+time.getSeconds()).slice(-2);
    new_state[sensor_name]['update_time'] = `${hrs}:${mins}`;
    this.setState({sensors: new_state});
  }

  render() {
    return (
    <div className="card" key="sensors_pane" id="sensors_pane">
      <ul>
          {this.render_sensor_list()}
      </ul>
    </div>)
  }

  render_sensor_list() {
    let sensor_list = [];
    for (const sensor_name of this.props.sensor_names) {
      sensor_list.push(
        <li key={`sensor_${sensor_name}_li`}>
          <label>{sensor_name}</label>
          <ul key={`sensor_${sensor_name}_row`}>
            {this.render_metrics_for_sensor(sensor_name)}
          </ul>
        </li>
      );
    }
    return sensor_list;
  }

  _openSensorHistory(sensor_name, metric) {
    return () => {
      window.open(`sensors.html?sensor_name={sensor_name}&metric={metric}`);
    };
  }

  render_metrics_for_sensor(sensor_name) {
    let metrics = [];
    for (const metric of this.props.all_known_metrics) {
      if (this.state.sensors[sensor_name][metric] !== null) {
        metrics.push(<li className={SensorsPane.extraStyleFor(metric, this.state.sensors[sensor_name][metric])}
                         key={`sensor_${sensor_name}_metric_${metric}`}>
                       <button className="modal-button" onClick={this._openSensorHistory(sensor_name, metric)}>
                         {SensorsPane.prettyMetricName(metric)} {this.state.sensors[sensor_name][metric]} {SensorsPane.prettyMetricUnit(metric)}
                       </button>
                     </li>)
      }
    }
    return metrics;
  }
}
