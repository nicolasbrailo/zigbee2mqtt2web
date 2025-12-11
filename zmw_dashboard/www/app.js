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
        MqttLights.buildProps('/zmw_lights'))}
      <a href={ProxiedServices.get('zmw_lights')}><img src="/zmw_lights/favicon.ico"/></a>
    </div>
  );
}

function SpeakersSection(props) {
  return (
    <div className="dashboard-section" id="speakers-section">
      <a href={ProxiedServices.get('zmw_speaker_announce')}><img src="/zmw_speaker_announce/favicon.ico"/></a>
      {React.createElement(
        TTSAnnounce,
        TTSAnnounce.buildProps('/zmw_speaker_announce'))}
    </div>
  );
}

function ContactMonSection(props) {
  return (
    <div className="dashboard-section" id="contactmon-section">
      <a href={ProxiedServices.get('zmw_contactmon')}><img src="/zmw_contactmon/favicon.ico"/></a>
      {React.createElement(
        ContactMonitor,
        ContactMonitor.buildProps('/zmw_contactmon'))}
    </div>
  );
}

function MqttHeatingSection(props) {
  return (
    <div className="dashboard-section" id="heating-section">
      <h2><a href={ProxiedServices.get('zmw_heating')}><img src="/zmw_heating/favicon.ico"/></a>Heating</h2>
      {React.createElement(
        HeatingControls,
        HeatingControls.buildProps('/zmw_heating'))}
    </div>
  );
}

function ReolinkDoorbellSection(props) {
  return (
    <div className="dashboard-section" id="reolink-doorbell-section">
      <a href={ProxiedServices.get('zmw_reolink_doorbell')}><img src="/zmw_reolink_doorbell/favicon.ico"/></a>
      {React.createElement(
        CamViewer,
        CamViewer.buildProps('/zmw_reolink_doorbell', ProxiedServices.get('zmw_reolink_doorbell')))}
    </div>
  );
}

function SensorsListSection(props) {
  return (
    <div className="dashboard-section" id="sensors-list-section" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <a href={ProxiedServices.get('zmw_sensormon')}>
        <img src="/zmw_sensormon/favicon.ico"/>
      </a>
      {React.createElement(
        SensorsList,
        { metrics: ['temperature'], api_base_path: '/zmw_sensormon' })}
    </div>
  );
}

function SceneListSection(props) {
  return (
    <div className="dashboard-section" id="scene-list-section" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <a href={ProxiedServices.get('baticasa_buttons')}>
        <img src="/baticasa_buttons/favicon.ico"/>
      </a>
      {React.createElement(
        ScenesList,
        { api_base_path: '/baticasa_buttons' })}
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
          { renderSvcBtn('Announce', 'zmw_speaker_announce') }
          { renderSvcBtn('Contact', 'zmw_contactmon') }
          { renderSvcBtn('Heating', 'zmw_heating') }
          { renderSvcBtn('Door', 'zmw_reolink_doorbell') }
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
