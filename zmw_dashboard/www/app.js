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
    <section id="lights-section">
      <a className="section-badge" href={ProxiedServices.get('ZmwLights')}><img src="/ZmwLights/favicon.ico"/></a>
      {React.createElement(
        MqttLights,
        MqttLights.buildProps('/ZmwLights'))}
    </section>
  );
}

function SceneListSection(props) {
  return (
    <section id="scene-list-section">
      <a className="section-badge" href={ProxiedServices.get('BaticasaButtons')}><img src="/BaticasaButtons/favicon.ico"/></a>
      {React.createElement(
        ScenesList,
        { api_base_path: '/BaticasaButtons' })}
    </section>
  );
}

function SensorsListSection(props) {
  return (
    <section id="sensors-list-section">
      <a className="section-badge" href={ProxiedServices.get('ZmwSensormon')}><img src="/ZmwSensormon/favicon.ico"/></a>
      {React.createElement(
        SensorsList,
        { metrics: ['temperature'], api_base_path: '/ZmwSensormon' })}
    </section>
  );
}

function TTSAnnounceSection(props) {
  return (
    <section id="ttsannounce-section">
      <a className="section-badge" href={ProxiedServices.get('ZmwSpeakerAnnounce')}><img src="/ZmwSpeakerAnnounce/favicon.ico"/></a>
      {React.createElement(
        TTSAnnounce,
        TTSAnnounce.buildProps('/ZmwSpeakerAnnounce'))}
    </section>
  );
}

function ContactMonSection(props) {
  return (
    <section id="contactmon-section">
      <a className="section-badge" href={ProxiedServices.get('ZmwContactmon')}><img src="/ZmwContactmon/favicon.ico"/></a>
      {React.createElement(
        ContactMonitor,
        ContactMonitor.buildProps('/ZmwContactmon'))}
    </section>
  );
}

function MqttHeatingSection(props) {
  return (
    <section id="heating-section">
      <a className="section-badge" href={ProxiedServices.get('ZmwHeating')}><img src="/ZmwHeating/favicon.ico"/></a>
      {React.createElement(
        HeatingControls,
        HeatingControls.buildProps('/ZmwHeating'))}
    </section>
  );
}

function ReolinkDoorbellSection(props) {
  return (
    <section id="reolink-doorbell-section">
      <a className="section-badge" href={ProxiedServices.get('ZmwReolinkDoorbell')}><img src="/ZmwReolinkDoorbell/favicon.ico"/></a>
      {React.createElement(
        CamViewer,
        CamViewer.buildProps('/ZmwReolinkDoorbell', ProxiedServices.get('ZmwReolinkDoorbell')))}
    </section>
  );
}

function ConfigSection(props) {
  const store = React.useMemo(() => new LocalStorageManager(), []);
  const savedTheme = store.cacheGet("ZmwDashboardConfig")?.theme || "no-theme";

  const handleThemeChange = (e) => {
    const theme = e.target.value;
    document.documentElement.setAttribute('data-theme', theme);
    store.cacheSave("ZmwDashboardConfig", { theme });
  };

  const handleClearCache = () => {
    localStorage.clear();
    location.reload();
  };

  return (
    <section id="config-section">
      <img className="section-badge" src="/settings.ico"/>
      <button alt="This fixes things if something is out of sync" onClick={handleClearCache}>Clear cache</button>
      <label htmlFor="configTheme">Theme</label>
      <select id="configTheme" defaultValue={savedTheme} onChange={handleThemeChange}>
        <option value="no-theme">no theme</option>
        <option value="dark">dark</option>
        <option value="light">light</option>
        <option value="sepia">sepia</option>
        <option value="milligram">milligram</option>
        <option value="pure">pure</option>
        <option value="sakura">sakura</option>
        <option value="skeleton">skeleton</option>
        <option value="bootstrap">bootstrap</option>
        <option value="medium">medium</option>
        <option value="tufte">tufte</option>
      </select>
    </section>
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
    return <button onClick={() => window.open(btnUrl, '_blank')}>
            <img src={btnIco} alt=""/>
            {btnLbl}
          </button>
  }

  const renderIcoBtn = (sectionName, icoUrl) => {
    return <button
              data-selected={expandedSection === sectionName}
              onClick={() => toggleSection(sectionName)}
           >
              <img src={icoUrl} alt=""/>
              {sectionName}
           </button>
  }
  const renderSvcBtn =
    (sectionName, serviceName) => renderIcoBtn(sectionName, `/${serviceName}/favicon.ico`);

  return (
    <main>
      <LightsSection />
      <SceneListSection />
      <SensorsListSection />

      <section id="zmw_other_services">
        { renderSvcBtn('Announce', 'ZmwSpeakerAnnounce') }
        { renderSvcBtn('Contact', 'ZmwContactmon') }
        { renderSvcBtn('Heating', 'ZmwHeating') }
        { renderSvcBtn('Door', 'ZmwReolinkDoorbell') }
        { renderIcoBtn('⚙', '/settings.ico') }
        { /* TODO move these to a config */}
        { renderBtn("Servicemon", "http://10.0.0.10:4200/index.html", "http://10.0.0.10:4200/favicon.ico") }
        { renderBtn("Z2M", "http://10.0.0.10:4100", "/z2m.ico") }
        { renderBtn("", "http://bati.casa:5000/client_ls_txt", "/wwwslider.ico") }
        { renderBtn("", "http://bati.casa:2222/photos", "/immich.ico") }
        { renderBtn("", "https://bati.casa:8443/", "/unifi.png") }
        { renderBtn("", "http://bati.casa:8444/admin/login.php", "/pihole.svg") }
      </section>

      <div ref={contentRef}>
        {expandedSection === 'Announce' && <TTSAnnounceSection />}
        {expandedSection === 'Contact' && <ContactMonSection />}
        {expandedSection === 'Heating' && <MqttHeatingSection />}
        {expandedSection === 'Door' && <ReolinkDoorbellSection />}
        {expandedSection === '⚙' && <ConfigSection />}
      </div>
    </main>
  );
}

Dashboard.buildProps = () => ({ key: 'dashboard' });

ProxiedServices.init(() => {
  z2mStartReactApp('#app_root', Dashboard);
  const store = new LocalStorageManager();
  const opts = store.cacheGet("ZmwDashboardConfig", null);
  document.documentElement.setAttribute('data-theme', opts?.theme);
});
