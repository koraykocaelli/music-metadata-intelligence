// Match analysis: candidate cards, verdicts and the shared filterable result
// list. Everything shown comes from API responses; nothing is recomputed here.

import {
  STATUS_LABELS,
  THRESHOLDS,
  classBadge,
  displayValue,
  el,
  formatScore,
  methodChip,
  ruleScale,
  statusBadge,
} from "./ui.js";

const VERDICTS = {
  matched: "A high-confidence candidate was found.",
  review: "Plausible candidates were found, but none reaches the high-confidence threshold. Confirm manually.",
  unmatched: "No reference track passed the matching rules.",
  invalid: "The input was rejected by validation and was not matched.",
};

function scaleTicks() {
  return el("div", { className: "scale-ticks", attrs: { "aria-hidden": "true" } }, [
    el("span", { text: "0" }),
    el("span", { className: "tick-80", text: String(THRESHOLDS.review) }),
    el("span", { className: "tick-95", text: String(THRESHOLDS.high) }),
  ]);
}

export function explainCandidate(match) {
  if (match.match_method === "isrc") {
    return "Found by ISRC: the identifier matches this recording exactly, so artist and title were not compared.";
  }
  const score = formatScore(match.score);
  if (match.classification === "high_confidence") {
    return `Artist and title passed every rule with a weighted score of ${score}, at or above the ${THRESHOLDS.high} high-confidence threshold.`;
  }
  return `Artist and title passed the matching rules, but ${score} is below ${THRESHOLDS.high}, so a person should confirm this candidate.`;
}

export function verdict(status, extra) {
  return el("div", { className: "verdict", attrs: { "data-status": status } }, [
    statusBadge(status),
    el("p", {}, [el("strong", { text: VERDICTS[status] || "" }), extra ? el("span", { text: ` ${extra}` }) : null]),
  ]);
}

function compareRow(label, inputValue, candidateValue) {
  const same =
    typeof inputValue === "string" &&
    typeof candidateValue === "string" &&
    inputValue.trim().toLowerCase() === candidateValue.trim().toLowerCase();
  return [
    el("dt", { text: label }),
    el("dd", { text: displayValue(inputValue), attrs: { "data-label": "Input" } }),
    el("dd", { className: same ? "same" : "", text: displayValue(candidateValue), attrs: { "data-label": "Candidate" } }),
  ];
}

/** One candidate with score, rule scale, classification, method and comparison. */
export function candidateCard(input, match, rank) {
  const card = el("article", { className: "candidate", attrs: { "data-method": match.match_method } });

  card.append(
    el("div", { className: "candidate-head" }, [
      el("div", { className: "candidate-name" }, [
        el("span", { className: "candidate-rank", text: `Candidate ${rank} · track #${match.track_id}` }),
        el("strong", { text: match.artist }),
        el("span", { text: match.title }),
      ]),
      el("div", { className: "candidate-tags" }, [methodChip(match.match_method), classBadge(match.classification)]),
    ]),
    el("div", { className: "candidate-score" }, [
      el("span", { className: "score-value", text: formatScore(match.score) }),
      el("div", { className: "scale-wrap" }, [ruleScale(match.score), scaleTicks()]),
    ]),
    el("p", { className: "explain", text: explainCandidate(match) }),
  );

  const compare = el("dl", { className: "compare" }, [
    el("dt", { className: "compare-head", text: "Field" }),
    el("dd", { className: "compare-head", text: "Input" }),
    el("dd", { className: "compare-head", text: "Candidate" }),
    ...compareRow("Artist", input.artist, match.artist),
    ...compareRow("Title", input.title, match.title),
  ]);
  card.append(compare);
  return card;
}

export function candidateList(input, matches) {
  return matches.map((match, index) => candidateCard(input, match, index + 1));
}

/**
 * Filterable list of result rows shared by batch and catalog matching.
 * rows: [{ status, indexLabel, input: {artist, title, album, isrc}, matches, errors }]
 */
