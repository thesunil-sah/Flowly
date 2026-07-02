// Flowly tracker — vanilla JS, zero runtime dependencies.
//
// Install on any page:
//   <script defer src="https://your-host/script.js" data-site="YOUR_SITE_ID"></script>
//
// Fires a pageview to {origin}/collect via navigator.sendBeacon. It must NEVER
// throw and NEVER break the host page — every path is wrapped and fails silently.
(function () {
  "use strict";
  try {
    // Capture the script element ONCE. document.currentScript is only valid during
    // this initial synchronous run — it is null inside the async SPA callbacks
    // below — so read every attribute we need right now.
    var el = document.currentScript || document.querySelector("script[data-site]");
    if (!el) return;

    var siteId = el.getAttribute("data-site");
    if (!siteId) return; // no site → do nothing

    // Endpoint: an explicit data-api override, else the origin the script itself
    // was served from. The ingestion path is {base}/collect.
    var base = el.getAttribute("data-api") || new URL(el.src).origin;
    var endpoint = base.replace(/\/+$/, "") + "/collect";

    var lastPath = null; // same-path dedupe guard

    function param(params, key) {
      var v = params.get(key);
      return v ? v : null;
    }

    function send(body) {
      // A text/plain body keeps the beacon a CORS-safelisted "simple request"
      // (no preflight). The server reads the raw body and parses it as JSON.
      try {
        if (navigator.sendBeacon) {
          var blob = new Blob([body], { type: "text/plain" });
          if (navigator.sendBeacon(endpoint, blob)) return;
        }
      } catch (_) {
        /* fall through to fetch */
      }
      // Fallback when sendBeacon is missing or refused the payload.
      try {
        fetch(endpoint, {
          method: "POST",
          body: body,
          keepalive: true,
          mode: "no-cors",
          headers: { "Content-Type": "text/plain" },
        });
      } catch (_) {
        /* fail silently */
      }
    }

    function track() {
      try {
        var path = location.pathname; // NO query string (may carry PII)
        if (path === lastPath) return; // dedupe repeated navigations to the same path
        lastPath = path;

        var params = new URLSearchParams(location.search);
        send(
          JSON.stringify({
            site_id: siteId,
            path: path,
            referrer: document.referrer,
            screen_w: screen.width,
            utm_source: param(params, "utm_source"),
            utm_medium: param(params, "utm_medium"),
            utm_campaign: param(params, "utm_campaign"),
          }),
        );
      } catch (_) {
        /* fail silently */
      }
    }

    // SPA support: fire on client-side navigations. Wrap the history methods so a
    // host-page error can never surface through our patch.
    function patch(name) {
      var orig = history[name];
      if (typeof orig !== "function") return;
      history[name] = function () {
        var ret = orig.apply(this, arguments);
        try {
          track();
        } catch (_) {
          /* fail silently */
        }
        return ret;
      };
    }
    patch("pushState");
    patch("replaceState");
    window.addEventListener("popstate", track);

    track(); // initial pageview
  } catch (_) {
    /* fail silently — never break the host page */
  }
})();
