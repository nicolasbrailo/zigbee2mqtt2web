const INTERESTING_PLOT_METRICS = ['temperature', 'humidity', 'pm25', 'voc_index'];

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

  mAjax({
      url: url,
      cache: false,
      type: 'get',
      dataType: 'text',
      success: function(t_csv) {
        const label_elm = document.getElementById(html_elm_id + '_label');
        if (label_elm) {
          dygraph_opts['labelsDiv'] = label_elm;
        }
        new Dygraph(
            document.getElementById(html_elm_id),
            t_csv,
            dygraph_opts);
      }
  });
}

class SensorsHistoryPane extends React.Component {
  static buildProps(thing_registry) {
    const urlParams = new URLSearchParams(window.location.search);
    const urlQueryMetric = urlParams.get('metric');
    const metric = urlQueryMetric? [urlQueryMetric] : INTERESTING_PLOT_METRICS;
    const plotSingleMetric = !!urlQueryMetric;
    return {
      thing_registry,
      plotSingleMetric,
      metrics_to_plot: metric,
      key: 'SensorsHistoryPane',
    };
  }

  constructor(props) {
    super(props);
    this.loadPlotsForSensorMeasuring = this.loadPlotsForSensorMeasuring.bind(this);
    this.updateConfigPeriod = this.updateConfigPeriod.bind(this);
    this.renderSingleMetric = this.renderSingleMetric.bind(this);

    this.state = {
      sensors: null,
      period: 'day_1',
    };
  }

  updateConfigPeriod() {
    const period = document.getElementById('SensorsHistoryConfig_period').value;
    this.setState({period});
  }

  render() {
    // Probably a race condition, but seems fast enough to not be a problem for now
    if (this.props.plotSingleMetric && !this.state.sensors) {
      this.loadPlotsForSensorMeasuring(this.props.metrics_to_plot[0]);
      return "Loading sensors...";
    } else if (this.props.plotSingleMetric) {
      return this.renderSingleMetric(this.props.metrics_to_plot[0], this.state.sensors);
    } else {
      return this.renderMetricInAllSensors();
    }
  }

  renderMetricInAllSensors() {
    let local_plots = [];
    for (const metric of this.props.metrics_to_plot) {
      simple_dygraph_plot(`local_plot_${metric}`, `/sensors/get_single_metric_in_all_sensors_csv/${metric}`);
      local_plots.push(
        <div className="card" key={`local_plot_${metric}_div`}>
          <h3>{metric}</h3>
          <div id={`local_plot_${metric}`} />
          <div id={`local_plot_${metric}_label`} />
        </div>);
    }

    return (<div id="SensorsHistoryPane">{local_plots}</div>)
  }

  loadPlotsForSensorMeasuring(metric) {
    mAjax({
        url: `/sensors/measuring/${metric}`,
        cache: false,
        type: 'get',
        dataType: 'text',
        success:(sensorLst) => { this.setState({sensors: JSON.parse(sensorLst)}); },
        error: (err) => {console.log(err); showGlobalError(err); },
    });
  }

  renderSingleMetric(metric, sensors) {
    function buildUrlForPeriod(period) {
      if (!period || period == 'all') { return ''; }
      let unit = 'days';
      let time = 1;
      if (period == "hour_1") { unit = "hour"; time = 1; }
      if (period == "hour_6") { unit = "hour"; time = 6; }
      if (period == "hour_12") { unit = "hour"; time = 12; }
      if (period == "day_1") { unit = "day"; time = 1; }
      if (period == "day_2") { unit = "day"; time = 2; }
      return `/history/${unit}/${time}`;
    }

    let local_plots = [];
    for (const sensor of sensors) {
      const url = `/sensors/get_metric_in_sensor_csv/${sensor}/${metric}${buildUrlForPeriod(this.state.period)}`
      simple_dygraph_plot(`local_plot_${sensor}`, url);
      local_plots.push(
        <div className="card" key={`local_plot_${sensor}_div`}>
          <h3>{metric} for {sensor}</h3>
          <div id={`local_plot_${sensor}`} />
          <div id={`local_plot_${sensor}_label`} />
        </div>);
    }

    return (
      <div id="SensorsHistoryPane">
        <div id="SensorsHistoryConfig">
          <label for="SensorsHistoryConfig_period">Period:</label>
          <select name="SensorsHistoryConfig_period" id="SensorsHistoryConfig_period" onChange={this.updateConfigPeriod}>
            <option value="hour_1">Last hour</option>
            <option value="hour_6">Last 6 hours</option>
            <option value="hour_12">Last 12 hours</option>
            <option value="day_1">Last day</option>
            <option value="day_2">Last 2 days</option>
            <option value="all">All</option>
          </select>
        </div>

        {local_plots}
      </div>
    )
  }
}

