class ScenesList extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      scenes: [],
      sceneStatus: null,
    };
    this.fetchScenes = this.fetchScenes.bind(this);
    this.applyScene = this.applyScene.bind(this);
  }

  componentDidMount() {
    this.fetchScenes();
  }

  fetchScenes() {
    mJsonGet(this.props.api_base_path + '/ls_scenes', (res) => {
      this.setState({ scenes: res || [] });
    });
  }

  applyScene(scene) {
    mJsonGet(this.props.api_base_path + '/apply_scene?scene=' + encodeURIComponent(scene), (res) => {
      if (res && res.success) {
        this.setState({ sceneStatus: 'Scene applied' });
        setTimeout(() => {
          this.setState({ sceneStatus: null });
        }, 3000);
      }
    });
  }

  render() {
    if (this.state.scenes.length === 0) {
      return null;
    }

    return (
      <div>
        <ul className="keyval-list">
          {this.state.scenes.map((scene, idx) => (
            <li key={idx} className="modal-button primary">
              <a href="#" onClick={(e) => { e.preventDefault(); this.applyScene(scene); }}>{scene.replace(/_/g, ' ')}</a>
            </li>
          ))}
        </ul>
        {this.state.sceneStatus && <p>{this.state.sceneStatus}</p>}
      </div>
    );
  }
}

class BaticasaButtonsMonitor extends React.Component {
  static buildProps() {
    return {
      key: 'BaticasaButtonsMonitor',
      api_base_path: '',
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      boundButtons: null,
      unboundButtons: null,
      discoveredActions: {},
      actionInputs: {},
      triggerStatus: {},
      showCustomInput: {},
    };
    this.fetchButtonsState = this.fetchButtonsState.bind(this);
    this.handleActionInputChange = this.handleActionInputChange.bind(this);
    this.handleDropdownChange = this.handleDropdownChange.bind(this);
    this.triggerAction = this.triggerAction.bind(this);
  }

  async componentDidMount() {
    this.fetchButtonsState();
  }

  on_app_became_visible() {
    this.fetchButtonsState();
  }

  fetchButtonsState() {
    mJsonGet(this.props.api_base_path + '/buttons_state', (res) => {
      this.setState({
        boundButtons: res.bound_actions,
        unboundButtons: res.unbound_actions,
        discoveredActions: res.discovered_actions || {}
      });
    });
  }

  handleActionInputChange(buttonName, value) {
    this.setState(state => ({
      actionInputs: {
        ...state.actionInputs,
        [buttonName]: value
      }
    }));
  }

  handleDropdownChange(buttonName, value) {
    if (value === '__other__') {
      this.setState(state => ({
        showCustomInput: {
          ...state.showCustomInput,
          [buttonName]: true
        },
        actionInputs: {
          ...state.actionInputs,
          [buttonName]: ''
        }
      }));
    } else {
      this.setState(state => ({
        showCustomInput: {
          ...state.showCustomInput,
          [buttonName]: false
        },
        actionInputs: {
          ...state.actionInputs,
          [buttonName]: value
        }
      }));
    }
  }

  async triggerAction(buttonName) {
    const actionValue = this.state.actionInputs[buttonName] || '';

    if (!actionValue) {
      this.setState(state => ({
        triggerStatus: {
          ...state.triggerStatus,
          [buttonName]: { success: false, message: 'Please enter an action value' }
        }
      }));
      return;
    }

    try {
      const response = await fetch(this.props.api_base_path + '/trigger_action', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          button_name: buttonName,
          action_value: actionValue
        })
      });

      const data = await response.json();

      if (response.ok) {
        this.setState(state => ({
          triggerStatus: {
            ...state.triggerStatus,
            [buttonName]: { success: true, message: data.message }
          }
        }));
      } else {
        this.setState(state => ({
          triggerStatus: {
            ...state.triggerStatus,
            [buttonName]: { success: false, message: data.error }
          }
        }));
      }

      setTimeout(() => {
        this.setState(state => ({
          triggerStatus: {
            ...state.triggerStatus,
            [buttonName]: null
          }
        }));
      }, 5000);

    } catch (error) {
      this.setState(state => ({
        triggerStatus: {
          ...state.triggerStatus,
          [buttonName]: { success: false, message: 'Failed to trigger action' }
        }
      }));
    }
  }

  render() {
    if (!this.state.boundButtons || !this.state.unboundButtons) {
      return ( <div className="app-loading">Loading...</div> );
    }

    const boundButtons = this.state.boundButtons;
    const unboundButtons = this.state.unboundButtons;

    return (
      <div id="BaticasaButtonsContainer">
        <h3>
          <img src="/favicon.ico" alt="Baticasa buttons"/>
          Baticasa Buttons
        </h3>

        {unboundButtons.length > 0 && (
          <div className="bd-error card text-error">
            <h4>⚠ Error: Unbound Actions ({unboundButtons.length})</h4>
            <p>The following callbacks could not be bound to Z2M things. Check if devices are missing or callback names are incorrect:</p>
            <ul>
              {unboundButtons.map((buttonName, idx) => (
                <li key={idx}><code>{buttonName}</code></li>
              ))}
            </ul>
          </div>
        )}

        {boundButtons.length > 0 && (
          <div>
            <h4>✓ Buttons bound to actions: ({boundButtons.length})</h4>
            <ul>
              {boundButtons.map((buttonName, idx) => this.renderButton(buttonName, idx))}
            </ul>

            Use this panel to trigger actions in the service. You'll need to provide the name
            of the MQTT action that would be sent by zigbee2mqtt.
          </div>
        )}

        {boundButtons.length === 0 && unboundButtons.length === 0 && (
          <div>
            No button callbacks found
          </div>
        )}

        <h4>Scenes</h4>
        <ScenesList api_base_path={this.props.api_base_path} />
      </div>
    )
  }

  renderButton(buttonName, idx) {
    const status = this.state.triggerStatus[buttonName];
    const actionInput = this.state.actionInputs[buttonName] || '';
    const discoveredActions = this.state.discoveredActions[buttonName] || [];
    const showCustomInput = this.state.showCustomInput[buttonName] || false;

    const hasDiscoveredActions = discoveredActions.length > 0;

    return (
      <li key={idx}>
        <strong style={{
          display: 'inline-block',
          width: '250px',
          marginRight: '10px'
        }}>{buttonName}</strong>

          {hasDiscoveredActions && !showCustomInput ? (
            <select
              value={actionInput}
              onChange={(e) => this.handleDropdownChange(buttonName, e.target.value)}
              style={{
                marginRight: '10px',
                padding: '5px',
                width: '300px',
                backgroundColor: '#2a2a2a',
                color: '#fff',
                border: '1px solid #444',
                display: 'inline-block',
              }}
            >
              <option value="">-- Select an action --</option>
              {discoveredActions.map((action, actionIdx) => (
                <option key={actionIdx} value={action}>{action}</option>
              ))}
              <option value="__other__">Other</option>
            </select>
          ) : (
            <input
              type="text"
              placeholder="MQTT Action (eg: on, toggle...)"
              value={actionInput}
              onChange={(e) => this.handleActionInputChange(buttonName, e.target.value)}
              style={{
                marginRight: '10px',
                padding: '5px',
                width: '300px',
                backgroundColor: '#2a2a2a',
                color: '#fff',
                border: '1px solid #444',
                display: 'inline-block',
              }}
            />
          )}

          <button
            type="button"
            onClick={() => this.triggerAction(buttonName)}
            style={{ padding: '5px 15px' }}
          >
            Trigger
          </button>
          {status && (
            <span className={ status.success ? "bg-success" : "bg-error" }>
              {status.message}
            </span>
          )}
      </li>
    );
  }
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
function millisecToNextSlotChg() {
  const now = new Date();
  const qr = Math.floor(now.getMinutes() / 15);
  const nxt_slot_chg_min = (15 * (qr + 1)) % 60;
  const slot_chg = new Date();
  slot_chg.setMinutes(nxt_slot_chg_min);
  slot_chg.setSeconds(0);
  const ms_to_chg = (slot_chg - now);

  if (nxt_slot_chg_min == 0) {
    // If we're rolling over to start of the hour, add one hour
    return ms_to_chg + 60 * 60 * 1000;
  }

  return ms_to_chg;
}

function renderScheduleTable(sched, slotGenerator) {
  const qr_groupped_sched = {};
  for (let hr=0; hr<24; ++hr) {
    qr_groupped_sched[hr] = sched.slice(hr*4,(hr+1)*4);
  }
  return (
    <table className="heating_sched">
    <tbody>
    {Object.keys(qr_groupped_sched).map((hour) => {
      return (<tr key={`table_schedule_${hour}`}>
        {qr_groupped_sched[hour].map((slot) => {
          const slot_t = `${('0' + slot.hour).slice(-2)}:${('0' + slot.minute).slice(-2)}`;
          const sched_slot_class = slot.request_on? 'heating_sched_slotBoilerOn' : 'heating_sched_slotBoilerOff';
          return <td key={`table_schedule_${slot.hour}_${slot.minute}`} className={sched_slot_class}>
                  {slotGenerator(slot)}
                 </td>;
        })}
      </tr>);
    })}
    </tbody>
    </table>
  );
}

