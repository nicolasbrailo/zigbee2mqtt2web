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
