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
    <div className="dashboard-section" id="lights-section">
      {React.createElement(
        MqttLights,
        MqttLights.buildProps('/ZmwLights'))}
      <a href={ProxiedServices.get('ZmwLights')}><img src="/ZmwLights/favicon.ico"/></a>
    </div>
  );
}

function SpeakersSection(props) {
  return (
    <div className="dashboard-section" id="speakers-section">
      <a href={ProxiedServices.get('ZmwSpeakerAnnounce')}><img src="/ZmwSpeakerAnnounce/favicon.ico"/></a>
      {React.createElement(
        TTSAnnounce,
        TTSAnnounce.buildProps('/ZmwSpeakerAnnounce'))}
    </div>
  );
}

function ContactMonSection(props) {
  return (
    <div className="dashboard-section" id="contactmon-section">
      <a href={ProxiedServices.get('ZmwContactmon')}><img src="/ZmwContactmon/favicon.ico"/></a>
      {React.createElement(
        ContactMonitor,
        ContactMonitor.buildProps('/ZmwContactmon'))}
    </div>
  );
}

function MqttHeatingSection(props) {
  return (
    <div className="dashboard-section" id="heating-section">
      <h2><a href={ProxiedServices.get('ZmwHeating')}><img src="/ZmwHeating/favicon.ico"/></a>Heating</h2>
      {React.createElement(
        HeatingControls,
        HeatingControls.buildProps('/ZmwHeating'))}
    </div>
  );
}

function ReolinkDoorbellSection(props) {
  return (
    <div className="dashboard-section" id="reolink-doorbell-section">
      <a href={ProxiedServices.get('ZmwReolinkDoorbell')}><img src="/ZmwReolinkDoorbell/favicon.ico"/></a>
      {React.createElement(
        CamViewer,
        CamViewer.buildProps('/ZmwReolinkDoorbell', ProxiedServices.get('ZmwReolinkDoorbell')))}
    </div>
  );
}

function SensorsListSection(props) {
  return (
    <div className="dashboard-section" id="sensors-list-section" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <a href={ProxiedServices.get('ZmwSensormon')}>
        <img src="/ZmwSensormon/favicon.ico"/>
      </a>
      {React.createElement(
        SensorsList,
        { metrics: ['temperature'], api_base_path: '/ZmwSensormon' })}
    </div>
  );
}

function SceneListSection(props) {
  return (
    <div className="dashboard-section" id="scene-list-section" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <a href={ProxiedServices.get('BaticasaButtons')}>
        <img src="/BaticasaButtons/favicon.ico"/>
      </a>
      {React.createElement(
        ScenesList,
        { api_base_path: '/BaticasaButtons' })}
    </div>
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
    return <button
            className="modal-button primary"
            onClick={() => window.open(btnUrl, '_blank')}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <img src={btnIco} alt="" style={{ width: '20px', height: '20px' }} />
            {btnLbl}
          </button>
  }

  const renderSvcBtn = (sectionName, serviceName) => {
    return <button
              className={expandedSection === sectionName ? 'modal-button primary bg-dark' : 'modal-button'}
              onClick={() => toggleSection(sectionName)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
           >
              <img src={`/${serviceName}/favicon.ico`} alt="" style={{ width: '20px', height: '20px' }} />
              {sectionName}
           </button>
  }

  return (
    <div>
      <div className="dashboard-sections">
        <LightsSection />
        <SceneListSection />
        <SensorsListSection />

        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
          { renderSvcBtn('Announce', 'ZmwSpeakerAnnounce') }
          { renderSvcBtn('Contact', 'ZmwContactmon') }
          { renderSvcBtn('Heating', 'ZmwHeating') }
          { renderSvcBtn('Door', 'ZmwReolinkDoorbell') }
          { /* TODO move these to a config */}
          { renderBtn("Baticasa Services", "http://10.0.0.10:4200/index.html", "http://10.0.0.10:4200/favicon.ico") }
          { renderBtn("Z2M", "http://10.0.0.10:4100", "/z2m.ico") }
          { renderBtn("", "http://bati.casa:5000/client_ls_txt", "/wwwslider.ico") }
          { renderBtn("", "http://bati.casa:2222/photos", "/immich.ico") }
          { renderBtn("", "https://bati.casa:8443/", "/unifi.png") }
          { renderBtn("", "http://bati.casa:8444/admin/login.php", "/pihole.svg") }
        </div>

        <div ref={contentRef}>
          {expandedSection === 'Announce' && <SpeakersSection />}
          {expandedSection === 'Contact' && <ContactMonSection />}
          {expandedSection === 'Heating' && <MqttHeatingSection />}
          {expandedSection === 'Door' && <ReolinkDoorbellSection />}
        </div>
      </div>
    </div>
  );
}

Dashboard.buildProps = () => ({ key: 'dashboard' });

ProxiedServices.init(() => {
  z2mStartReactApp('#app_root', Dashboard);
});