class HeatingControls extends React.Component {
  static buildProps(api_base_path = '', state = {}) {
    const props = {
      api_base_path: api_base_path,
    };

    // Optional: pass state data to avoid fetching if already available
    if (state.allow_on !== undefined) props.allow_on = state.allow_on;
    if (state.mqtt_thing_reports_on !== undefined) props.mqtt_thing_reports_on = state.mqtt_thing_reports_on;
    if (state.monitoring_sensors !== undefined) props.monitoring_sensors = state.monitoring_sensors;
    if (state.onRefresh !== undefined) props.onRefresh = state.onRefresh;

    return props;
  }

  constructor(props) {
    super(props);
    this._offNow = this._offNow.bind(this);
    this._refresh = this._refresh.bind(this);

    this.state = {
      allow_on: props.allow_on || null,
      mqtt_thing_reports_on: props.mqtt_thing_reports_on || null,
      monitoring_sensors: props.monitoring_sensors || null,
    };
  }

  componentDidMount() {
    // If no data provided via props, fetch it
    if (!this.props.allow_on && this.props.api_base_path) {
      this._refresh();
    }
  }

  componentDidUpdate(prevProps) {
    // Update internal state if props change
    if (prevProps.allow_on !== this.props.allow_on ||
        prevProps.mqtt_thing_reports_on !== this.props.mqtt_thing_reports_on ||
        prevProps.monitoring_sensors !== this.props.monitoring_sensors) {
      this.setState({
        allow_on: this.props.allow_on,
        mqtt_thing_reports_on: this.props.mqtt_thing_reports_on,
        monitoring_sensors: this.props.monitoring_sensors,
      });
    }
  }

  _refresh() {
    if (this.props.api_base_path) {
      mJsonGet(`${this.props.api_base_path}/svc_state`, state => {
        this.setState({
          allow_on: state.allow_on,
          mqtt_thing_reports_on: state.mqtt_thing_reports_on,
          monitoring_sensors: state.monitoring_sensors,
        });
        if (this.props.onRefresh) {
          this.props.onRefresh();
        }
      });
    }
  }

  _mkBoost(hours) {
    return () => {
      mJsonGet(`${this.props.api_base_path}/boost=${hours}`, this._refresh);
    };
  }

  _offNow() {
    mJsonGet(`${this.props.api_base_path}/off_now`, this._refresh);
  }

  renderHeatingOverrides() {
    let policy_state = "Boiler manager unknown state";
    if (this.state.allow_on == 'Never') {
      policy_state = "Boiler should be off";
    } else if (this.state.allow_on == 'Always') {
      policy_state = "Boiler should be on";
    } else if (this.state.allow_on == 'Rule') {
      policy_state = "Rule controls boiler state";
    }
    return <div className="card heating_cfg_ctrls">
        <div>
          Current status: {policy_state}, boiler reports {this.state.mqtt_thing_reports_on}
        </div>
        <button className="modal-button" onClick={this._mkBoost(1)}>Boost 1 hour</button>
        <button className="modal-button" onClick={this._mkBoost(2)}>Boost 2 hours</button>
        <button className="modal-button" onClick={this._offNow}>Off now</button>
      </div>
  }

  renderMonitoringSensors() {
    if (!this.state.monitoring_sensors) {
      return null;
    }
    return <div className="card heating_cfg_ctrls">
        {Object.entries(this.state.monitoring_sensors).map(([name, value]) => (
          <span key={name} className="bd-dark modal-button">{name}: {value || '?'}</span>
        ))}
      </div>
  }

  render() {
    return <>
      {this.renderHeatingOverrides()}
      {this.renderMonitoringSensors()}
    </>;
  }
}

class HeatingScheduleConfig extends React.Component {
  static buildProps(api_base_path = '', onRefresh = null, onToggleConfig = null, state = {}, renderFunctions = {}) {
    return {
      api_base_path: api_base_path,
      onRefresh: onRefresh,
      onToggleConfig: onToggleConfig,
      configuring: state.configuring || false,
      active_schedule: state.active_schedule || null,
      schedule_template: state.schedule_template || null,
      renderSlot: renderFunctions.renderSlot || null,
      renderTemplateSlot: renderFunctions.renderTemplateSlot || null,
    };
  }

  constructor(props) {
    super(props);
    this._applyTemplate = this._applyTemplate.bind(this);
    this._resetTemplateAlwaysOff = this._resetTemplateAlwaysOff.bind(this);
    this._resetTemplateAlwaysRule = this._resetTemplateAlwaysRule.bind(this);
    this._showLogs = this._showLogs.bind(this);
  }

  _applyTemplate() {
    mJsonGet(`${this.props.api_base_path}/template_apply`, this.props.onRefresh);
  }

  _resetTemplateAlwaysOff() {
    mJsonGet(`${this.props.api_base_path}/template_reset=Never`, this.props.onRefresh);
  }

  _resetTemplateAlwaysRule() {
    mJsonGet(`${this.props.api_base_path}/template_reset=Rule`, this.props.onRefresh);
  }

  _showLogs() {
    window.open('/logs.html', '_self');
  }

  renderConfig() {
    if (!this.props.schedule_template) {
      return null;
    }
    return <div>
        {this.renderTemplateControls()}
        {renderScheduleTable(this.props.schedule_template, this.props.renderTemplateSlot)}
      </div>;
  }

  renderState() {
    if (!this.props.active_schedule) {
      return null;
    }
    return <div>
      {renderScheduleTable(this.props.active_schedule, this.props.renderSlot)}
      {this.renderConfigControls()}
    </div>
  }

  renderConfigControls() {
    return <div className="card heating_cfg_ctrls">
        <button className="modal-button" onClick={this.props.onToggleConfig}>Config</button>
        <button className="modal-button" onClick={this._applyTemplate}>Reset today schedule</button>
        <button className="modal-button" onClick={this._showLogs}>Logs</button>
      </div>
  }

  renderTemplateControls() {
    return <div className="card heating_cfg_ctrls">
        <button className="modal-button" onClick={this.props.onToggleConfig}>Finish Config</button>
        <button className="modal-button" onClick={this._applyTemplate}>Apply template / reset today schedule</button>
        <button className="modal-button" onClick={this._resetTemplateAlwaysOff}>Reset template: Always off</button>
        <button className="modal-button" onClick={this._resetTemplateAlwaysRule}>Reset template: Always rule-based</button>
      </div>
  }

  render() {
    return this.props.configuring ? this.renderConfig() : this.renderState();
  }
}

class MqttHeating extends React.Component {
  static buildProps(api_base_path = '') {
    return {
      key: 'HeatingPane',
      api_base_path: api_base_path,
    };
  }

  constructor(props) {
    super(props);
    this.refresh = this.refresh.bind(this);
    this._toggleConfig = this._toggleConfig.bind(this);
    this._renderSlot = this._renderSlot.bind(this);
    this._renderTemplateSlot = this._renderTemplateSlot.bind(this);

    const app_visibility = new VisibilityCallback();
    app_visibility.app_became_visible = this.refresh;

    this.state = {
      configuring: false,
      active_schedule: null,
      schedule_template: null,
      allow_on: null,
      mqtt_thing_reports_on: null,
      monitoring_sensors: null,
      refreshId: null,
      app_visibility,
    };
  }

  refresh() {
    if (this.state.refreshId) {
      // Calling clearTimeout with an invalid id doesn't throw an error
      clearTimeout(this.state.refreshId);
    }

    if (this.state.configuring) {
      console.log("Configuring: will refresh schedule");
      mJsonGet(`${this.props.api_base_path}/template_schedule`, tmpl_state => {
        this.setState({schedule_template: tmpl_state.template});
      });
      return;
    }

    console.log("Refreshing boiler state...");
    mJsonGet(`${this.props.api_base_path}/svc_state`, state => {
      this.setState({active_schedule: state.active_schedule,
                     allow_on: state.allow_on,
                     mqtt_thing_reports_on: state.mqtt_thing_reports_on,
                     monitoring_sensors: state.monitoring_sensors,
                     refreshId: setInterval(this.refresh, millisecToNextSlotChg())});
    });
  }

  _toggleConfig() {
    this.setState({configuring: !this.state.configuring});
  }

  render() {
    return this.state.configuring? this.renderConfig() : this.renderState();
  }

