class MediaPlayer extends React.Component {
  static buildProps(thing_registry, player) {
    return {
      thing_registry: thing_registry,
      player: player,
      can_tts: Object.keys(player.actions).includes("tts_announce"),
      can_announce: Object.keys(player.actions).includes("play_announcement"),
    }
  }

  constructor(props, thing_registry) {
    super(props);

    this.state = {
      is_authenticated: true,
      volume: 0,
      media_info: null,
    };

    this.props.thing_registry.get_thing_action_state(this.props.player.name, 'media_player_state')
    .then(state => {
      if (!state.volume) state.volume = 0;
      this.setState(state);
    });

    this.onPlayClicked = this.onPlayClicked.bind(this);
    this.onStopClicked = this.onStopClicked.bind(this);
    this.onVolumeChanged = this.onVolumeChanged.bind(this);
    this.onNextClicked = this.onNextClicked.bind(this);
    this.onPrevClicked = this.onPrevClicked.bind(this);
    this.onTTSRequested = this.onTTSRequested.bind(this);
    this.onAnnouncementRequested = this.onAnnouncementRequested.bind(this);
  }

  onPlayClicked() {
    this.props.thing_registry.set_thing(this.props.player.name, 'toggle_play');
  }

  onStopClicked() {
    this.props.thing_registry.set_thing(this.props.player.name, 'stop');
  }

  onNextClicked() {
    this.props.thing_registry.set_thing(this.props.player.name, 'relative_jump_to_track=1');
  }

  onPrevClicked() {
    this.props.thing_registry.set_thing(this.props.player.name, 'relative_jump_to_track=-1');
  }

  onVolumeChanged(evnt) {
    const vol = evnt.target.value;
    this.props.thing_registry.set_thing(this.props.player.name, `volume=${vol}`);
  }

  onTTSRequested() {
    if (!this.props.can_tts) {
      showGlobalError(`Requested unsupported action 'TTS' on player ${this.props.player.name}`);
      return;
    }

    // TODO
  }

  onAnnouncementRequested() {
    if (!this.props.can_announce) {
      showGlobalError(`Requested unsupported action 'announcement' on player ${this.props.player.name}`);
      return;
    }

    // TODO
  }

  render() {
    if (this.state.is_authenticated == false) {
      return this.render_no_auth();
    }

    if (!this.state.media_info || Object.keys(this.state.media_info).length == 0) {
      return this.render_no_media();
    }

    return this.render_playing_media();
  }

  render_no_auth() {
    return <div className="bd-error text-error"
                key={`${this.props.player.name}_media_player_div`}>
        {this.props.player.name} is not authenticated. Goto <a href={this.state.reauth_url} target="_blank">
        reauthentication page</a> then refresh this page.
      </div>
  }

  render_announce_or_tts() {
    let announcements = [];
    if (this.props.can_tts) {
      announcements.push(
        <button key={`MediaPlayer_${this.props.player.name}_tts_btn`}
                className="player-button"
                onClick={this.onTTSRequested}>
          TTS
        </button>
      );
    }

    if (this.props.can_announce) {
      announcements.push(
        <button key={`MediaPlayer_${this.props.player.name}_announce_btn`}
                className="player-button"
                onClick={this.onAnnouncementRequested}>
          Say
        </button>
      );
    }

    return announcements;
  }

  render_no_media() {
    return this.render_announce_or_tts();
    return (
      <div className="thing_div row container"
           key={`${this.props.player.name}_media_player_div`}>
        { this.render_announce_or_tts() }
      </div>
    );
  }

  render_playing_media() {
    return (
      <div className="thing_div row container"
           key={`${this.props.player.name}_media_player_div`}>
        this.render_announce_or_tts();
        <table>
        <tbody>
        <tr>
        <td className="col-media-icon">
          <img className="media-icon" src={this.state.media_info.icon}/>
        </td>

        <td className="col-media-mainpanel">
          <div className="media-info-label">{this.state.media_info.title} - {this.state.media_info.album_name}</div>
          <div className="media-info-label">{this.props.player.name} - {this.state.media_info.artist}</div>
          <button className="player-button" onClick={this.onPlayClicked}>&#9199;&#xFE0F;</button>
          <DebouncedRange
                 className="player-volume"
                 onChange={this.onVolumeChanged}
                 key={`${this.props.player.name}_set_volume`}
                 min="0"
                 max="100"
                 value={this.state.volume} />
          <button className="player-button" onClick={this.onPrevClicked}>&#x23EA;&#xFE0F;</button>
          <button className="player-button" onClick={this.onNextClicked}>&#x23ED;&#xFE0F;</button>
        </td>
        </tr>
        </tbody>
        </table>
      </div>
    );
  }
}

class MediaPlayerList extends React.Component {
  static buildProps(thing_registry) {
    return {
      thing_registry: thing_registry,
      media_players: thing_registry.mediaplayer_things,
      key: 'MediaPlayerList',
    }
  }

  constructor(props, thing_registry) {
    super(props);
  }

  render() {
    if (this.props.media_players.length == 0) return '';

    let renderPlayers = []
    for (const player of this.props.media_players) {
      renderPlayers.push(
        <li key={`MediaPlayerList_li_${player.name}`}>
          {React.createElement(MediaPlayer, MediaPlayer.buildProps(this.props.thing_registry, player))}
        </li>);
    }

    return (
      <ul id="MediaPlayerList">{renderPlayers}</ul>
    );
  }
}
