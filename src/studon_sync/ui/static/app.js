"use strict";
let api, S = {}, state = null, polling = null, logNext = 0;
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const t = (key, vars = {}) => (S[key] || key).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtDate = iso => iso ? new Date(iso).toLocaleDateString(undefined, { year: "2-digit", month: "2-digit", day: "2-digit" }) : "";
const fmtWhen = iso => iso ? new Date(iso).toLocaleString(undefined, { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "";

window.addEventListener("pywebviewready", init);
window.addEventListener("unhandledrejection", e => console.error("unhandled:", e.reason && e.reason.stack || e.reason));

async function init() {
  api = window.pywebview.api;
  S = await api.strings();
  $$("[data-t]").forEach(el => (el.textContent = t(el.dataset.t)));
  $$("[data-tp]").forEach(el => (el.placeholder = t(el.dataset.tp)));
  bindNav(); bindSync(); bindCourses(); bindFiles(); bindAccount();
  await refresh();
  const p = await api.progress(0);
  if (p.job) watchJob();
}

async function refresh() {
  state = await api.state();
  renderSync(); renderCourses(); renderCourseSelect(); renderAccount();
  const pending = state.courses.reduce((n, c) => n + c.pending, 0);
  $("#pending-pill").hidden = !pending;
  $("#pending-pill").textContent = pending;
}

/* ---------- navigation ---------- */
function bindNav() {
  $$("nav button").forEach(b => b.addEventListener("click", () => show(b.dataset.view)));
}
function show(view) {
  $$("nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + view));
  if (view === "files") loadTree();
}

/* ---------- sync ---------- */
function bindSync() {
  $("#sync-btn").addEventListener("click", async () => {
    const r = await api.start_sync(null);
    if (!r.ok) return alert(r.error);
    show("sync"); $("#log").textContent = ""; watchJob();
  });
  $("#open-logs").addEventListener("click", () => api.open_folder(""));
  $$("#sched-mode button").forEach(b => b.addEventListener("click", () => saveSchedule(b.dataset.mode)));
  $("#sched-time").addEventListener("change", () => saveSchedule());
  $("#sched-hours").addEventListener("change", () => saveSchedule());
}

function renderSync() {
  const last = state.last_sync
    ? t("sync.last", { when: fmtWhen(state.last_sync), result: t(state.last_sync_ok ? "sync.ok" : "sync.failed") })
    : t("sync.never");
  $("#last-sync").textContent = last;
  $("#brand-status").textContent = state.job ? t("sync.running") : (state.last_sync ? fmtWhen(state.last_sync) : "");
  $("#course-cards").innerHTML = state.courses.length ? state.courses.map(c => `
    <div class="card ccard ${c.enabled ? "" : "off"}">
      <h3>${esc(c.title)}</h3>
      <div class="label">${c.enabled ? "" : t("crs.disabled")}</div>
      <div class="stats">
        <div><b>${c.files}</b><span>${t("sync.files")}</span></div>
        ${c.pending ? `<div><b style="color:var(--warn)">${c.pending}</b><span>${t("sync.pending")}</span></div>` : ""}
      </div>
    </div>`).join("") : `<div class="card empty">${t("sync.no_courses")}</div>`;
  const s = state.schedule;
  $$("#sched-mode button").forEach(b => b.classList.toggle("on", b.dataset.mode === s.mode));
  $("#sched-time").value = s.time; $("#sched-hours").value = s.hours;
  $("#sched-time-wrap").hidden = s.mode !== "daily";
  $("#sched-hours-wrap").hidden = s.mode !== "interval";
  setRunning(!!state.job);
}

async function saveSchedule(mode) {
  const m = mode || state.schedule.mode;
  const r = await api.set_schedule(m, $("#sched-time").value || "08:00", +$("#sched-hours").value || 6);
  if (!r.ok) alert(r.error);
  await refresh();
}

function setRunning(running) {
  const b = $("#sync-btn");
  b.disabled = running; b.classList.toggle("running", running);
  $("span", b).textContent = t(running ? "sync.running" : "sync.now");
}

function watchJob(onDone) {
  setRunning(true); logNext = 0;
  clearInterval(polling);
  polling = setInterval(async () => {
    const p = await api.progress(logNext);
    logNext = p.next;
    if (p.lines.length) { const log = $("#log"); log.textContent += p.lines.join("\n") + "\n"; log.scrollTop = log.scrollHeight; }
    if (!p.job && p.result) {
      clearInterval(polling); setRunning(false);
      await refresh();
      if (onDone) onDone(p.result);
    }
  }, 600);
}

/* ---------- courses ---------- */
function bindCourses() {
  $("#add-form").addEventListener("submit", async e => {
    e.preventDefault();
    const url = $("#add-url").value.trim();
    if (!url) return;
    $("#add-btn").disabled = true; msg("#add-msg", t("crs.adding"));
    const r = await api.add_course(url);
    $("#add-btn").disabled = false;
    if (!r.ok) return msg("#add-msg", r.error, "bad");
    $("#add-url").value = ""; msg("#add-msg", t("crs.added"), "ok");
    await refresh();
  });
  $("#default-dir-btn").addEventListener("click", async () => { await api.choose_folder(""); refresh(); });
}

function renderCourses() {
  $("#default-dir").textContent = state.default_target_dir;
  $("#course-list").innerHTML = state.courses.map(c => `
    <div class="card course" data-id="${c.ref_id}">
      <label class="toggle" title="${t("crs.enabled")}"><input type="checkbox" ${c.enabled ? "checked" : ""} data-act="enabled"><span></span></label>
      <div>
        <h3>${esc(c.title)}</h3>
        <div class="path">${esc(c.target_dir)}</div>
      </div>
      <div class="actions">
        <button class="link" data-act="files">${t("crs.files")}</button>
        <button class="link" data-act="folder">${t("crs.change_target")}</button>
        <button class="link" data-act="open">${t("crs.open")}</button>
        <button class="link danger" data-act="remove">${t("crs.remove")}</button>
      </div>
    </div>`).join("");
  $$("#course-list .course").forEach(el => {
    const id = el.dataset.id;
    $("[data-act=enabled]", el).addEventListener("change", e => api.update_course(id, { enabled: e.target.checked }).then(refresh));
    $("[data-act=files]", el).addEventListener("click", () => { $("#files-course").value = id; show("files"); });
    $("[data-act=folder]", el).addEventListener("click", async () => { await api.choose_folder(id); refresh(); });
    $("[data-act=open]", el).addEventListener("click", () => api.open_folder(id));
    $("[data-act=remove]", el).addEventListener("click", async () => {
      if (confirm(t("crs.remove_confirm"))) { await api.remove_course(id); refresh(); }
    });
  });
}

/* ---------- files ---------- */
const STATUS = ["downloaded", "edited", "kept_edited", "pending", "not_yet", "unselected", "deleted_locally", "removed_remote"];
let treeData = [], openFolders = new Set();

function bindFiles() {
  $("#files-course").addEventListener("change", loadTree);
  $("#only-new").addEventListener("change", renderTree);
  $$("#new-policy button").forEach(b => b.addEventListener("click", async () => {
    await api.update_course($("#files-course").value, { new_files: b.dataset.policy });
    await refresh(); loadTree();
  }));
  $("#refresh-tree").addEventListener("click", async () => {
    const id = $("#files-course").value;
    const r = await api.refresh_tree(id);
    if (!r.ok) return alert(r.error);
    $("#refresh-tree").disabled = true; $("#tree-hint").textContent = t("files.refreshing");
    watchJob(() => { $("#refresh-tree").disabled = false; loadTree(); });
  });
  $("#legend").innerHTML = STATUS.map(s => `<span class="badge ${s}">${t("st." + s)}</span>`).join("");
}

function renderCourseSelect() {
  const sel = $("#files-course"), cur = sel.value;
  sel.innerHTML = state.courses.map(c => `<option value="${c.ref_id}">${esc(c.title)}${c.pending ? ` (${c.pending})` : ""}</option>`).join("");
  if (cur && state.courses.some(c => c.ref_id === cur)) sel.value = cur;
}

async function loadTree() {
  const id = $("#files-course").value;
  if (!id) { $("#tree").innerHTML = `<div class="empty">${t("sync.no_courses")}</div>`; return; }
  const course = state.courses.find(c => c.ref_id === id);
  $$("#new-policy button").forEach(b => b.classList.toggle("on", b.dataset.policy === course.new_files));
  const r = await api.tree(id);
  treeData = r.files;
  $("#tree-hint").textContent = r.last_run && r.last_run.at ? t("files.as_of", { when: fmtWhen(r.last_run.at) }) : t("files.never");
  renderTree();
}

function buildTree(files) {
  const root = { children: new Map(), files: [] };
  for (const f of files) {
    const parts = f.path.split("/");
    let node = root, prefix = "";
    for (const part of parts.slice(0, -1)) {
      prefix = prefix ? prefix + "/" + part : part;
      if (!node.children.has(part)) node.children.set(part, { name: part, path: prefix, children: new Map(), files: [] });
      node = node.children.get(part);
    }
    node.files.push({ ...f, name: parts[parts.length - 1] });
  }
  return root;
}
function allFiles(node) { return [...node.files, ...[...node.children.values()].flatMap(allFiles)]; }

function renderTree() {
  const onlyNew = $("#only-new").checked;
  const files = onlyNew ? treeData.filter(f => f.new || f.status === "pending") : treeData;
  if (!files.length) { $("#tree").innerHTML = `<div class="empty">${t(treeData.length ? "files.none_new" : "files.empty")}</div>`; return; }
  const root = buildTree(files);
  $("#tree").innerHTML = renderNode(root, 0);
  $$("#tree [data-folder]").forEach(el => el.addEventListener("click", () => {
    const p = el.dataset.folder;
    openFolders.has(p) ? openFolders.delete(p) : openFolders.add(p);
    renderTree();
  }));
  $$("#tree input[type=checkbox]").forEach(cb => {
    if (cb.dataset.mixed) cb.indeterminate = true;
    cb.addEventListener("change", async () => {
      await api.set_selection($("#files-course").value, cb.dataset.path, cb.checked);
      await refresh(); loadTree();
    });
  });
  $$("#tree [data-open]").forEach(el => el.addEventListener("dblclick", () => api.open_file($("#files-course").value, el.dataset.open)));
}

function renderNode(node, depth) {
  const pad = d => `style="padding-left:${6 + d * 18}px"`;
  let html = "";
  for (const child of [...node.children.values()].sort((a, b) => a.name.localeCompare(b.name))) {
    const leaves = allFiles(child), on = leaves.filter(f => f.selected).length;
    const open = openFolders.has(child.path) || depth === 0 && openFolders.size === 0;
    const anyNew = leaves.some(f => f.new || f.status === "pending");
    html += `<div class="node folder ${anyNew ? "is-new" : ""}" ${pad(depth)}>
      <span class="twisty" data-folder="${esc(child.path)}">${open ? "▾" : "▸"}</span>
      <input type="checkbox" data-path="${esc(child.path)}" ${on === leaves.length ? "checked" : ""} ${on && on < leaves.length ? 'data-mixed="1"' : ""}>
      <span class="name" data-folder="${esc(child.path)}">📁 ${esc(child.name)}</span>
      <span class="label">${on}/${leaves.length}</span>
    </div><div class="children ${open ? "" : "closed"}">${renderNode(child, depth + 1)}</div>`;
  }
  for (const f of node.files.sort((a, b) => a.name.localeCompare(b.name))) {
    const dim = !f.selected || f.status === "removed_remote";
    const title = f.alt_versions.length ? ` title="${esc(t("st.alt_hint", { files: f.alt_versions.join(", ") }))}"` : "";
    html += `<div class="node ${f.new || f.status === "pending" ? "is-new" : ""} ${dim ? "dim" : ""}" ${pad(depth)} data-open="${esc(f.path)}"${title}>
      <span class="twisty"></span>
      <input type="checkbox" data-path="${esc(f.path)}" ${f.selected ? "checked" : ""}>
      <span class="name">${esc(f.name)}</span>
      <span class="badge ${f.status}">${t("st." + f.status)}</span>
      <span class="date">${fmtDate(f.mtime)}</span>
    </div>`;
  }
  return html;
}

/* ---------- account ---------- */
let totpTimer = null;
function bindAccount() {
  $("#acc-form").addEventListener("submit", async e => {
    e.preventDefault();
    const r = await api.save_credentials($("#acc-user").value.trim(), $("#acc-pass").value, $("#acc-secret").value.trim());
    if (!r.ok) return msg("#acc-msg", r.error, "bad");
    $("#acc-pass").value = ""; $("#acc-secret").value = "";
    msg("#acc-msg", t("acc.saved"), "ok"); refresh();
  });
  $("#acc-test").addEventListener("click", async () => {
    $("#acc-test").disabled = true; msg("#acc-msg", t("acc.testing"));
    const r = await api.test_login();
    $("#acc-test").disabled = false;
    r.ok ? msg("#acc-msg", t("acc.test_ok"), "ok") : msg("#acc-msg", t("acc.test_fail", { err: r.error }), "bad");
  });
  $("#acc-secret").addEventListener("input", updateTotp);
  $("#totp-copy").addEventListener("click", () => {
    const code = $("#totp-code").textContent.replace(/\s/g, "");
    if (/^\d{6}$/.test(code)) navigator.clipboard.writeText(code).then(() => msg("#acc-msg", t("acc.copied"), "ok"));
  });
  totpTimer = setInterval(updateTotp, 1000);
}

function renderAccount() {
  if (!$("#acc-user").value) $("#acc-user").value = state.username;
  $("#acc-pass").placeholder = state.has_password ? t("acc.saved_placeholder") : "";
  $("#acc-secret").placeholder = state.has_secret ? t("acc.saved_placeholder") : t("acc.secret_placeholder");
  updateTotp();
}

async function updateTotp() {
  if (!$("#view-account").classList.contains("active") || !api) return;
  const r = await api.totp($("#acc-secret").value.trim());
  if (r.code) {
    $("#totp-code").textContent = r.code.slice(0, 3) + " " + r.code.slice(3);
    $("#totp-left").textContent = r.left;
    $("#totp-bar").style.strokeDashoffset = 100.5 * (1 - r.left / 30);
  } else {
    $("#totp-code").textContent = "— — —"; $("#totp-left").textContent = "";
    $("#totp-bar").style.strokeDashoffset = 100.5;
    if (r.error) msg("#acc-msg", r.error, "bad");
  }
}

function msg(sel, text, cls = "") { const el = $(sel); el.textContent = text; el.className = "msg " + cls; }
