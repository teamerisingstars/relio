// Relio Studio frontend — no build step, plain JS.
// All dynamic content is inserted via textContent / DOM APIs (never innerHTML),
// so user-supplied project names and paths can't inject markup.
"use strict";

const state = {
  projects: [],
  selected: null,   // project record
  logAction: null,  // action whose output is shown in the console
  logNext: 0,
  poller: null,
};

// ---- tiny DOM helpers ----
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") el[k.toLowerCase()] = v;
    else if (v !== undefined && v !== null) el.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null) continue;
    el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return el;
}
function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }

// Per-launch token injected into the page by the server; sent on every /api call.
const TOKEN = window.__RELIO_TOKEN__ || "";

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (TOKEN) opts.headers["X-Relio-Studio-Token"] = TOKEN;
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch("/api" + path, opts);
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) throw new Error((data && data.detail) || resp.statusText);
  return data;
}

function toast(msg, isErr) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 3200);
}

// ---- project list ----
async function loadProjects() {
  try {
    state.projects = await api("GET", "/projects");
  } catch (e) {
    toast("Failed to load projects: " + e.message, true);
    state.projects = [];
  }
  renderList();
}

function isRunning(rec) {
  const st = rec.status || {};
  return Object.values(st).some((s) => s.running);
}

function renderList() {
  const ul = $("#project-list");
  clear(ul);
  for (const p of state.projects) {
    const active = state.selected && state.selected.id === p.id;
    const tail = p.exists === false
      ? h("span", { class: "p-missing", text: "missing" })
      : h("span", { class: "badge", text: p.kind });
    const li = h("li", { class: active ? "active" : "", onClick: () => selectProject(p.id) },
      h("span", { class: "p-run " + (isRunning(p) ? "on" : "") }),
      h("span", { class: "p-name", text: p.name }),
      tail);
    ul.appendChild(li);
  }
}

function selectProject(id) {
  state.selected = state.projects.find((p) => p.id === id) || null;
  stopPolling();
  state.logAction = null;
  state.logNext = 0;
  $("#log").textContent = "";
  $("#log-status").className = "pill";
  $("#log-status").textContent = "";
  $("#open-app").hidden = true;
  $("#open-app").dataset.url = "";
  $("#check-result").hidden = true;
  clear($("#mem-wrap"));
  renderDetail();
  renderList();
}

function renderDetail() {
  const rec = state.selected;
  $("#empty").hidden = !!rec;
  $("#detail").hidden = !rec;
  if (!rec) return;
  $("#d-name").textContent = rec.name;
  $("#d-path").textContent = rec.path;
  $("#d-kind").textContent = rec.kind;
}

// ---- actions ----
async function runAction(action) {
  const rec = state.selected;
  if (!rec) return;
  const params = {};
  if (action === "serve") params.port = Number($("#serve-port").value) || 8000;
  if (action === "deploy") {
    params.name = $("#image-name").value || "relio-app";
    params.target = $("#deploy-target").value || "docker";
  }
  if (action === "sdk") params.out = $("#sdk-out").value || "sdk";
  try {
    const res = await api("POST", `/projects/${rec.id}/actions/${action}`, params);
    toast(`Started ${action}`);
    if (res.url) {
      const link = $("#open-app");
      link.href = res.url;
      link.hidden = false;
      link.dataset.url = res.url;
    }
    watchLogs(action);
    setTimeout(loadProjects, 500);
  } catch (e) {
    toast(`${action} failed: ` + e.message, true);
  }
}

async function stopAction(action) {
  const rec = state.selected;
  if (!rec) return;
  try {
    await api("POST", `/projects/${rec.id}/stop/${action}`);
    toast(`Stopped ${action}`);
    setTimeout(loadProjects, 300);
  } catch (e) {
    toast("Stop failed: " + e.message, true);
  }
}

// ---- log polling ----
function watchLogs(action) {
  stopPolling();
  state.logAction = action;
  state.logNext = 0;
  $("#log").textContent = "";
  $("#log-title").textContent = `Output — ${action}`;
  pollLogsOnce();
  state.poller = setInterval(pollLogsOnce, 1000);
}

async function pollLogsOnce() {
  const rec = state.selected;
  if (!rec || !state.logAction) return;
  try {
    const data = await api(
      "GET", `/projects/${rec.id}/logs/${state.logAction}?since=${state.logNext}`);
    if (data.lines.length) {
      const el = $("#log");
      const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 4;
      el.appendChild(document.createTextNode(data.lines.join("\n") + "\n"));
      if (atBottom) el.scrollTop = el.scrollHeight;
      state.logNext = data.next;
    }
    const pill = $("#log-status");
    if (data.running) {
      pill.className = "pill running";
      pill.textContent = "running";
    } else if (data.returncode === 0 || data.returncode === null) {
      pill.className = "pill ok";
      pill.textContent = data.returncode === 0 ? "done" : "";
      stopPolling();
    } else {
      pill.className = "pill fail";
      pill.textContent = "exit " + data.returncode;
      stopPolling();
    }
  } catch (e) {
    stopPolling();
  }
}

function stopPolling() {
  if (state.poller) clearInterval(state.poller);
  state.poller = null;
}

async function runCheck() {
  const rec = state.selected;
  if (!rec) return;
  const box = $("#check-result");
  box.hidden = false;
  box.className = "check-result";
  box.textContent = "Running check…";
  try {
    const data = await api("GET", `/projects/${rec.id}/check`);
    clear(box);
    if (!data.violations.length) {
      box.className = "check-result ok";
      box.appendChild(document.createTextNode("✓ Every module has a test and a doc."));
    } else {
      box.className = "check-result fail";
      box.appendChild(h("strong", { text: `${data.violations.length} violation(s):` }));
      const ul = h("ul", {});
      for (const v of data.violations) {
        ul.appendChild(h("li", { text: `${v.path} — missing ${v.missing}` }));
      }
      box.appendChild(ul);
    }
  } catch (e) {
    box.className = "check-result fail";
    box.textContent = "check failed: " + e.message;
  }
}

