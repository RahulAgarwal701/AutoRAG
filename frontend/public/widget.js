(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) return;
  var agentId = script.dataset.agentId;
  var apiUrl = (script.dataset.apiUrl || "http://localhost:8000").replace(/\/$/, "");
  if (!agentId) { console.error("AutoRAG widget: data-agent-id is required"); return; }

  var root = document.createElement("div");
  root.id = "autorag-widget-" + agentId;
  root.style.cssText = "position:fixed;z-index:2147483647;right:22px;bottom:22px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;color:#0f172a";
  var shadow = root.attachShadow({ mode: "open" });
  document.body.appendChild(root);

  shadow.innerHTML = '<style>' +
    '*{box-sizing:border-box}button,input{font:inherit}.launcher{width:58px;height:58px;border:0;border-radius:20px;background:#7c3aed;color:white;box-shadow:0 16px 40px rgba(76,29,149,.32);cursor:pointer;font-size:24px}.panel{display:none;position:absolute;right:0;bottom:72px;width:min(380px,calc(100vw - 28px));height:min(620px,calc(100vh - 110px));background:white;border:1px solid #e2e8f0;border-radius:22px;overflow:hidden;box-shadow:0 24px 70px rgba(15,23,42,.2)}.panel.open{display:flex;flex-direction:column}.head{padding:17px 18px;background:#0f172a;color:white;display:flex;align-items:center;justify-content:space-between}.name{font-weight:700}.sub{font-size:11px;color:#94a3b8;margin-top:2px}.close{border:0;background:transparent;color:white;cursor:pointer;font-size:20px}.messages{flex:1;overflow:auto;padding:16px;background:#f8fafc}.bubble{max-width:86%;padding:10px 12px;margin:0 0 12px;border-radius:15px;font-size:13px;line-height:1.55;white-space:pre-wrap}.bot{background:white;border:1px solid #e2e8f0}.user{background:#7c3aed;color:white;margin-left:auto}.sources{margin-top:8px;padding-top:8px;border-top:1px solid #e2e8f0}.sources a{display:block;color:#6d28d9;text-decoration:none;font-size:11px;margin-top:5px}.form{padding:12px;border-top:1px solid #e2e8f0;display:flex;gap:8px}.input{min-width:0;flex:1;border:1px solid #cbd5e1;border-radius:12px;padding:10px 11px;outline:none}.input:focus{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.12)}.send{width:42px;border:0;border-radius:12px;background:#7c3aed;color:white;cursor:pointer}.send:disabled{opacity:.5}.error{color:#be123c;font-size:12px;padding:8px 16px;background:#fff1f2}' +
    '@media(max-width:480px){.panel{position:fixed;inset:12px;width:auto;height:auto}.launcher{width:54px;height:54px}}' +
    '</style><div class="panel"><div class="head"><div><div class="name">AutoRAG</div><div class="sub">Grounded in your documents</div></div><button class="close" aria-label="Close">×</button></div><div class="messages"></div><div class="error" hidden></div><form class="form"><input class="input" aria-label="Message" placeholder="Ask a question…"><button class="send" aria-label="Send">↑</button></form></div><button class="launcher" aria-label="Open chat">✦</button>';

  var panel = shadow.querySelector(".panel");
  var launcher = shadow.querySelector(".launcher");
  var close = shadow.querySelector(".close");
  var messages = shadow.querySelector(".messages");
  var form = shadow.querySelector(".form");
  var input = shadow.querySelector(".input");
  var send = shadow.querySelector(".send");
  var error = shadow.querySelector(".error");
  var name = shadow.querySelector(".name");
  var token = null;
  var sessionId = null;
  var initialized = false;

  function bubble(role, content) {
    var node = document.createElement("div");
    node.className = "bubble " + role;
    node.textContent = content;
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
    return node;
  }
  function showError(message) { error.textContent = message; error.hidden = !message; }
  async function initialize() {
    if (initialized) return;
    initialized = true;
    try {
      var configResponse = await fetch(apiUrl + "/v1/agents/" + agentId + "/public-config");
      if (!configResponse.ok) throw new Error("This widget is not allowed on this website.");
      var config = await configResponse.json();
      name.textContent = config.name;
      var primary = config.theme && config.theme.primary_color;
      if (primary) { launcher.style.background = primary; send.style.background = primary; }
      bubble("bot", config.greeting);
      await renewToken();
    } catch (reason) { showError(reason.message || "Unable to load chat."); }
  }
  async function renewToken() {
    var response = await fetch(apiUrl + "/v1/agents/" + agentId + "/widget/session", { method: "POST" });
    if (!response.ok) throw new Error("Unable to start a secure chat session.");
    token = (await response.json()).token;
  }
  function parseEvents(text, onEvent) {
    text.replace(/\r\n/g, "\n").split("\n\n").forEach(function (block) {
      if (!block.trim()) return;
      var event = "message", data = [];
      block.split("\n").forEach(function (line) { if (line.indexOf("event:") === 0) event = line.slice(6).trim(); if (line.indexOf("data:") === 0) data.push(line.slice(5).trim()); });
      if (data.length) { try { onEvent(event, JSON.parse(data.join("\n"))); } catch (_) {} }
    });
  }
  async function chat(message) {
    if (!token) await renewToken();
    var response = await fetch(apiUrl + "/v1/agents/" + agentId + "/chat", {
      method: "POST", headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "text/event-stream" },
      body: JSON.stringify({ message: message, session_id: sessionId, stream: true })
    });
    if (response.status === 401) { await renewToken(); return chat(message); }
    if (!response.ok || !response.body) throw new Error("The agent could not answer right now.");
    var answer = bubble("bot", "");
    var reader = response.body.getReader(), decoder = new TextDecoder(), buffer = "";
    while (true) {
      var part = await reader.read();
      buffer += decoder.decode(part.value || new Uint8Array(), { stream: !part.done });
      var blocks = buffer.replace(/\r\n/g, "\n").split("\n\n"); buffer = blocks.pop() || "";
      parseEvents(blocks.join("\n\n"), function (event, data) {
        if (event === "session") sessionId = data.session_id;
        if (event === "token") answer.textContent += data.text;
        if (event === "citations" && data.length) { var sources = document.createElement("div"); sources.className = "sources"; data.forEach(function (item, index) { var link = document.createElement("a"); link.href = item.link; link.target = "_blank"; link.rel = "noreferrer"; link.textContent = "[" + (index + 1) + "] " + item.document + (item.page ? " · page " + item.page : ""); sources.appendChild(link); }); answer.appendChild(sources); }
        if (event === "error") showError("The agent could not complete this request.");
        messages.scrollTop = messages.scrollHeight;
      });
      if (part.done) break;
    }
  }
  launcher.addEventListener("click", function () { panel.classList.toggle("open"); if (panel.classList.contains("open")) { initialize(); setTimeout(function () { input.focus(); }, 0); } });
  close.addEventListener("click", function () { panel.classList.remove("open"); });
  form.addEventListener("submit", async function (event) { event.preventDefault(); var value = input.value.trim(); if (!value) return; input.value = ""; send.disabled = true; showError(""); bubble("user", value); try { await chat(value); } catch (reason) { showError(reason.message || "Unable to send message."); } finally { send.disabled = false; input.focus(); } });
})();
