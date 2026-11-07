import { replaceMethod } from "./page-runtime.js";

/* No bodies, request headers, synthetic browser events, or URL/time identity joins. */
export function installNetwork({ enabled, begin, change, capability }) {
  let alive = true,
    notify = change,
    pendingFetch = 0,
    sequence = 0;
  const active = new Set(),
    metadata = new WeakMap(),
    watchers = new WeakMap();
  const stamp = (row, phase, fields = {}) => {
    if (!alive || !row) return;
    row.events.push({
      sequence: ++sequence,
      phase,
      elapsedMs: Math.max(0, performance.now() - row.monotonicStart),
      ...fields,
    });
    if (row.events.length > 32) {
      row.events.splice(1, 1);
      row.eventsTruncated = true;
    }
    try {
      notify?.();
    } catch {
      /* Never alter page behavior for a UI failure. */
    }
  };
  const safely = (fn) => {
    try {
      return fn();
    } catch {
      return undefined;
    }
  };
  function start(method, url, kind) {
    if (!alive || !enabled()) return null;
    return safely(() => {
      const row = begin(method, url, kind);
      if (row) {
        row.source = "page-instrumentation";
        row.events = [];
        row.monotonicStart = performance.now();
        row.outcome = "pending";
        stamp(row, "request-start");
      }
      return row;
    });
  }
  function finish(row, outcome, fields = {}) {
    if (!row || !alive) return;
    Object.assign(row, fields, {
      outcome,
      duration: Math.max(0, performance.now() - row.monotonicStart),
    });
    stamp(row, outcome);
  }
  // Read data descriptors only: native conversion must be the only coercion of
  // caller-defined URL objects and accessor-valued RequestInit properties.
  function fetchMetadata(args) {
    let method = null,
      url = null;
    const input = args[0],
      init = args[1];
    if (typeof input === "string") url = input;
    else if (typeof Request === "function") {
      safely(() => {
        url = Object.getOwnPropertyDescriptor(
          Request.prototype,
          "url",
        ).get.call(input);
        method = Object.getOwnPropertyDescriptor(
          Request.prototype,
          "method",
        ).get.call(input);
      });
    }
    if (typeof URL === "function" && url === null)
      safely(() => {
        url = Object.getOwnPropertyDescriptor(URL.prototype, "href").get.call(
          input,
        );
      });
    if (init == null) method = method || "GET";
    else {
      const d = safely(() => Object.getOwnPropertyDescriptor(init, "method"));
      if (d && "value" in d && typeof d.value === "string") method = d.value;
      else if (
        !d &&
        safely(() => Object.getPrototypeOf(init)) === Object.prototype
      )
        method = method || "GET";
    }
    return { method, url };
  }
  const fetchHook = replaceMethod(
    window,
    "fetch",
    (original) =>
      function (...args) {
        if (!alive || !enabled()) return Reflect.apply(original, this, args);
        const meta = safely(() => fetchMetadata(args)) || {
          method: null,
          url: null,
        };
        const row = start(meta.method, meta.url, "fetch");
        let result;
        try {
          result = Reflect.apply(original, this, args);
        } catch (error) {
          safely(() => finish(row, "call-threw"));
          throw error;
        }
        if (!(result instanceof Promise)) {
          safely(() =>
            finish(row, "unavailable", { gap: "non-promise-fetch-result" }),
          );
          return result;
        }
        if (pendingFetch >= 128) {
          safely(() =>
            finish(row, "unavailable", { gap: "observer-capacity" }),
          );
          return result;
        }
        pendingFetch++;
        // A returned chain preserves rejection behavior (including unhandled rejection)
        // and the exact Response/error objects, but changes Promise identity/timing.
        return result.then(
          (response) => {
            pendingFetch--;
            if (alive && row)
              try {
                row.status = response.status;
                row.responseURL = response.url;
                row.responseType = response.type;
                stamp(row, "response-available", { status: row.status });
                finish(row, "fulfilled");
              } catch {
                safely(() =>
                  finish(row, "unavailable", {
                    gap: "response-metadata-access-denied",
                  }),
                );
              }
            return response;
          },
          (error) => {
            pendingFetch--;
            safely(() => finish(row, "rejected"));
            throw error;
          },
        );
      },
  );
  capability("fetch", fetchHook);
  const xhrPrototype =
    typeof XMLHttpRequest === "function" ? XMLHttpRequest.prototype : null;
  const xhrGetters = Object.fromEntries(
    ["readyState", "status", "responseURL"].map((key) => [
      key,
      xhrPrototype && Object.getOwnPropertyDescriptor(xhrPrototype, key)?.get,
    ]),
  );
  const read = (xhr, key) =>
    safely(() => Reflect.apply(xhrGetters[key], xhr, []));
  function release(watch, reason) {
    if (!watch) return;
    for (const [type, listener] of watch.listeners)
      safely(() => watch.xhr.removeEventListener(type, listener, true));
    active.delete(watch);
    if (watchers.get(watch.xhr) === watch) watchers.delete(watch.xhr);
    if (reason && alive && watch.row) {
      watch.row.gap = reason;
      if (watch.row.outcome === "pending") finish(watch.row, "unavailable");
      stamp(watch.row, "observation-ended");
    }
  }
  const openHook = replaceMethod(
    xhrPrototype,
    "open",
    (original) =>
      function (...args) {
        // An invalid open must throw natively without invalidating the current request.
        const result = Reflect.apply(original, this, args);
        if (!alive) return result;
        safely(() => release(watchers.get(this), "reopened-before-loadend"));
        if (!enabled()) {
          metadata.delete(this);
          return result;
        }
        metadata.set(this, {
          method: typeof args[0] === "string" ? args[0] : null,
          url: typeof args[1] === "string" ? args[1] : null,
        });
        return result;
      },
  );
  const sendHook = replaceMethod(
    xhrPrototype,
    "send",
    (original) =>
      function (...args) {
        if (!alive || !enabled()) return Reflect.apply(original, this, args);
        // Invalid repeated send is owned by the browser, not a new observed request.
        if (watchers.has(this) || read(this, "readyState") !== 1)
          return Reflect.apply(original, this, args);
        const meta = metadata.get(this) || { method: null, url: null },
          row = start(meta.method, meta.url, "xhr");
        if (!row) return Reflect.apply(original, this, args);
        if (active.size >= 128) {
          finish(row, "unavailable", { gap: "observer-capacity" });
          return Reflect.apply(original, this, args);
        }
        const watch = { xhr: this, row, listeners: [], done: false };
        watchers.set(this, watch);
        active.add(watch);
        const snapshot = () => {
          row.status = read(this, "status") ?? null;
          row.responseURL = read(this, "responseURL") ?? null;
          row.readyState = read(this, "readyState") ?? null;
        };
        const observe = (event) => {
          if (!alive || watchers.get(this) !== watch) return;
          const state = read(this, "readyState");
          if (event.type === "readystatechange") {
            if (state < 2) return;
            snapshot();
            stamp(row, "readystatechange", {
              readyState: state,
              status: row.status,
            });
            if (state === 4) {
              watch.done = true;
              finish(row, "done");
            }
            return;
          }
          // A prior request's terminal event may arrive after a reentrant open/send.
          // Never attribute it to the new, still-pending request.
          if (!watch.done && state !== 4) return;
          if (!watch.done) {
            snapshot();
            watch.done = true;
          }
          if (event.type === "loadend") {
            stamp(row, event.type, {
              readyState: row.readyState,
              status: row.status,
            });
            release(watch);
            return;
          }
          finish(row, event.type);
        };
        try {
          for (const type of [
            "readystatechange",
            "load",
            "error",
            "abort",
            "timeout",
            "loadend",
          ]) {
            const listener = (e) => safely(() => observe(e));
            this.addEventListener(type, listener, true);
            watch.listeners.push([type, listener]);
          }
        } catch {
          safely(() =>
            finish(row, "unavailable", { gap: "event-listener-access-denied" }),
          );
          release(watch);
          capability("xhr", {
            status: "partial",
            reason: "event-listener-access-denied",
          });
          return Reflect.apply(original, this, args);
        }
        try {
          return Reflect.apply(original, this, args);
        } catch (error) {
          safely(() => {
            finish(row, "send-threw");
            release(watch);
          });
          throw error;
        }
      },
  );
  if (openHook.status !== "available" || sendHook.status !== "available") {
    openHook.restore();
    sendHook.restore();
    capability("xhr", {
      status: !xhrPrototype ? "unsupported" : "denied",
      reason: !xhrPrototype ? "missing-api" : "protected-method",
    });
  } else
    capability("xhr", {
      status: "available",
      reason: "page-wrapper-installed",
    });
  return {
    stop() {
      if (!alive) return;
      for (const watch of [...active])
        safely(() => release(watch, "console-destroyed"));
      alive = false;
      notify = null;
      begin = null;
      enabled = null;
      capability = null;
      fetchHook.restore();
      sendHook.restore();
      openHook.restore();
    },
  };
}
