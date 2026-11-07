// Track library: list, search, sort, and add reference tracks.

import { api, validationErrors } from "./api.js";
import { prefillMatch } from "./match.js";
import { displayValue, el, foldForSearch, formatDate, setBusy, showError, skeletonRows, toast } from "./ui.js";

const PAGE_SIZE = 50;
const $ = (id) => document.getElementById(id);

const state = {
  tracks: [],
  loaded: false,
  query: "",
  isrcOnly: false,
  sort: { key: "created_at", direction: "descending" },
  limit: PAGE_SIZE,
};

function compare(a, b, key) {
  const left = a[key] ?? "";
  const right = b[key] ?? "";
  if (key === "created_at") return new Date(left) - new Date(right);
  return String(left).localeCompare(String(right), "en", { sensitivity: "base" });
}

function visibleTracks() {
  const query = foldForSearch(state.query.trim());
  const filtered = state.tracks.filter((track) => {
    if (state.isrcOnly && !track.isrc) return false;
    if (!query) return true;
    return [track.artist, track.title, track.album, track.isrc].some((value) => foldForSearch(value).includes(query));
  });
  const factor = state.sort.direction === "ascending" ? 1 : -1;
  return filtered.sort((a, b) => factor * compare(a, b, state.sort.key));
}

function trackRow(track) {
  const matchButton = el("button", {
    className: "button ghost",
    text: "Match",
    attrs: { type: "button", "aria-label": `Find matches for ${track.artist} — ${track.title}` },
  });
  matchButton.addEventListener("click", () => {
    prefillMatch(track);
    window.location.hash = "#/match";
  });

  return el("tr", {}, [
    el("td", { className: "cell-strong", text: track.artist }),
    el("td", { text: track.title }),
    el("td", { className: "cell-soft", text: displayValue(track.album) }),
    el("td", {}, [track.isrc ? el("span", { className: "isrc", text: track.isrc }) : el("span", { className: "cell-faint", text: "—" })]),
    el("td", { className: "cell-soft", text: formatDate(track.created_at) }),
    el("td", { className: "num" }, [matchButton]),
  ]);
}

function render() {
  const body = $("library-body");
  const stateBox = $("library-state");
  const tracks = visibleTracks();
  const shown = tracks.slice(0, state.limit);

  body.replaceChildren(...shown.map(trackRow));
  $("library-more").hidden = tracks.length <= state.limit;

  const total = state.tracks.length;
  $("library-count").textContent =
    tracks.length === total ? `${total.toLocaleString("en")} tracks` : `${tracks.length.toLocaleString("en")} of ${total.toLocaleString("en")} tracks`;

  stateBox.replaceChildren();
  if (!total) {
    const add = el("button", { className: "button secondary", text: "Add the first track", attrs: { type: "button" } });
    add.addEventListener("click", openDialog);
    stateBox.append(
      el("strong", { text: "The reference catalog is empty" }),
      el("p", { text: "Add reference tracks to match incoming metadata against them." }),
      add,
    );
  } else if (!tracks.length) {
    stateBox.append(el("strong", { text: "No tracks match your search" }), el("p", { text: "Try a different artist, title, album or ISRC." }));
  }

  for (const button of document.querySelectorAll("#library-table .sort")) {
    const active = button.dataset.sort === state.sort.key;
    if (active) button.setAttribute("aria-sort", state.sort.direction);
    else button.removeAttribute("aria-sort");
    button.closest("th").setAttribute("aria-sort", active ? state.sort.direction : "none");
  }
}

async function load() {
  const body = $("library-body");
  const stateBox = $("library-state");
  skeletonRows(body, 6);
  stateBox.replaceChildren();
  $("library-count").textContent = "Loading…";

  try {
    state.tracks = await api.listTracks();
    state.loaded = true;
    render();
  } catch (error) {
    body.replaceChildren();
    $("library-count").textContent = "";
    const retry = el("button", { className: "button secondary", text: "Try again", attrs: { type: "button" } });
    retry.addEventListener("click", load);
    stateBox.replaceChildren(el("strong", { text: "Could not load tracks" }), el("p", { text: error.message }), retry);
  }
}

// --- Add track dialog -------------------------------------------------------

const FIELDS = ["artist", "title", "album", "isrc"];

function clearFieldErrors(form) {
  for (const input of form.querySelectorAll("input")) input.removeAttribute("aria-invalid");
  for (const node of form.querySelectorAll(".field-error")) node.remove();
}

function markField(form, field, message) {
  if (!FIELDS.includes(field)) return false;
  const input = form.elements[field];
  if (!input) return false;
  input.setAttribute("aria-invalid", "true");
  const note = el("p", { className: "field-error", text: message, attrs: { id: `${input.id}-error` } });
  input.setAttribute("aria-describedby", note.id);
  input.closest(".field").append(note);
  return true;
}

function openDialog() {
  const dialog = $("add-track-dialog");
  const form = $("add-track-form");
  form.reset();
  clearFieldErrors(form);
  showError($("add-track-error"), "");
  dialog.showModal();
  $("add-artist").focus();
}

async function submitTrack(event) {
  event.preventDefault();
  const form = $("add-track-form");
  const submit = $("add-track-submit");
  clearFieldErrors(form);
  showError($("add-track-error"), "");

  const data = Object.fromEntries(FIELDS.map((field) => [field, form.elements[field].value]));
  let missing = false;
  for (const field of ["artist", "title"]) {
    if (!data[field].trim()) missing = markField(form, field, "Required.") || missing;
  }
  if (missing) return;

  const payload = { artist: data.artist, title: data.title };
  if (data.album.trim()) payload.album = data.album;
  if (data.isrc.trim()) payload.isrc = data.isrc;

  setBusy(submit, true, "Adding…");
  try {
    const track = await api.createTrack(payload);
    $("add-track-dialog").close();
    toast(`Added ${track.artist} — ${track.title} to the reference catalog.`);
    await load();
  } catch (error) {
    const fieldErrors = validationErrors(error);
    const unmapped = fieldErrors.filter((item) => !markField(form, item.field, item.message));
    if (!fieldErrors.length || unmapped.length) {
      showError($("add-track-error"), unmapped.length ? unmapped.map((item) => item.message).join(" ") : error.message);
    }
  } finally {
    setBusy(submit, false);
  }
}

let initialized = false;

function init() {
  $("library-search").addEventListener("input", (event) => {
    state.query = event.target.value;
    state.limit = PAGE_SIZE;
    render();
  });
  $("library-isrc-only").addEventListener("change", (event) => {
    state.isrcOnly = event.target.checked;
    state.limit = PAGE_SIZE;
    render();
  });
  for (const button of document.querySelectorAll("#library-table .sort")) {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      state.sort =
        state.sort.key === key
          ? { key, direction: state.sort.direction === "ascending" ? "descending" : "ascending" }
          : { key, direction: key === "created_at" ? "descending" : "ascending" };
      render();
    });
  }
  $("library-more").addEventListener("click", () => {
    state.limit += PAGE_SIZE;
    render();
  });
  $("add-track-open").addEventListener("click", openDialog);
  $("add-track-cancel").addEventListener("click", () => $("add-track-dialog").close());
  $("add-track-form").addEventListener("submit", submitTrack);
}

export function showLibrary() {
  if (!initialized) {
    init();
    initialized = true;
  }
  load();
}