function showMemory() {
  const wrap = $("#mem-wrap");
  clear(wrap);
  const link = $("#open-app");
  const url = link.dataset.url;
  if (url && !link.hidden) {
    wrap.appendChild(h("iframe", { src: url, title: "app" }));
  } else {
    wrap.appendChild(h("div", { class: "placeholder" },
      "Start dev or serve in the Run tab, then come back here."));
  }
}

// ---- modals ----
function openModal(title, bodyNodes, onOk) {
  $("#modal-title").textContent = title;
  const body = $("#modal-body");
  clear(body);
  for (const n of bodyNodes) body.appendChild(n);
  $("#modal-ok").textContent = "OK";
  $("#modal").hidden = false;
  $("#modal-ok").onclick = async () => { if (await onOk()) closeModal(); };
}
function closeModal() { $("#modal").hidden = true; }

function field(labelText, input) {
  return [h("label", { text: labelText }), input];
}

function newProjectModal() {
  const name = h("input", { class: "input", id: "np-name", placeholder: "my-app" });
  const parent = h("input", { class: "input", id: "np-parent", placeholder: "C:\\work  or  /home/you/work" });
  const kind = h("select", { id: "np-kind" },
    h("option", { value: "app", text: "app — zero-build HTML starter" }),
    h("option", { value: "web", text: "web — React + Vite" }),
    h("option", { value: "mobile", text: "mobile — React Native / Expo" }),
    h("option", { value: "desktop", text: "desktop — Tauri" }),
    h("option", { value: "ai", text: "ai — AIApp (agent + memory)" }));
  openModal("New project",
    [...field("Name", name), ...field("Parent folder (absolute path)", parent), ...field("Kind", kind)],
    async () => {
      const n = name.value.trim(), p = parent.value.trim(), k = kind.value;
      if (!n || !p) { toast("Name and parent folder are required", true); return false; }
      try {
        const rec = await api("POST", "/projects", { name: n, parent_dir: p, kind: k });
        toast("Created " + rec.name);
        await loadProjects();
        selectProject(rec.id);
        return true;
      } catch (e) { toast("Create failed: " + e.message, true); return false; }
    });
}

function importModal() {
  const path = h("input", { class: "input", id: "imp-path", placeholder: "path to a folder with app.py" });
  openModal("Add existing project", field("Project folder (absolute path)", path), async () => {
    const p = path.value.trim();
    if (!p) return false;
    try {
      const rec = await api("POST", "/projects/import", { path: p });
      toast("Added " + rec.name);
      await loadProjects();
      selectProject(rec.id);
      return true;
    } catch (e) { toast("Import failed: " + e.message, true); return false; }
  });
}

function scanModal() {
  const path = h("input", { class: "input", id: "scan-path", placeholder: "folder containing projects" });
  const found = h("ul", { class: "scan-found" });
  const go = h("button", { class: "btn", style: "margin-top:10px", text: "Scan" });
  openModal("Scan folder", [...field("Workspace folder to scan", path), go, found], async () => true);
  $("#modal-ok").textContent = "Done";
  go.onclick = async () => {
    const folder = path.value.trim();
    if (!folder) return;
    try {
      const data = await api("POST", "/projects/scan", { folder });
      clear(found);
      if (!data.found.length) { found.appendChild(h("li", { text: "No Relio projects found." })); return; }
      for (const p of data.found) {
        const add = h("button", { class: "btn", text: "Add" });
        add.onclick = async () => {
          try { await api("POST", "/projects/import", { path: p }); add.textContent = "Added"; add.disabled = true; loadProjects(); }
          catch (e) { toast(e.message, true); }
        };
        found.appendChild(h("li", {}, h("span", { text: p }), add));
      }
    } catch (e) { toast("Scan failed: " + e.message, true); }
  };
}

async function removeProject() {
  const rec = state.selected;
  if (!rec) return;
  if (!confirm(`Remove "${rec.name}" from Studio? (Files are kept on disk.)`)) return;
  try {
    await api("DELETE", `/projects/${rec.id}`);
    state.selected = null;
    renderDetail();
    await loadProjects();
  } catch (e) { toast("Remove failed: " + e.message, true); }
}

// ---- wire up ----
function init() {
  $("#btn-new").onclick = newProjectModal;
  $("#btn-import").onclick = importModal;
  $("#btn-scan").onclick = scanModal;
  $("#btn-refresh").onclick = loadProjects;
  $("#btn-remove").onclick = removeProject;
  $("#btn-check").onclick = runCheck;
  $("#btn-clear-log").onclick = () => { $("#log").textContent = ""; };
  $("#modal-cancel").onclick = closeModal;
  $("#modal").onclick = (e) => { if (e.target.id === "modal") closeModal(); };

  $$(".tab").forEach((tab) => {
    tab.onclick = () => {
      $$(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const pane = tab.dataset.tab;
      $$(".tabpane").forEach((p) => (p.hidden = p.dataset.pane !== pane));
      if (pane === "memory") showMemory();
    };
  });

  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-action]");
    if (a) runAction(a.dataset.action);
    const s = e.target.closest("[data-stop]");
    if (s) stopAction(s.dataset.stop);
  });

  loadProjects();
  setInterval(() => { if (!state.poller) loadProjects(); }, 5000);
}

document.addEventListener("DOMContentLoaded", init);