  renderConfig() {
    if (!this.state.schedule_template) {
      this.refresh();
      return "Loading configuration...";
    }
    return <div>
      <HeatingScheduleConfig
        configuring={true}
        schedule_template={this.state.schedule_template}
        renderTemplateSlot={this._renderTemplateSlot}
        api_base_path={this.props.api_base_path}
        onRefresh={this.refresh}
        onToggleConfig={this._toggleConfig}
      />
    </div>;
  }

  renderState() {
    if (!this.state.active_schedule) {
      this.refresh();
      return "Loading...";
    }

    return <div>
      <HeatingControls
        allow_on={this.state.allow_on}
        mqtt_thing_reports_on={this.state.mqtt_thing_reports_on}
        monitoring_sensors={this.state.monitoring_sensors}
        api_base_path={this.props.api_base_path}
        onRefresh={this.refresh}
      />
      <HeatingScheduleConfig
        configuring={false}
        active_schedule={this.state.active_schedule}
        renderSlot={this._renderSlot}
        api_base_path={this.props.api_base_path}
        onRefresh={this.refresh}
        onToggleConfig={this._toggleConfig}
      />
    </div>
  }

  _renderSlot(slot) {
    const slot_name = `${('0' + slot.hour).slice(-2)}:${('0' + slot.minute).slice(-2)}`;
    const cb = () => {
      console.log("User toggling slot", slot_name);
      mJsonGet(`${this.props.api_base_path}/slot_toggle=${slot_name}`, this.refresh)
    };

    let descr = "Error";
    if (slot.allow_on == 'Never') {
      descr = `Off: ${slot.reason}`
    } else if (slot.allow_on == 'Always') {
      descr = `On: ${slot.reason}`
    } else if (slot.allow_on == 'Rule' && slot.request_on) {
      descr = `On: Rule ${slot.reason}`
    } else if (slot.allow_on == 'Rule' && !slot.request_on) {
      descr = `Off: Rule ${slot.reason}`
    }

    return <button className="modal-button" onClick={cb}>
             {slot_name}<wbr/> {descr}
           </button>
  }

  _renderTemplateSlot(slot) {
    const slot_name = `${('0' + slot.hour).slice(-2)}:${('0' + slot.minute).slice(-2)}`;
    const cb = (evt) => {
      const selected = evt.nativeEvent.target.value;
      console.log("Uset setting template", slot_name, selected);
      mJsonGet(`${this.props.api_base_path}/template_slot_set=${slot.hour},${slot.minute},${selected}`, this.refresh)
    };

    return <div>
            {slot_name}<wbr/> {slot.reason}
            <select key="`table_schedule_${slot.hour}_${slot.minute}_opt`"
                    defaultValue={slot.allow_on}
                    onChange={cb}>
              <option value="Always">Always on</option>
              <option value="Never">Always off</option>
              <option value="Rule">Follow rule</option>
            </select>
      </div>
  }
}
class DebouncedRange extends React.Component {
  constructor(props) {
    super(props);

    // Fail early on missing props
    props.min.this_is_a_required_prop;
    props.max.this_is_a_required_prop;
    props.value.this_is_a_required_prop;

    const val = (props.value)? props.value : props.min;
    this.state = {
      changing: false,
      value: val,
    };
  }

  UNSAFE_componentWillReceiveProps(next_props) {
    // Without this, we need to rely on having a key being set for the
    // component to update its state from both parent and internal changes
    // If UNSAFE_componentWillReceiveProps stops working (it may be removed?)
    // then using this element will need to include a key with the current
    // value., Eg:
    // <DebouncedRange
    //       key={`${UNIQ_ELEMENT_NAME}_slider_${parent.state.value}`}
    //       min={$min}
    //       max={$max}
    //       value={parent.state.value} />
    const val = (next_props && next_props.value)? next_props.value : 0;
    this.setState({value: val});
  }

  onChange(value) {
      this.setState({value: value});
  }

  onMouseUp(_) {
      this.setState({changing: false});
      this.props.onChange({target: { value: this.state.value }});
  }

  onMouseDown(_) {
      this.setState({changing: true});
  }

  render() {
    return <input type="range"
             onChange={ (evnt) => this.onChange(evnt.target.value)}
             onMouseUp={ (evnt) => { this.onMouseUp(evnt.target.value) }  }
             onMouseDown={ (evnt) => this.onMouseDown(evnt.target.value) }
             onTouchStart={ (evnt) => this.onMouseDown(evnt.target.value)}
             onTouchEnd={ (evnt) => this.onMouseUp(evnt.target.value)}
             className={this.props.className}
             min={this.props.min}
             max={this.props.max}
             value={this.state.value} />
  }
}
class Light extends React.Component {
  static buildProps(meta, state, api_base_path = '') {
    var props = {
      name: meta.name,
      description: meta.description,
      manufacturer: meta.manufacturer,
      model: meta.model,
      supports_brightness: false,
      brightness_min: 0,
      brightness_max: 0,
      supports_color_temp: false,
      color_temp_min: 0,
      color_temp_max: 0,
      color_temp_presets: [],
      supports_rgb: false,
      user_defined: meta.user_defined,
      api_base_path: api_base_path,
      // Current state from server
      current_state: state.state || false,
      current_brightness: state.brightness || 0,
      current_color_temp: state.color_temp || 0,
      current_color_rgb: state.color_rgb || '',
    }

    for (const action_name of Object.keys(meta.actions)) {
      var desc = meta.actions[action_name].value.meta;
      if (!desc) desc = {};

      if (action_name == 'brightness') {
        props.supports_brightness = true;
        props.brightness_min = desc.value_min;
        props.brightness_max = desc.value_max;
      }

      else if (action_name == 'color_temp') {
        props.supports_color_temp = true;
        props.color_temp_min = desc.value_min;
        props.color_temp_max = desc.value_max;
        props.color_temp_presets = desc.presets;
      }

      else if (action_name == 'color_rgb') {
        props.supports_rgb = true;
      }
    }

    props.has_extra_details = props.supports_color_temp
                              || props.supports_rgb;
    return props;
  }

  constructor(props) {
    super(props);
    this.state = {
      state: props.current_state,
      brightness: props.current_brightness || props.brightness_min,
      color_temp: props.current_color_temp || props.color_temp_min,
      color_rgb: props.current_color_rgb || '',
      details_shown: false,
    };

    /* TODO
    this.props.thing_registry.subscribe_to_state_updates(this.props.name,
      (state) => {
        this.setState(state);
      });
      */
  }

  componentDidUpdate(prevProps) {
    // Only update state from props when props actually change (server state updated)
    if (prevProps.current_state !== this.props.current_state ||
        prevProps.current_brightness !== this.props.current_brightness ||
        prevProps.current_color_temp !== this.props.current_color_temp ||
        prevProps.current_color_rgb !== this.props.current_color_rgb) {
      this.setState({
        state: this.props.current_state,
        brightness: this.props.current_brightness || this.props.brightness_min,
        color_temp: this.props.current_color_temp || this.props.color_temp_min,
        color_rgb: this.props.current_color_rgb || '',
      });
    }
  }

  setLightOn(v) {
    this.setState({ state: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.name}`, `state=${v}`);
  }

  changeBrightness(v) {
    if (v == 0) {
      this.setState({ brightness: 0, state: false });
    } else {
      this.setState({ brightness: v, state: true });
    }
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.name}`, `brightness=${v}`);
  }

