class ContactMonitor extends React.Component {
  static buildProps(api_base_path = '') {
    return {
      key: 'ContactMonitor',
      api_base_path: api_base_path,
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      svc_state: null,
      expandedHistory: {}, // Track which sensor histories are expanded
    };
    this.skipChimeReq = this.skipChimeReq.bind(this);
    this.enableChimeReq = this.enableChimeReq.bind(this);
    this.fetchServiceState = this.fetchServiceState.bind(this);
    this.toggleHistory = this.toggleHistory.bind(this);
    this.timer = null;
  }

  async componentDidMount() {
    this.fetchServiceState();
  }

  on_app_became_visible() {
    this.fetchServiceState();
  }

  componentDidUpdate(prevProps, prevState) {
    const prevSkip = prevState.svc_state?.skipping_chimes;
    const currSkip = this.state.svc_state?.skipping_chimes;

    if (!prevSkip && currSkip) {
      this.startSkipTimer();
    }
  }

  startSkipTimer() {
    if (this.timer) clearInterval(this.timer);

    this.timer = setInterval(() => {
      this.setState(state => {
        const timeout = state.svc_state.skipping_chime_timeout - 1;

        // reached 0 → stop skipping, refresh service state
        if (timeout <= 0) {
          clearInterval(this.timer);
          this.timer = null;
          this.fetchServiceState();
          return {
            svc_state: {
              ...state.svc_state,
              skipping_chimes: false,
              skipping_chime_timeout: 0
            }
          };
        }

        // continue counting down
        return {
          svc_state: {
            ...state.svc_state,
            skipping_chime_timeout: timeout
          }
        };
      });
    }, 1000);
  }

  componentWillUnmount() {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }

  fetchServiceState() {
    mJsonGet(`${this.props.api_base_path}/svc_state`, (res) => {
      this.setState({
        svc_state: {
          ...res,
          skipping_chime_timeout: res.skipping_chimes_timeout_secs
        }
      });
    });
  }

  skipChimeReq() {
    mJsonGet(`${this.props.api_base_path}/skip_chimes`, (res) => {
      this.setState(state => ({
        svc_state: {
          ...state.svc_state,
          skipping_chimes: true,
          skipping_chime_timeout: Number(res.timeout)
        }
      }));
    });
  }

  enableChimeReq() {
    mJsonGet(`${this.props.api_base_path}/enable_chimes`, (res) => {
      this.fetchServiceState();
    });
  }

  toggleHistory(sensorName) {
    this.setState(state => ({
      expandedHistory: {
        ...state.expandedHistory,
        [sensorName]: !state.expandedHistory[sensorName]
      }
    }));
  }

