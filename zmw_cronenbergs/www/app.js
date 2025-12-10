class CronenbergMonitor extends React.Component {
  static buildProps() {
    return {
      key: 'CronenbergMonitor',
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      stats: null,
    };
    this.fetchStats = this.fetchStats.bind(this);
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

  formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString();
  }

  formatTimestamp(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString();
  }

  calculateSummary() {
    if (!this.state.stats || this.state.stats.length === 0) {
      return { forgotten: 0, clean: 0 };
    }

    const forgotten = this.state.stats.filter(s => s.lights_forgotten).length;
    const clean = this.state.stats.filter(s => !s.lights_forgotten).length;

    return { forgotten, clean };
  }

  render() {
    if (!this.state.stats) {
      return ( <div className="app-loading">Loading...</div> );
    }

    const summary = this.calculateSummary();

    return (
      <div id="CronenbergMonitorContainer">
        <h3><img src="/favicon.ico" alt="Crons" />Light Check Statistics</h3>

        {this.state.stats.length === 0 ? (
          <p>No light checks recorded yet</p>
        ) : (
          <div>
            <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#2a2a2a', borderRadius: '5px' }}>
              <h4 style={{ marginTop: 0 }}>Summary</h4>
              <div style={{ display: 'flex', gap: '30px', flexWrap: 'wrap' }}>
                <div>
                  <span style={{ color: '#ff6b6b', fontSize: '2em', fontWeight: 'bold' }}>{summary.forgotten}</span>
                  <div style={{ color: '#888', fontSize: '0.9em' }}>Days with lights forgotten</div>
                </div>
                <div>
                  <span style={{ color: '#51cf66', fontSize: '2em', fontWeight: 'bold' }}>{summary.clean}</span>
                  <div style={{ color: '#888', fontSize: '0.9em' }}>Days with no lights on</div>
                </div>
                <div>
                  <span style={{ color: '#4a90e2', fontSize: '2em', fontWeight: 'bold' }}>{this.state.stats.length}</span>
                  <div style={{ color: '#888', fontSize: '0.9em' }}>Total checks (last 10 days)</div>
                </div>
              </div>
            </div>

            <h4>Recent Checks</h4>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {this.state.stats.slice().reverse().map((check, idx) => this.renderCheck(check, idx))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  renderCheck(check, idx) {
    const statusColor = check.lights_forgotten ? '#ff6b6b' : '#51cf66';
    const statusIcon = check.lights_forgotten ? '⚠️' : '✓';
    const statusText = check.lights_forgotten ? 'Lights forgotten' : 'All clear';

    return (
      <li key={idx} style={{
        marginBottom: '15px',
        padding: '12px',
        backgroundColor: '#2a2a2a',
        borderRadius: '5px',
        borderLeft: `4px solid ${statusColor}`
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
          <div>
            <span style={{ fontSize: '1.2em' }}>{statusIcon}</span>
            <span style={{ marginLeft: '10px', fontWeight: 'bold', color: statusColor }}>
              {statusText}
            </span>
          </div>
          <div style={{ color: '#888', fontSize: '0.9em' }}>
            {this.formatDate(check.date)} at {new Date(check.timestamp).toLocaleTimeString()}
          </div>
        </div>
        {check.lights_forgotten && check.lights_left_on && check.lights_left_on.length > 0 && (
          <div style={{ marginLeft: '30px', fontSize: '0.95em', color: '#ccc' }}>
            <strong>Lights left on:</strong> {check.lights_left_on.join(', ')}
          </div>
        )}
      </li>
    );
  }
}

z2mStartReactApp('#app_root', CronenbergMonitor);
