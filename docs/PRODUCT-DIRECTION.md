# The phone experience Elyon should earn

“100 times better than Eruda” is an ambition, not a measured result. This document
turns it into concrete experiences and testable goals.

## Walkthrough from the phone user's point of view

I open a page I control and see a small square launcher. One tap opens a readable
console. Settings stays in reach while the other tabs scroll; changing a palette
recolors the entire inspector, and it still looks the same when I return tomorrow.
I can run an expression, inspect an element, read storage, and follow a failing
request without hunting through a desktop dashboard.

When the page hangs, I need a separate recorder that still answers. When the page
crashes, I want the request and redirect chain that led to it. When I share a report,
I want sensitive payloads removed and uncertainty preserved. Those are the strongest
reasons for Elyon to exist alongside an established mobile console.

## Implemented now

- Square, isolated Shadow DOM page console; pinned Settings and scrollable tool tabs.
- Console capture and async-result REPL, level/text filters, and bounded retention.
- Fetch/XHR lifecycle metadata with reentrant reuse handling and explicit gaps.
- DOM selector/picker inspection, computed metadata, tracking highlights, and storage editing.
- Draggable launcher/panel, resizing, visual-viewport layout, and a standalone static device lab.
- 20 independently authored palettes: ten dark and ten light. Shared palettes also
  apply to the desktop workbench. Text token contrast is checked at full opacity.
- Persistent typography, height, opacity, wrapping, timestamps, follow-scroll,
  capture toggles, error auto-open, JavaScript execution, and row limits.
- No response-body capture in the page console. Redacted page-session export removes
  console messages and request URLs. It is distinct from a broker evidence archive.
- Conditional teardown restores our installed wrappers without overwriting later
  wrappers installed by the page. Getters are not invoked for object previews.

The page console shares the inspected page's thread. It cannot implement the
independent recorder promise by itself. The existing desktop broker/harness proves
that architecture in Chromium; native iOS needs the work in GECKO.md.

## Eruda comparison

Reviewed [Eruda's live npm 3.4.3 Settings panel](https://www.npmjs.com/package/eruda)
and [source at 0c55928](https://github.com/liriliri/eruda/tree/0c55928fec802fb2102934c4b5928686178b467b).
The useful reference is its dense tool tabs, persisted theme/transparency/size
controls, logging options, and reset flow. Elyon preserves that directness while
pinning Settings on small screens. Original source, theme names, and palette
definitions are not copied. Advanced object expansion and getter evaluation in
Eruda remain richer than Elyon's bounded previews; Elyon does not claim parity.

## Differentiators to build next, in priority order

| Experience | Implementation needed | Acceptance target, not a current claim |
| --- | --- | --- |
| Physical Safari/Reynard validation | Run the device acceptance guide, keyboard/orientation and long-session profiling | Signed-off results on the actual supported phones |
| Phone to inspector without setup friction | Authenticated short-code pairing, QR, transport diagnostics | First authorized target within 30 seconds on a known network |
| A dead page leaves an inspectable session | Native independent recorder, persistent capture list, reconnect | All acknowledged evidence survives renderer termination |
| Explain a request's history | Correlated native request IDs and explicit coverage gaps | Redirect chain without URL/time identity guesses |
| A focused failure report | Link errors, requests, navigation, and selected evidence; redact by default | One portable report that reopens with the same relationships |
| Faster debugging on a small screen | Bounded rendering, keyboard-safe controls, target picker, search | Frame/memory/control budgets measured on supported physical iPhones |
| Trust what the UI says | Display source, capability, last acknowledgment, and uncertainty | Unsupported native capabilities never appear active |

Do not add speculative performance meters, fake engine selectors, or decorative
settings. Measure against Eruda on the same device/page before claiming an advantage.
