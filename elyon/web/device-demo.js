import { createConsole } from "./mobile-console.js";
const $ = (s) => document.querySelector(s);
let api,
  count = 0;
function install() {
  try {
    api = createConsole();
    api.open();
    $("#installation").textContent =
      "Console installed in this page. Info reports unavailable or denied capabilities.";
  } catch (error) {
    $("#installation").textContent = "Installation failed: " + error.message;
  }
}
$("#install").onclick = install;
$("#remove").onclick = () => {
  api?.destroy();
  $("#installation").textContent =
    "Console removed. Open console reinstalls it; recorded page-session rows were discarded.";
};
$("#counter").onclick = () => {
  $("#counter").textContent = `Count: ${++count}`;
  console.log("Device-lab counter", { count });
};
const fixture = new URL("./fixtures/response.json", import.meta.url).href;
$("#fetch").onclick = async () => {
  try {
    const response = await fetch(fixture);
    const body = await response.json();
    console.info("Device-lab fetch", response.status);
    $("#output").textContent = JSON.stringify(
      { source: "actual Fetch result", status: response.status, body },
      null,
      2,
    );
  } catch (error) {
    $("#output").textContent = "Fetch failed: " + error.message;
  }
};
function xhr(abort) {
  const request = new XMLHttpRequest(),
    events = [];
  for (const type of [
    "readystatechange",
    "load",
    "error",
    "abort",
    "timeout",
    "loadend",
  ])
    request.addEventListener(type, () => {
      events.push({
        type,
        readyState: request.readyState,
        status: request.status,
      });
      if (type === "loadend") {
        $("#output").textContent = JSON.stringify(
          { source: "actual XHR events", events },
          null,
          2,
        );
        console.info("Device-lab XHR ended", events);
      }
    });
  request.open("GET", fixture);
  request.send();
  if (abort) request.abort();
}
$("#xhr").onclick = () => xhr(false);
$("#abort").onclick = () => xhr(true);
$("#warning").onclick = () =>
  console.warn("Device-lab warning: an explicitly triggered fixture.");
$("#storage").onclick = () => {
  try {
    localStorage.setItem(
      "elyon-device-lab-note",
      "Written by the device-lab storage fixture.",
    );
    $("#output").textContent =
      "Demo key written. Open Storage to inspect, edit, or delete it.";
  } catch (error) {
    $("#output").textContent = "Storage denied: " + error.message;
  }
};
install();
