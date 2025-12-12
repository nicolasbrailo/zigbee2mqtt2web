class ShellyPlugMonitor extends React.Component {
  static buildProps() {
    return {
      key: 'ShellyPlugMonitor',
    };
  }

  constructor(props) {
    super(props);
    this.state = {
      devices: null,
    };
    this.fetchStats = this.fetchStats.bind(this);
    this.refreshInterval = null;
  }

  async componentDidMount() {
    this.fetchStats();
    this.refreshInterval = setInterval(this.fetchStats, 10000);
  }

  componentWillUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  on_app_became_visible() {
    this.fetchStats();
  }

  fetchStats() {
    mJsonGet('/all_stats', (res) => {
      this.setState({ devices: res });
    });
  }

  formatUptime(seconds) {
    const months = Math.floor(seconds / (30 * 24 * 3600));
    seconds %= 30 * 24 * 3600;
    const days = Math.floor(seconds / (24 * 3600));
    seconds %= 24 * 3600;
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;

    const parts = [];
    if (months > 0) parts.push(`${months} month${months !== 1 ? 's' : ''}`);
    if (days > 0) parts.push(`${days} day${days !== 1 ? 's' : ''}`);
    if (hours > 0) parts.push(`${hours} hour${hours !== 1 ? 's' : ''}`);
    if (mins > 0) parts.push(`${mins} min${mins !== 1 ? 's' : ''}`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs} sec${secs !== 1 ? 's' : ''}`);

    return parts.join(', ');
  }

  renderDevice(name, stats) {
    const powerStatus = stats.powered_on ? 'ON' : 'OFF';
    const powerClass = stats.powered_on ? 'bg-success' : 'bg-error';

    return (
      <div key={name} className="col-6 col-12-md">
        <div className="card">
          <header className="row is-vertical-align">
            <h4 className="is-marginless" style={{flex: 1}}>{name}</h4>
            <span className="text-grey is-small">Last updated: {stats.device_current_time}</span>
            <span className={`${powerClass} text-white is-a-bit-rounded`} style={{marginLeft: '1rem', padding: '0.3rem 0.8rem'}}>{powerStatus}</span>
          </header>
          <table>
            <tbody>
              <tr><td>Power</td><td>{stats.active_power_watts.toFixed(1)} W</td></tr>
              <tr><td>Current</td><td>{stats.current_amps.toFixed(3)} A</td></tr>
              <tr><td>Voltage</td><td>{stats.voltage_volts.toFixed(1)} V</td></tr>
              <tr><td>Temperature</td><td>{stats.temperature_c.toFixed(1)} °C</td></tr>
              <tr><td>Energy (last min)</td><td>{stats.last_minute_energy_use_watt_hour.toFixed(3)} Wh</td></tr>
              <tr><td>Energy (lifetime)</td><td>{stats.lifetime_energy_use_watt_hour.toFixed(3)} Wh</td></tr>
              <tr><td>Uptime</td><td>{this.formatUptime(stats.device_uptime)}</td></tr>
              <tr><td>IP</td><td>{stats.device_ip}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  render() {
    if (!this.state.devices) {
      return (<div className="app-loading">Loading...</div>);
    }

    const deviceNames = Object.keys(this.state.devices);

    return (
      <div id="ShellyPlugContainer">
        <h3 className="is-vertical-align">
          <img src="/favicon.ico" alt="Shelly Plug Monitor" style={{width: '32px', height: '32px', marginRight: '10px'}} />
          Shelly Plug Monitor
        </h3>
        {deviceNames.length === 0 ? (
          <p>No devices found</p>
        ) : (
          <div className="row">
            {deviceNames.map((name) => this.renderDevice(name, this.state.devices[name]))}
          </div>
        )}
      </div>
    );
  }
}
