function NVRViewer(props) {
  const [cameras, setCameras] = React.useState([]);
  const [selectedCam, setSelectedCam] = React.useState(null);
  const [recordings, setRecordings] = React.useState([]);
  const [days, setDays] = React.useState(3);
  const [isLoading, setIsLoading] = React.useState(true);

  React.useEffect(() => {
    // Fetch list of cameras on component mount
    mJsonGet(`${props.api_base_path}/nvr/api/cameras`, (cams) => {
      console.log(cams)
        setCameras(cams.cameras);
        if (cams.cameras.length > 0) {
          setSelectedCam(cams.cameras[0]);
        }
        setIsLoading(false);
      }
    );
  }, []);

  React.useEffect(() => {
    // Fetch recordings when camera or days changes
    if (!selectedCam) return;

    setIsLoading(true);
    mJsonGet(`${props.api_base_path}/nvr/api/${selectedCam}/recordings?days=${days}`,
      (data) => {
        setRecordings(data.recordings);
        setIsLoading(false);
      },
      (err) => {
        setIsLoading(false);
      }
    );
  }, [selectedCam, days]);

  const formatFilename = (filename) => {
    try {
      const dateStr = filename.split('.')[0];
      const hour = dateStr.split('_')[1];
      const month = parseInt(dateStr.substring(4, 6));
      const day = parseInt(dateStr.substring(6, 8));
      const hr = parseInt(hour.substring(0, 2));
      const minute = parseInt(hour.substring(2, 4));

      const monthNames = [
        "January", "February", "March", "April",
        "May", "June", "July", "August",
        "September", "October", "November", "December"
      ];

      const monthName = monthNames[month - 1] || `Month ${month}`;
      return `${monthName} - ${day.toString().padStart(2, '0')} - ${hr.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
    } catch (e) {
      return filename;
    }
  };

  if (isLoading && cameras.length === 0) {
    return (
      <div className="nvr-container">
        <div className="loading-message">Loading cameras...</div>
      </div>
    );
  }

  return (
    <div className="nvr-container">
      <h1><img src="/favicon.ico" alt="NVR"/>NVR - Recordings</h1>

      <div className="nvr-controls">
        {cameras.length > 1 && (
          <select
            value={selectedCam || ''}
            onChange={e => setSelectedCam(e.target.value)}
          >
            {cameras.map(cam => (
              <option key={cam} value={cam}>{cam}</option>
            ))}
          </select>
        )}

        <select
          value={days}
          onChange={e => setDays(parseInt(e.target.value))}
        >
          <option value="1">Last 1 day</option>
          <option value="3">Last 3 days</option>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="0">All recordings</option>
        </select>

        <a href="/" className="back-link">← Back to Camera</a>
      </div>

      {isLoading ? (
        <div className="loading-message">Loading recordings...</div>
      ) : recordings.length === 0 ? (
        <div className="empty-message">No recordings found for the selected period</div>
      ) : (
        <div className="gallery-container">
          {recordings.map((rec, idx) => (
            <div key={idx} className="gallery-item">
              <a href={rec.video_url} target="_blank">
                <img src={rec.thumbnail_url} alt={rec.filename}/>
                <div className="gallery-item-info">
                  <div className="gallery-item-name">{formatFilename(rec.filename)}</div>
                  <div className="gallery-item-size">{rec.size}</div>
                </div>
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

NVRViewer.buildProps = (api_base_path = '') => ({
  key: 'nvr_viewer',
  api_base_path: api_base_path,
});

z2mStartReactApp('#app_root', NVRViewer);
