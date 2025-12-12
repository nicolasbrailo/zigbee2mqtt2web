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

    return (
      <div>
        <h1>ZMW Services</h1>
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
      </div>
    );
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

    return <div>
      <h1>Systemd services status</h1>
      {!this.state.systemdServicesStdout ? (
        <div>Loading systemd...</div>
      ):(
        <div>
          <p>{statusSummary}</p>
          <pre dangerouslySetInnerHTML={{__html: this.state.systemdServicesStdout}}></pre>
        </div>
      )}
    </div>
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

    return <div style={{ margin: '20px' }}>
      <h1>Recent Errors ({errors.length}) <button onClick={() => this.clearRecentErrors()}>Clear</button> <button onClick={() => this.simulateError()}>Simulate error</button></h1>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ backgroundColor: '#333', color: 'white' }}>
            <th style={{ padding: '10px', textAlign: 'left' }}>Time</th>
            <th style={{ padding: '10px', textAlign: 'left' }}>Service</th>
            <th style={{ padding: '10px', textAlign: 'left' }}>Level</th>
            <th style={{ padding: '10px', textAlign: 'left' }}>Message</th>
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
              <tr key={idx} style={{ borderBottom: '1px solid #ddd' }}>
                <td style={{ padding: '8px', fontSize: '12px' }}>
                  {new Date(err.timestamp).toLocaleString()}
                </td>
                <td style={{ padding: '8px', fontWeight: 'bold' }}>{err.service}</td>
                <td style={{
                  padding: '8px',
                  color: priorityColors[err.priority_name] || '#999',
                  fontWeight: 'bold'
                }}>
                  {err.priority_name}
                </td>
                <td style={{ padding: '8px', fontFamily: 'monospace', fontSize: '12px' }}>
                  {err.message}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>;
  }

  render() {
    return (
      <div id="ServiceMonitorContainer">
        <h1><img src="/favicon.ico" alt="Service mon"/> Service Monitor</h1>
        {this.renderServices()}
        {this.renderSystemdStatus()}
        {this.renderRecentErrors()}
      </div>
    );
  }
};

z2mStartReactApp('#app_root', ServiceMonitor);
