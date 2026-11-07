// Single-track matching via POST /api/v1/tracks/similar.

import { candidateList, verdict } from "./analysis.js";
import { api, validationErrors } from "./api.js";
import { el, setBusy, showError } from "./ui.js";

const FIELDS = ["artist", "title", "album", "isrc"];
const INPUT_IDS = { artist: "match-artist", title: "match-title-input", album: "match-album", isrc: "match-isrc" };
const $ = (id) => document.getElementById(id);

let pendingPrefill = null;

export function prefillMatch(track) {
  pendingPrefill = track;
}

function form() {
  return $("match-form");
}

function clearFieldErrors() {
  for (const field of FIELDS) {
    const input = $(INPUT_IDS[field]);
    input.removeAttribute("aria-invalid");
    const describedBy = (input.getAttribute("aria-describedby") || "").split(" ").filter((id) => !id.endsWith("-error"));
    if (describedBy.length) input.setAttribute("aria-describedby", describedBy.join(" "));
    else input.removeAttribute("aria-describedby");
  }
  for (const node of form().querySelectorAll(".field-error")) node.remove();
  showError($("match-form-error"), "");
}

function markField(field, message) {
  if (!FIELDS.includes(field)) return false;
  const input = $(INPUT_IDS[field]);
  const note = el("p", { className: "field-error", text: message, attrs: { id: `${input.id}-error` } });
  input.setAttribute("aria-invalid", "true");
  input.setAttribute("aria-describedby", [input.getAttribute("aria-describedby"), note.id].filter(Boolean).join(" "));
  input.closest(".field").append(note);
  return true;
}

function placeholder() {
  return el("div", { className: "placeholder" }, [
    el("h2", { text: "Candidates appear here" }),
    el("p", {
      text: "Each candidate shows its similarity score on the rule scale, its classification and whether it was found by ISRC or by artist and title.",
    }),
  ]);
}

function statusFor(matches) {
  if (!matches.length) return "unmatched";
  return matches.some((match) => match.classification === "high_confidence") ? "matched" : "review";
}

function renderResults(input, matches) {
  const pane = $("match-results");
  const heading = el("h2", { className: "section-title", text: "Candidates", attrs: { tabindex: "-1" } });
  const nodes = [heading];

  if (!matches.length) {
    nodes.push(
      verdict("unmatched"),
      el("p", {
        className: "explain",
        text: "Only the reference catalog in the connected database was searched. Either it has no similar track, or a similar track was rejected by a rule (for example a different version such as a remix or live recording). This does not mean the recording does not exist elsewhere. Nothing was added to the catalog.",
      }),
    );
  } else {
    const isrc = matches[0].match_method === "isrc";
    const extra = isrc ? "Matched by ISRC." : `${matches.length} candidate${matches.length === 1 ? "" : "s"} by artist and title.`;
    nodes.push(verdict(statusFor(matches), extra), ...candidateList(input, matches));
  }
  pane.replaceChildren(...nodes);
  heading.focus({ preventScroll: true });
}

async function submit(event) {
  event.preventDefault();
  clearFieldErrors();

  const values = Object.fromEntries(FIELDS.map((field) => [field, $(INPUT_IDS[field]).value]));
  let missing = false;
  for (const field of ["artist", "title"]) {
    if (!values[field].trim()) missing = markField(field, "Required.") || missing;
  }
  if (missing) return;

  const payload = { artist: values.artist, title: values.title };
  if (values.album.trim()) payload.album = values.album;
  if (values.isrc.trim()) payload.isrc = values.isrc;

  const button = $("match-submit");
  setBusy(button, true, "Matching…");
  $("match-results").setAttribute("aria-busy", "true");
  try {
    const matches = await api.matchTrack(payload);
    renderResults(payload, matches);
  } catch (error) {
    const errors = validationErrors(error);
    const unmapped = errors.filter((item) => !markField(item.field, item.message));
    if (!errors.length || unmapped.length) {
      showError($("match-form-error"), unmapped.length ? unmapped.map((item) => item.message).join(" ") : error.message);
    }
  } finally {
    setBusy(button, false);
    $("match-results").removeAttribute("aria-busy");
  }
}

let initialized = false;

export function showMatch() {
  if (!initialized) {
    form().addEventListener("submit", submit);
    $("match-clear").addEventListener("click", () => {
      form().reset();
      clearFieldErrors();
      $("match-results").replaceChildren(placeholder());
      $("match-artist").focus();
    });
    initialized = true;
  }

  if (pendingPrefill) {
    const track = pendingPrefill;
    pendingPrefill = null;
    clearFieldErrors();
    for (const field of FIELDS) $(INPUT_IDS[field]).value = track[field] || "";
    form().requestSubmit();
  }
}
