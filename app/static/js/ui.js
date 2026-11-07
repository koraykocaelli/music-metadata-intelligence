// DOM helpers. Untrusted text is only ever assigned with textContent.

export const STATUS_LABELS = {
  matched: "Matched",
  review: "Review",
  unmatched: "Unmatched",
  invalid: "Invalid",
};

export const CLASS_LABELS = {
  high_confidence: "High confidence",
  review: "Review",
  no_match: "No match",
};

export const METHOD_LABELS = { isrc: "ISRC", metadata: "Metadata" };

export const THRESHOLDS = { review: 80, high: 95 };

export function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined && options.text !== null) node.textContent = String(options.text);
  if (options.attrs) {
    for (const [name, value] of Object.entries(options.attrs)) {
      if (value !== undefined && value !== null) node.setAttribute(name, String(value));
    }
  }
  for (const child of children) if (child) node.append(child);
  return node;
}

export function statusBadge(status) {
  return el("span", { className: "badge", text: STATUS_LABELS[status] || status, attrs: { "data-status": status } });
}

export function classBadge(classification) {
  return el("span", {
    className: "badge",
    text: CLASS_LABELS[classification] || classification,
    attrs: { "data-class": classification },
  });
}

export function methodChip(method) {
  return el("span", {
    className: "method-chip",
    text: METHOD_LABELS[method] || method,
    attrs: { "data-method": method, title: method === "isrc" ? "Matched by ISRC identifier" : "Matched by artist and title" },
  });
}

/** The 0–100 rule scale with the real 80 / 95 boundaries and a score marker. */
export function ruleScale(score) {
  const value = Math.max(0, Math.min(100, Number(score) || 0));
  const marker = el("span", { className: "scale-marker" });
  marker.style.left = `${value}%`;
  return el(
    "div",
    {
      className: "scale",
      attrs: {
        role: "img",
        "aria-label": `Score ${value.toFixed(1)} on a 0 to 100 scale; review from ${THRESHOLDS.review}, high confidence from ${THRESHOLDS.high}`,
      },
    },
    [
      el("span", { className: "zone zone-none" }),
      el("span", { className: "zone zone-review" }),
      el("span", { className: "zone zone-high" }),
      marker,
    ],
  );
}

export function displayValue(value, fallback = "—") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export function formatScore(score) {
  return Number(score).toFixed(1);
}

const dateFormat = new Intl.DateTimeFormat("en", { dateStyle: "medium" });

export function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateFormat.format(date);
}

export function setBusy(button, busy, busyLabel) {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    if (busyLabel) button.textContent = busyLabel;
  } else if (button.dataset.label) {
    button.textContent = button.dataset.label;
  }
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
}

export function showError(node, message) {
  node.textContent = message || "";
  node.hidden = !message;
}

export function toast(message, tone = "matched") {
  const region = document.getElementById("toast-region");
  const item = el("div", { className: "toast", text: message, attrs: { "data-status": tone } });
  region.append(item);
  setTimeout(() => item.remove(), 4000);
}

export function foldForSearch(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase();
}

export function skeletonRows(tbody, columns, rows = 4) {
  tbody.replaceChildren(
    ...Array.from({ length: rows }, () =>
      el(
        "tr",
        { attrs: { "aria-hidden": "true" } },
        Array.from({ length: columns }, () => el("td", {}, [el("span", { className: "skeleton" })])),
      ),
    ),
  );
}
