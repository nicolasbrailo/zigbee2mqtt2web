class VisibilityCallback {
  constructor(cb, intervalMs) {
    this.install_visibility_callback();
  }

  app_became_hidden() {
  }

  app_became_visible() {
  }

  static warn_if_visibility_not_supported(visChangeAction) {
    if (this.visibility_checked !== undefined) return;
    this.visibility_checked = true;
    if (visChangeAction === undefined) {
      console.log("Visibility changes not supported: UI elements won't auto-refresh");
    }
  }

  install_visibility_callback() {
    if (this.vis_cb_installed !== undefined) return;
    this.vis_cb_installed = true;

    var hidden, visChangeAction;
    if (typeof document.hidden !== "undefined") { // Opera 12.10 and Firefox 18 and later support
        hidden = "hidden";
        visChangeAction = "visibilitychange";
    } else if (typeof document.msHidden !== "undefined") {
        hidden = "msHidden";
        visChangeAction = "msvisibilitychange";
    } else if (typeof document.webkitHidden !== "undefined") {
        hidden = "webkitHidden";
        visChangeAction = "webkitvisibilitychange";
    }

    VisibilityCallback.warn_if_visibility_not_supported(visChangeAction);
    if (visChangeAction !== undefined) {
      document.addEventListener(visChangeAction, () => {
        const app_hidden = document[hidden];
        app_hidden? this.app_became_hidden() : this.app_became_visible();
      });
    }
  }
};
