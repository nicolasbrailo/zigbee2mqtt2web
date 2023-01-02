function simple_dygraph_plot(html_elm_id, url) {
  $.ajax({
      url: url,
      cache: false,
      type: 'get',
      dataType: 'text',
      success: function(t_csv) {
              new Dygraph(
                  document.getElementById(html_elm_id),
                  t_csv,
                  {
                      fillGraph: false,
                      connectSeparatedPoints: true,
                      highlightCircleSize: 2,
                      strokeWidth: 1,
                      highlightSeriesOpts: {
                          strokeWidth: 3,
                          strokeBorderWidth: 1,
                          highlightCircleSize: 5
                      },
                  });
          }
  });
}

class SensorsHistoryPane extends React.Component {
  static buildProps(thing_registry, metrics_to_plot) {
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

    // Probably a race condition, but seems fast enough to not be a problem for now
    const to_render = this.render_expanded();
    for (const metric of this.props.metrics_to_plot) {
      simple_dygraph_plot(`local_plot_${metric}`, `/sensors/get_single_metric_in_all_sensors_csv/${metric}`);
    }
    return to_render;
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

