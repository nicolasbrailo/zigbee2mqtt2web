const INTERESTING_PLOT_METRICS = ['temperature', 'humidity', 'pm25', 'voc_index'];

function buildUrlForPeriod(period, prefix = '/history') {
  if (!period || period == 'all') return '';
  let unit = 'days';
  let time = 1;
  if (period == "hour_1") { unit = "hours"; time = 1; }
  if (period == "hour_6") { unit = "hours"; time = 6; }
  if (period == "hour_12") { unit = "hours"; time = 12; }
  if (period == "day_1") { unit = "days"; time = 1; }
  if (period == "day_2") { unit = "days"; time = 2; }
  return `${prefix}/${unit}/${time}`;
}

// Return sensor data as a list of values
function renderSensorValues(sensorData, metrics) {
  function getUnit(metric) {
    const units = {
      temperature: '°C',
      device_temperature: '°C',
      humidity: '%',
      voltage: 'V',
      voltage_volts: 'V',
      battery: '%',
      pm25: 'µg/m³',
      active_power_watts: 'W',
      current_amps: 'A',
      lifetime_energy_use_watt_hour: 'Wh',
      last_minute_energy_use_watt_hour: 'Wh',
    };
    return units[metric] || '';
  }

  function formatValue(value, metric) {
    if (typeof value !== 'number') {
      return '?';
    }
    const unit = getUnit(metric);
    return unit ? `${value}${unit}` : value;
  }

  if (sensorData === undefined) {
    return '...';
  }
  if (sensorData === null) {
    return '?';
  }

  // Check if all values are unknown
  const hasAnyValue = metrics.some(m => typeof sensorData[m] === 'number');
  if (!hasAnyValue) {
    return 'No data yet';
  }

  if (metrics.length === 1) {
    // Single metric: just show the value
    return formatValue(sensorData[metrics[0]], metrics[0]);
  } else {
    // Multiple metrics: show key=value pairs
    return metrics
      .map(m => `${m}=${formatValue(sensorData[m], m)}`)
      .join(', ');
  }
}


function simple_dygraph_plot(html_elm_id, url) {
  let dygraph_opts = {
                      fillGraph: false,
                      connectSeparatedPoints: true,
                      highlightCircleSize: 2,
                      strokeWidth: 1,
                      width: window.innerWidth * .9,
                      // smooth graph, helps fill in periods where sensors aren't concurrent
                      rollPeriod: 5,
                      legend: 'always',
                      highlightSeriesOpts: {
                          strokeWidth: 3,
                          strokeBorderWidth: 1,
                          highlightCircleSize: 5
                      },
                  };

  mTextGet(url, (t_csv) => {
    const label_elm = document.getElementById(html_elm_id + '_label');
    if (label_elm) {
      dygraph_opts['labelsDiv'] = label_elm;
    }
    new Dygraph(
        document.getElementById(html_elm_id),
        t_csv,
        dygraph_opts);
  });
}

class SensorsHistoryPane extends React.Component {
  static buildProps() {
    const urlParams = new URLSearchParams(window.location.search);
    const urlQueryMetric = urlParams.get('metric');
    const metric = urlQueryMetric ? [urlQueryMetric] : INTERESTING_PLOT_METRICS;
    const urlQueryPeriod = urlParams.get('period');
    const period = urlQueryPeriod ? [urlQueryPeriod] : 'day_2';
    const plotSingleMetric = !!urlQueryMetric;
    const selectedSensor = urlParams.get('sensor');

    return {
      plotSingleMetric,
      metrics_to_plot: metric,
      period,
      selectedSensor,
      key: 'SensorsHistoryPane',
    };
  }

  constructor(props) {
    super(props);
    this.loadPlotsForSensorMeasuring = this.loadPlotsForSensorMeasuring.bind(this);
    this.updateConfigPeriod = this.updateConfigPeriod.bind(this);
    this.updateConfigMetric = this.updateConfigMetric.bind(this);
    this.sensorsListRef = React.createRef();

    this.state = {
      sensors: null,
      period: this.props.period,
      allMetrics: [],
      selectedMetrics: this.props.metrics_to_plot,
      selectedSensor: this.props.selectedSensor,
      sensorMetrics: null,
    };
  }

