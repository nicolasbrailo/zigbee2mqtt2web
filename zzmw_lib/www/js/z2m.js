function m$(elem) {
  return document.getElementById(elem);
}

function mAjax(cfg) {
  const req = new XMLHttpRequest();

  if (!cfg.cache && (!cfg.type || cfg.type.toLowerCase() == "get" || cfg.type.toLowerCase() == "head")) {
    const t = Date.now();
    cfg.url = (cfg.url.search('\\?') == -1) ? `${cfg.url}?_=${t}` : `${cfg.url}&_=${t}`;
  }

  req.open(cfg.type, cfg.url, /*async=*/true);

  req.onreadystatechange = () => {
    if (req.readyState == XMLHttpRequest.DONE) {
      if (req.status == 200) {
        let resp = req.responseText;
        if (cfg.dataType && cfg.dataType.toLowerCase() == 'json') {
          if (resp.trim().length == 0) {
            resp = {};
          } else {
            resp = JSON.parse(resp);
          }
        }
        // console.log(cfg.url, req, resp)
        cfg.success(resp);
      } else {
        if (req.status == 0 && req.statusText.length == 0) {
          cfg.error({
            status: 0,
            statusText: "Can't reach server",
            responseText: "Server unreachable or connection aborted",
            responseURL: req.responseUrl,
            request: req,
          });
        } else {
          cfg.error(req);
        }
      }
    }
  };


  if (cfg.type.toLowerCase() == "put") {
    if (cfg.dataType && cfg.dataType.toLowerCase() == 'json') {
      req.setRequestHeader('Content-type', 'application/json');
      let dataToSend = cfg.data;
      if (cfg.data != null) {
        if (typeof cfg.data === 'object') {
          dataToSend = JSON.stringify(cfg.data);
        } else {
          const err = `mAjax: dataType for '${cfg.url}' is JSON but data is not an object/array: ${typeof cfg.data}`;
          console.error(err, cfg);
          if (cfg.error) {
            cfg.error({
              status: 0,
              statusText: `Invalid JSON data for ${cfg.url}`,
              responseText: err,
            });
          }
          return req;
        }
      }
      req.send(dataToSend);
    } else {
      req.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
      req.send(cfg.data);
    }
  } else {
    if (cfg.data) {
      console.error("Request.data is not null for non-PUT method, not sure if valid", cfg);
    }
    req.send();
  }

  return req;
}

function mJsonGet(url, success_cb, error_cb) {
  return mAjax({
    url,
    type: 'GET',
    dataType: 'JSON',
    success: success_cb,
    error: error_cb? (e) => { error_cb; showGlobalError(e); } : showGlobalError,
  });
}

function mJsonPut(url, val, success_cb, error_cb) {
  return mAjax({
    url,
    type: 'PUT',
    dataType: 'JSON',
    data: val,
    success: success_cb || (()=>{}),
    error: error_cb? (e) => { error_cb; showGlobalError(e); } : showGlobalError,
  });
}

function z2mStartReactApp(appRootSelector, appClass, apiBasePath='') {

  const appRef = React.createRef();
  ReactDOM.createRoot(document.querySelector(appRootSelector)).render(
    React.createElement(appClass, { ...appClass.buildProps(apiBasePath), ref: appRef })
  );

  // appLoaded
  m$('global_loading').classList.add('app-finished-loading');
  m$('global_loading').classList.remove('app-loading');

  if (appClass.prototype.on_app_became_visible) {
    const app_visibility = new VisibilityCallback();
    app_visibility.app_became_visible = () => {
      console.log("App became visible, will refresh state")
      appRef.current.on_app_became_visible();
    }
  }
}

const showGlobalError = (msg) => {
  if (typeof(msg) == "string") {
    m$('global_error_msg').innerText = msg;
  } else if (typeof(msg) == "object" && msg.responseText || msg.status || msg.statusText) {
    // Probably an ajax response object
    const stat = `Error ${msg.status||'???'}: ${msg.statusText||'unknown'}`;
    m$('global_error_msg').innerText = `${stat} \n\n ${msg.responseText||''}`;
  } else {
    m$('global_error_msg').innerText = msg;
  }
  m$('global_error_ui').classList.remove('no-error');
};

if (m$('global_error_ui_ack')) {
  m$('global_error_ui_ack').onclick = () => {
    m$('global_error_msg').innerText = '';
    m$('global_error_ui').classList.add('no-error');
  };
}
