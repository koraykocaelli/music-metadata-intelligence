// Batch matching via POST /api/v1/tracks/batch/match (read-only, max 100).

import { createResultList } from "./analysis.js";
import { api, validationErrors } from "./api.js";
import { el, setBusy, showError } from "./ui.js";

const MAX_ROWS = 100;
const FIELDS = ["artist", "title", "album", "isrc"];
const FIELD_LABELS = { artist: "Artist", title: "Title", album: "Album", isrc: "ISRC" };
const $ = (id) => document.getElementById(id);

// Sample inputs only (fictional metadata); results always come from the API.
const SAMPLE_ROWS = [
  { artist: "Neon Harbor", title: "Midnight Signal (Official Audio)", album: "", isrc: "ZZNHB2600001" },
  { artist: "Luna Vael", title: "Paper Satellites", album: "Orbit Notes", isrc: "" },
  { artist: "Glass Orchard", title: "Slow Motion Summer", album: "", isrc: "" },
  { artist: "SILVER ÉCHO", title: "Golden Hour", album: "", isrc: "" },
  { artist: "Unknown Collective", title: "Brand New Song", album: "", isrc: "" },
];

let rows = [];
let resultList = null;

const emptyRow = () => ({ artist: "", title: "", album: "", isrc: "" });
const isBlank = (row) => FIELDS.every((field) => !row[field].trim());

function renderEditor() {
  const body = $("batch-rows");
  body.replaceChildren();

  rows.forEach((row, index) => {
    const tr = el("tr", { attrs: { "data-row": index } }, [el("td", { className: "num", text: index + 1 })]);
    for (const field of FIELDS) {
      const input = el("input", {
        className: field === "isrc" ? "mono" : "",
        attrs: {
          type: "text",
          value: row[field],
          maxlength: field === "isrc" ? 15 : 255,
          "aria-label": `${FIELD_LABELS[field]}, row ${index + 1}`,
          "data-field": field,
          autocomplete: "off",
        },
      });
      input.value = row[field];
      input.addEventListener("input", () => {
        rows[index][field] = input.value;
      });
      tr.append(el("td", {}, [input]));
    }
    const remove = el("button", {
      className: "icon-button",
      text: "×",
      attrs: { type: "button", "aria-label": `Remove row ${index + 1}` },
    });
    remove.disabled = rows.length === 1;
    remove.addEventListener("click", () => {
      rows.splice(index, 1);
      renderEditor();
    });
    tr.append(el("td", {}, [remove]));
    body.append(tr);
  });

  const filled = rows.filter((row) => !isBlank(row)).length;
  $("batch-row-count").textContent = `${filled} of ${MAX_ROWS} max`;
  $("batch-add").disabled = rows.length >= MAX_ROWS;
}

function showRowErrors(errorsByRow) {
  for (const [rowIndex, messages] of errorsByRow) {
    const tr = $("batch-rows").querySelector(`tr[data-row="${rowIndex}"]`);
    if (!tr) continue;
    for (const { field } of messages) {
      const input = tr.querySelector(`input[data-field="${field}"]`);
      if (input) input.setAttribute("aria-invalid", "true");
    }
    const note = el("tr", { className: "row-error" }, [
      el("td"),
      el("td", { attrs: { colspan: 5 } }, [
        el("p", {
          text: messages.map((item) => `${FIELD_LABELS[item.field] || item.field}: ${item.message}`).join(" "),
        }),
      ]),
    ]);
    tr.after(note);
  }
}

async function submit() {
  const error = $("batch-error");
  showError(error, "");
  $("batch-status").textContent = "";
  renderEditor();

  // Blank rows are skipped; remember which editor row each request item is.
  const sent = [];
  const payload = [];
  rows.forEach((row, index) => {
    if (isBlank(row)) return;
    const track = { artist: row.artist, title: row.title };
    if (row.album.trim()) track.album = row.album;
    if (row.isrc.trim()) track.isrc = row.isrc;
    sent.push(index);
    payload.push(track);
  });

  if (!payload.length) {
    showError(error, "Add at least one track with an artist and a title.");
    return;
  }

  const missing = new Map();
  payload.forEach((track, i) => {
    const fields = ["artist", "title"].filter((field) => !track[field].trim());
    if (fields.length) missing.set(sent[i], fields.map((field) => ({ field, message: "Required." })));
  });
  if (missing.size) {
    showRowErrors(missing);
    showError(error, `${missing.size} row${missing.size === 1 ? " needs" : "s need"} an artist and a title.`);
    return;
  }

  const button = $("batch-submit");
  setBusy(button, true, "Matching…");
  $("batch-status").textContent = `Matching ${payload.length} track${payload.length === 1 ? "" : "s"}…`;

  try {
    const response = await api.matchBatch(payload);
    const results = response.results.map((result) => ({
      status: result.status,
      indexLabel: `Row ${sent[result.input_index] + 1}`,
      input: payload[result.input_index],
      matches: result.matches,
      errors: [],
    }));
    resultList.render(results, ["matched", "review", "unmatched"]);
    $("batch-results").hidden = false;
    $("batch-status").textContent =
      `Matched ${response.total} track${response.total === 1 ? "" : "s"}: ${response.matched} matched, ${response.review} review, ${response.unmatched} unmatched.`;
  } catch (err) {
    const fieldErrors = validationErrors(err);
    const byRow = new Map();
    const general = [];
    for (const item of fieldErrors) {
      const [, requestIndex, field] = item.path;
      if (item.path[0] === "tracks" && Number.isInteger(requestIndex) && FIELDS.includes(field)) {
        const editorIndex = sent[requestIndex];
        if (!byRow.has(editorIndex)) byRow.set(editorIndex, []);
        byRow.get(editorIndex).push({ field, message: item.message });
      } else {
        general.push(item.message);
      }
    }
    if (byRow.size) {
      showRowErrors(byRow);
      showError(
        error,
        `${byRow.size} row${byRow.size === 1 ? " has" : "s have"} invalid values. The batch was not matched; fix the highlighted rows and try again.`,
      );
    } else {
      showError(error, general.length ? general.join(" ") : err.message);
    }
    $("batch-status").textContent = "";
    $("batch-results").hidden = true;
  } finally {
    setBusy(button, false);
  }
}

let initialized = false;

export function showBatch() {
  if (initialized) return;
  initialized = true;

  rows = Array.from({ length: 3 }, emptyRow);
  resultList = createResultList({
    meter: $("batch-meter"),
    filters: $("batch-filters"),
    list: $("batch-list"),
    emptyNote: $("batch-empty-filter"),
    reviewHint: $("batch-review-hint"),
  });

  $("batch-add").addEventListener("click", () => {
    if (rows.length >= MAX_ROWS) return;
    rows.push(emptyRow());
    renderEditor();
    const inputs = $("batch-rows").querySelectorAll('input[data-field="artist"]');
    inputs[inputs.length - 1].focus();
  });
  $("batch-sample").addEventListener("click", () => {
    rows = SAMPLE_ROWS.map((row) => ({ ...row }));
    renderEditor();
  });
  $("batch-clear").addEventListener("click", () => {
    rows = Array.from({ length: 3 }, emptyRow);
    showError($("batch-error"), "");
    $("batch-status").textContent = "";
    $("batch-results").hidden = true;
    renderEditor();
  });
  $("batch-submit").addEventListener("click", submit);
  renderEditor();
}