  componentDidMount() {
    this.on_app_became_visible();
  }

  on_app_became_visible() {
    mJsonGet('/sensors/metrics', metrics => {
        this.setState({
          allMetrics: metrics,
          sensors: null // Force reload of plots
        });
    });
    if (this.sensorsListRef.current) {
      this.sensorsListRef.current.loadSensors();
    }
  }

  updateConfigPeriod() {
    const period = document.getElementById('SensorsHistoryConfig_period').value;
    window.history.replaceState(null, "Sensors", `?metric=${this.state.selectedMetrics.join(',')}&period=${period}`);
    this.setState({ period });
  }

  updateConfigMetric() {
    const select = document.getElementById('SensorsHistoryConfig_metric');
    const selected = Array.from(select.selectedOptions).map(o => o.value);

    window.history.replaceState(
      null,
      "Sensors",
      `?metric=${selected.join(',')}&period=${this.state.period}`
    );

    this.setState({
      selectedMetrics: selected,
      sensors: null, // reset so plots reload
    });
  }

  render() {
    return (
      <div id="SensorsHistoryPane">
        <div class="SensorsHistoryConfig">
          <label htmlFor="SensorsHistoryConfig_period">Period:</label>
          <select
            value={this.state.period}
            name="SensorsHistoryConfig_period"
            id="SensorsHistoryConfig_period"
            onChange={this.updateConfigPeriod}
          >
            <option value="hour_1">Last hour</option>
            <option value="hour_6">Last 6 hours</option>
            <option value="hour_12">Last 12 hours</option>
            <option value="day_1">Last day</option>
            <option value="day_2">Last 2 days</option>
            <option value="all">All</option>
          </select>

          <label htmlFor="SensorsHistoryConfig_metric" style={{ marginLeft: "10px" }}>
            Metrics:
          </label>
          <select
            id="SensorsHistoryConfig_metric"
            multiple
            value={this.state.selectedMetrics}
            onChange={this.updateConfigMetric}
          >
            {this.state.allMetrics.map(m => (
              <option value={m} key={m}>{m}</option>
            ))}
          </select>
        </div>

        <SensorsList ref={this.sensorsListRef} metrics={this.state.selectedMetrics} api_base_path={this.props.api_base_path} />

        {this.render_plots()}
      </div>
    );
  }

  render_plots() {
    // Single sensor view: show all metrics for one sensor
    if (this.state.selectedSensor) {
      if (!this.state.sensorMetrics) {
        this.loadMetricsForSensor(this.state.selectedSensor);
        return "Loading sensor metrics...";
      }
      return this.renderSingleSensor(this.state.selectedSensor, this.state.sensorMetrics);
    }

    // Metric-based views
    const metrics = this.state.selectedMetrics;

    if (metrics.length === 1 && !this.state.sensors) {
      this.loadPlotsForSensorMeasuring(metrics[0]);
      return "Loading sensors...";
    } else if (metrics.length === 1) {
      return this.renderSingleMetric(metrics[0], this.state.sensors);
    } else {
      return this.renderMetricInAllSensors(metrics);
    }
  }

  loadMetricsForSensor(sensorName) {
    mJsonGet(`/sensors/metrics/${sensorName}`,
      (metrics) => { this.setState({ sensorMetrics: metrics }); });
  }

  renderSingleSensor(sensorName, metrics) {
    let local_plots = [];
    for (const metric of metrics) {
      const plotId = `local_plot_${sensorName}_${metric}`;
      const url = `/sensors/get_metric_in_sensor_csv/${sensorName}/${metric}${buildUrlForPeriod(this.state.period)}`;

      setTimeout(() => {
        const plotDiv = document.getElementById(plotId);
        if (plotDiv) {
          plotDiv.innerHTML = '';
        }
        simple_dygraph_plot(plotId, url);
      }, 50);

      local_plots.push(
        <div className="card" key={`${sensorName}_${metric}_${this.state.period}_div`}>
          <h3><a href={`?metric=${metric}`}>{metric}</a> for {sensorName}</h3>
          <div id={plotId} />
          <div id={`${plotId}_label`} />
        </div>
      );
    }

    return local_plots;
  }

