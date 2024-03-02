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

function loadPlotsForSensorMeasuring(metric) {
  function _plotSensors(t_csv) {
    console.log(t_csv);
  }
  mAjax({
      url: `/sensors/measuring/${metric}`,
      cache: false,
      type: 'get',
      dataType: 'text',
      success: _plotSensors
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
  }

  render() {
    // Probably a race condition, but seems fast enough to not be a problem for now
    if (this.props.plotSingleMetric) {
      return loadPlotsForSensorMeasuring(this.props.metrics_to_plot[0]);
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
}

