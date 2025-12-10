class MediaPlayer extends React.Component {
  static buildProps(thing_registry, player) {
    return {
      thing_registry: thing_registry,
      player: player,
      can_tts: Object.keys(player.actions).includes("tts_announce"),
      can_announce: Object.keys(player.actions).includes("user_audio_announce"),
      // Mobile browsers don't accept calls to getUserMedia if no https
      can_record_mic: 'https:' == document.location.protocol,
    }
  }

  constructor(props, thing_registry) {
    super(props);

    this.state = {
      is_authenticated: true,
      volume: 0,
      media_info: null,
      announce_ui_shown: false,
      mic_recorder: null,
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
    this.onAnnouncementUiEnable = this.onAnnouncementUiEnable.bind(this);
    this.onAnnouncementEnd = this.onAnnouncementEnd.bind(this);
    this.onTTSRequested = this.onTTSRequested.bind(this);
    this.onMicRecRequested = this.onMicRecRequested.bind(this);
    this.onMicRecSend = this.onMicRecSend.bind(this);
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

  onAnnouncementUiEnable() {
    const st = this.state;
    st.announce_ui_shown = true;
    this.setState(st);
  }

  onAnnouncementEnd() {
    const st = this.state;
    st.announce_ui_shown = false;
    st.mic_recorder = null; // TODO cleanup
    this.setState(st);
  }

  onTTSRequested() {
    if (!this.props.can_tts) {
      showGlobalError(`Requested unsupported action 'TTS' on player ${this.props.player.name}`);
      return;
    }

    const phrase = prompt(`What should ${this.props.player.name} say?`);
    const langIdx = document.getElementById(`MediaPlayer_${this.props.player.name}_tts_lang_select`).options.selectedIndex;
    const lang = document.getElementById(`MediaPlayer_${this.props.player.name}_tts_lang_select`).options[langIdx].value;
    if (!!phrase && phrase.length > 0) {
      this.props.thing_registry.set_thing(
        this.props.player.name,
        `tts_announce={"lang": "${lang}", "phrase": "${phrase}"}`
      );
    }

    this.onAnnouncementEnd();
  }

  onMicRecRequested() {
    if (!this.props.can_announce) {
      showGlobalError(`Requested unsupported action 'announcement' on player ${this.props.player.name}`);
      this.onAnnouncementEnd();
      return;
    }

    if (!this.props.can_record_mic) {
      showGlobalError('Requested mic recording, but this only works on https mode');
      this.onAnnouncementEnd();
      return;
    }

    if (!navigator.mediaDevices) {
      showGlobalError(`Can't access microphone (hint: this only works on https pages)`);
      this.onAnnouncementEnd();
      return;
    }

    navigator.mediaDevices.getUserMedia({video: false, audio: true})
    .then(mic => {
      const mediaRecorder = new MediaRecorder(mic);
      mediaRecorder.mic = mic;
      mediaRecorder.chunks = [];
      mediaRecorder.ondataavailable = e => { mediaRecorder.chunks.push(e.data); };
      mediaRecorder.start();

      const st = this.state;
      st.mic_recorder = mediaRecorder;
      st.announce_ui_shown = false;
      this.setState(st);
    }).catch(err => {
      showGlobalError(`Can't find microphone to record message: ${err}`);
      this.onAnnouncementEnd();
    });
  }

  onMicRecSend() {
    if (this.state.mic_recorder == null) {
      showGlobalError("Application state error: can't find mic");
      this.onAnnouncementEnd();
      return;
    }

    const micRec = this.state.mic_recorder;
    micRec.addEventListener("stop", _ => {
      const blob = new Blob(micRec.chunks, { type: 'audio/ogg; codecs=opus' });
      // Useful to debug
      if (false) {
        const audioElement = new Audio();
        audioElement.src = URL.createObjectURL(blob);
        audioElement.controls = true;
        document.getElementById('ConfigPane_config_options').appendChild(audioElement);
      }

      var audioForm = new FormData();
      audioForm.append("audio_data", blob, "mic_cap.mp3");

      $.ajax({
        url: `/${this.props.player.name}/announce_user_recording`,
        data: audioForm,
        cache: false,
        contentType: false,
        processData: false,
        method: 'POST',
        type: 'POST',
        success: _ => { console.log('Sent user recording for announcement'); },
        error: showGlobalError,
      });
    });

    micRec.stop();
    this.onAnnouncementEnd();
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

  render_announce_ui() {
    if (this.state.announce_ui_shown) {
      return this.render_active_announce_ui();
    }

    if (this.state.mic_recorder) {
      return this.render_announce_ui_mic_recording();
    }

    if (this.props.can_tts || this.props.can_announce) {
        return (
          <div key={`MediaPlayer_${this.props.player.name}_tts_div`}>
            <button key={`MediaPlayer_${this.props.player.name}_tts_ui_start_btn`}
                  className="player-tts-button"
                  onClick={ this.onAnnouncementUiEnable }>
              {this.props.player.name} Say
            </button>
          </div>
        );
    }

    return '';
  }

  render_active_announce_ui() {
      let announceMethods = [];
      if (this.props.can_announce && this.props.can_record_mic) {
        announceMethods.push(
          <li key={`MediaPlayerAnnounceMicRecord_${this.props.player.name}`}>
            <button key={`MediaPlayer_${this.props.player.name}_announce_mic_rec_btn`}
                  className="player-button"
                  onClick={ this.onMicRecRequested }>
              Record
            </button>
          </li>);
      }
      if (this.props.can_tts) {
        announceMethods.push(
          <li key={`MediaPlayerAnnounceTTS_${this.props.player.name}`}>
            <button key={`MediaPlayer_${this.props.player.name}_announce_tts_btn`}
                  className="player-button"
                  onClick={ this.onTTSRequested }>
              TTS
            </button>
            <select key={`MediaPlayer_${this.props.player.name}_tts_lang_select`}
                     id={`MediaPlayer_${this.props.player.name}_tts_lang_select`}
                     className="player-tts-lang-select">
              <option value='es_ar'>AR</option>
              <option value='es'>ES</option>
              <option value='en'>EN</option>
            </select>
          </li>);
      }
      return (
        <ul className="player-announce-methods"
            id={`MediaPlayerAnnouncementMethods_${this.props.player.name}`}>
          {announceMethods}
          <li key={`MediaPlayerAnnounceCancel_${this.props.player.name}`}>
            <button key={`MediaPlayer_${this.props.player.name}_announce_cancel_btn`}
                  className="player-button"
                  onClick={ this.onAnnouncementEnd }>
              Cancel
            </button>
          </li>
        </ul>
      );
  }

  render_announce_ui_mic_recording() {
      return (
        <ul className="player-announce-methods"
            id={`MediaPlayerAnnouncementMethods_${this.props.player.name}`}>
          <li key={`MediaPlayerAnnounce_${this.props.player.name}_mic_send_li`}>
            <button key={`MediaPlayer_${this.props.player.name}_mic_rec_send_btn`}
                  className="player-button"
                  onClick={ this.onMicRecSend }>
              Send
            </button>
          </li>
          <li key={`MediaPlayerAnnounce_${this.props.player.name}_mic_rec_cancel_li`}>
            <button key={`MediaPlayer_${this.props.player.name}_mic_rec_cancel_btn`}
                  className="player-button"
                  onClick={ this.onAnnouncementEnd }>
              Cancel
            </button>
          </li>
        </ul>
      );
  }

  render_no_media() {
    return (
      <div className="thing_div"
           key={`${this.props.player.name}_media_player_div`}>
        { this.render_announce_ui() }
      </div>
    );
  }

  render_playing_media() {
    return (
      <div className=""
           key={`${this.props.player.name}_media_player_div`}>
        { this.render_announce_ui() }
        <table>
        <tbody>
        <tr>
        <td className="col-media-icon hide-xs hide-md">
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
      <div id="MediaPlayersDiv" className="card" key="MediaPlayersDiv">
        <ul id="MediaPlayerList">{renderPlayers}</ul>
      </div>
    );
  }
}