  renderMetricInAllSensors(metrics) {
    let local_plots = [];
    for (const metric of metrics) {
      const plotId = `local_plot_${metric}`;
      const url = `/sensors/get_single_metric_in_all_sensors_csv/${metric}${buildUrlForPeriod(this.state.period, '')}`;

      // Clear existing plot div content to force recreation
      setTimeout(() => {
        const plotDiv = document.getElementById(plotId);
        if (plotDiv) {
          plotDiv.innerHTML = '';
        }
        simple_dygraph_plot(plotId, url);
      }, 0);

      local_plots.push(
        <div className="card" key={`${metric}_${this.state.period}_div`}>
          <h3><a href={`?metric=${metric}`}>{metric}</a></h3>
          <div id={plotId} />
          <div id={`${plotId}_label`} />
        </div>
      );
    }

    return local_plots;
  }

  loadPlotsForSensorMeasuring(metric) {
    mJsonGet(`/sensors/measuring/${metric}`,
      (sensors) => { this.setState({ sensors }); });
  }

  renderSingleMetric(metric, sensors) {
    let local_plots = [];
    for (const sensor of sensors) {
      const plotId = `local_plot_${sensor}`;
      const url = `/sensors/get_metric_in_sensor_csv/${sensor}/${metric}${buildUrlForPeriod(this.state.period)}`;

      // Clear existing plot div content to force recreation
      setTimeout(() => {
        const plotDiv = document.getElementById(plotId);
        if (plotDiv) {
          plotDiv.innerHTML = '';
        }
        simple_dygraph_plot(plotId, url);
      }, 50); // Give it a bit of time to let the element load, otherwise Dygraph can't find it

      local_plots.push(
        <div className="card" key={`${sensor}_${this.state.period}_div`}>
          <h3>{metric} for {sensor}</h3>
          <div id={plotId} />
          <div id={`${plotId}_label`} />
        </div>
      );
    }

    return local_plots;
  }
};

class SensorsList extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      sensors: null,
      sensorData: {},
    };
  }

  componentDidMount() {
    this.loadSensors();
  }

  componentDidUpdate(prevProps) {
    if (prevProps.metrics !== this.props.metrics) {
      this.loadSensors();
    }
  }

  loadSensors() {
    const metrics = this.props.metrics;
    if (!metrics || metrics.length === 0) {
      this.setState({ sensors: [], sensorData: {} });
      return;
    }

    const basePath = this.props.api_base_path || '';

    // Fetch all metrics in parallel using the combined endpoint
    const allSensorData = {};
    let pending = metrics.length;

    metrics.forEach(metric => {
      mJsonGet(`${basePath}/sensors/get_all/${metric}`, data => {
        // data is {"SensorA": value, "SensorB": value, ...}
        for (const [sensor, value] of Object.entries(data)) {
          if (!allSensorData[sensor]) {
            allSensorData[sensor] = {};
          }
          allSensorData[sensor][metric] = value;
        }
        pending--;
        if (pending === 0) {
          const sensors = Object.keys(allSensorData).sort();
          this.setState({ sensors, sensorData: allSensorData });
        }
      });
    });
  }

  render() {
    if (this.state.sensors === null) {
      return (<div className="card hint">
              <p>Loading sensors!</p>
              <p>Please wait...</p>
              </div>)
    }

    return (
      <ul className="not-a-list">
        {this.state.sensors.map(sensor => (
          <li key={sensor} className="infobadge">
            <a href={`?sensor=${sensor}`}>{sensor}</a>: {renderSensorValues(this.state.sensorData[sensor], this.props.metrics)}
          </li>
        ))}
      </ul>
    );
  }
}
