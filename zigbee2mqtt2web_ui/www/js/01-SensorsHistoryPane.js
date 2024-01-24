function simple_dygraph_plot(html_elm_id, url) {
  let dygraph_opts = {
                      fillGraph: false,
                      connectSeparatedPoints: true,
                      highlightCircleSize: 2,
                      strokeWidth: 1,
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

let gDygraphLoaded = false;

class SensorsHistoryPane extends React.Component {
  static buildProps(thing_registry, metrics_to_plot) {
    var script = document.createElement('script');
    script.src = '/www/extjsdeps/dygraph.min.js';
    script.onload = () => { gDygraphLoaded = true; };
    document.head.appendChild(script);

    return {
      thing_registry: thing_registry,
      metrics_to_plot: metrics_to_plot,
      key: 'SensorsHistoryPane',
    };
  }

  constructor(props) {
    super(props);
    this.toggleExpanded = this.toggleExpanded.bind(this);
    this.state = {expanded: false};
  }

  toggleExpanded() {
    this.setState({expanded: !this.state.expanded});
  }

  render() {
    if (!this.state.expanded) {
      return this.render_minimized();
    }

    if (!gDygraphLoaded) {
      return this.render_no_dygraph();
    }

    // Probably a race condition, but seems fast enough to not be a problem for now
    const to_render = this.render_expanded();
    for (const metric of this.props.metrics_to_plot) {
      simple_dygraph_plot(`local_plot_${metric}`, `/sensors/get_single_metric_in_all_sensors_csv/${metric}`);
    }
    return to_render;
  }

  render_no_dygraph() {
    return <button className="modal-button" onClick={this.toggleExpanded}>Sensors history: plots loading, please retry</button>
  }

  render_minimized() {
    return <button className="modal-button" onClick={this.toggleExpanded}>Sensors history</button>
  }

  render_expanded() {
    let local_plots = [];
    for (const metric of this.props.metrics_to_plot) {
      local_plots.push(
        <div className="col card" key={`local_plot_${metric}_div`}>
          <h3>{metric}</h3>
          <div id={`local_plot_${metric}`} />
          <div id={`local_plot_${metric}_label`} />
        </div>);
    }

    return (<div id="SensorsHistoryPane" className="card container row col">
              <button className="modal-button" onClick={this.toggleExpanded}>X</button>
              <div className="row">
                {local_plots}
              </div>
            </div>)
  }
}

