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
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const monthName = monthNames[month - 1] || `Month ${month}`;
      return `${monthName} - ${day.toString().padStart(2, '0')} - ${hr.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
    } catch (e) {
      return filename;
    }
  };

  if (isLoading && cameras.length === 0) {
    return (<div className="card hint">
            <p>Loading cameras!</p>
            <p>Please wait...</p>
            </div>)
  }

  return (
    <section id="zmw_reolink_nvr">
      <details open>
      <summary>Config</summary>
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

        <button onClick={() => window.location.href = '/'}>← Back to Camera</button>
      </details>

      {isLoading ? (
        <p>Loading recordings...</p>
      ) : recordings.length === 0 ? (
        <p>No recordings found for the selected period</p>
      ) : (
        <div className="gallery">
          {recordings.map((rec, idx) => (
            <figure key={idx}>
              <a href={rec.video_url} target="_blank">
                <img src={rec.thumbnail_url} alt={rec.filename}/>
                <figcaption>
                  {formatFilename(rec.filename)} ({rec.size})
                </figcaption>
              </a>
            </figure>
          ))}
        </div>
      )}
    </section>
  );
}

NVRViewer.buildProps = (api_base_path = '') => ({
  key: 'nvr_viewer',
  api_base_path: api_base_path,
});
