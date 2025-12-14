class ServiceMonitor extends React.Component {
  static buildProps() {
    return {
      key: "ServiceMonitor",
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      services: null,
      systemdServicesStdout: null,
      recentErrors: null,
    };
  }

  componentDidMount() {
    this.on_app_became_visible();
  }

  on_app_became_visible() {
    mJsonGet('/ls', (data) => {
      this.setState({ services: data });
    });
    mJsonGet('/recent_errors', (data) => {
      this.setState({ recentErrors: data });
    });
    mAjax({
      url: '/systemd_status',
      type: 'GET',
      dataType: 'text',
      success: (stdout) => { this.setState({ systemdServicesStdout: stdout }); },
      error: showGlobalError,
    });
  }

  isStale(lastSeen) {
    if (!lastSeen) return true;
    // Convert "YYYY-MM-DD HH:mm:ss.microsec" → timestamp
    const last = new Date(lastSeen.replace(" ", "T"));
    const now = new Date();
    const diffMs = now - last;
    const diffMinutes = diffMs / 1000 / 60;
    return diffMinutes > 5;
  }

  formatServiceName(srv) {
    let name = srv.name;
    if (name.startsWith('Zmw')) {
      name = name.slice(3);
    }
    if (srv.www) {
      try {
        const url = new URL(srv.www);
        const port = url.port || (url.protocol === 'https:' ? '443' : '80');
        name = `${name}:${port}`;
      } catch (e) {}
    }
    return name;
  }

  renderServices() {
    if (!this.state.services) return <div>Loading services...</div>;

    const services = Object.values(this.state.services);
    const total = services.length;
    const running = services.filter(srv => !this.isStale(srv.last_seen)).length;
    const unhealthy = total - running;
    let statusSummary = `${running} out of ${total} services up and running`;
    if (unhealthy > 0) {
      statusSummary += `, ${unhealthy} service${unhealthy > 1 ? 's' : ''} unhealthy`;
    }

    return <section id="zmw_services" className="card">
      <h3>ZMW Services</h3>
        <p>{statusSummary}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '10px', marginBottom: '20px' }}>
        {services.map((srv) => (
          <div key={srv.name} className="card" style={{ padding: '10px', position: 'relative', paddingBottom: '35px' }}>
            <h4 style={{ margin: '0 0 5px 0' }}>
            {srv.www ? (
              <a href={srv.www} target="_blank" rel="noopener noreferrer">
                <img src={`${srv.www}/favicon.ico`} style={{ width: '16px', height: '16px', marginRight: '5px', verticalAlign: 'middle' }} />
                {this.formatServiceName(srv)}
              </a>
            ) : (
              <strong>{this.formatServiceName(srv)}</strong>
            )}
            </h4>

            <div style={{ fontSize: '0.9em', color: this.isStale(srv.last_seen)? "red" : "inherit", marginBottom: '5px' }}>
              {srv.last_seen || "Service down"}
            </div>

            {(srv.methods && (srv.methods.length > 0) && (
            <div style={{ fontSize: '0.85em', color: '#666' }}>
              <em>Methods:</em> {srv.methods.join(", ")}
            </div>
            ))}

            {srv.www && (
              <a href={`${srv.www}/svc_logs.html`} target="_blank" rel="noopener noreferrer"
                 style={{ position: 'absolute', bottom: '8px', right: '8px', fontSize: '0.8em' }}>
                📜 Logs
              </a>
            )}
          </div>
        ))}
        </div>
      </section>
  }

  renderSystemdStatus() {
    let statusSummary = null;
    if (this.state.systemdServicesStdout) {
      const lines = this.state.systemdServicesStdout.split('\n').filter(line => line.trim());
      const total = lines.length;
      const running = lines.filter(line => line.includes('active') && line.includes('running')).length;
      const unhealthy = total - running;
      statusSummary = `${running} out of ${total} services up and running`;
      if (unhealthy > 0) {
        statusSummary += `, ${unhealthy} service${unhealthy > 1 ? 's' : ''} unhealthy`;
      }
    }

    return <section id="systemd_status" className="card">
      <h3>Systemd services status</h3>
      {!this.state.systemdServicesStdout ? (
        <div className="app-loading">Loading systemd status...</div>
      ):(
        <div>
          <p>{statusSummary}</p>
          <pre dangerouslySetInnerHTML={{__html: this.state.systemdServicesStdout}}></pre>
        </div>
      )}
    </section>
  }

  clearRecentErrors() {
    mJsonGet('/recent_errors_clear', () => {
      mJsonGet('/recent_errors', (data) => {
        this.setState({ recentErrors: data });
      });
    });
  }

  simulateError() {
    mJsonGet('/recent_errors_test_new', () => {
      mJsonGet('/recent_errors', (data) => {
        this.setState({ recentErrors: data });
      });
    });
  }

  renderRecentErrors() {
    if (!this.state.recentErrors) return <div>Loading errors...</div>;

    const errors = this.state.recentErrors;
    if (errors.length === 0) {
      return <div>
        <h1>Recent Errors <button onClick={() => this.simulateError()}>Simulate error</button></h1>
        <p>No errors detected! All services running cleanly.</p>
      </div>;
    }

    return (
      <section id="journal_errors" className="card">
      <h3>Recent Errors ({errors.length})</h3>
      <button onClick={() => this.clearRecentErrors()}>Clear</button>
      <button onClick={() => this.simulateError()}>Simulate error</button>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Service</th>
            <th>Level</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          {errors.slice().reverse().map((err, idx) => {
            const priorityColors = {
              'EMERG': '#ff0000',
              'ALERT': '#ff3300',
              'CRIT': '#ff6600',
              'ERR': '#ff9900',
              'WARNING': '#ffcc00'
            };
            return (
              <tr key={idx}>
                <td>{new Date(err.timestamp).toLocaleString()}</td>
                <td>{err.service}</td>
                <td style={{ color: priorityColors[err.priority_name] || '#999' }}>{err.priority_name}</td>
                <td className="journal-entry">{err.message}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>);
  }

  render() {
    return (
      <div id="ServiceMonitorContainer">
        {this.renderServices()}
        {this.renderSystemdStatus()}
        {this.renderRecentErrors()}
      </div>
    );
  }
};
