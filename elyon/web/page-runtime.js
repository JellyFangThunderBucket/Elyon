/* Page-only helpers. Observers must never throw into the inspected operation. */
export function replaceMethod(target, key, make) {
  let original, descriptor;
  try {
    if (!target || typeof target[key] !== "function")
      return { status: "unsupported", reason: "missing-api", restore() {} };
    descriptor = Object.getOwnPropertyDescriptor(target, key);
    if (
      descriptor &&
      (!("value" in descriptor) || descriptor.writable === false)
    )
      throw new Error("protected-method");
    original = target[key];
    const wrapped = make(original);
    if (!Reflect.set(target, key, wrapped) || target[key] !== wrapped)
      throw new Error("protected-method");
    return {
      status: "available",
      reason: "page-wrapper-installed",
      restore() {
        // A later library may own this slot. Never overwrite its wrapper.
        try {
          if (target[key] !== wrapped) return;
          if (descriptor) Object.defineProperty(target, key, descriptor);
          else delete target[key];
        } catch {
          /* The page may freeze its API after installation. */
        }
      },
    };
  } catch {
    return { status: "denied", reason: "protected-method", restore() {} };
  }
}

export function preview(value, depth = 0, seen = new WeakSet()) {
  try {
    if (value === null) return "null";
    if (typeof value === "string") return value.slice(0, 10000);
    if (typeof value === "function") return "[Function]";
    if (typeof value !== "object") return String(value).slice(0, 10000);
    if (typeof DOMException === "function") {
      try {
        const name = Object.getOwnPropertyDescriptor(
          DOMException.prototype,
          "name",
        ).get.call(value);
        const message = Object.getOwnPropertyDescriptor(
          DOMException.prototype,
          "message",
        ).get.call(value);
        return `${name}: ${message}`.slice(0, 10000);
      } catch {
        /* Not a branded DOMException. Do not call custom getters. */
      }
    }
    if (value instanceof Error) {
      const names = [
        [EvalError, "EvalError"],
        [SyntaxError, "SyntaxError"],
        [TypeError, "TypeError"],
        [RangeError, "RangeError"],
        [ReferenceError, "ReferenceError"],
        [URIError, "URIError"],
      ];
      const name =
        names.find(([type]) => value instanceof type)?.[1] || "Error";
      const message = Object.getOwnPropertyDescriptor(value, "message");
      const stack = Object.getOwnPropertyDescriptor(value, "stack");
      return `${name}: ${message && "value" in message && typeof message.value === "string" ? message.value : "[message getter not invoked]"}${stack && "value" in stack && typeof stack.value === "string" ? "\n" + stack.value : ""}`.slice(
        0,
        10000,
      );
    }
    if (seen.has(value)) return "[Circular]";
    if (depth >= 2) return "[object]";
    seen.add(value);
    // Descriptor reads avoid invoking property getters or custom toString hooks.
    // A Proxy can still trap reflection; failures are reported rather than hidden.
    const keys = Reflect.ownKeys(value),
      parts = [];
    for (const key of keys.slice(0, 25)) {
      const d = Object.getOwnPropertyDescriptor(value, key);
      if (!d) continue;
      parts.push(
        `${String(key)}: ${"value" in d ? preview(d.value, depth + 1, seen).slice(0, 500) : "[getter not invoked]"}`,
      );
    }
    if (keys.length > 25) parts.push(`… ${keys.length - 25} more properties`);
    return `${Array.isArray(value) ? "[" : "{"}${parts.join(", ")}${Array.isArray(value) ? "]" : "}"}`.slice(
      0,
      10000,
    );
  } catch {
    return "[Uninspectable value: reflection denied]";
  }
}
