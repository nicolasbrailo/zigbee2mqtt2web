function getMediaType(speaker) {
  if (speaker.is_playing_line_in) return 'Line-In';
  if (speaker.is_playing_radio) return 'Radio';
  if (speaker.is_playing_tv) return 'TV';
  if (speaker.transport_state === 'PLAYING') return 'Other';
  return null;
}

function findSpeakerGroup(speakerName, groups) {
  for (const [coordinator, members] of Object.entries(groups)) {
    if (members.includes(speakerName)) {
      return coordinator;
    }
  }
  return null;
}

class SonosSpeaker extends React.Component {
  onVolumeChange(e) {
    const v = parseInt(e.target.value, 10);
    this.props.onVolumeChange(this.props.speaker.name, v);
  }

  renderExtraCfgs() {
    const speaker = this.props.speaker;
    const speakerInfo = speaker.speaker_info || {};
    const mediaType = getMediaType(speaker);

    return (
      <details className="light_details">
        <summary>⚙</summary>
        <div>
          <div>Name: {speakerInfo.player_name || speaker.name}</div>
          <div>Model: {speakerInfo.model_name}</div>
          <div>Model Number: {speakerInfo.model_number}</div>
          <div>Zone: {speakerInfo.zone_name}</div>
          <div>URI: {speaker.uri || 'None'}</div>
          <div>Media Type: {mediaType || 'None'}</div>
        </div>
      </details>
    );
  }

  render() {
    const speaker = this.props.speaker;
    const groups = this.props.groups;
    const groupCoordinator = findSpeakerGroup(speaker.name, groups);
    const groupLabel = (groupCoordinator && groupCoordinator != speaker.name)? `[${groupCoordinator}]` : null;
    let transport = speaker.transport_state;
    if (speaker.transport_state === "PLAYING") transport = '▶';
    if (speaker.transport_state === "STOPPED") transport = '⏹';
    return (
      <li>
        <p>
          <input
            id={`${speaker.name}_control`}
            type="checkbox"
            checked={this.props.controlSelected}
            onChange={() => this.props.onControlToggle(speaker.name)}
          />
          <label htmlFor={`${speaker.name}_control`}>
            {speaker.name} {groupLabel} {transport}
          </label>
        </p>
        Vol: {this.props.volume}
        <DebouncedRange
          min={0}
          max={100}
          value={this.props.volume}
          onChange={(e) => this.onVolumeChange(e)}
        />
        {this.renderExtraCfgs()}
      </li>
    );
  }
}

class SonosCtrl extends React.Component {
  static buildProps(api_base_path = '') {
    return {
      key: 'SonosCtrl',
      api_base_path: api_base_path,
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      speakers: null,
      groups: null,
      zones: null,
      controlSpeakers: {},
      masterVolume: 50,
      spotifyUri: null,
      speakerVolumes: {},
      volumeRatios: {},
      hijackInProgress: false,
      hijackLogs: [],
      hijackComplete: false,
    };
  }

  onControlToggle(speakerName) {
    this.setState(prev => ({
      controlSpeakers: {
        ...prev.controlSpeakers,
        [speakerName]: !prev.controlSpeakers[speakerName],
      },
    }));
  }

