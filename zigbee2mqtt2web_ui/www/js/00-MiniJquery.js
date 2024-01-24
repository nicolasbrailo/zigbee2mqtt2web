// jQuery was a significant % of app size, and we only need a few functions, so
// this is an incomplete reimplementation of those functions that somewhat
// mimics the interface (but some behaviour may be different - only what this
// app uses is supported)

function m$(elem) {
  return document.getElementById(elem);
}

function mDeferred() {
  const self = (this == undefined)? window : this;

  const trampoline = {
    _cbSet: (resolve, reject) => {
      trampoline.resolve = resolve;
      trampoline.reject = reject;
    },
  };

  const p = new Promise((resolve, reject) => {
    trampoline._cbSet(resolve, reject);
  });

  p.resolve = (...args) => { return trampoline.resolve.apply(self, args); }
  p.reject = (...args) => { return trampoline.reject.apply(self, args); }

  return p;
}

function mAjax(cfg) {
  const req = new XMLHttpRequest();

  if (!cfg.cache && (cfg.type.toLowerCase() == "get" || cfg.type.toLowerCase() == "head")) {
    const t = Date.now();
    cfg.url = (cfg.url.search('\\?') == -1) ? `${cfg.url}?_=${t}` : `${cfg.url}&_=${t}`;
  }

  req.open(cfg.type, cfg.url, /*async=*/true);

  req.onreadystatechange = () => {
    if (req.readyState == XMLHttpRequest.DONE) {
      if (req.status == 200) {
        let resp = req.responseText;
        if (cfg.dataType.toLowerCase() == 'json') {
          if (resp.trim().length == 0) {
            resp = {};
          } else {
            resp = JSON.parse(resp);
          }
        }
        // console.log(cfg.url, req, resp)
        cfg.success(resp);
      } else {
        cfg.error(req);
      }
    }
  };


  if (cfg.type.toLowerCase() == "put") {
    req.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
    req.send(cfg.data);
  } else {
    if (cfg.data) {
      console.warning("Request.data is not null for non-PUT method, not sure if valid", cfg);
    }
    req.send();
  }

  return req;
}

