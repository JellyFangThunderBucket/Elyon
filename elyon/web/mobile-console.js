import { THEMES, applyTheme } from "./themes.js";
import { preview, replaceMethod } from "./page-runtime.js";
import { installNetwork } from "./network.js";

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
  panelY: 1,
  launcherX: 0.95,
  launcherY: 0.9,
};
const KEY = "elyon.mobile.settings.v1";
let instance;
const REGISTRY = Symbol.for("elyon.page.console.instance");
export function createConsole() {
  if (instance) return instance;
  const registered = window[REGISTRY];
  if (
    registered?.source === "elyon-page-console" &&
    registered.snapshot().installed
  )
    return registered;
  if (document.getElementById("elyon-console"))
    throw new Error("An unrelated element owns #elyon-console");
  let settings = { ...DEFAULTS };
  let preferences = { status: "available", reason: "origin-storage-read" },
    raw = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    preferences = { status: "denied", reason: "storage-read-failed" };
  }
  if (raw !== null)
    try {
      const saved = JSON.parse(raw);
      if (!saved || typeof saved !== "object" || Array.isArray(saved))
        throw new Error("invalid-preferences");
      for (const key of Object.keys(DEFAULTS))
        if (typeof saved[key] === typeof DEFAULTS[key])
          settings[key] = saved[key];
    } catch {
      preferences = {
        status: "invalid",
        reason: "malformed-preferences-defaults-used",
      };
    }
  settings.fontSize = Math.max(11, Math.min(20, settings.fontSize));
  settings.height = Math.max(30, Math.min(100, settings.height));
  settings.opacity = Math.max(0.85, Math.min(1, settings.opacity));
  settings.maxRows = [100, 500, 1000, 2000].includes(settings.maxRows)
    ? settings.maxRows
    : 500;
  for (const key of ["panelY", "launcherX", "launcherY"])
    settings[key] = Math.max(0, Math.min(1, settings[key]));
  const capabilities = {
    evaluation: { status: "not-probed", reason: "checked-on-execution" },
    nativeGecko: { status: "unsupported", reason: "no-native-bridge" },
    broker: { status: "not-connected", reason: "page-only-session" },
    preferences,
    pointerEvents: {
      status: typeof PointerEvent === "function" ? "available" : "unsupported",
      reason:
        typeof PointerEvent === "function"
          ? "pointer-events"
          : "keyboard-handles-only",
    },
    visualViewport: {
      status: window.visualViewport ? "available" : "unsupported",
      reason: window.visualViewport
        ? "visual-viewport"
        : "layout-viewport-fallback",
    },
    styles: { status: "loading", reason: "stylesheet-requested" },
  };
  const capability = (name, value) => {
    capabilities[name] = { status: value.status, reason: value.reason };
  };
  const host = document.createElement("div");
  host.id = "elyon-console";
  host.style.cssText =
    "position:fixed;inset:0;pointer-events:none;z-index:2147483647";
  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = new URL("./mobile-console.css", import.meta.url).href;
  style.onload = () =>
    capability("styles", { status: "available", reason: "stylesheet-loaded" });
  style.onerror = () =>
    capability("styles", {
      status: "denied",
      reason: "stylesheet-unavailable-or-blocked",
    });
  root.append(style);
  const shell = document.createElement("div");
  shell.className = "elyon-shell";
  shell.innerHTML = `
  <button class="launcher" aria-label="Open Elyon console">E_</button>
  <section class="console" aria-label="Elyon developer console" hidden>
   <header><button id="move-handle" aria-label="Move console" title="Drag to move; arrow keys move panel">⠿ ELYON</button><div><button id="size-handle" aria-label="Resize console" title="Drag or use arrow keys to resize">↕</button><button id="export" aria-label="Export redacted session">Export</button><button id="close" aria-label="Minimize console">−</button></div></header>
   <nav aria-label="Console panels" role="tablist"><div class="scroll-tabs"><button role="tab" data-tab="console">Console</button><button role="tab" data-tab="network">Network</button><button role="tab" data-tab="elements">Elements</button><button role="tab" data-tab="storage">Storage</button><button role="tab" data-tab="info">Info</button></div><button role="tab" data-tab="settings" id="settings-tab">⚙ Settings</button></nav>
   <div class="panel" id="console-panel" role="tabpanel"><div class="toolbar"><select id="level" aria-label="Log level"><option value="">All levels</option><option>log</option><option>info</option><option>warn</option><option>error</option><option>debug</option><option>result</option></select><input id="log-search" placeholder="Filter logs" aria-label="Filter console logs"><button id="clear">Clear view</button></div><div id="logs" class="rows" role="log" aria-label="Console output"></div><form id="repl"><label for="expression">❯</label><select id="eval-mode" aria-label="Evaluation mode"><option value="script">JS</option><option value="await">Await</option></select><input id="expression" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="JavaScript in this page" aria-label="JavaScript expression"><button>Run</button></form></div>
   <div class="panel" id="network-panel" role="tabpanel" hidden><div class="toolbar"><input id="network-search" aria-label="Filter requests" placeholder="Filter requests"><span>Metadata only</span><button id="clear-network">Clear view</button></div><div class="rows" id="requests"></div></div>
   <div class="panel" id="elements-panel" role="tabpanel" hidden><form id="selector-form" class="toolbar"><input id="selector" value="body" aria-label="CSS selector"><button>Inspect</button><button type="button" id="highlight">Highlight</button><button type="button" id="pick">Pick</button></form><div class="rows"><p id="element-summary"></p><pre id="element-metadata"></pre><pre id="element-output"></pre></div></div>
   <div class="panel" id="storage-panel" role="tabpanel" hidden><div class="toolbar"><select id="storage-type" aria-label="Storage type"><option value="localStorage">Local storage</option><option value="sessionStorage">Session storage</option></select><button id="refresh-storage">Refresh</button></div><form id="storage-form" class="storage-editor"><input id="storage-key" placeholder="Key" aria-label="Storage key" required><input id="storage-value" placeholder="Value" aria-label="Storage value"><button>Save value</button></form><p id="storage-status" role="status"></p><div id="storage-output" class="rows"></div></div>
   <div class="panel" id="info-panel" role="tabpanel" hidden><div class="rows"><h2>Current page</h2><pre id="page-info"></pre><p>This console runs inside this page. It shares the page’s JavaScript thread and cannot stay responsive during a page stall. Use the independent Elyon broker for durable browser evidence.</p><p>Gecko and native iOS bridges are research work, not enabled capabilities.</p></div></div>
   <div class="panel" id="settings-panel" role="tabpanel" hidden><div class="rows settings"><div class="section-title">APPEARANCE <span>20 ORIGINAL PALETTES</span></div><div id="themes" class="themes" aria-label="Color themes"></div><div id="settings-controls"></div><button id="reset">Restore Elyon defaults</button><p id="save-state" role="status">Preferences are stored on this origin.</p><p>Only Elyon preferences are reset. Page storage and recorded broker evidence are never cleared here.</p></div></div>
   <footer><span id="session-state">PAGE INSTRUMENTATION</span><span id="row-count">0 logs</span></footer>
  </section>`;
  root.append(shell);
  document.documentElement.append(host);
  const $ = (q) => root.querySelector(q);
  const $$ = (q) => [...root.querySelectorAll(q)];
  let serial = 0,
    logsDropped = 0,
    requestsDropped = 0;
  const newId = () => `page-${++serial}`;
  let logs = [],
    requests = [],
    tab = "console",
    destroyed = false,
    selected = null,
    renderPending = false;
  let frame = null,
    picking = false;
  const objectURLs = new Set();
  const cleanups = [
    () => {
      style.onload = null;
      style.onerror = null;
    },
  ];
  const timers = new Set();

  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(settings));
      capability("preferences", {
        status: "available",
        reason: "saved-on-origin",
      });
      $("#save-state").textContent = "Preferences saved on this origin.";
    } catch {
      capability("preferences", {
        status: "denied",
        reason: "storage-write-failed",
      });
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
    logsDropped += Math.max(0, logs.length - settings.maxRows);
    logs = logs.slice(-settings.maxRows);
    requestsDropped += Math.max(0, requests.length - settings.maxRows);
    requests = requests.slice(-settings.maxRows);
    layout();
    schedule();
  }
  function open() {
    if (destroyed) return;
    stopPicking();
    layout();
    $(".console").hidden = false;
    $(".launcher").hidden = true;
    schedule();
  }
  function close() {
    if (destroyed) return;
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
    frame = requestAnimationFrame(() => {
      renderPending = false;
      if (!destroyed && !$(".console").hidden) render();
    });
  }
  function add(level, args) {
    if (destroyed) return;
    logs.push({
      id: newId(),
      time: Date.now(),
      level,
      text: args.map((value) => preview(value)).join(" "),
    });
    logsDropped += Math.max(0, logs.length - settings.maxRows);
    logs = logs.slice(-settings.maxRows);
    if (level === "error" && settings.autoOpenError) {
      open();
      activate("console");
    }
    schedule();
  }
  const requestElements = new Map();
  function render() {
    if (tab === "console") {
      const logScroll = $("#logs").scrollTop;
      const q = $("#log-search").value.toLowerCase(),
        level = $("#level").value;
      const rows = logs.filter(
        (l) =>
          (!level || l.level === level) && l.text.toLowerCase().includes(q),
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
      if (settings.autoScroll && tab === "console")
        $("#logs").scrollTop = $("#logs").scrollHeight;
      else $("#logs").scrollTop = logScroll;
    }
    if (tab === "network") {
      if (!requestElements.size) $("#requests").replaceChildren();
      const networkQuery = $("#network-search").value.toLowerCase();
      const visibleRequests = requests
        .filter((n) => JSON.stringify(n).toLowerCase().includes(networkQuery))
        .slice(-250);
      const visibleIDs = new Set(visibleRequests.map((n) => n.id));
      for (const [id, el] of requestElements)
        if (!visibleIDs.has(id)) {
          el.remove();
          requestElements.delete(id);
        }
      for (const n of visibleRequests) {
        const row =
          requestElements.get(n.id) || document.createElement("details");
        const wasOpen = row.open;
        row.replaceChildren();
        row.className = "request";
        const summary = document.createElement("summary");
        summary.textContent = `${n.method ?? "?"}  ${n.status ?? "—"}  ${n.outcome}  ${n.duration === null ? "…" : n.duration.toFixed(1) + " ms"}  ${n.url ?? "URL unavailable"}`;
        const pre = document.createElement("pre");
        const { monotonicStart, ...details } = n;
        pre.textContent = JSON.stringify(details, null, 2);
        row.append(summary, pre);
        row.open = wasOpen;
        if (!requestElements.has(n.id)) {
          requestElements.set(n.id, row);
          $("#requests").append(row);
        }
      }
      if (!requests.length)
        $("#requests").textContent =
          "No requests captured yet. Fetch a response from the playground.";
    }
    $("#session-state").textContent =
      logsDropped + requestsDropped
        ? `PAGE · ${logsDropped + requestsDropped} older rows evicted`
        : "PAGE INSTRUMENTATION";
    $("#row-count").textContent =
      `${logs.length} logs · ${requests.length} requests · view ≤250`;
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
    const hook = replaceMethod(
      console,
      level,
      (original) =>
        function (...args) {
          const result = Reflect.apply(original, this, args);
          if (!destroyed && settings.console)
            try {
              if (level === "assert") {
                if (!args[0]) add("error", args.slice(1));
              } else add(level, args);
            } catch {
              /* Observation must not replace the native result or exception. */
            }
          return result;
        },
    );
    capability(`console.${level}`, hook);
    cleanups.push(hook.restore);
  }
  const errorListener = (e) => {
    if (settings.errors && !destroyed)
      try {
        add("error", [e.error || e.message || "Resource load error"]);
      } catch {}
  };
  const rejectionListener = (e) => {
    if (settings.errors && !destroyed)
      try {
        add("error", ["Unhandled rejection:", e.reason]);
      } catch {}
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
      id: newId(),
      kind,
      method: typeof method === "string" ? method.slice(0, 32) : null,
      url: typeof url === "string" ? url.slice(0, 4000) : null,
      status: null,
      duration: null,
      started: Date.now(),
    };
    requests.push(row);
    requestsDropped += Math.max(0, requests.length - settings.maxRows);
    requests = requests.slice(-settings.maxRows);
    schedule();
    return row;
  }
  const network = installNetwork({
    enabled: () => settings.network,
    begin,
    change: schedule,
    capability,
  });
  cleanups.push(() => network.stop());
  function inspectElement(element) {
    selected = element;
    if (!selected) {
      $("#element-summary").textContent = "No matching element";
      $("#element-output").textContent = "";
      $("#element-metadata").textContent = "";
      return;
    }
    try {
      const rect = selected.getBoundingClientRect(),
        css = getComputedStyle(selected);
      $("#element-summary").textContent =
        `${selected.tagName.toLowerCase()} · ${selected.childElementCount} child elements`;
      $("#element-metadata").textContent = JSON.stringify(
        {
          source: "page-dom",
          connected: selected.isConnected,
          tag: selected.tagName.toLowerCase(),
          id: selected.id,
          classes: [...selected.classList],
          attributes: [...selected.attributes]
            .slice(0, 40)
            .map((a) => ({ name: a.name, value: a.value.slice(0, 500) })),
          rect: {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
          },
          computed: {
            display: css.display,
            visibility: css.visibility,
            position: css.position,
            color: css.color,
            fontSize: css.fontSize,
          },
          text: selected.textContent.slice(0, 2000),
        },
        null,
        2,
      );
      const html = selected.outerHTML;
      $("#element-output").textContent =
        html.slice(0, 30000) +
        (html.length > 30000 ? "\n[HTML truncated at 30000 characters]" : "");
    } catch (error) {
      selected = null;
      $("#element-summary").textContent = preview(error);
    }
  }
  function inspect() {
    selected = null;
    try {
      inspectElement(document.querySelector($("#selector").value));
    } catch (error) {
      $("#element-summary").textContent = preview(error);
      $("#element-output").textContent = "";
      $("#element-metadata").textContent = "";
    }
  }
  let highlightCleanup = () => {};
  function highlight() {
    highlightCleanup();
    if (!selected?.isConnected) {
      $("#element-summary").textContent =
        "Selected element is no longer connected.";
      return;
    }
    const mark = document.createElement("div");
    mark.className = "element-highlight";
    root.append(mark);
    const update = () => {
      if (!selected?.isConnected) {
        highlightCleanup();
        return;
      }
      const r = selected.getBoundingClientRect();
      mark.style.cssText = `left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px`;
    };
    const timer = setTimeout(() => highlightCleanup(), 1800);
    timers.add(timer);
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    highlightCleanup = () => {
      clearTimeout(timer);
      timers.delete(timer);
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
      mark.remove();
    };
    update();
  }
  cleanups.push(() => highlightCleanup());
  function stopPicking() {
    picking = false;
    document.removeEventListener("pointerdown", pickElement, true);
    document.removeEventListener("keydown", cancelPick, true);
    $(".launcher").textContent = "E_";
  }
  function cancelPick(e) {
    if (e.key === "Escape") {
      stopPicking();
      open();
    }
  }
  function pickElement(e) {
    if (e.composedPath().includes(host)) return;
    if (!(e.target instanceof Element)) return;
    e.preventDefault();
    e.stopPropagation();
    const element = e.target;
    stopPicking();
    open();
    activate("elements");
    $("#selector").value = "";
    inspectElement(element);
    highlight();
  }
  $("#pick").onclick = () => {
    picking = true;
    close();
    $(".launcher").textContent = "Cancel";
    document.addEventListener("pointerdown", pickElement, true);
    document.addEventListener("keydown", cancelPick, true);
  };
  cleanups.push(stopPicking);
  function storage() {
    const out = $("#storage-output");
    out.replaceChildren();
    const name = $("#storage-type").value;
    try {
      const store = window[name];
      capability(name, { status: "available", reason: "read-access" });
      for (let i = 0; i < Math.min(store.length, 250); i++) {
        const key = store.key(i),
          row = document.createElement("div");
        row.className = "storage-row";
        const title = document.createElement("b");
        title.textContent = key;
        const value = document.createElement("pre");
        const stored = store.getItem(key);
        value.textContent =
          stored?.slice(0, 10000) +
          (stored?.length > 10000
            ? "\n[value truncated at 10000 characters]"
            : "");
        const edit = document.createElement("button");
        edit.textContent = "Edit";
        edit.setAttribute("aria-label", `Edit ${key}`);
        edit.onclick = () => {
          $("#storage-key").value = key;
          $("#storage-value").value = store.getItem(key) || "";
        };
        const remove = document.createElement("button");
        remove.textContent = "Delete";
        remove.setAttribute("aria-label", `Delete ${key}`);
        remove.onclick = () => {
          if (window.confirm("Delete this one storage key?"))
            try {
              store.removeItem(key);
              $("#storage-status").textContent = "Value deleted.";
              storage();
            } catch (error) {
              $("#storage-status").textContent = preview(error);
            }
        };
        row.append(title, value, edit, remove);
        out.append(row);
      }
      if (!store.length) out.textContent = "No stored values on this origin.";
      if (store.length > 250)
        out.prepend(
          document.createTextNode(
            "Showing first 250 keys. Values are truncated at 10000 characters.",
          ),
        );
    } catch (error) {
      capability(name, { status: "denied", reason: "storage-read-failed" });
      out.textContent = "Storage unavailable: " + preview(error);
    }
  }
  $("#storage-form").onsubmit = (e) => {
    e.preventDefault();
    try {
      window[$("#storage-type").value].setItem(
        $("#storage-key").value,
        $("#storage-value").value,
      );
      $("#storage-status").textContent = "Value saved.";
      storage();
    } catch (error) {
      $("#storage-status").textContent =
        "Storage write failed: " + preview(error);
    }
  };
  function info() {
    $("#page-info").textContent = JSON.stringify(
      {
        url: location.href,
        userAgent: navigator.userAgent,
        viewport: viewport(),
        online: navigator.onLine,
        secureContext: isSecureContext,
        timeOrigin: performance.timeOrigin,
        source: "page-instrumentation",
        nativeBridge: false,
        enabled: {
          network: settings.network,
          console: settings.console,
          errors: settings.errors,
          evaluation: settings.jsExecution,
        },
        capabilities,
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
  $("#network-search").oninput = schedule;
  $("#level").onchange = schedule;
  $("#repl").onsubmit = async (e) => {
    e.preventDefault();
    if (!settings.jsExecution) return;
    const source = $("#expression").value;
    if (!source.trim()) return;
    $("#expression").value = "";
    add("input", [source]);
    try {
      const result =
        $("#eval-mode").value === "await"
          ? await new (Object.getPrototypeOf(async function () {}).constructor)(
              `return (${source}\n)`,
            )()
          : await (0, eval)(source);
      capability("evaluation", {
        status: "available",
        reason: "page-execution",
      });
      if (!destroyed) add("result", [result]);
    } catch (error) {
      capability("evaluation", {
        status: error instanceof EvalError ? "denied" : "available",
        reason:
          error instanceof EvalError
            ? "eval-blocked-by-page-policy"
            : "evaluation-error",
      });
      if (!destroyed) add("error", [error]);
    }
  };
  $("#selector-form").onsubmit = (e) => {
    e.preventDefault();
    inspect();
  };
  $("#highlight").onclick = highlight;
  $("#storage-type").onchange = storage;
  $("#refresh-storage").onclick = storage;
  $("#export").onclick = () => {
    const data = snapshot();
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    objectURLs.add(url);
    a.href = url;
    a.download = "elyon-page-session-redacted.json";
    a.click();
    const timer = setTimeout(() => {
      URL.revokeObjectURL(url);
      objectURLs.delete(url);
      timers.delete(timer);
    }, 1000);
    timers.add(timer);
  };
  $("#reset").onclick = () => {
    settings = { ...DEFAULTS };
    apply();
    save();
  };
  function viewport() {
    const v = window.visualViewport;
    return {
      width: v?.width || innerWidth,
      height: v?.height || innerHeight,
      left: v?.offsetLeft || 0,
      top: v?.offsetTop || 0,
    };
  }
  function layout() {
    if (destroyed) return;
    const v = viewport();
    shell.classList.toggle("keyboard-compact", v.height < 320);
    shell.classList.toggle(
      "keyboard-tiny",
      v.height < 190 && root.activeElement === $("#expression"),
    );
    const height = Math.min(
      v.height,
      Math.max(200, (innerHeight * settings.height) / 100),
    );
    shell.style.setProperty("--panel-height", height + "px");
    shell.style.setProperty(
      "--panel-top",
      v.top + Math.max(0, v.height - height) * settings.panelY + "px",
    );
    shell.style.setProperty("--viewport-left", v.left + "px");
    shell.style.setProperty("--viewport-width", v.width + "px");
    $(".launcher").style.left =
      v.left + Math.max(0, v.width - 48) * settings.launcherX + "px";
    $(".launcher").style.top =
      v.top + Math.max(0, v.height - 48) * settings.launcherY + "px";
    if (tab === "info") info();
  }
  function draggable(element, mode) {
    let drag = null,
      moved = false;
    const down = (e) => {
      if (e.button !== 0) return;
      const v = viewport(),
        r = $(".console").getBoundingClientRect();
      drag = {
        id: e.pointerId,
        x: e.clientX,
        y: e.clientY,
        height: r.height,
        top: r.top,
        launcher: $(".launcher").getBoundingClientRect(),
        v,
      };
      moved = false;
      element.setPointerCapture(e.pointerId);
    };
    const move = (e) => {
      if (!drag || drag.id !== e.pointerId) return;
      const dx = e.clientX - drag.x,
        dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) < 4 && !moved) return;
      moved = true;
      e.preventDefault();
      const v = viewport();
      if (mode === "launcher") {
        settings.launcherX = Math.max(
          0,
          Math.min(
            1,
            (drag.launcher.left + dx - v.left) / Math.max(1, v.width - 48),
          ),
        );
        settings.launcherY = Math.max(
          0,
          Math.min(
            1,
            (drag.launcher.top + dy - v.top) / Math.max(1, v.height - 48),
          ),
        );
      } else if (mode === "move") {
        settings.panelY = Math.max(
          0,
          Math.min(
            1,
            (drag.top + dy - v.top) / Math.max(1, v.height - drag.height),
          ),
        );
      } else {
        settings.height = Math.max(
          30,
          Math.min(100, ((drag.height - dy) / innerHeight) * 100),
        );
      }
      layout();
    };
    const up = (e) => {
      if (!drag || drag.id !== e.pointerId) return;
      drag = null;
      if (moved) save();
    };
    const click = (e) => {
      if (moved) {
        e.preventDefault();
        e.stopImmediatePropagation();
        moved = false;
      }
    };
    element.addEventListener("pointerdown", down);
    element.addEventListener("pointermove", move);
    element.addEventListener("pointerup", up);
    element.addEventListener("pointercancel", up);
    element.addEventListener("click", click, true);
    cleanups.push(() => {
      if (drag && element.hasPointerCapture(drag.id))
        element.releasePointerCapture(drag.id);
      drag = null;
      element.removeEventListener("pointerdown", down);
      element.removeEventListener("pointermove", move);
      element.removeEventListener("pointerup", up);
      element.removeEventListener("pointercancel", up);
      element.removeEventListener("click", click, true);
    });
  }
  draggable($(".launcher"), "launcher");
  draggable($("#move-handle"), "move");
  draggable($("#size-handle"), "resize");
  $("#move-handle").onkeydown = (e) => {
    if (["ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) {
      e.preventDefault();
      settings.panelY =
        e.key === "Home"
          ? 0
          : e.key === "End"
            ? 1
            : Math.max(
                0,
                Math.min(
                  1,
                  settings.panelY + (e.key === "ArrowUp" ? -0.1 : 0.1),
                ),
              );
      layout();
      save();
    }
  };
  $("#size-handle").onkeydown = (e) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      settings.height = Math.max(
        30,
        Math.min(100, settings.height + (e.key === "ArrowUp" ? 5 : -5)),
      );
      apply();
      save();
    }
  };
  shell.addEventListener("focusin", layout);
  shell.addEventListener("focusout", layout);
  window.addEventListener("resize", layout);
  window.visualViewport?.addEventListener("resize", layout);
  window.visualViewport?.addEventListener("scroll", layout);
  cleanups.push(
    () => window.removeEventListener("resize", layout),
    () => window.visualViewport?.removeEventListener("resize", layout),
    () => window.visualViewport?.removeEventListener("scroll", layout),
  );
  function snapshot({ redacted = true } = {}) {
    const safeMethods = new Set([
      "GET",
      "HEAD",
      "POST",
      "PUT",
      "PATCH",
      "DELETE",
      "OPTIONS",
      "CONNECT",
      "TRACE",
    ]);
    return JSON.parse(
      JSON.stringify({
        version: 2,
        source: "elyon-page-console",
        redacted,
        independentEvidence: false,
        installed: !destroyed,
        enabled: {
          console: settings.console,
          errors: settings.errors,
          network: settings.network,
          evaluation: settings.jsExecution,
        },
        coverage: {
          scope: "current-document",
          complete: false,
          settingsHistory: "not-recorded",
        },
        retention: {
          policy: "volatile-drop-oldest",
          maxRows: settings.maxRows,
          visibleRows: 250,
          logsDropped,
          requestsDropped,
        },
        capabilities,
        logs: logs.map((l) =>
          redacted
            ? { time: l.time, level: l.level, text: "[redacted]" }
            : { ...l },
        ),
        requests: requests.map(({ monotonicStart, ...r }) =>
          redacted
            ? {
                id: r.id,
                kind: r.kind,
                source: r.source,
                method: safeMethods.has(r.method?.toUpperCase())
                  ? r.method
                  : "[redacted]",
                status: r.status,
                outcome: r.outcome,
                duration: r.duration,
                url: "[redacted]",
                gap: r.gap,
                eventsTruncated: Boolean(r.eventsTruncated),
                events: r.events,
              }
            : r,
        ),
      }),
    );
  }
  const api = {
    source: "elyon-page-console",
    snapshot,
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
      if (destroyed) return;
      cleanups.forEach((fn) => {
        try {
          fn();
        } catch {
          capability("cleanup", {
            status: "partial",
            reason: "page-prevented-cleanup",
          });
        }
      });
      destroyed = true;
      if (frame !== null) cancelAnimationFrame(frame);
      timers.forEach(clearTimeout);
      objectURLs.forEach((url) => URL.revokeObjectURL(url));
      objectURLs.clear();
      logs = [];
      requests = [];
      requestElements.clear();
      selected = null;
      for (const state of Object.values(capabilities))
        if (state.status === "available") {
          state.status = "stopped";
          state.reason = "console-destroyed";
        }
      host.remove();
      try {
        if (window.elyonConsole === api) delete window.elyonConsole;
      } catch {
        capability("globalAPI", {
          status: "denied",
          reason: "protected-global",
        });
      }
      try {
        if (window[REGISTRY] === api) delete window[REGISTRY];
      } catch {
        capability("globalAPI", {
          status: "denied",
          reason: "protected-registry",
        });
      }
      instance = null;
    },
  };
  instance = api;
  try {
    window[REGISTRY] = api;
    window.elyonConsole = api;
  } catch {
    capability("globalAPI", { status: "denied", reason: "protected-global" });
  }
  apply();
  activate("console");
  add("info", [
    "Elyon ready. Page instrumentation; native engine access unavailable.",
  ]);
  return api;
}