  changeColorTemp(v) {
    this.setState({ color_temp: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.name}`, `color_temp=${v}`);
  }

  toggleDetailsPanel() {
    this.setState({ details_shown: !this.state.details_shown });
  }

  changeRGB(v) {
    this.setState({ color_rgb: v });
    mJsonPut(`${this.props.api_base_path}/z2m/set/${this.props.name}`, `color_rgb=${encodeURIComponent(v)}`);
  }

  render() {
    return (
      <div className='thing_div' key={`${this.props.name}_light_div`}>

        <div className="row">
          <div className="col-primary-action">
            <input type="checkbox"
                   checked={this.state.state}
                   value={this.state.state}
                   onChange={(evnt) => this.setLightOn(evnt.target.checked)}
                   key={`${this.props.name}_light_is_on`} />
          </div>

          <div className="col-fixed-fill thing-no-linebreak">
            <div className="row">
              <div className="col-fixed-fill">
              <label className='thing_name' htmlFor={`${this.props.name}_light_is_on`}>
                {this.props.name}
              </label>
              </div>

              { this.render_details_toggle() }
            </div>

            <div className="row">
              { this.render_brightness_select() }
            </div>
          </div>
        </div>

        { this.render_details_panel() }
      </div>
    );
  }

  render_details_toggle() {
    if (!this.props.has_extra_details) return '';
    return <div key={`${this.props.name}_light_details_panel_toggle_div`} className="toggle-details-panel">
             {this.render_details_toggle_link()}
           </div>;
  }

  render_details_toggle_link() {
    if (!this.state.details_shown) {
      return (<a key={`${this.props.name}_light_details_panel_toggle`}
                 onClick={evnt => this.toggleDetailsPanel()}>▼</a>);
    }

    return (<a key={`${this.props.name}_light_details_panel_toggle`}
               onClick={evnt => this.toggleDetailsPanel()} >▲</a>);
  }

  render_details_panel() {
    if (!this.props.has_extra_details) return '';
    if (!this.state.details_shown) return '';
    return (
        <div className="card modal">
          { [this.render_rgb_picker(), this.render_color_temp()] }
        </div>)
  }

  render_brightness_select() {
    if (!this.props.supports_brightness) return '';
    return (
      <DebouncedRange
             onChange={ (evnt) => this.changeBrightness(evnt.target.value) }
             key={`${this.props.name}_light_brightness_slider`}
             min={this.props.brightness_min}
             max={this.props.brightness_max}
             value={this.state.brightness} />
    )
  }

  render_color_temp() {
    if (!this.props.supports_color_temp) return '';
    return (
      <div key={`${this.props.name}_div_color_temp`}>
        <label>Temperature</label>
        <DebouncedRange
               onChange={(evnt) => this.changeColorTemp(evnt.target.value)}
               key={`${this.props.name}_light_color_temp`}
               min={this.props.color_temp_min}
               max={this.props.color_temp_max}
               value={this.state.color_temp} />
        { this.render_color_temp_presets() }
      </div>
    )
  }

  render_color_temp_presets() {
    if (!this.props.color_temp_presets || this.props.color_temp_presets.length == 0) {
      return '';
    }

    var presets = []
    for (const p of this.props.color_temp_presets) {
      presets.push(
        <option
            key={`${this.props.name}_option_color_temp_preset_${p.name}`}
            value={p.value}>
          {p.name}
        </option> 
      )
    }

    return (
      <select
          onChange={(evnt) => this.changeColorTemp(evnt.target.value)}
          key={`${this.props.name}_div_color_temp_presets`}
          value="">
        { presets }
      </select>
    )
  }

  render_rgb_picker() {
    if (!this.props.supports_rgb) return '';
    return (
      <div key={`${this.props.name}_div_color_picker`}>
        <label>Lamp color</label>
        <input type="color"
               onChange={(evt) => this.changeRGB(evt.target.value)}
               key={`${this.props.name}_light_rgb`}
               value={this.state.color_rgb} />
      </div>
    )
  }
}
class ThingsPane extends React.Component {
  static buildProps(local_storage, things, onResetOrder, onToggleReorder) {
    return {
      key: 'global_thing_list',
      things: things,
      local_storage: local_storage,
      onResetOrder: onResetOrder,
      onToggleReorder: onToggleReorder,
    };
  }

  _getOrderedThings(props) {
    // Create default order for list
    let default_things_order = [];
    for (const elm of props.things) {
      default_things_order.push(elm.props.name);
    }

    // Try to fetch from cache
    let cached_things_order = this.props.local_storage.get('ThingsPane.things_order', default_things_order);
    const set_existing_things = new Set(default_things_order);
    const set_cached_things_order = new Set(cached_things_order);
    let order_changed = false;

    // If non existing things are in the order, delete them
    for (const [idx,elm] of cached_things_order.entries()) {
      if (!set_existing_things.has(elm)) {
        delete cached_things_order[idx];
        order_changed = true;
      }
    }
    cached_things_order = cached_things_order.filter(x => x != null);

    // If things are missing from the order, add them to the end
    for (const elm of default_things_order) {
      if (!set_cached_things_order.has(elm)) {
        cached_things_order.push(elm);
        order_changed = true;
      }
    }

    if (order_changed) {
      this.props.local_storage.save('ThingsPane.things_order', cached_things_order);
    }

    return cached_things_order;
  }

  static getDerivedStateFromProps(props, state) {
    // Rebuild things_lookup whenever props.things changes
    const things_lookup = {};
    for (const elm of props.things) {
      things_lookup[elm.props.name] = elm;
    }
    return { things_lookup };
  }

  constructor(props) {
    super(props);

    const things_lookup = {};
    for (const elm of props.things) {
      things_lookup[elm.props.name] = elm;
    }

    this.state = {
      things_lookup: things_lookup,
      things_order: this._getOrderedThings(props),
      reordering: false,
      showHiddenThings: false,
      visibleGroup: null,
    };
  }

  toggleReordering() {
    this.setState({reordering: !this.state.reordering});
  }

  toggleShowHidden() {
    this.setState({showHiddenThings: !this.state.showHiddenThings});
  }

  reorder(idx, delta) {
    if ((idx + delta < 0) || (idx + delta >= this.state.things_order.length)) {
      return;
    }
    let new_order = this.state.things_order;
    const tmp = new_order[idx];
    new_order[idx] = new_order[idx+delta];
    new_order[idx+delta] = tmp;

    this.props.local_storage.save('ThingsPane.things_order', new_order);
    this.setState({things_order: new_order});
  }

  render() {
    if (this.state.reordering) return this.render_reordering();
    return <div key="global_thing_list_pane">
             {this._buildList()}
           </div>
  }

  _buildList() {
    const groupedThingList = new Map();
    groupedThingList.set(null, []);
    let current_group = null;
    for (const thing_name of this.state.things_order) {
      const thing = this.state.things_lookup[thing_name];

      let group = null;
      if (thing.props.user_defined) group = thing.props.user_defined.ui_group;
      if (group === undefined) group = null;
      if (group != current_group) {
        current_group = group;
        if (!groupedThingList.has(current_group)) {
          groupedThingList.set(current_group, []);
        }
      }

      const ui_hide = thing.props.user_defined && thing.props.user_defined.ui_hide;
      const classNames = (!this.state.showHiddenThings && ui_hide)? 'is-hidden' : '';
      groupedThingList.get(current_group).push(
        <li className={classNames} key={`${thing.props.name}_thing_li`}>
          {thing}
        </li>)
    }

    const groupList = [];
    const visibleGroup = (() => {
      if (this.state.visibleGroup) return this.state.visibleGroup;
      const groups = Array.from(groupedThingList.entries());
      if (groups.length == 0) return null;
      return groups[0][0];
    })();

    for (const e of groupedThingList.entries()) {
      const group = e[0];
      if (!group) continue; // We'll add null-group at the bottom

      const thinglist = e[1];
      const visible = (!this.state.showHiddenThings && group != null && group != visibleGroup)? 'is-hidden' : '';
      const expandGroupCtrl = (
        <div onClick={_ => this.setState({visibleGroup: group})} className="is-full-width text-dark bd-primary is-small is-a-bit-rounded">
          <b>{group}</b>
        </div>)
      groupList.push(
        <div className="light-group-collapsed" key={`${group}_thing_pane_group`}>
        {expandGroupCtrl}
        <ul className={visible} key={`${group}_thing_pane_group_ul`}>
          {thinglist}
        </ul>
        </div>);
    }

    if (groupedThingList.get(null).length > 0) {
      groupList.push(
        <div className="light-group-expanded" key={`nullgroup_thing_pane_group`}>
        <ul key={`nullgroup_thing_pane_group_ul`}>
          {groupedThingList.get(null)}
        </ul>
        </div>);
    }

    return groupList;
  }

  render_reordering() {
    const thing_list = this.state.things_order.map((thing_name, idx) => {
      const thing = this.state.things_lookup[thing_name];
      const reorder_up = () => {
        return (idx == 0)?
                  '▲' :
                  <a className="thing-list-reorder-link" onClick={evnt => this.reorder(idx, -1)}>▲</a>
      }
      const reorder_down = () => {
        return (idx == this.state.things_order.length-1)?
                  '▼' :
                  <a className="thing-list-reorder-link" onClick={evnt => this.reorder(idx, +1)}>▼</a>
      }
      return <li key={`${thing.props.name}_thing_reorder_li`}>
        <div className="thing_div row"
             key={`${thing.props.name}_reorder_div`}>
          <div className="col-primary-action">
            { reorder_down() }
            { reorder_up() }
          </div>
          <div className="col-fixed-fill">
            <h3>{thing.props.name}</h3>
          </div>
        </div>
      </li>
    });

    return <div key="global_thing_list_pane">
             <button onClick={() => this.toggleReordering()}>
               Done
             </button>
             <ul key="global_thing_list_ul">
               {thing_list}
             </ul>
           </div>
  }
}

class MqttLights extends React.Component {
  static buildProps(api_base_path = '') {
    return {
      key: 'MqttLights',
      local_storage: new LocalStorageManager(),
      api_base_path: api_base_path,
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      lights: null,
      thingsPaneKey: 0,
      autoGrouping: props.local_storage.get('autoGrouping', true),
      configExpanded: false,
    };
    this.thingsPaneRef = React.createRef();
  }

  analyzeGroups(lights) {
    console.log('=== Starting group analysis ===');
    console.log('Light names:', lights.map(l => l.meta.name));

    // Extract possible prefixes from each name
    const extractPrefix = (name) => {
      // Match sequences like "TVRoom" (all-caps followed by capitalized word)
      // Examples: "TVRoomSnoopy" -> "TVRoom", "TVRoomFloorlampLeft" -> "TVRoom"
      const capsWordMatch = name.match(/^([A-Z]{2,}[A-Z][a-z]+)/);
      if (capsWordMatch) {
        console.log(`    extractPrefix("${name}") caps+word match: ${capsWordMatch[1]}`);
        return capsWordMatch[1];
      }

      // Match simple camelCase: get the first word before another uppercase letter
      // Examples: "OliviaFloorlamp" -> "Olivia", "EmmaVelador" -> "Emma"
      const camelMatch = name.match(/^([A-Z][a-z]+)/);
      if (camelMatch) {
        console.log(`    extractPrefix("${name}") camelCase match: ${camelMatch[1]}`);
        return camelMatch[1];
      }

      // Fallback: match all letters until non-letter
      const fallbackMatch = name.match(/^([A-Za-z]+)/);
      const result = fallbackMatch ? fallbackMatch[1] : null;
      console.log(`    extractPrefix("${name}") fallback: ${result}`);
      return result;
    };

    // Count prefix occurrences
    const prefixCounts = {};
    const nameToPrefixes = {};

    for (const light of lights) {
      const name = light.meta.name;
      const prefix = extractPrefix(name);
      console.log(`  ${name} -> prefix: ${prefix}`);
      if (prefix && prefix.length >= 3) {
        prefixCounts[prefix] = (prefixCounts[prefix] || 0) + 1;
        nameToPrefixes[name] = prefix;
      }
    }

    console.log('Prefix counts:', prefixCounts);

    // Assign groups (only if prefix appears 2+ times)
    const groups = {};
    for (const light of lights) {
      const name = light.meta.name;
      const prefix = nameToPrefixes[name];
      if (prefix && prefixCounts[prefix] >= 2) {
        groups[name] = prefix;
        console.log(`  ${name} assigned to group: ${prefix}`);
      } else {
        groups[name] = null;
        console.log(`  ${name} not grouped (prefix: ${prefix}, count: ${prefixCounts[prefix] || 0})`);
      }
    }

    console.log('Final groups:', groups);
    return groups;
  }

  applyGrouping(lights, enabled) {
    console.log(`=== applyGrouping called, enabled: ${enabled} ===`);

    if (!enabled) {
      console.log('Removing all grouping');
      // Remove grouping
      for (const light of lights) {
        if (!light.meta.user_defined) light.meta.user_defined = {};
        light.meta.user_defined.ui_group = undefined;
      }
      return lights;
    }

    // Apply auto-grouping
    const groups = this.analyzeGroups(lights);
    console.log('Applying grouping to lights...');
    for (const light of lights) {
      if (!light.meta.user_defined) light.meta.user_defined = {};
      light.meta.user_defined.ui_group = groups[light.meta.name];
      console.log(`  ${light.meta.name}.ui_group = ${light.meta.user_defined.ui_group}`);
    }
    console.log('=== Grouping applied ===');
    return lights;
  }

  applyGroupingNow() {
    // Toggle grouping state
    const newValue = !this.state.autoGrouping;
    this.props.local_storage.save('autoGrouping', newValue);
    this.setState({ autoGrouping: newValue });

    // Clear cached metadata and order to force recalculation
    this.props.local_storage.remove('things_meta');
    this.props.local_storage.remove('things_hash');
    this.props.local_storage.remove('ThingsPane.things_order');

    // Reload lights with new grouping setting
    this.fetchLights();
  }

  resetOrder() {
    if (!this.state.lights) return;

    // Sort by group first, then alphabetically (grouping already applied to metadata)
    const sorted_lights = [...this.state.lights].sort((a, b) => {
      const groupA = a.meta.user_defined?.ui_group || '';
      const groupB = b.meta.user_defined?.ui_group || '';

      if (groupA && groupB) {
        if (groupA !== groupB) {
          return groupA.localeCompare(groupB);
        }
        return a.meta.name.localeCompare(b.meta.name);
      }

      if (groupA && !groupB) return -1;
      if (!groupA && groupB) return 1;

      return a.meta.name.localeCompare(b.meta.name);
    });

    const sorted_names = sorted_lights.map(light => light.meta.name);

    // Save to local storage
    this.props.local_storage.save('ThingsPane.things_order', sorted_names);

    // Force ThingsPane to re-mount by changing its key
    this.setState({ thingsPaneKey: this.state.thingsPaneKey + 1 });
  }

  fetchLights(force_reload = false) {
    mJsonGet(`${this.props.api_base_path}/z2m/get_known_things_hash`, (server_hash) => {
      const cached_hash = this.props.local_storage.cacheGet('things_hash');
      const cached_meta = this.props.local_storage.cacheGet('things_meta');
      const hash_changed = cached_hash !== server_hash;

      // Always fetch current state with /get_lights
      mJsonGet(`${this.props.api_base_path}/get_lights`, async (lights_list) => {
        // If hash changed or no cached metadata, fetch metadata for all lights
        if (hash_changed || !cached_meta) {
          const lights_with_meta = await Promise.all(
            lights_list.map(light =>
              new Promise(resolve => {
                mJsonGet(`${this.props.api_base_path}/z2m/meta/${light.thing_name}`, (meta) => {
                  resolve({ state: light, meta: meta });
                });
              })
            )
          );

          // Apply grouping if enabled
          console.log('Applying grouping during fetch, autoGrouping:', this.state.autoGrouping);
          this.applyGrouping(lights_with_meta, this.state.autoGrouping);

          // Cache the metadata WITH grouping applied, using thing_name as key
          const meta_by_name = {};
          for (const light of lights_with_meta) {
            meta_by_name[light.state.thing_name] = light.meta;
          }
          this.props.local_storage.cacheSave('things_meta', meta_by_name);
          this.props.local_storage.cacheSave('things_hash', server_hash);

          this.setState({ lights: lights_with_meta });
        } else {
          // Use cached metadata, only fetched fresh state
          const lights_with_meta = lights_list.map(light => ({
            state: light,
            meta: cached_meta[light.thing_name]
          }));
          // Grouping is already in cached meta, no need to reapply
          this.setState({ lights: lights_with_meta });
        }
      });
    });
  }

  async componentDidMount() {
    this.fetchLights();
  }

  on_app_became_visible() {
    this.fetchLights(true);
  }

  componentWillUnmount() {
  }

  fetchStats() {
    mJsonGet(`${this.props.api_base_path}/get_lights`, (res) => {
      this.setState({ lights: res });
    });
  }

  render() {
    if (!this.state.lights) {
      return ( <div className="app-loading">Loading...</div> );
    }

    console.log('=== MqttLights.render() ===');
    console.log('autoGrouping state:', this.state.autoGrouping);

    // Grouping is already applied in the cached data, just sort
    const sorted_lights = [...this.state.lights].sort((a, b) => {
      const groupA = a.meta.user_defined?.ui_group || '';
      const groupB = b.meta.user_defined?.ui_group || '';

      // If both have groups, sort by group then name
      if (groupA && groupB) {
        if (groupA !== groupB) {
          return groupA.localeCompare(groupB);
        }
        return a.meta.name.localeCompare(b.meta.name);
      }

      // Items with groups come before items without
      if (groupA && !groupB) return -1;
      if (!groupA && groupB) return 1;

      // Both without groups, sort alphabetically
      return a.meta.name.localeCompare(b.meta.name);
    });

    // Create Light components from the fetched lights
    const light_components = sorted_lights.map(light => {
      const props = Light.buildProps(light.meta, light.state, this.props.api_base_path);
      return React.createElement(Light, props);
    });

    // Create and render ThingsPane with the Light components
    const thingsPaneProps = ThingsPane.buildProps(
      this.props.local_storage,
      light_components,
      () => this.resetOrder(),
      () => this.thingsPaneRef.current && this.thingsPaneRef.current.toggleReordering()
    );
    // Use thingsPaneKey to force re-mount when order is reset
    thingsPaneProps.key = `ThingsPane_${this.state.thingsPaneKey}`;
    thingsPaneProps.ref = this.thingsPaneRef;
    const thingsPane = React.createElement(ThingsPane, thingsPaneProps);

    return (
      <div>
        {thingsPane}
        <div className="config-section">
          <div
            className="config-toggle"
            onClick={() => this.setState({ configExpanded: !this.state.configExpanded })}>
            Config {this.state.configExpanded ? '▲' : '▼'}
          </div>
          {this.state.configExpanded && (
            <div className="config-panel">
              <button className="modal-button" onClick={() => this.thingsPaneRef.current && this.thingsPaneRef.current.toggleReordering()}>
                Reorder
              </button>
              <button className="modal-button" onClick={() => this.resetOrder()}>
                Reset order
              </button>
              <button className="modal-button" onClick={() => this.fetchLights(true)}>
                Refresh things
              </button>
              <button className="modal-button" onClick={() => this.applyGroupingNow()}>
                {this.state.autoGrouping ? 'Disable grouping' : 'Enable grouping'}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }
}
class CamViewer extends React.Component {
  static buildProps(api_base_path = '', svc_full_url = '') {
    return {
      key: 'cam_viewer',
      api_base_path,
      svc_full_url,
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      imageTimestamp: Date.now(),
      isLoading: false,
      isRecording: false,
    };

    this.onSnapRequested = this.onSnapRequested.bind(this);
    this.onRecordRequested = this.onRecordRequested.bind(this);
  }

  on_app_became_visible() {
    // We can request a snap to refresh state, but this is unlikely to be the behaviour the suer wants. It's more
    // likely that the user wants to see the last time the snap was updated due to motion. If the user does want
    // to trigger an update, they can do it manually.
    // this.onSnapRequested();
  }

  onSnapRequested() {
    this.setState({ isLoading: true });

    mAjax({
      url: `${this.props.api_base_path}/snap`,
      type: 'get',
      success: () => {
        console.log("Snapshot captured");
        // Refresh the image by updating timestamp
        setTimeout(() => {
          this.setState({
            imageTimestamp: Date.now(),
            isLoading: false
          });
        }, 500); // Small delay to ensure snapshot is saved
      },
      error: (err) => {
        showGlobalError("Failed to capture snapshot: " + err);
        this.setState({ isLoading: false });
      }
    });
  }

  onRecordRequested() {
    this.setState({ isRecording: true });

    mAjax({
      url: `${this.props.api_base_path}/record?secs=20`,
      type: 'get',
      success: (response) => {
        console.log("Recording started for 20 seconds");
        // Keep recording state for 20 seconds
        setTimeout(() => {
          this.setState({ isRecording: false });
        }, 20000);
      },
      error: (err) => {
        showGlobalError("Failed to start recording: " + err.response);
        this.setState({ isRecording: false });
      }
    });
  }

  render() {
    return (
      <div className="cam-container">
        <div className="cam-controls">
          <button
            onClick={this.onSnapRequested}
            disabled={this.state.isLoading || this.state.isRecording}
            className="snap-button"
          >
            {this.state.isLoading ? "Capturing..." : "Take New Snapshot"}
          </button>
          <button
            onClick={this.onRecordRequested}
            disabled={this.state.isRecording || this.state.isLoading}
            className="record-button"
          >
            {this.state.isRecording ? "Recording (20s)..." : "Record Video (20s)"}
          </button>
          <a href={`${this.props.svc_full_url}/nvr`} className="nvr-link">View Recordings</a>
        </div>

        <div className="cam-image-container">
          <img
            src={`${this.props.api_base_path}/lastsnap?t=${this.state.imageTimestamp}`}
            alt="Last doorbell snap"
            className="cam-image"
          />
        </div>
      </div>
    );
  }
}
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

class SensorsHistoryPane extends React.Component {
  static buildProps() {
    const urlParams = new URLSearchParams(window.location.search);
    const urlQueryMetric = urlParams.get('metric');
    const metric = urlQueryMetric ? [urlQueryMetric] : INTERESTING_PLOT_METRICS;
    const urlQueryPeriod = urlParams.get('period');
    const period = urlQueryPeriod ? [urlQueryPeriod] : 'day_2';
    const plotSingleMetric = !!urlQueryMetric;

    return {
      plotSingleMetric,
      metrics_to_plot: metric,
      period,
      key: 'SensorsHistoryPane',
    };
  }

  constructor(props) {
    super(props);
    this.loadPlotsForSensorMeasuring = this.loadPlotsForSensorMeasuring.bind(this);
    this.updateConfigPeriod = this.updateConfigPeriod.bind(this);
    this.updateConfigMetric = this.updateConfigMetric.bind(this);
    this.sensorsListRef = React.createRef();

    this.state = {
      sensors: null,
      period: this.props.period,
      allMetrics: [],
      selectedMetrics: this.props.metrics_to_plot,
    };
  }

  componentDidMount() {
    this.on_app_became_visible();
  }

  on_app_became_visible() {
    mJsonGet('/sensors/metrics', metrics => {
        this.setState({
          allMetrics: metrics,
          sensors: null // Force reload of plots
        });
    });
    if (this.sensorsListRef.current) {
      this.sensorsListRef.current.refresh();
    }
  }

  updateConfigPeriod() {
    const period = document.getElementById('SensorsHistoryConfig_period').value;
    window.history.replaceState(null, "Sensors", `?metric=${this.state.selectedMetrics.join(',')}&period=${period}`);
    this.setState({ period });
  }

  updateConfigMetric() {
    const select = document.getElementById('SensorsHistoryConfig_metric');
    const selected = Array.from(select.selectedOptions).map(o => o.value);

    window.history.replaceState(
      null,
      "Sensors",
      `?metric=${selected.join(',')}&period=${this.state.period}`
    );

    this.setState({
      selectedMetrics: selected,
      sensors: null, // reset so plots reload
    });
  }

  render() {
    return (
      <div id="SensorsHistoryPane">
        <div class="SensorsHistoryConfig">
          <h1>
            <img src="/favicon.ico" alt="Sensor history" />
            Sensor history
          </h1>
          <label htmlFor="SensorsHistoryConfig_period">Period:</label>
          <select
            value={this.state.period}
            name="SensorsHistoryConfig_period"
            id="SensorsHistoryConfig_period"
            onChange={this.updateConfigPeriod}
          >
            <option value="hour_1">Last hour</option>
            <option value="hour_6">Last 6 hours</option>
            <option value="hour_12">Last 12 hours</option>
            <option value="day_1">Last day</option>
            <option value="day_2">Last 2 days</option>
            <option value="all">All</option>
          </select>

          <label htmlFor="SensorsHistoryConfig_metric" style={{ marginLeft: "10px" }}>
            Metrics:
          </label>
          <select
            id="SensorsHistoryConfig_metric"
            multiple
            value={this.state.selectedMetrics}
            onChange={this.updateConfigMetric}
          >
            {this.state.allMetrics.map(m => (
              <option value={m} key={m}>{m}</option>
            ))}
          </select>
        </div>

        <SensorsList ref={this.sensorsListRef} metrics={this.state.selectedMetrics} api_base_path={this.props.api_base_path} />

        {this.render_plots()}
      </div>
    );
  }

  render_plots() {
    const metrics = this.state.selectedMetrics;

    if (metrics.length === 1 && !this.state.sensors) {
      this.loadPlotsForSensorMeasuring(metrics[0]);
      return "Loading sensors...";
    } else if (metrics.length === 1) {
      return this.renderSingleMetric(metrics[0], this.state.sensors);
    } else {
      return this.renderMetricInAllSensors(metrics);
    }
  }

  renderMetricInAllSensors(metrics) {
    function buildUrlForPeriod(period) {
      if (!period || period == 'all') return '';
      let unit = 'days';
      let time = 1;
      if (period == "hour_1") { unit = "hours"; time = 1; }
      if (period == "hour_6") { unit = "hours"; time = 6; }
      if (period == "hour_12") { unit = "hours"; time = 12; }
      if (period == "day_1") { unit = "days"; time = 1; }
      if (period == "day_2") { unit = "days"; time = 2; }
      return `/${unit}/${time}`;
    }

    let local_plots = [];
    for (const metric of metrics) {
      const plotId = `local_plot_${metric}`;
      const url = `/sensors/get_single_metric_in_all_sensors_csv/${metric}${buildUrlForPeriod(this.state.period)}`;

      // Clear existing plot div content to force recreation
      setTimeout(() => {
        const plotDiv = document.getElementById(plotId);
        if (plotDiv) {
          plotDiv.innerHTML = '';
        }
        simple_dygraph_plot(plotId, url);
      }, 0);

      local_plots.push(
        <div className="card" key={`${metric}_${this.state.period}_div`}>
          <h3><a href={`?metric=${metric}`}>{metric}</a></h3>
          <div id={plotId} />
          <div id={`${plotId}_label`} />
        </div>
      );
    }

    return local_plots;
  }

  loadPlotsForSensorMeasuring(metric) {
    mAjax({
      url: `/sensors/measuring/${metric}`,
      cache: false,
      type: 'get',
      dataType: 'text',
      success: (sensorLst) => { this.setState({ sensors: JSON.parse(sensorLst) }); },
      error: (err) => { console.log(err); showGlobalError(err); },
    });
  }

  renderSingleMetric(metric, sensors) {
    function buildUrlForPeriod(period) {
      if (!period || period == 'all') return '';
      let unit = 'days';
      let time = 1;
      if (period == "hour_1") { unit = "hours"; time = 1; }
      if (period == "hour_6") { unit = "hours"; time = 6; }
      if (period == "hour_12") { unit = "hours"; time = 12; }
      if (period == "day_1") { unit = "days"; time = 1; }
      if (period == "day_2") { unit = "days"; time = 2; }
      return `/history/${unit}/${time}`;
    }

    let local_plots = [];
    for (const sensor of sensors) {
      const plotId = `local_plot_${sensor}`;
      const url = `/sensors/get_metric_in_sensor_csv/${sensor}/${metric}${buildUrlForPeriod(this.state.period)}`;

      // Clear existing plot div content to force recreation
      setTimeout(() => {
        const plotDiv = document.getElementById(plotId);
        if (plotDiv) {
          plotDiv.innerHTML = '';
        }
        simple_dygraph_plot(plotId, url);
      }, 50); // Give it a bit of time to let the element load, otherwise Dygraph can't find it

      local_plots.push(
        <div className="card" key={`${sensor}_${this.state.period}_div`}>
          <h3>{metric} for {sensor}</h3>
          <div id={plotId} />
          <div id={`${plotId}_label`} />
        </div>
      );
    }

    return local_plots;
  }
};

class SensorsList extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      sensors: null,
      sensorData: {},
    };
  }

  componentDidMount() {
    this.loadSensors();
  }

  componentDidUpdate(prevProps) {
    if (prevProps.metrics !== this.props.metrics) {
      this.loadSensors();
    }
  }

  refresh() {
    this.loadSensors();
  }

  loadSensors() {
    const metrics = this.props.metrics;
    if (!metrics || metrics.length === 0) {
      this.setState({ sensors: [], sensorData: {} });
      return;
    }

    const basePath = this.props.api_base_path || '';

    if (metrics.length === 1) {
      // Single metric: fetch sensors that measure this metric
      mJsonGet(`${basePath}/sensors/measuring/${metrics[0]}`, sensors => {
        this.setState({ sensors, sensorData: {} });
        this.loadSensorData(sensors);
      });
    } else {
      // Multiple metrics: need to find all sensors that have any of these metrics
      // Fetch sensors for each metric and combine
      const allSensors = new Set();
      let pending = metrics.length;

      metrics.forEach(metric => {
        mJsonGet(`${basePath}/sensors/measuring/${metric}`, sensorLst => {
          sensorLst.forEach(s => allSensors.add(s));
          pending--;
          if (pending === 0) {
            const sensors = Array.from(allSensors).sort();
            this.setState({ sensors, sensorData: {} });
            this.loadSensorData(sensors);
          }
        });
      });
    }
  }

  loadSensorData(sensors) {
    const basePath = this.props.api_base_path || '';
    sensors.forEach(sensor => {
      mJsonGet(`${basePath}/z2m/get/${sensor}`, data => {
        this.setState(prevState => ({
          sensorData: {
            ...prevState.sensorData,
            [sensor]: data,
          },
        }));
      });
    });
  }

  getUnit(metric) {
    const units = {
      temperature: '°C',
      device_temperature: '°C',
      humidity: '%',
      voltage: 'V',
      battery: '%',
      pm25: 'µg/m³',
    };
    return units[metric] || '';
  }

  formatValue(value, metric) {
    if (typeof value !== 'number') {
      return '?';
    }
    const unit = this.getUnit(metric);
    return unit ? `${value}${unit}` : value;
  }

  renderSensorValues(sensor) {
    const data = this.state.sensorData[sensor];
    const metrics = this.props.metrics;

    if (data === undefined) {
      return '...';
    }
    if (data === null) {
      return '?';
    }

    // Check if all values are unknown
    const hasAnyValue = metrics.some(m => typeof data[m] === 'number');
    if (!hasAnyValue) {
      return 'No data yet';
    }

    if (metrics.length === 1) {
      // Single metric: just show the value
      return this.formatValue(data[metrics[0]], metrics[0]);
    } else {
      // Multiple metrics: show key=value pairs
      return metrics
        .map(m => `${m}=${this.formatValue(data[m], m)}`)
        .join(', ');
    }
  }

  render() {
    if (this.state.sensors === null) {
      return <div className="sensors-list">Loading sensors...</div>;
    }

    return (
      <ul className="sensors-list keyval-list">
        {this.state.sensors.map(sensor => (
          <li key={sensor} className="bd-dark modal-button">
            <strong>{sensor}:</strong> {this.renderSensorValues(sensor)}
          </li>
        ))}
      </ul>
    );
  }
}
class TTSAnnounce extends React.Component {
  static buildProps(api_base_path = '') {
    return {
      key: 'tts_announce',
      api_base_path: api_base_path,
    };
  }

  constructor(props) {
    super(props);
    this.canRecordMic = window.location.protocol === "https:";

    this.state = {
      ttsPhrase: "",
      ttsLang: "es-ES",
      isRecording: false,
      speakerList: null,
      announcementHistory: [],
      historyExpanded: false,
    };

    this.recorderRef = React.createRef();
    this.onTTSRequested = this.onTTSRequested.bind(this);
    this.onMicRecRequested = this.onMicRecRequested.bind(this);
    this.onMicRecSend = this.onMicRecSend.bind(this);
    this.onCancel = this.onCancel.bind(this);
    this.fetchAnnouncementHistory = this.fetchAnnouncementHistory.bind(this);
  }

  componentDidMount() {
    this.on_app_became_visible();
  }

  on_app_became_visible() {
    mJsonGet(`${this.props.api_base_path}/ls_speakers`, (data) => this.setState({ speakerList: data }));
    this.fetchAnnouncementHistory();
  }

  fetchAnnouncementHistory() {
    mJsonGet(`${this.props.api_base_path}/announcement_history`, (data) => this.setState({ announcementHistory: data }));
  }

  onTTSRequested() {
    const phrase = this.state.ttsPhrase.trim() || prompt("What is so important?");
    if (!phrase) return;
    this.setState({ ttsPhrase: phrase });

    console.log(`announce {"lang": "${this.state.ttsLang}", "phrase": "${phrase}"}`);

    const newEntry = {
      timestamp: new Date().toISOString(),
      phrase: phrase,
      lang: this.state.ttsLang,
      volume: 'default',
      uri: `${this.props.api_base_path}/tts/${phrase}_${this.state.ttsLang}.mp3`
    };

    this.setState(prev => ({
      announcementHistory: [...prev.announcementHistory, newEntry].slice(-10)
    }));

    console.log("BCAST ");
    console.log(`${this.props.api_base_path}/announce_tts?lang=${this.state.ttsLang}&phrase=${phrase}`)
    mAjax({
      url: `${this.props.api_base_path}/announce_tts?lang=${this.state.ttsLang}&phrase=${phrase}`,
      type: 'get',
      success: () => {
        console.log("Sent TTS request");
        this.fetchAnnouncementHistory();
      },
      error: showGlobalError
    });
  }

  async onMicRecRequested() {
    if (!this.canRecordMic) {
      showGlobalError("Mic recording only works on https pages");
      return;
    }

    if (!navigator.mediaDevices) {
      showGlobalError("Your browser does not support microphone recording");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const rec = new MediaRecorder(stream);

      rec.chunks = [];
      rec.ondataavailable = e => rec.chunks.push(e.data);

      this.recorderRef.current = rec;
      rec.start();
      this.setState({ isRecording: true });
    } catch (err) {
      showGlobalError("Mic error: " + err);
    }
  }

  onMicRecSend() {
    const rec = this.recorderRef.current;
    if (!rec) {
      showGlobalError("No microphone recording in progress");
      return;
    }

    rec.onstop = () => {
      const blob = new Blob(rec.chunks, { type: "audio/ogg; codecs=opus" });

      const form = new FormData();
      form.append("audio_data", blob, "mic_cap.ogg");

      mAjax({
        url: `${this.props.api_base_path}/announce_user_recording`,
        data: form,
        cache: false,
        contentType: false,
        processData: false,
        method: "POST",
        success: () => console.log("Sent user recording"),
        error: showGlobalError
      });

      rec.stream.getTracks().forEach(t => t.stop());
      this.recorderRef.current = null;
      this.setState({ isRecording: false });
    };

    rec.stop();
  }

  onCancel() {
    const rec = this.recorderRef.current;
    if (rec) {
      rec.stream.getTracks().forEach(t => t.stop());
      this.recorderRef.current = null;
    }
    this.setState({ isRecording: false });
  }

  render() {
    if (this.state.isRecording) {
      return (
        <ul className="player-announce-methods">
          <li>
            <button className="player-button" onClick={this.onMicRecSend}>Send</button>
          </li>
          <li>
            <button className="player-button" onClick={this.onCancel}>Cancel</button>
          </li>
        </ul>
      );
    }

    return (
      <div className="announce-container">
        <div className="announce-input-div">
          <input
            type="text"
            placeholder="Text to announce"
            value={this.state.ttsPhrase}
            onChange={e => this.setState({ ttsPhrase: e.target.value })}
          />
        </div>

        <div className="announce-ctrls-div">
          <button onClick={this.onTTSRequested}>
            Announce!
          </button>

          <select
            value={this.state.ttsLang}
            onChange={e => this.setState({ ttsLang: e.target.value })}
          >
            { /* https://developers.google.com/assistant/console/languages-locales */ }
            <option value="es-ES">ES</option>
            <option value="es-419">es 419</option>
            <option value="en-GB">EN GB</option>
          </select>

          {this.canRecordMic && (
            <button onClick={this.onMicRecRequested}>
              Record
            </button>
          )}
        </div>

        {this.state.speakerList && (
          <div className="announce-speaker-list">
            Will announce in: <ul>
              {this.state.speakerList.map(x => <li key={x}>{x}</li>) }
            </ul>
          </div>
        )}

        <div className="announce-history-section">
          <small
            onClick={() => this.setState({ historyExpanded: !this.state.historyExpanded })}
            style={{ cursor: 'pointer', userSelect: 'none' }}
          >
            {this.state.historyExpanded ? '▼' : '▶'} Announcement History ({this.state.announcementHistory.length})
          </small>

          {this.state.historyExpanded && (
            <div className="announce-history-list card">
              {this.state.announcementHistory.length === 0 ? (
                <p>No announcements yet</p>
              ) : (
                <ul>
                  {this.state.announcementHistory.slice().reverse().map((item, idx) => (
                    <li key={idx}>
                      <div className="history-item">
                        <span className="history-timestamp">
                          {new Date(item.timestamp).toLocaleString()}
                        </span>
                        <span className="history-phrase">
                          "{item.phrase}"
                        </span>
                        <span className="history-details">
                          (Lang: {item.lang}, vol: {item.volume}, <a href={item.uri}>link</a>)
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }
}
const ProxiedServices = {
  CACHE_KEY: 'proxied_services',
  _services: null,
  _storage: new LocalStorageManager(),

  _fetchServices(callback) {
    mJsonGet('/get_proxied_services', services => {
      this._services = services;
      this._storage.cacheSave(this.CACHE_KEY, services);
      if (callback) callback(services);
    });
  },

  get(serviceName) {
    return this._services ? this._services[serviceName] : null;
  },

  init(callback) {
    const fresh = this._storage.cacheGet(this.CACHE_KEY);
    const cached = fresh || this._storage.cacheGet_ignoreExpire(this.CACHE_KEY);

    if (cached) {
      this._services = cached;
      if (!fresh) this._fetchServices(); // Refresh in background if expired
      callback();
    } else {
      this._fetchServices(callback);
    }
  },
};

function LightsSection(props) {
  return (
    <div className="dashboard-section" id="lights-section">
      {React.createElement(
        MqttLights,
        MqttLights.buildProps('/ZmwLights'))}
      <a href={ProxiedServices.get('ZmwLights')}><img src="/ZmwLights/favicon.ico"/></a>
    </div>
  );
}

function SpeakersSection(props) {
  return (
    <div className="dashboard-section" id="speakers-section">
      <a href={ProxiedServices.get('ZmwSpeakerAnnounce')}><img src="/ZmwSpeakerAnnounce/favicon.ico"/></a>
      {React.createElement(
        TTSAnnounce,
        TTSAnnounce.buildProps('/ZmwSpeakerAnnounce'))}
    </div>
  );
}

function ContactMonSection(props) {
  return (
    <div className="dashboard-section" id="contactmon-section">
      <a href={ProxiedServices.get('ZmwContactmon')}><img src="/ZmwContactmon/favicon.ico"/></a>
      {React.createElement(
        ContactMonitor,
        ContactMonitor.buildProps('/ZmwContactmon'))}
    </div>
  );
}

function MqttHeatingSection(props) {
  return (
    <div className="dashboard-section" id="heating-section">
      <h2><a href={ProxiedServices.get('ZmwHeating')}><img src="/ZmwHeating/favicon.ico"/></a>Heating</h2>
      {React.createElement(
        HeatingControls,
        HeatingControls.buildProps('/ZmwHeating'))}
    </div>
  );
}

function ReolinkDoorbellSection(props) {
  return (
    <div className="dashboard-section" id="reolink-doorbell-section">
      <a href={ProxiedServices.get('ZmwReolinkDoorbell')}><img src="/ZmwReolinkDoorbell/favicon.ico"/></a>
      {React.createElement(
        CamViewer,
        CamViewer.buildProps('/ZmwReolinkDoorbell', ProxiedServices.get('ZmwReolinkDoorbell')))}
    </div>
  );
}

function SensorsListSection(props) {
  return (
    <div className="dashboard-section" id="sensors-list-section" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <a href={ProxiedServices.get('ZmwSensormon')}>
        <img src="/ZmwSensormon/favicon.ico"/>
      </a>
      {React.createElement(
        SensorsList,
        { metrics: ['temperature'], api_base_path: '/ZmwSensormon' })}
    </div>
  );
}

function SceneListSection(props) {
  return (
    <div className="dashboard-section" id="scene-list-section" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <a href={ProxiedServices.get('BaticasaButtons')}>
        <img src="/BaticasaButtons/favicon.ico"/>
      </a>
      {React.createElement(
        ScenesList,
        { api_base_path: '/BaticasaButtons' })}
    </div>
  );
}

// Main Dashboard Component
function Dashboard(props) {
  const [expandedSection, setExpandedSection] = React.useState(null);
  const contentRef = React.useRef(null);

  const toggleSection = (section) => {
    const newSection = expandedSection === section ? null : section;
    setExpandedSection(newSection);

    // Scroll to content after state update
    if (newSection !== null) {
      setTimeout(() => {
        if (contentRef.current) {
          contentRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 50);
    }
  };

  const renderBtn = (btnLbl, btnUrl, btnIco) => {
    return <button
            className="modal-button primary"
            onClick={() => window.open(btnUrl, '_blank')}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <img src={btnIco} alt="" style={{ width: '20px', height: '20px' }} />
            {btnLbl}
          </button>
  }

  const renderSvcBtn = (sectionName, serviceName) => {
    return <button
              className={expandedSection === sectionName ? 'modal-button primary bg-dark' : 'modal-button'}
              onClick={() => toggleSection(sectionName)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
           >
              <img src={`/${serviceName}/favicon.ico`} alt="" style={{ width: '20px', height: '20px' }} />
              {sectionName}
           </button>
  }

  return (
    <div>
      <div className="dashboard-sections">
        <LightsSection />
        <SceneListSection />
        <SensorsListSection />

        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
          { renderSvcBtn('Announce', 'ZmwSpeakerAnnounce') }
          { renderSvcBtn('Contact', 'ZmwContactmon') }
          { renderSvcBtn('Heating', 'ZmwHeating') }
          { renderSvcBtn('Door', 'ZmwReolinkDoorbell') }
          { /* TODO move these to a config */}
          { renderBtn("Baticasa Services", "http://10.0.0.10:4200/index.html", "http://10.0.0.10:4200/favicon.ico") }
          { renderBtn("Z2M", "http://10.0.0.10:4100", "/z2m.ico") }
          { renderBtn("", "http://bati.casa:5000/client_ls_txt", "/wwwslider.ico") }
          { renderBtn("", "http://bati.casa:2222/photos", "/immich.ico") }
          { renderBtn("", "https://bati.casa:8443/", "/unifi.png") }
          { renderBtn("", "http://bati.casa:8444/admin/login.php", "/pihole.svg") }
        </div>

        <div ref={contentRef}>
          {expandedSection === 'Announce' && <SpeakersSection />}
          {expandedSection === 'Contact' && <ContactMonSection />}
          {expandedSection === 'Heating' && <MqttHeatingSection />}
          {expandedSection === 'Door' && <ReolinkDoorbellSection />}
        </div>
      </div>
    </div>
  );
}

Dashboard.buildProps = () => ({ key: 'dashboard' });

ProxiedServices.init(() => {
  z2mStartReactApp('#app_root', Dashboard);
});