export function createResultList({ meter, filters, list, emptyNote, reviewHint }) {
  let filter = "all";

  function applyFilter() {
    for (const button of filters.querySelectorAll(".filter")) {
      button.setAttribute("aria-pressed", String(button.dataset.filter === filter));
    }
    for (const segment of meter.querySelectorAll(".meter-segment")) {
      segment.classList.toggle("is-dimmed", filter !== "all" && segment.dataset.status !== filter);
      segment.setAttribute("aria-pressed", String(segment.dataset.status === filter));
    }
    let visible = 0;
    for (const row of list.children) {
      const show = filter === "all" || row.dataset.status === filter;
      row.hidden = !show;
      if (show) visible += 1;
    }
    emptyNote.hidden = visible > 0;
  }

  function setFilter(value) {
    filter = filter === value && value !== "all" ? "all" : value;
    applyFilter();
  }

  function renderSummary(counts, statuses) {
    meter.replaceChildren();
    filters.replaceChildren();

    const total = statuses.reduce((sum, status) => sum + counts[status], 0);
    const all = el("button", { className: "filter", attrs: { type: "button", "data-filter": "all" } }, [
      el("span", { className: "filter-count", text: total }),
      el("span", { text: "All" }),
    ]);
    all.addEventListener("click", () => setFilter("all"));
    filters.append(all);

    for (const status of statuses) {
      const count = counts[status];
      if (count > 0) {
        const segment = el("button", {
          className: "meter-segment",
          attrs: {
            type: "button",
            "data-status": status,
            "aria-label": `Show ${count} ${STATUS_LABELS[status].toLowerCase()} rows`,
            title: `${count} ${STATUS_LABELS[status].toLowerCase()}`,
          },
        });
        segment.style.flexGrow = String(count);
        segment.addEventListener("click", () => setFilter(status));
        meter.append(segment);
      }

      const button = el(
        "button",
        { className: "filter", attrs: { type: "button", "data-filter": status, "data-status": status } },
        [
          el("span", { className: "swatch", attrs: { "aria-hidden": "true" } }),
          el("span", { className: "filter-count", text: count }),
          el("span", { text: STATUS_LABELS[status] }),
        ],
      );
      button.addEventListener("click", () => setFilter(status));
      filters.append(button);
    }

    if (reviewHint) reviewHint.hidden = !counts.review;
  }

  function resultRow(row) {
    const best = row.matches[0];
    const details = el("details", { className: "result-row", attrs: { "data-status": row.status } });

    const summary = el("summary", {}, [
      el("span", { className: "row-index", text: row.indexLabel }),
      el("span", { className: "stack" }, [
        el("strong", { text: displayValue(row.input.artist, "(no artist)") }),
        el("span", { text: displayValue(row.input.title, "(no title)") }),
      ]),
      el("span", {}, [statusBadge(row.status)]),
      best
        ? el("span", { className: "stack" }, [el("strong", { text: best.artist }), el("span", { text: best.title })])
        : el("span", {
            className: "cell-faint",
            text: row.status === "invalid" ? "Fix the input to match" : "No candidate",
          }),
      el("span", { className: "row-score", text: best ? formatScore(best.score) : "—" }),
      el("span", {}, [best ? methodChip(best.match_method) : el("span", { className: "cell-faint", text: "—" })]),
    ]);
    details.append(summary);

    const detail = el("div", { className: "row-detail" });
    if (row.errors && row.errors.length) {
      detail.append(verdict("invalid"));
      const list = el("ul", { className: "row-errors" });
      for (const error of row.errors) {
        list.append(el("li", { text: error.field ? `${error.field}: ${error.message}` : error.message }));
      }
      detail.append(list);
    } else {
      const extra = row.matches.length > 1 ? `${row.matches.length} candidates.` : null;
      detail.append(verdict(row.status, extra), ...candidateList(row.input, row.matches));
    }
    details.append(detail);
    return details;
  }

  return {
    render(rows, statuses) {
      const counts = Object.fromEntries(statuses.map((status) => [status, 0]));
      for (const row of rows) counts[row.status] = (counts[row.status] || 0) + 1;
      filter = "all";
      renderSummary(counts, statuses);
      list.replaceChildren(...rows.map(resultRow));
      applyFilter();
    },
  };
}