  onSpotifyHijack() {
    const { controlSpeakers, speakerVolumes } = this.state;
    const speakers = {};
    const speakerNames = [];
    for (const [name, selected] of Object.entries(controlSpeakers)) {
      if (selected) {
        speakers[name] = { vol: speakerVolumes[name] || 0 };
        speakerNames.push(name);
      }
    }
    if (Object.keys(speakers).length === 0) {
      showGlobalError("You need to select a set of speakers to control");
      return;
    }

    const initialMsg = `Requested Spotify-Hijack to ${speakerNames.join(', ')}`;
    this.setState({
      hijackInProgress: true,
      hijackLogs: [initialMsg],
      hijackComplete: false,
    });

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${this.props.api_base_path}/spotify_hijack`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      ws.send(JSON.stringify(speakers));
    };

    ws.onmessage = (event) => {
      this.setState(prev => ({
        hijackLogs: [...prev.hijackLogs, event.data],
      }));
    };

    ws.onclose = () => {
      this.setState({ hijackInProgress: false, hijackComplete: true });
    };

    ws.onerror = (error) => {
      this.setState(prev => ({
        hijackLogs: [...prev.hijackLogs, `Error: ${error.message || 'Connection error'}`],
        hijackInProgress: false,
        hijackComplete: true,
      }));
    };
  }

  onHijackLogClose() {
    this.setState({ hijackLogs: [], hijackComplete: false });
  }

  onStopAll() {
    mJsonPut(`${this.props.api_base_path}/stop_all_playback`);
  }

  onSpeakerVolumeChange(speakerName, volume) {
    this.setState(prev => {
      // Update ratio = master / speaker
      const newRatio = volume > 0 ? prev.masterVolume / volume : prev.masterVolume;
      return {
        speakerVolumes: {
          ...prev.speakerVolumes,
          [speakerName]: volume,
        },
        volumeRatios: {
          ...prev.volumeRatios,
          [speakerName]: newRatio,
        },
      };
    });
    mJsonPut(`${this.props.api_base_path}/volume`, { [speakerName]: volume });
  }

  onMasterVolumeChange(e) {
    const newMaster = parseInt(e.target.value, 10);
    const { volumeRatios, controlSpeakers, speakerVolumes } = this.state;

    // Calculate new volumes only for controlled speakers
    const updatedVolumes = {};
    for (const [name, ratio] of Object.entries(volumeRatios)) {
      if (controlSpeakers[name]) {
        const newVol = Math.round(Math.min(100, Math.max(0, newMaster / ratio)));
        updatedVolumes[name] = newVol;
      }
    }

    if (Object.keys(updatedVolumes).length > 0) {
      mJsonPut(`${this.props.api_base_path}/volume`, updatedVolumes);
    }

    this.setState({
      masterVolume: newMaster,
      speakerVolumes: { ...speakerVolumes, ...updatedVolumes },
    });
  }

  componentDidMount() {
    this.fetchState();
  }

  on_app_became_visible() {
    this.fetchState();
  }

  fetchState() {
    mJsonGet(`${this.props.api_base_path}/world_state`, (data) => {
      const speakerVolumes = {};
      const volumeRatios = {};
      const masterVolume = this.state.masterVolume;
      for (const speaker of data.speakers) {
        speakerVolumes[speaker.name] = speaker.volume;
        // ratio = master / speaker, avoid division by zero
        volumeRatios[speaker.name] = speaker.volume > 0 ? masterVolume / speaker.volume : masterVolume;
      }
      this.setState({
        speakers: data.speakers,
        groups: data.groups,
        zones: data.zones,
        speakerVolumes: speakerVolumes,
        volumeRatios: volumeRatios,
      });
    });
    mJsonGet(`${this.props.api_base_path}/get_spotify_uri`, (data) => {
      this.setState({ spotifyUri: data.spotify_uri });
    });
  }

  render() {
    if (!this.state.speakers) {
      return <div>Loading...</div>;
    }

    const hasSpotify = this.state.spotifyUri != null;

    return (
      <div id="zmw_lights">
        <div id="master_ctrls" className="card">
          <button
            onClick={() => this.onSpotifyHijack()}
            disabled={!hasSpotify || this.state.hijackInProgress}
          >
            {this.state.hijackInProgress ? 'Hijacking...' : (hasSpotify ? 'Spotify Hijack' : 'Spotify Hijack (Not playing)')}
          </button>
          <button onClick={() => this.onStopAll()}>Stop all</button>
          <div>URI: {this.state.spotifyUri || 'None'}</div>

          <label>Master volume</label>
          <DebouncedRange
            min={0}
            max={100}
            value={this.state.masterVolume}
            onChange={(e) => this.onMasterVolumeChange(e)}
          />
        </div>
        {this.state.hijackLogs.length > 0 && (
          <div id="hijack_log">
            <ul>
              {this.state.hijackLogs.map((msg, idx) => (
                <li key={idx}>{msg}</li>
              ))}
            </ul>
            {this.state.hijackComplete && (
              <button onClick={() => this.onHijackLogClose()}>Close</button>
            )}
          </div>
        )}
        <details open>
          <summary>Speakers</summary>
          <ul>
            {this.state.speakers.map((speaker) => (
              <SonosSpeaker
                key={speaker.name}
                speaker={speaker}
                groups={this.state.groups}
                api_base_path={this.props.api_base_path}
                controlSelected={!!this.state.controlSpeakers[speaker.name]}
                onControlToggle={(name) => this.onControlToggle(name)}
                volume={this.state.speakerVolumes[speaker.name] || 0}
                onVolumeChange={(name, vol) => this.onSpeakerVolumeChange(name, vol)}
              />
            ))}
          </ul>
        </details>
      </div>
    );
  }
}

z2mStartReactApp('#app_root', SonosCtrl);
