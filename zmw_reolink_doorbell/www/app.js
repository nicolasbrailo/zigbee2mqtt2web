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
      recordDuration: 20,
      recordingTimeLeft: 0,
    };
    this.countdownInterval = null;

    this.onSnapRequested = this.onSnapRequested.bind(this);
    this.onRecordRequested = this.onRecordRequested.bind(this);
  }

  on_app_became_visible() {
    // We can request a snap to refresh state, but this is unlikely to be the behaviour the user wants. It's more
    // likely that the user wants to see the last time the snap was updated due to motion. If the user does want
    // to trigger an update, they can do it manually.
    // this.onSnapRequested();
  }

  onSnapRequested() {
    this.setState({ isLoading: true });

    mTextGet(`${this.props.api_base_path}/snap`,
      () => {
        console.log("Snapshot captured");
        // Refresh the image by updating timestamp
        setTimeout(() => {
          this.setState({
            imageTimestamp: Date.now(),
            isLoading: false
          });
        }, 500); // Small delay to ensure snapshot is saved
      },
      (err) => {
        showGlobalError("Failed to capture snapshot: " + err);
        this.setState({ isLoading: false });
      });
  }

  onRecordRequested() {
    const secs = this.state.recordDuration;
    this.setState({ isRecording: true, recordingTimeLeft: secs });

    mTextGet(`${this.props.api_base_path}/record?secs=${secs}`,
      () => {
        console.log(`Recording started for ${secs} seconds`);
        this.countdownInterval = setInterval(() => {
          this.setState((prevState) => {
            const newTime = prevState.recordingTimeLeft - 1;
            if (newTime <= 0) {
              clearInterval(this.countdownInterval);
              return { isRecording: false, recordingTimeLeft: 0 };
            }
            return { recordingTimeLeft: newTime };
          });
        }, 1000);
      },
      (err) => {
        showGlobalError("Failed to start recording: " + err.response);
        this.setState({ isRecording: false, recordingTimeLeft: 0 });
      });
  }

  render() {
    return (
      <section id="zwm_reolink_doorcam">
        <div>
          <button onClick={this.onSnapRequested} disabled={this.state.isLoading || this.state.isRecording}>
            {this.state.isLoading ? "Capturing..." : "Take New Snapshot"}
          </button>
          <button onClick={this.onRecordRequested} disabled={this.state.isRecording || this.state.isLoading}>
            {this.state.isRecording ? `Recording (${this.state.recordingTimeLeft}s)...` : `Record Video (${this.state.recordDuration}s)`}
          </button>
          <button onClick={() => window.location.href=`${this.props.svc_full_url}/nvr`}>View Recordings</button>
          <input
            type="range"
            min="10"
            max="100"
            value={this.state.recordDuration}
            onChange={(e) => this.setState({ recordDuration: parseInt(e.target.value) })}
            disabled={this.state.isRecording}
          />
        </div>

        <a href={`${this.props.api_base_path}/lastsnap?t=${this.state.imageTimestamp}`}>
        <img
          className="img-always-on-screen quite-round"
          src={`${this.props.api_base_path}/lastsnap?t=${this.state.imageTimestamp}`}
          alt="Last doorbell snap"
        /></a>
      </section>
    );
  }
}
