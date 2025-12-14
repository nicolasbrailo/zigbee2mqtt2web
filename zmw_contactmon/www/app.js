function formatTime(seconds) {
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
    };
    this.skipChimeReq = this.skipChimeReq.bind(this);
    this.enableChimeReq = this.enableChimeReq.bind(this);
    this.fetchServiceState = this.fetchServiceState.bind(this);
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

  render() {
    if (!this.state.svc_state) {
      return ( <div>Loading...</div> );
    }

    const hasTimeouts = this.state.svc_state.timeout_sensors && this.state.svc_state.timeout_sensors.length > 0;
    const hasCurfews = this.state.svc_state.curfew_sensors && this.state.svc_state.curfew_sensors.length > 0;

    const sensors = this.state.svc_state.sensors || {};
    const sensorNames = Object.keys(sensors).sort();

    return (
      <section id="zmw_contactmon" className="card">
        { this.state.svc_state.skipping_chimes ? (
          <button type="button" onClick={this.enableChimeReq}>Enable chimes</button>
        ) : (
          <button type="button" onClick={this.skipChimeReq}>Skip next chime</button>
        )}

        { this.state.svc_state.skipping_chimes && (
          <div className="card warn">
          <p>Skipping chimes!</p>
          <p>Will skip chimes for the next { Math.round(this.state.svc_state.skipping_chime_timeout) } seconds</p>
          </div>
        )}

        {hasTimeouts && (
          <div className="card info">
          <p>Pending Timeouts</p>
          <ul>
            {this.state.svc_state.timeout_sensors.map((timeout, idx) => (
              <li key={idx}>
                <strong>{timeout.sensor}</strong> - will timeout in {formatTime(timeout.seconds_remaining)}
              </li>
            ))}
          </ul>
          </div>
        )}

        {hasCurfews && (
          <div className="card info">
          <p>Curfew Alerts</p>
          <ul>
            {this.state.svc_state.curfew_sensors.map((curfew, idx) => (
              <li key={idx}>
                <strong>{curfew.sensor}</strong> - will trigger in {formatTime(curfew.seconds_until_trigger)}
              </li>
            ))}
          </ul>
          </div>
        )}

        <ul>
          {sensorNames.map((sensorName) => this.renderSensor(sensorName, sensors[sensorName]))}
        </ul>
      </section>
    )
  }

  renderSensor(sensorName, sensor) {
    let displayText = '';
    if (sensor.contact === true) {
      displayText = "closed";
    } else if (sensor.contact === false) {
      displayText = "open";
    } else {
      displayText = "in unknown state (waiting for sensor report)";
    }

    const changedDate = sensor.changed ? new Date(sensor.changed) : null;
    const changedStr = changedDate ? changedDate.toLocaleString() : 'unknown';

    // Calculate duration since last change
    let durationStr = '';
    if (changedDate) {
      const now = new Date();
      const durationSecs = (now - changedDate) / 1000;
      durationStr = formatTime(durationSecs);
    }

    const history = this.state.svc_state.history?.[sensorName] || [];

    return (
      <li key={sensorName}>
        <strong>{sensorName}</strong>: {displayText}
        {changedDate && (
          <span>
            {' '} @ {changedStr} ({durationStr} ago)
          </span>
        )}
        {this.renderHistory(sensorName, history)}
      </li>
    );
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
      <details>
        <summary>History (last {sortedHistory.length} events)</summary>
        <table>
          <thead>
            <tr>
              <th>Contact</th>
              <th>Action</th>
              <th>Changed</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {sortedHistory.map((evt, idx) => {
              const contact = evt.contact === true ? 'closed' : evt.contact === false ? 'open' : 'unknown';
              const action = evt.action || 'unknown';
              const changedDate = evt.changed ? new Date(evt.changed) : null;
              const changedStr = changedDate ? changedDate.toLocaleString() : 'unknown';
              const isOpen = evt.contact === false;

              // Calculate duration
              let duration = '';
              const isFirstItem = idx === 0;
              const isCurrentState = currentSensor &&
                                    currentSensor.contact === evt.contact &&
                                    currentSensor.action === evt.action;

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
                duration = formatTime(durationSecs);
              }

              return (
                <tr key={idx} className={evt.contact? "hint" : "warn"}>
                  <td>{contact}</td>
                  <td>{action}</td>
                  <td>{changedStr}</td>
                  <td>{duration}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
    );
  }
}
