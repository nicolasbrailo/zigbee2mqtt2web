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
        <ul className="not-a-list">
          {this.state.scenes.map((scene, idx) => (
            <li key={idx}>
              <button type="button" onClick={() => this.applyScene(scene)}>{scene.replace(/_/g, ' ')}</button>
            </li>
          ))}
          {this.state.sceneStatus && 
            <li><blockquote className="hint">{this.state.sceneStatus}</blockquote></li>}
        </ul>
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

  renderButton(buttonName, idx) {
  }

  renderWarningUnboundActions(unboundButtons) {
    return (unboundButtons.length > 0 && (
        <div className="card warn">
          <h4>⚠ Error: Unbound Actions ({unboundButtons.length})</h4>
          <p>
            The following callbacks could not be bound to Z2M things. Check if devices are missing or callback names are incorrect:
            <ul className="compact-list">
              {unboundButtons.map((buttonName, idx) => (
                <li key={idx}><code>{buttonName}</code></li>
              ))}
            </ul>
          </p>
        </div>
      ));
  }

  renderBoundActions(boundButtons) {
    if (boundButtons.length === 0) {
      return (<div className="card warn">No button callbacks found</div>);
    }
    return (
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Actions</th>
            <th>Test</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
        { boundButtons.map((buttonName, idx) => {
            const status = this.state.triggerStatus[buttonName];
            const actionInput = this.state.actionInputs[buttonName] || '';
            const discoveredActions = this.state.discoveredActions[buttonName] || [];
            const showCustomInput = this.state.showCustomInput[buttonName] || false;
            const hasDiscoveredActions = discoveredActions.length > 0;
            return (
              <tr key={idx}>
                <td>{buttonName}</td>
                <td>
                    {hasDiscoveredActions && !showCustomInput ? (
                      <select value={actionInput} onChange={(e) => this.handleDropdownChange(buttonName, e.target.value)}>
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
                      />
                    )}
                </td>
                <td>
                  <button type="button" onClick={() => this.triggerAction(buttonName)}>Do it</button>
                </td>
                <td>
                  { status && (<blockquote className={status.success ? "hint" : "warn"}>{status.message}</blockquote>) }
                </td>
              </tr>
            );
        })}
        </tbody>
      </table>
    );
  }

  render() {
    if (!this.state.boundButtons || !this.state.unboundButtons) {
      return ( <div className="app-loading">Loading...</div> );
    }

    return (
      <div id="BaticasaButtonsContainer">
        { this.renderWarningUnboundActions(this.state.unboundButtons) }
        { this.renderBoundActions(this.state.boundButtons) }

        <h4>Scenes</h4>
        <ScenesList api_base_path={this.props.api_base_path} />
      </div>
    )
  }
}
