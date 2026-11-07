// App shell: hash router, navigation state and database status.

import { api } from "./api.js";
import { showBatch } from "./batch.js";
import { showCatalog } from "./catalog.js";
import { showLibrary } from "./library.js";
import { showMatch } from "./match.js";
import { showOverview } from "./overview.js";

const ROUTES = {
  overview: { title: "Overview", show: showOverview },
  library: { title: "Track library", show: showLibrary },
  match: { title: "Match a track", show: showMatch },
  batch: { title: "Batch match", show: showBatch },
  catalog: { title: "Match a file", show: showCatalog },
  rules: { title: "How matching works", show: () => {} },
};

const $ = (id) => document.getElementById(id);

function currentRoute() {
  const name = window.location.hash.replace(/^#\/?/, "");
  return ROUTES[name] ? name : "overview";
}

function navigate({ focus }) {
  const name = currentRoute();
  const route = ROUTES[name];

  for (const view of document.querySelectorAll("[data-view]")) view.hidden = view.dataset.view !== name;
  for (const link of document.querySelectorAll("[data-route]")) {
    if (link.dataset.route === name) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }

  document.title = `${route.title} · Music Metadata Intelligence`;
  closeMenu();
  route.show();

  if (focus) {
    const heading = document.querySelector(`[data-view="${name}"] h1`);
    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
  }
}

function closeMenu() {
  document.querySelector(".sidebar").classList.remove("is-open");
  document.querySelector(".menu-toggle").setAttribute("aria-expanded", "false");
}

async function checkDatabase() {
  const status = $("db-status");
  const text = status.querySelector(".db-status-text");
  try {
    await api.health();
    status.dataset.state = "ok";
    text.textContent = "Database connected";
  } catch (error) {
    status.dataset.state = "error";
    text.textContent = "Database unavailable";
  }
}

async function showVersion() {
  try {
    $("app-version").textContent = `v${await api.version()}`;
  } catch (error) {
    // Version is informational only.
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelector(".menu-toggle").addEventListener("click", (event) => {
    const sidebar = document.querySelector(".sidebar");
    const open = !sidebar.classList.contains("is-open");
    sidebar.classList.toggle("is-open", open);
    event.currentTarget.setAttribute("aria-expanded", String(open));
  });

  // The skip link moves focus without changing the route.
  document.querySelector(".skip-link").addEventListener("click", (event) => {
    event.preventDefault();
    $("main").focus();
  });

  window.addEventListener("hashchange", () => {
    // Only "#/name" hashes are routes; ignore in-page anchors.
    if (window.location.hash.startsWith("#/") || window.location.hash === "") navigate({ focus: true });
  });
  navigate({ focus: false });
  checkDatabase();
  showVersion();
});
