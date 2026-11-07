// Catalog file matching via /api/v1/catalog/match and /match/export.

import { createResultList } from "./analysis.js";
import { ApiError, postFile } from "./api.js";
import { el, setBusy } from "./ui.js";

const MAX_BYTES = 1024 * 1024;
const MATCH_URL = "/api/v1/catalog/match";
const EXPORT_URL = "/api/v1/catalog/match/export";
const $ = (id) => document.getElementById(id);

const state = { file: null, busy: false };
let resultList = null;

function contentTypeFor(name) {
  const lower = name.toLowerCase();
  if (lower.endsWith(".csv")) return "text/csv; charset=utf-8";
  if (lower.endsWith(".json")) return "application/json";
  return null;
}

function formatBytes(bytes) {
  return bytes < 1024 ? `${bytes} bytes` : `${(bytes / 1024).toFixed(1)} KB`;
}

function setStatus(message, isError = false) {
  const status = $("upload-status");
  status.textContent = message;
  status.classList.toggle("is-error", isError);
}

function setBusyState(busy) {
  state.busy = busy;
  $("match-button").disabled = busy || !state.file;
  for (const button of document.querySelectorAll("[data-download], [data-example]")) button.disabled = busy;
}

function selectFile(name, blob) {
  const contentType = contentTypeFor(name);
  const fileName = $("file-name");
  fileName.classList.remove("is-empty");

  if (!contentType) {
    state.file = null;
    fileName.textContent = "No file selected";
    fileName.classList.add("is-empty");
    setStatus("Choose a .csv or .json file.", true);
  } else if (blob.size > MAX_BYTES) {
    state.file = null;
    fileName.textContent = name;
    setStatus(`This file is ${formatBytes(blob.size)}. The limit is 1 MB.`, true);
  } else {
    state.file = { name, blob, contentType };
    fileName.textContent = `${name} (${formatBytes(blob.size)})`;
    setStatus("Ready to match.");
  }
  setBusyState(false);
}

function toRows(result) {
  return result.results.map((row) => ({
    status: row.status,
    indexLabel: row.line_number ? `Line ${row.line_number}` : `#${row.input_index + 1}`,
    input: { artist: row.artist, title: row.title, album: row.album, isrc: row.isrc },
    matches: row.matches,
    errors: row.errors,
  }));
}

async function matchCatalog() {
  if (!state.file || state.busy) return;
  const button = $("match-button");
  setBusyState(true);
  setBusy(button, true, "Matching…");
  setStatus(`Matching ${state.file.name}…`);

  try {
    const result = await (await postFile(MATCH_URL, state.file.blob, state.file.contentType)).json();
    resultList.render(toRows(result), ["matched", "review", "unmatched", "invalid"]);

    const ignored = $("ignored");
    ignored.hidden = !result.ignored_columns.length;
    ignored.textContent = result.ignored_columns.length ? `Ignored columns: ${result.ignored_columns.join(", ")}` : "";

    const total = result.summary.total;
    setStatus(`Matched ${total} ${total === 1 ? "row" : "rows"} from ${state.file.name}.`);
    $("results").hidden = false;
    $("results-heading").focus({ preventScroll: true });
    $("results").scrollIntoView({ block: "start", behavior: "auto" });
  } catch (error) {
    setStatus(error instanceof ApiError ? error.message : "Matching failed.", true);
  } finally {
    setBusy(button, false);
    setBusyState(false);
  }
}

async function download(format) {
  if (!state.file || state.busy) return;
  setBusyState(true);
  setStatus(`Preparing ${format.toUpperCase()} download…`);

  try {
    const response = await postFile(`${EXPORT_URL}?format=${encodeURIComponent(format)}`, state.file.blob, state.file.contentType);
    const url = URL.createObjectURL(await response.blob());
    const link = el("a", { attrs: { href: url, download: `catalog_match_results.${format}` } });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setStatus(`Downloaded catalog_match_results.${format}.`);
  } catch (error) {
    setStatus(error instanceof ApiError ? error.message : "Download failed.", true);
  } finally {
    setBusyState(false);
  }
}

async function loadExample(name) {
  if (state.busy) return;
  setStatus(`Loading ${name}…`);
  try {
    const response = await fetch(`/examples/${encodeURIComponent(name)}`);
    if (!response.ok) {
      setStatus("The example catalog is not available.", true);
      return;
    }
    selectFile(name, await response.blob());
    await matchCatalog();
  } catch (error) {
    setStatus("Could not reach the server. Check that the application is running.", true);
  }
}

let initialized = false;

export function showCatalog() {
  if (initialized) return;
  initialized = true;

  resultList = createResultList({
    meter: $("meter"),
    filters: $("legend"),
    list: $("rows-body"),
    emptyNote: $("empty-filter"),
  });

  $("file-input").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) selectFile(file.name, file);
  });
  $("match-button").addEventListener("click", matchCatalog);
  for (const button of document.querySelectorAll("[data-example]")) {
    button.addEventListener("click", () => loadExample(button.dataset.example));
  }
  for (const button of document.querySelectorAll("[data-download]")) {
    button.addEventListener("click", () => download(button.dataset.download));
  }
}
