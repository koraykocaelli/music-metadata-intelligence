// Overview: metrics derived only from GET /api/v1/tracks.

import { api } from "./api.js";
import { displayValue, formatDate, showError } from "./ui.js";

const $ = (id) => document.getElementById(id);

function setMetric(id, value) {
  $(id).textContent = value;
}

export async function showOverview() {
  const error = $("overview-error");
  showError(error, "");
  for (const id of ["metric-tracks", "metric-isrc", "metric-artists", "metric-latest"]) setMetric(id, "…");

  try {
    const tracks = await api.listTracks();
    const total = tracks.length;
    const withIsrc = tracks.filter((track) => track.isrc).length;
    const artists = new Set(tracks.map((track) => track.normalized_artist || track.artist)).size;
    const latest = tracks.reduce(
      (newest, track) => (!newest || new Date(track.created_at) > new Date(newest.created_at) ? track : newest),
      null,
    );

    setMetric("metric-tracks", total.toLocaleString("en"));
    setMetric("metric-isrc", total ? `${Math.round((withIsrc / total) * 100)}%` : "—");
    $("metric-isrc-note").textContent = total
      ? `${withIsrc.toLocaleString("en")} of ${total.toLocaleString("en")} tracks have an ISRC`
      : "No tracks yet";
    setMetric("metric-artists", artists.toLocaleString("en"));
    setMetric("metric-latest", latest ? `${displayValue(latest.artist)} — ${displayValue(latest.title)}` : "—");
    $("metric-latest-note").textContent = latest ? `Added ${formatDate(latest.created_at)}` : "No tracks yet";
  } catch (err) {
    for (const id of ["metric-tracks", "metric-isrc", "metric-artists", "metric-latest"]) setMetric(id, "—");
    showError(error, `Could not load catalog metrics. ${err.message}`);
  }
}
