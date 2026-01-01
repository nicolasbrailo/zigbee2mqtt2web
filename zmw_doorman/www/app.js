class DoorMan extends React.Component {
  static buildProps() {
    return {
      key: 'DoorMan',
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      stats: null,
    };
    this.fetchStats = this.fetchStats.bind(this);
    this.refreshInterval = null;
  }

  async componentDidMount() {
    this.fetchStats();
    this.refreshInterval = setInterval(this.fetchStats, 10000);
  }

  componentWillUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  on_app_became_visible() {
    this.fetchStats();
  }

  fetchStats() {
    mJsonGet('/stats', (res) => {
      this.setState({ stats: res });
    });
  }

  formatTimestamp(ts) {
    if (!ts) return '?';
    const date = new Date(ts * 1000);
    return date.toLocaleString();
  }

  formatDuration(secs) {
    if (secs === null || secs === undefined) return '?';
    if (secs < 60) return `${secs.toFixed(1)}s`;
    const mins = Math.floor(secs / 60);
    const remainingSecs = secs % 60;
    return `${mins}m ${remainingSecs.toFixed(0)}s`;
  }

  renderDoorbellPresses(presses) {
    if (!presses || presses.length === 0) {
      return <p>No doorbell presses recorded</p>;
    }
    return (
      <table>
        <thead>
          <tr><th>Time</th><th>Snap</th></tr>
        </thead>
        <tbody>
          {presses.slice().reverse().map((p, i) => (
            <tr key={i}>
              <td>{this.formatTimestamp(p.timestamp)}</td>
              <td>{p.snap_path || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  renderMotionEvents(events) {
    if (!events || events.length === 0) {
      return <p>No motion events recorded</p>;
    }
    return (
      <table>
        <thead>
          <tr><th>Time</th><th>Duration</th></tr>
        </thead>
        <tbody>
          {events.slice().reverse().map((e, i) => (
            <tr key={i}>
              <td>{this.formatTimestamp(e.start_time)}</td>
              <td>{this.formatDuration(e.duration_secs)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  renderDoorOpenEvents(events) {
    if (!events || events.length === 0) {
      return <p>No door open events recorded</p>;
    }
    return (
      <table>
        <thead>
          <tr><th>Time</th><th>Duration</th></tr>
        </thead>
        <tbody>
          {events.slice().reverse().map((e, i) => (
            <tr key={i}>
              <td>{this.formatTimestamp(e.start_time)}</td>
              <td>{this.formatDuration(e.duration_secs)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  render() {
    const { stats } = this.state;

    if (!stats) {
      return <div>Loading...</div>;
    }

    return (
      <div>
        <h2>Today</h2>
        <p>Doorbell presses: {stats.doorbell_press_count_today}</p>
        <p>Motion detections: {stats.motion_detection_count_today}</p>

        <h2>Status</h2>
        <p>Motion in progress: {stats.motion_in_progress ? 'Yes' : 'No'}</p>
        <p>Door open: {stats.door_open_in_progress ? 'Yes' : 'No'}</p>
        <p>Last snap: {stats.last_snap_path || '-'}</p>

        <h2>Doorbell Presses (last 10)</h2>
        {this.renderDoorbellPresses(stats.doorbell_presses)}

        <h2>Motion Events (last 10)</h2>
        {this.renderMotionEvents(stats.motion_events)}

        <h2>Door Open Events (last 10)</h2>
        {this.renderDoorOpenEvents(stats.door_open_events)}
      </div>
    );
  }
}