  formatTime(seconds) {
    if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    }

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
      const secs = Math.round(seconds % 60);
      return `${minutes}m ${secs}s`;
    }

    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
      const mins = minutes % 60;
      return `${hours}h ${mins}m`;
    }

    const days = Math.floor(hours / 24);
    if (days < 7) {
      const hrs = hours % 24;
      return `${days}d ${hrs}h`;
    }

    const weeks = Math.floor(days / 7);
    const remainingDays = days % 7;
    return `${weeks}w ${remainingDays}d`;
  }

  render() {
    if (!this.state.svc_state) {
      return ( <div className="app-loading">Loading...</div> );
    }

    const hasTimeouts = this.state.svc_state.timeout_sensors && this.state.svc_state.timeout_sensors.length > 0;
    const hasCurfews = this.state.svc_state.curfew_sensors && this.state.svc_state.curfew_sensors.length > 0;

    const sensors = this.state.svc_state.sensors || {};
    const sensorNames = Object.keys(sensors).sort();

    return (
      <div id="ContactMonitorContainer">
        { this.state.svc_state.skipping_chimes && (
          <div className="bd-error bg-dark text-center">
          Will skip chimes for the next { Math.round(this.state.svc_state.skipping_chime_timeout) } seconds
          </div>
        )}
        { this.state.svc_state.skipping_chimes ? (
          <button type="button" onClick={this.enableChimeReq}>Enable chimes</button>
        ) : (
          <button type="button" onClick={this.skipChimeReq}>Skip next chime</button>
        )}

        {hasTimeouts && (
          <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#fff3cd', border: '1px solid #ffc107', borderRadius: '4px' }}>
            <h4 style={{ margin: '0 0 10px 0' }}>⏰ Pending Timeouts</h4>
            <ul style={{ margin: 0 }}>
              {this.state.svc_state.timeout_sensors.map((timeout, idx) => (
                <li key={idx}>
                  <strong>{timeout.sensor}</strong> - will timeout in {this.formatTime(timeout.seconds_remaining)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {hasCurfews && (
          <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#d1ecf1', border: '1px solid #0c5460', borderRadius: '4px' }}>
            <h4 style={{ margin: '0 0 10px 0' }}>🌙 Scheduled Curfew Alerts</h4>
            <ul style={{ margin: 0 }}>
              {this.state.svc_state.curfew_sensors.map((curfew, idx) => (
                <li key={idx}>
                  <strong>{curfew.sensor}</strong> - will trigger in {this.formatTime(curfew.seconds_until_trigger)}
                </li>
              ))}
            </ul>
          </div>
        )}

        <ul>
          {sensorNames.map((sensorName) => this.renderSensor(sensorName, sensors[sensorName]))}
        </ul>
      </div>
    )
  }

  formatDuration(startTime, endTime) {
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const durationSecs = (end - start) / 1000;
    return this.formatTime(durationSecs);
  }

  renderHistory(sensorName, history) {
    if (!history || history.length === 0) {
      return null;
    }

    // Sort history by newest first
    const sortedHistory = [...history].sort((a, b) => {
      const timeA = a.changed ? new Date(a.changed).getTime() : 0;
      const timeB = b.changed ? new Date(b.changed).getTime() : 0;
      return timeB - timeA; // newest first
    });

    const currentSensor = this.state.svc_state.sensors?.[sensorName];

    return (
      <div style={{
        marginLeft: '20px',
        marginTop: '10px',
        fontSize: '0.85em',
        padding: '10px',
        borderRadius: '4px',
        border: '1px solid #444'
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>
          History (last {sortedHistory.length} events):
        </div>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.95em'
        }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #555' }}>
              <th style={{ textAlign: 'left', padding: '4px' }}>Contact</th>
              <th style={{ textAlign: 'left', padding: '4px' }}>Action</th>
              <th style={{ textAlign: 'left', padding: '4px' }}>Changed</th>
              <th style={{ textAlign: 'left', padding: '4px' }}>Duration</th>
            </tr>
          </thead>
          <tbody>
            {sortedHistory.map((event, idx) => {
              const contact = event.contact === true ? 'closed' : event.contact === false ? 'open' : 'unknown';
              const action = event.action || 'unknown';
              const changedDate = event.changed ? new Date(event.changed) : null;
              const changedStr = changedDate ? changedDate.toLocaleString() : 'unknown';
              const isOpen = event.contact === false;

              // Calculate duration
              let duration = '';
              const isFirstItem = idx === 0;
              const isCurrentState = currentSensor &&
                                    currentSensor.contact === event.contact &&
                                    currentSensor.action === event.action;

              if (isFirstItem && isCurrentState) {
                duration = 'current';
              } else if (changedDate) {
                // Calculate duration from this event to the next newer event or now
                let endDate;
                if (isFirstItem) {
                  // First item (newest) but not current state
                  endDate = new Date();
                } else {
                  // Look at the previous item in array (which is newer in time)
                  const newerEvent = sortedHistory[idx - 1];
                  endDate = newerEvent && newerEvent.changed ? new Date(newerEvent.changed) : new Date();
                }
                const durationSecs = (endDate - changedDate) / 1000;
                duration = this.formatTime(durationSecs);
              }

              return (
                <tr key={idx} className={isOpen ? 'text-error' : 'text-success'} style={{
                  borderBottom: '1px solid #333'
                }}>
                  <td style={{ padding: '4px' }}>
                    {contact}
                  </td>
                  <td style={{ padding: '4px' }}>
                    {action}
                  </td>
                  <td style={{ padding: '4px' }}>
                    {changedStr}
                  </td>
                  <td style={{ padding: '4px' }}>
                    {duration}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  renderSensor(sensorName, sensor) {
    let contact = '';
    let displayText = '';
    let isOpen = false;

    if (sensor.contact === true) {
      contact = "closed";
      const action = sensor.action || 'unknown';
      displayText = `${contact} (${action})`;
      isOpen = false;
    } else if (sensor.contact === false) {
      contact = "open";
      const action = sensor.action || 'unknown';
      displayText = `${contact} (${action})`;
      isOpen = true;
    } else {
      displayText = "in unknown state (waiting for sensor report)";
      isOpen = false;
    }

    const changedDate = sensor.changed ? new Date(sensor.changed) : null;
    const changedStr = changedDate ? changedDate.toLocaleString() : 'unknown';

    // Calculate duration since last change
    let durationStr = '';
    if (changedDate) {
      const now = new Date();
      const durationSecs = (now - changedDate) / 1000;
      durationStr = this.formatTime(durationSecs);
    }

    const isExpanded = this.state.expandedHistory[sensorName];
    const history = this.state.svc_state.history?.[sensorName] || [];

    return (
      <li key={sensorName}>
        <div className={isOpen ? 'bd-error' : ''} style={isOpen ? { padding: '5px', marginBottom: '5px' } : {}}>
          <strong>{sensorName}</strong>: {displayText}
          {changedDate && (
            <span style={{ fontSize: '0.9em', color: '#666', marginLeft: '10px' }}>
              - changed at {changedStr} ({durationStr} ago)
            </span>
          )}
          {history.length > 0 && (
            <span
              onClick={() => this.toggleHistory(sensorName)}
              style={{
                marginLeft: '10px',
                cursor: 'pointer',
                color: '#4a9eff',
                textDecoration: 'underline'
              }}
            >
              (history)
            </span>
          )}
        </div>
        {isExpanded && this.renderHistory(sensorName, history)}
      </li>
    );
  }
}
