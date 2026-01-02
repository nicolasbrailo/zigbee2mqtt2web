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
      snapLoading: false,
      snapKey: 0,
    };
    this.fetchStats = this.fetchStats.bind(this);
    this.requestSnap = this.requestSnap.bind(this);
    this.openCamsService = this.openCamsService.bind(this);
    this.openContactmonService = this.openContactmonService.bind(this);
  }

  async componentDidMount() {
    this.fetchStats();
  }

  on_app_became_visible() {
    this.fetchStats();
  }

  fetchStats() {
    mJsonGet('/stats', (res) => {
      this.setState({ stats: res });
    });
  }

  requestSnap() {
    this.setState({ snapLoading: true, snapKey: this.state.snapKey + 1 });
    fetch('/request_snap', { method: 'PUT' });
    setTimeout(() => {
      this.setState({ snapLoading: false, snapKey: this.state.snapKey + 1 });
      this.fetchStats();
    }, 500);
  }

  openCamsService() {
    mJsonGet('/get_cams_svc_url', (res) => {
      if (res.url) {
        window.open(res.url, '_blank');
      }
    });
  }

  openContactmonService() {
    mJsonGet('/get_contactmon_svc_url', (res) => {
      if (res.url) {
        window.open(res.url, '_blank');
      }
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

  renderHistory(history) {
    if (!history || history.length === 0) {
      return <p>No events recorded</p>;
    }
    return (
      <table>
        <thead>
          <tr><th>Type</th><th>Time</th><th>Duration</th><th>Snap</th></tr>
        </thead>
        <tbody>
          {history.map((e, i) => (
            <tr key={i}>
              <td>{e.event_type}</td>
              <td>{this.formatTimestamp(e.time)}</td>
              <td>{e.duration_secs !== undefined ? this.formatDuration(e.duration_secs) : '-'}</td>
              <td>{e.snap ? <a href={`/get_snap/${e.snap}`} target="_blank">{e.snap}</a> : '-'}</td>
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
        {stats.door_open_in_progress ?
          <p className="warn">Door open</p> :
          <p className="hint">Door closed</p>}
        <button onClick={this.requestSnap} disabled={this.state.snapLoading}>
          {this.state.snapLoading ? 'Loading...' : 'New Snap'}
        </button>
        <button onClick={this.openCamsService}>Cameras</button>
        <button onClick={this.openContactmonService}>Contact</button>
        {stats.last_snap && (
          <div>
            {!this.state.snapLoading && (
              <a href={`/get_snap/${stats.last_snap}`} target="_blank">
                <img key={this.state.snapKey} src={`/get_snap/${stats.last_snap}?t=${this.state.snapKey}`} alt="Last snap" style={{maxWidth: '100%', maxHeight: '300px'}} />
              </a>
            )}
            <p>Door cam snap @ {this.formatTimestamp(stats.last_snap_time)}</p>
          </div>
        )}
        <p>{stats.motion_in_progress ? 'Motion detected' : ''}</p>
        <p>Doorbell rang {stats.doorbell_press_count_today} times.</p>
        <p>{stats.motion_detection_count_today} motion detection events.</p>

        <details>
        <summary>History</summary>
        {this.renderHistory(stats.history)}
        </details>
      </div>
    );
  }
}
