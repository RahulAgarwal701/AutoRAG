(function () {
  "use strict";

  var script = document.currentScript;
  if (!script || script.dataset.autoragLoaded === "true") return;
  script.dataset.autoragLoaded = "true";

  var agentId = script.dataset.agentId;
  if (!agentId) {
    console.error("AutoRAG widget: data-agent-id is required");
    return;
  }

  var appOrigin;
  try {
    appOrigin = new URL(script.src).origin;
  } catch {
    console.error("AutoRAG widget: widget.js must be loaded from an absolute URL");
    return;
  }

  var root = document.createElement("div");
  root.id = "autorag-widget-" + agentId;
  root.style.cssText = "position:fixed;right:20px;bottom:20px;z-index:2147483647";
  var shadow = root.attachShadow({ mode: "open" });
  shadow.innerHTML =
    '<style>*{box-sizing:border-box}.launcher{display:grid;place-items:center;width:58px;height:58px;border:0;border-radius:20px;background:#7c3aed;color:#fff;box-shadow:0 16px 40px rgba(76,29,149,.3);cursor:pointer;font:700 24px/1 system-ui;transition:transform .18s,box-shadow .18s}.launcher:hover{transform:translateY(-2px);box-shadow:0 20px 45px rgba(76,29,149,.36)}.frame{display:none;width:380px;height:620px;max-width:calc(100vw - 28px);max-height:calc(100vh - 104px);margin-bottom:12px;border:0;border-radius:22px;background:#fff;box-shadow:0 24px 70px rgba(15,23,42,.24)}.open .frame{display:block}.open .launcher{display:none}@media(max-width:480px){:host{right:12px!important;bottom:12px!important}.frame{width:calc(100vw - 24px);height:calc(100vh - 24px);max-width:none;max-height:none;margin:0;border-radius:18px}}</style>' +
    '<div class="shell"><iframe class="frame" title="AutoRAG chat" allow="clipboard-write"></iframe><button class="launcher" type="button" aria-label="Open chat">✦</button></div>';
  (document.body || document.documentElement).appendChild(root);

  var shell = shadow.querySelector(".shell");
  var frame = shadow.querySelector(".frame");
  var launcher = shadow.querySelector(".launcher");
  var initialized = false;
  var opening = false;
  var sessionPayload = null;

  function setPosition(position) {
    root.style.left = position === "bottom-left" ? "20px" : "auto";
    root.style.right = position === "bottom-left" ? "auto" : "20px";
  }

  function applyConfig(config) {
    var theme = config && config.theme ? config.theme : {};
    if (theme.primary_color) launcher.style.background = theme.primary_color;
    setPosition(theme.position);
  }

  async function createSession() {
    var response = await fetch(
      appOrigin + "/api/widget/" + encodeURIComponent(agentId) + "/session",
      { method: "POST", mode: "cors", credentials: "omit", cache: "no-store" }
    );
    var payload = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      throw new Error(payload.error && payload.error.message || "This widget is not allowed on this website.");
    }
    sessionPayload = payload;
    applyConfig(payload.config);
    return payload;
  }

  function sendInit() {
    if (!sessionPayload || !frame.contentWindow) return;
    frame.contentWindow.postMessage({
      type: "autorag:init",
      agentId: agentId,
      parentOrigin: window.location.origin,
      token: sessionPayload.token,
      expiresIn: sessionPayload.expires_in,
      config: sessionPayload.config
    }, appOrigin);
  }

  function sendOpen() {
    if (frame.contentWindow) {
      frame.contentWindow.postMessage({ type: "autorag:open" }, appOrigin);
    }
  }

  async function openWidget() {
    if (opening) return;
    opening = true;
    launcher.disabled = true;
    try {
      if (!initialized) {
        await createSession();
        frame.src = appOrigin + "/embed/" + encodeURIComponent(agentId);
        initialized = true;
      }
      shell.classList.add("open");
      launcher.setAttribute("aria-expanded", "true");
      sendInit();
      sendOpen();
    } catch (error) {
      console.error("AutoRAG widget:", error);
      launcher.title = error instanceof Error ? error.message : "Unable to open chat";
    } finally {
      launcher.disabled = false;
      opening = false;
    }
  }

  function closeWidget() {
    shell.classList.remove("open");
    launcher.setAttribute("aria-expanded", "false");
    launcher.focus();
  }

  launcher.addEventListener("click", openWidget);
  window.addEventListener("message", function (event) {
    if (event.origin !== appOrigin || event.source !== frame.contentWindow || !event.data) return;
    if (event.data.type === "autorag:ready") { sendInit(); sendOpen(); }
    if (event.data.type === "autorag:close") closeWidget();
    if (event.data.type === "autorag:open") openWidget();
    if (event.data.type === "autorag:resize") {
      var width = Math.max(300, Math.min(480, Number(event.data.width) || 380));
      var height = Math.max(360, Math.min(760, Number(event.data.height) || 620));
      frame.style.width = width + "px";
      frame.style.height = height + "px";
    }
    if (event.data.type === "autorag:refresh-session") {
      createSession().then(sendInit).catch(function (error) {
        frame.contentWindow.postMessage({ type: "autorag:error", message: error.message }, appOrigin);
      });
    }
  });
})();
