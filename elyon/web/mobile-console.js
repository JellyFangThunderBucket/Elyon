import { THEMES, applyTheme } from "./themes.js";

const DEFAULTS = {
  theme: "basalt-circuit",
  fontSize: 13,
  height: 62,
  opacity: 1,
  wrap: true,
  timestamps: true,
  autoScroll: true,
  console: true,
  errors: true,
  network: true,
  autoOpenError: false,
  jsExecution: true,
  maxRows: 500,
};
const KEY = "elyon.mobile.settings.v1";
export function createConsole() {
  if (window.elyonConsole) return window.elyonConsole;
  let settings = { ...DEFAULTS };
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
    for (const key of Object.keys(DEFAULTS))
      if (typeof saved[key] === typeof DEFAULTS[key])
        settings[key] = saved[key];
  } catch {
    /* Storage can be blocked by the inspected page. */
  }
  settings.fontSize = Math.max(11, Math.min(20, settings.fontSize));
  settings.height = Math.max(30, Math.min(100, settings.height));
  settings.opacity = Math.max(0.85, Math.min(1, settings.opacity));
  settings.maxRows = [100, 500, 1000, 2000].includes(settings.maxRows)
    ? settings.maxRows
    : 500;
  const host = document.createElement("div");
  host.id = "elyon-console";
  host.style.cssText =
    "position:fixed;inset:0;pointer-events:none;z-index:2147483647";
  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = new URL("./mobile-console.css", import.meta.url).href;
  root.append(style);
  const shell = document.createElement("div");
  shell.className = "elyon-shell";
  shell.innerHTML = `
  <button class="launcher" aria-label="Open Elyon console">E_</button>
  <section class="console" aria-label="Elyon developer console" hidden>
   <header><b>ELYON<span> / PAGE CONSOLE</span></b><div><button id="export">Export redacted</button><button id="close" aria-label="Minimize console">−</button></div></header>
   <nav aria-label="Console panels" role="tablist"><div class="scroll-tabs"><button role="tab" data-tab="console">Console</button><button role="tab" data-tab="network">Network</button><button role="tab" data-tab="elements">Elements</button><button role="tab" data-tab="storage">Storage</button><button role="tab" data-tab="info">Info</button></div><button role="tab" data-tab="settings" id="settings-tab">⚙ Settings</button></nav>
   <div class="panel" id="console-panel" role="tabpanel"><div class="toolbar"><select id="level" aria-label="Log level"><option value="">All levels</option><option>log</option><option>info</option><option>warn</option><option>error</option><option>debug</option><option>result</option></select><input id="log-search" placeholder="Filter logs" aria-label="Filter console logs"><button id="clear">Clear view</button></div><div id="logs" class="rows" role="log" aria-label="Console output"></div><form id="repl"><label for="expression">❯</label><input id="expression" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="JavaScript in this page" aria-label="JavaScript expression"><button>Run</button></form></div>
   <div class="panel" id="network-panel" role="tabpanel" hidden><div class="toolbar"><span>Fetch + XHR · metadata only</span><button id="clear-network">Clear view</button></div><div class="rows" id="requests"></div></div>
   <div class="panel" id="elements-panel" role="tabpanel" hidden><form id="selector-form" class="toolbar"><input id="selector" value="body" aria-label="CSS selector"><button>Inspect</button><button type="button" id="highlight">Highlight</button></form><div class="rows"><p id="element-summary"></p><pre id="element-output"></pre></div></div>
   <div class="panel" id="storage-panel" role="tabpanel" hidden><div class="toolbar"><select id="storage-type" aria-label="Storage type"><option value="localStorage">Local storage</option><option value="sessionStorage">Session storage</option></select><button id="refresh-storage">Refresh</button></div><div id="storage-output" class="rows"></div></div>
   <div class="panel" id="info-panel" role="tabpanel" hidden><div class="rows"><h2>Current page</h2><pre id="page-info"></pre><p>This console runs inside this page. It shares the page’s JavaScript thread and cannot stay responsive during a page stall. Use the independent Elyon broker for durable browser evidence.</p><p>Gecko and native iOS bridges are research work, not enabled capabilities.</p></div></div>
   <div class="panel" id="settings-panel" role="tabpanel" hidden><div class="rows settings"><div class="section-title">APPEARANCE <span>20 ORIGINAL PALETTES</span></div><div id="themes" class="themes" aria-label="Color themes"></div><div id="settings-controls"></div><button id="reset">Restore Elyon defaults</button><p id="save-state" role="status">Preferences are stored on this origin.</p><p>Only Elyon preferences are reset. Page storage and recorded broker evidence are never cleared here.</p></div></div>
   <footer><span id="session-state">PAGE INSTRUMENTATION</span><span id="row-count">0 logs</span></footer>
  </section>`;
  root.append(shell);
  document.documentElement.append(host);
  const $ = (q) => root.querySelector(q);
  const $$ = (q) => [...root.querySelectorAll(q)];
  let logs = [],
    requests = [],
    tab = "console",
    destroyed = false,
    selected = null,
    renderPending = false;
  const cleanups = [];
  const timers = new Set();
  const originalConsole = new Map();
  function preview(value) {
    try {
      if (typeof value === "string") return value.slice(0, 10000);
      if (value instanceof Error)
        return `${value.name}: ${value.message}\n${value.stack || ""}`.slice(
          0,
          10000,
        );
      if (typeof value === "object" && value !== null) {
        const descriptors = Object.getOwnPropertyDescriptors(value);
        return (
          (Array.isArray(value) ? "[" : "{") +
          Object.entries(descriptors)
            .slice(0, 25)
            .map(
              ([k, d]) =>
                `${k}: ${"value" in d ? (typeof d.value === "object" && d.value !== null ? "[object]" : String(d.value).slice(0, 500)) : "[getter not invoked]"}`,
            )
            .join(", ") +
          (Array.isArray(value) ? "]" : "}")
        );
      }
      return String(value).slice(0, 10000);
    } catch {
      return "[Uninspectable value]";
    }
  }
  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(settings));
      $("#save-state").textContent = "Preferences saved on this origin.";
    } catch {
      $("#save-state").textContent =
        "Storage unavailable; preferences last for this session.";
    }
  }
  function apply() {
    const theme = applyTheme(shell, settings.theme);
    settings.theme = theme.id;
    shell.style.setProperty("--font-size", settings.fontSize + "px");
    shell.style.setProperty("--height", settings.height + "dvh");
    shell.style.setProperty("--opacity", settings.opacity);
    shell.classList.toggle("wrap", settings.wrap);
    $$("[data-theme]").forEach((b) =>
      b.setAttribute(
        "aria-pressed",
        String(b.dataset.theme === settings.theme),
      ),
    );
    $$("[data-setting]").forEach((i) => {
      const key = i.dataset.setting;
      if (i.type === "checkbox") i.checked = settings[key];
      else i.value = settings[key];
      const out = $(`#value-${key}`);
      if (out) out.textContent = settings[key];
    });
    $("#expression").disabled = !settings.jsExecution;
    $("#expression").placeholder = settings.jsExecution
      ? "JavaScript in this page"
      : "JavaScript execution disabled in Settings";
    logs = logs.slice(-settings.maxRows);
    requests = requests.slice(-settings.maxRows);
    schedule();
  }
  function open() {
    $(".console").hidden = false;
    $(".launcher").hidden = true;
  }
  function close() {
    $(".console").hidden = true;
    $(".launcher").hidden = false;
  }
  function activate(name) {
    tab = name;
    $$('[role="tab"]').forEach((b) => {
      const active = b.dataset.tab === name;
      b.setAttribute("aria-selected", String(active));
      b.tabIndex = active ? 0 : -1;
    });
    $$(".panel").forEach((p) => (p.hidden = p.id !== `${name}-panel`));
    if (name === "storage") storage();
    if (name === "info") info();
    if (name === "elements") inspect();
    schedule();
  }
  function schedule() {
    if (renderPending || destroyed) return;
    renderPending = true;
    requestAnimationFrame(() => {
      renderPending = false;
      if (!destroyed) render();
    });
  }
  function add(level, args) {
    if (destroyed) return;
    logs.push({
      id: crypto.randomUUID?.() || String(Math.random()),
      time: Date.now(),
      level,
      text: args.map(preview).join(" "),
    });
    logs = logs.slice(-settings.maxRows);
    if (level === "error" && settings.autoOpenError) {
      open();
      activate("console");
    }
    schedule();
  }
  function render() {
    const q = $("#log-search").value.toLowerCase(),
      level = $("#level").value;
    const rows = logs.filter(
      (l) => (!level || l.level === level) && l.text.toLowerCase().includes(q),
    );
    $("#logs").replaceChildren();
    for (const l of rows.slice(-250)) {
      const row = document.createElement("div");
      row.className = `row level-${l.level}`;
      if (settings.timestamps) {
        const time = document.createElement("time");
        time.textContent = new Date(l.time).toLocaleTimeString();
        row.append(time);
      }
      const badge = document.createElement("span");
      badge.className = "level";
      badge.textContent = l.level;
      const text = document.createElement("pre");
      text.textContent = l.text;
      row.append(badge, text);
      $("#logs").append(row);
    }
    if (!rows.length) {
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent =
        "No matching logs. Use the page or run a JavaScript expression.";
      $("#logs").append(p);
    }
    $("#requests").replaceChildren();
    for (const n of requests.slice(-250)) {
      const row = document.createElement("details");
      row.className = "request";
      const summary = document.createElement("summary");
      summary.textContent = `${n.method}  ${n.status ?? "pending"}  ${n.duration === null ? "…" : n.duration.toFixed(1) + " ms"}  ${n.url}`;
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(n, null, 2);
      row.append(summary, pre);
      $("#requests").append(row);
    }
    if (!requests.length)
      $("#requests").textContent =
        "No requests captured yet. Fetch a response from the playground.";
    $("#row-count").textContent =
      `${logs.length} logs · ${requests.length} requests · view ≤250`;
    if (settings.autoScroll && tab === "console")
      $("#logs").scrollTop = $("#logs").scrollHeight;
  }
  for (const level of [
    "log",
    "info",
    "warn",
    "error",
    "debug",
    "table",
    "dir",
    "trace",
    "assert",
  ]) {
    const original = console[level];
    if (typeof original !== "function") continue;
    const wrapped = function (...args) {
      Reflect.apply(original, console, args);
      if (destroyed || !settings.console) return;
      if (level === "assert") {
        if (!args[0]) add("error", args.slice(1));
        return;
      }
      add(level, args);
    };
    originalConsole.set(level, { original, wrapped });
    console[level] = wrapped;
  }
  const errorListener = (e) => {
    if (settings.errors)
      add("error", [e.error || e.message || "Resource load error"]);
  };
  const rejectionListener = (e) => {
    if (settings.errors) add("error", ["Unhandled rejection:", e.reason]);
  };
  window.addEventListener("error", errorListener);
  window.addEventListener("unhandledrejection", rejectionListener);
  cleanups.push(
    () => window.removeEventListener("error", errorListener),
    () => window.removeEventListener("unhandledrejection", rejectionListener),
  );
  function begin(method, url, kind) {
    if (destroyed || !settings.network) return null;
    const row = {
      id: crypto.randomUUID?.() || String(Math.random()),
      kind,
      method: String(method).slice(0, 32),
      url: String(url).slice(0, 4000),
      status: null,
      duration: null,
      started: Date.now(),
    };
    requests.push(row);
    requests = requests.slice(-settings.maxRows);
    schedule();
    return row;
  }
  function finish(row, status, error) {
    if (!row || destroyed) return;
    row.status = status;
    row.duration = Date.now() - row.started;
    if (error) row.error = preview(error);
    schedule();
  }
  const originalFetch = window.fetch;
  const wrappedFetch = function (...args) {
    let row = null;
    try {
      const [input, init] = args;
      row = begin(
        init?.method || (input instanceof Request ? input.method : "GET"),
        input instanceof Request ? input.url : String(input),
        "fetch",
      );
    } catch {}
    let result;
    try {
      result = Reflect.apply(originalFetch, this, args);
    } catch (error) {
      finish(row, "failed", error);
      throw error;
    }
    return result.then(
      (response) => {
        finish(row, response.status);
        return response;
      },
      (error) => {
        finish(row, "failed", error);
        throw error;
      },
    );
  };
  if (originalFetch) window.fetch = wrappedFetch;
  cleanups.push(() => {
    if (window.fetch === wrappedFetch) window.fetch = originalFetch;
  });
  const xhrOpen = XMLHttpRequest.prototype.open,
    xhrSend = XMLHttpRequest.prototype.send,
    xhrMeta = new WeakMap();
  function openXHR(method, url, ...rest) {
    const result = Reflect.apply(xhrOpen, this, [method, url, ...rest]);
    xhrMeta.set(this, { method, url });
    return result;
  }
  function sendXHR(...args) {
    const meta = xhrMeta.get(this);
    let row = null;
    try {
      if (meta) row = begin(meta.method, meta.url, "xhr");
    } catch {}
    this.addEventListener("loadend", () => finish(row, this.status), {
      once: true,
    });
    try {
      return Reflect.apply(xhrSend, this, args);
    } catch (error) {
      finish(row, "failed", error);
      throw error;
    }
  }
  XMLHttpRequest.prototype.open = openXHR;
  XMLHttpRequest.prototype.send = sendXHR;
  cleanups.push(() => {
    if (XMLHttpRequest.prototype.open === openXHR)
      XMLHttpRequest.prototype.open = xhrOpen;
    if (XMLHttpRequest.prototype.send === sendXHR)
      XMLHttpRequest.prototype.send = xhrSend;
  });
  function inspect() {
    try {
      selected = document.querySelector($("#selector").value);
      $("#element-summary").textContent = selected
        ? `${selected.tagName.toLowerCase()} · ${selected.childElementCount} child elements`
        : "No matching element";
      $("#element-output").textContent = selected
        ? selected.outerHTML.slice(0, 30000)
        : "";
    } catch (error) {
      $("#element-summary").textContent = preview(error);
      $("#element-output").textContent = "";
    }
  }
  function storage() {
    const out = $("#storage-output");
    out.replaceChildren();
    try {
      const store = window[$("#storage-type").value];
      for (let i = 0; i < store.length; i++) {
        const key = store.key(i);
        const row = document.createElement("div");
        row.className = "storage-row";
        const title = document.createElement("b");
        title.textContent = key;
        const value = document.createElement("pre");
        value.textContent = store.getItem(key)?.slice(0, 10000);
        row.append(title, value);
        out.append(row);
      }
      if (!store.length) out.textContent = "No stored values on this origin.";
    } catch (error) {
      out.textContent = "Storage unavailable: " + preview(error);
    }
  }
  function info() {
    $("#page-info").textContent = JSON.stringify(
      {
        url: location.href,
        userAgent: navigator.userAgent,
        viewport: {
          width: innerWidth,
          height: innerHeight,
          dpr: devicePixelRatio,
        },
        online: navigator.onLine,
        secureContext: isSecureContext,
        timeOrigin: performance.timeOrigin,
        source: "page-instrumentation",
        nativeBridge: false,
      },
      null,
      2,
    );
  }
  for (const theme of THEMES) {
    const b = document.createElement("button");
    b.dataset.theme = theme.id;
    b.setAttribute("aria-label", theme.name);
    b.innerHTML =
      '<span class="swatches"></span><span class="theme-name"></span>';
    b.querySelector(".theme-name").textContent = theme.name;
    for (const color of [
      theme.tokens.bg,
      theme.tokens.surface,
      theme.tokens.accent,
    ]) {
      const swatch = document.createElement("i");
      swatch.style.background = color;
      b.querySelector(".swatches").append(swatch);
    }
    b.onclick = () => {
      settings.theme = theme.id;
      apply();
      save();
    };
    $("#themes").append(b);
  }
  const controls = [
    ["fontSize", "Text size", "range", 11, 20, 1],
    ["height", "Console height (%)", "range", 30, 100, 1],
    ["opacity", "Opacity", "range", 0.85, 1, 0.01],
    ["wrap", "Wrap long lines", "checkbox"],
    ["timestamps", "Show timestamps", "checkbox"],
    ["autoScroll", "Follow new logs", "checkbox"],
    ["console", "Capture console methods", "checkbox"],
    ["errors", "Catch errors and rejections", "checkbox"],
    ["autoOpenError", "Open console on error", "checkbox"],
    ["network", "Capture Fetch and XHR metadata", "checkbox"],
    ["jsExecution", "Enable JavaScript execution", "checkbox"],
    ["maxRows", "Maximum retained rows", "select"],
  ];
  for (const [key, label, type, min, max, step] of controls) {
    const row = document.createElement("label");
    row.className = "setting-row";
    const span = document.createElement("span");
    span.textContent = label;
    let input = document.createElement(type === "select" ? "select" : "input");
    if (type === "select")
      for (const n of [100, 500, 1000, 2000]) {
        const o = document.createElement("option");
        o.value = n;
        o.textContent = n;
        input.append(o);
      }
    else {
      input.type = type;
      if (type === "range") {
        input.min = min;
        input.max = max;
        input.step = step;
      }
    }
    input.dataset.setting = key;
    input.id = "setting-" + key;
    row.htmlFor = input.id;
    const value = document.createElement("output");
    value.id = "value-" + key;
    if (type === "checkbox") value.hidden = true;
    input.oninput = () => {
      settings[key] = type === "checkbox" ? input.checked : Number(input.value);
      apply();
      save();
    };
    row.append(span, value, input);
    $("#settings-controls").append(row);
  }
  $$("[data-tab]").forEach((button) => {
    button.id = `tab-${button.dataset.tab}`;
    button.setAttribute("aria-controls", `${button.dataset.tab}-panel`);
    $(`#${button.dataset.tab}-panel`).setAttribute(
      "aria-labelledby",
      button.id,
    );
  });
  $(".launcher").onclick = open;
  $("#close").onclick = close;
  $$("[data-tab]").forEach((b) => (b.onclick = () => activate(b.dataset.tab)));
  $("nav").onkeydown = (e) => {
    const tabs = $$('[role="tab"]');
    const i = tabs.indexOf(root.activeElement);
    if (i < 0) return;
    let n;
    if (e.key === "ArrowRight") n = (i + 1) % tabs.length;
    if (e.key === "ArrowLeft") n = (i + tabs.length - 1) % tabs.length;
    if (e.key === "Home") n = 0;
    if (e.key === "End") n = tabs.length - 1;
    if (n !== undefined) {
      e.preventDefault();
      tabs[n].click();
      tabs[n].focus();
    }
  };
  $("#clear").onclick = () => {
    logs = [];
    schedule();
  };
  $("#clear-network").onclick = () => {
    requests = [];
    schedule();
  };
  $("#log-search").oninput = schedule;
  $("#level").onchange = schedule;
  $("#repl").onsubmit = async (e) => {
    e.preventDefault();
    if (!settings.jsExecution) return;
    const source = $("#expression").value;
    if (!source.trim()) return;
    $("#expression").value = "";
    add("input", [source]);
    try {
      const result = await (0, eval)(source);
      if (!destroyed) add("result", [result]);
    } catch (error) {
      if (!destroyed) add("error", [error]);
    }
  };
  $("#selector-form").onsubmit = (e) => {
    e.preventDefault();
    inspect();
  };
  $("#highlight").onclick = () => {
    if (!selected) return;
    const rect = selected.getBoundingClientRect(),
      mark = document.createElement("div");
    mark.className = "element-highlight";
    mark.style.cssText = `left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px`;
    root.append(mark);
    const timer = setTimeout(() => {
      mark.remove();
      timers.delete(timer);
    }, 1500);
    timers.add(timer);
  };
  $("#storage-type").onchange = storage;
  $("#refresh-storage").onclick = storage;
  $("#export").onclick = () => {
    const data = {
      version: 1,
      source: "elyon-page-console",
      redacted: true,
      logs: logs.map(({ time, level }) => ({
        time,
        level,
        text: "[redacted]",
      })),
      requests: requests.map(({ kind, method, status, duration }) => ({
        kind,
        method,
        status,
        duration,
        url: "[redacted]",
      })),
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "elyon-page-session-redacted.json";
    a.click();
    const timer = setTimeout(() => {
      URL.revokeObjectURL(url);
      timers.delete(timer);
    }, 1000);
    timers.add(timer);
  };
  $("#reset").onclick = () => {
    settings = { ...DEFAULTS };
    apply();
    save();
  };
  const api = {
    open,
    close,
    showTab: (name) => {
      if (
        [
          "console",
          "network",
          "elements",
          "storage",
          "info",
          "settings",
        ].includes(name)
      ) {
        open();
        activate(name);
      }
    },
    destroy() {
      destroyed = true;
      for (const [level, { original, wrapped }] of originalConsole)
        if (console[level] === wrapped) console[level] = original;
      cleanups.forEach((fn) => fn());
      timers.forEach(clearTimeout);
      host.remove();
      if (window.elyonConsole === api) delete window.elyonConsole;
    },
  };
  window.elyonConsole = api;
  apply();
  activate("console");
  add("info", [
    "Elyon ready. Page instrumentation; native engine access unavailable.",
  ]);
  return api;
}
