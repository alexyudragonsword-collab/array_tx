/* The array_tx page.  Every control comes from /api/spec (guispec), every
 * number from a job's report (guiutil); this file arranges, never computes.
 * One page, two hosts: arraytx.webhost on a laptop (app window or tab) and,
 * later, a WebView on a phone.  All POSTs carry the X-ArrayTX header. */
"use strict";
const $ = id => document.getElementById(id);
const COLORS = { none: "#2a78d6", per_element: "#eb6834", array: "#1baf7a" };
const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
/* ---------------------------------------------------------- language */
const T = {
  zh: { none: "无 DPD", per_element: "每单元 ILA-GMP", array: "阵列 ILA-GMP (OTA)", beam: "波束", sidelobe: "旁瓣", baseline: "基线",
        vs_base: "对基线", results_none: "还没有结果：改好配置后按 ▶ 运行，或 ⇄ 扫描。", symbols: "符号", eq: "均衡", elements: "单元",
        queued: "排队", running: "运行中", done: "完成", error: "失败", cancelled: "已取消", cancel: "取消", idle: "空闲", active: "个在跑 / 排队",
        info: "信息", limit: "64-QAM 限值 8 %", pass: "✓ 通过", fail: "✗ 越限", pertone_note: "逐子载波均衡能抹掉的线性部分",
        bw3: "3 dB 波束宽", ttd: "真延时", phase: "相移器", no_sidelobe: "单元数 1：无旁瓣", highest_sl: "最高旁瓣",
        form_changed: "（当前表单已改）", study: "研究", points: "点，边跑边画", low_good: "低 = 好", high_good: "高 = 好",
        grid_title: "扫描角 × DPD · OTA ACLR1 @ 波束 [dBc]", grid_sub: "点击一格切换", mask_note: "stylized 工程模板，非一致性条款",
        element: "单元", errors_hdr: "误差抽取 gain / phase / delay / PA", prev: "上次会话", valid: "合法", differ: "处与文件不同",
        unsaved: "处未保存", default_cfg: "（默认配置，未保存）", run_failed: "运行失败",
        open_prompt: "要载入的 YAML 路径（本机）；或在下一步粘贴 YAML 文本", paste_prompt: "粘贴 YAML 文本",
        save_prompt: "已下载。也写回本机文件？输入路径（留空跳过）", no_prov: "非数值字段，无出处记录", none_note: "（无说明）" },
  en: { none: "no DPD", per_element: "per-element ILA-GMP", array: "array ILA-GMP (OTA)", beam: "beam", sidelobe: "sidelobe", baseline: "baseline",
        vs_base: "vs baseline", results_none: "No results yet: set the config and press ▶ Run or ⇄ Scan.", symbols: "symbols", eq: "EQ", elements: "elements",
        queued: "queued", running: "running", done: "done", error: "failed", cancelled: "cancelled", cancel: "cancel", idle: "idle", active: "running / queued",
        info: "info", limit: "64-QAM limit 8 %", pass: "✓ pass", fail: "✗ fail", pertone_note: "the linear part a per-tone equaliser removes",
        bw3: "3 dB beamwidth", ttd: "true time delay", phase: "phase shifters", no_sidelobe: "one element: no sidelobe", highest_sl: "highest sidelobe",
        form_changed: "(form edited since)", study: "study", points: "points, drawn as they land", low_good: "lower = better", high_good: "higher = better",
        grid_title: "scan angle × DPD · OTA ACLR1 @ beam [dBc]", grid_sub: "click a cell", mask_note: "stylized template, not a conformance clause",
        element: "element", errors_hdr: "drawn errors gain / phase / delay / PA", prev: "previous session", valid: "valid", differ: "differ from the file",
        unsaved: "unsaved", default_cfg: "(defaults, unsaved)", run_failed: "run failed",
        open_prompt: "YAML path to load (this machine); or paste YAML text in the next step", paste_prompt: "paste YAML text",
        save_prompt: "Downloaded. Also write it back to a file? Path (empty = skip)", no_prov: "not a number: no provenance record", none_note: "(no note)" },
};
let LANG = "zh";
try { LANG = localStorage.getItem("arraytx.lang") === "en" ? "en" : "zh"; } catch (e) { /* no storage */ }
const t = k => (T[LANG][k] !== undefined ? T[LANG][k] : (T.zh[k] !== undefined ? T.zh[k] : k));
const LABELS = new Proxy({}, { get: (_, k) => t(k) });
function applyLang() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-zh]").forEach(e => { e.textContent = e.dataset[LANG] || e.dataset.zh; });
  const b = $("lang"); if (b) b.textContent = LANG === "zh" ? "EN" : "中";
}

const S = {                       // page state
  spec: null, loaded: null,       // loaded: the host's config payload (values, provenance, yaml, sha)
  values: {}, errors: null, sha: null,
  reports: [], selected: null, baseline: null,   // reports: [{key, jobId, i, rep, ts}]
  jobs: {}, seenRows: {}, polling: false, provPath: null,
};

/* ----------------------------------------------------------------- api */
async function api(route, body) {
  const r = await fetch("api/" + route, body === undefined ? {} :
    { method: "POST", headers: { "Content-Type": "application/json", "X-ArrayTX": "1" }, body: JSON.stringify(body) });
  const j = await r.json();
  if (j.ok === false) throw new Error(j.error || ("api/" + route + " failed"));
  return j;
}
function showError(e) { const b = $("error"); if (!e) { b.hidden = true; return; } b.hidden = false; b.textContent = String(e.message || e); }

/* ---------------------------------------------------------------- form */
const ctlById = {};
function visible(c) {
  if (!c.visible_when) return true;
  const [path, vals] = c.visible_when; const v = S.values[path];
  if (vals.includes("<set>")) return v !== null && v !== undefined && v !== "";
  return vals.includes(v);
}
function isModified(path) { return S.loaded && JSON.stringify(S.values[path]) !== JSON.stringify(S.loaded.values[path]); }
function parseList(text) { return String(text).split(/[,\s]+/).filter(Boolean).map(Number); }

function controlEl(c) {
  const row = document.createElement("div"); row.className = "row"; row.dataset.path = c.path;
  const lab = document.createElement("label"); lab.textContent = c.label; lab.title = c.path + " — " + c.help;
  if (c.unit && c.unit !== "path") { const u = document.createElement("span"); u.className = "u"; u.textContent = c.unit; lab.appendChild(u); }
  const ctl = document.createElement("div"); ctl.className = "ctl";
  let input;
  const set = v => { S.values[c.path] = v; onChange(c.path); };
  if (c.kind === "bool") {
    input = document.createElement("button"); input.className = "sw"; input.type = "button";
    input.addEventListener("click", () => set(!S.values[c.path]));
    input.update = () => input.classList.toggle("on", !!S.values[c.path]);
  } else if (c.kind === "choice") {
    input = document.createElement("select");
    c.choices.forEach(ch => { const o = document.createElement("option"); o.value = ch === null ? "" : String(ch); o.textContent = ch === null ? "null (polar_tx 预设 LO)" : String(ch); input.appendChild(o); });
    input.addEventListener("change", () => set(input.value === "" ? null : input.value));
    input.update = () => { input.value = S.values[c.path] === null || S.values[c.path] === undefined ? "" : String(S.values[c.path]); };
  } else if (c.kind === "int" || c.kind === "float") {
    input = document.createElement("input"); input.type = "number";
    if (c.step) input.step = c.step; if (c.lo !== null) input.min = c.lo; if (c.hi !== null) input.max = c.hi;
    input.addEventListener("change", () => { const v = input.value === "-inf" ? "-inf" : (c.kind === "int" ? parseInt(input.value, 10) : parseFloat(input.value)); set(Number.isNaN(v) ? S.values[c.path] : v); });
    input.update = () => { input.value = S.values[c.path]; };
  } else if (c.kind === "optional_float") {
    input = document.createElement("input"); input.type = "text"; input.placeholder = "null = 关";
    input.addEventListener("change", () => { const t = input.value.trim().toLowerCase(); set(t === "" || t === "null" || t === "none" ? null : parseFloat(t)); });
    input.update = () => { input.value = S.values[c.path] === null ? "" : S.values[c.path]; };
  } else if (c.kind === "list") {
    input = document.createElement("input"); input.type = "text";
    input.addEventListener("change", () => set(parseList(input.value)));
    input.update = () => { input.value = (S.values[c.path] || []).join(", "); };
  } else {                                           // text / path
    input = document.createElement("input"); input.type = "text"; input.placeholder = c.kind === "path" ? "路径（相对 config 文件）" : "";
    input.addEventListener("change", () => { const t = input.value.trim(); set(t === "" && c.kind === "path" ? null : (c.path === "beam.sidelobe" && t !== "auto" ? parseFloat(t) : t)); });
    input.update = () => { input.value = S.values[c.path] === null || S.values[c.path] === undefined ? "" : S.values[c.path]; };
  }
  ctl.appendChild(input);
  const pill = document.createElement("button"); pill.className = "pill"; pill.type = "button"; ctl.appendChild(pill);
  pill.addEventListener("click", () => showProvenance(c.path));
  row.append(lab, ctl);
  row.refresh = () => {
    input.update(); row.hidden = !visible(c); row.classList.toggle("modified", isModified(c.path));
    const p = provenanceOf(c.path); pill.hidden = !p; if (p) { pill.textContent = p.source; pill.className = "pill " + p.source; pill.title = p.ref || p.source; }
  };
  ctlById[c.path] = row;
  return row;
}
function provenanceOf(path) {
  if (S.errors === null && S.liveProv && S.liveProv[path]) return S.liveProv[path];
  return S.loaded && S.loaded.provenance[path];
}
function buildForm() {
  const form = $("form"); form.innerHTML = "";
  const groups = {}; S.spec.controls.forEach(c => (groups[c.group] = groups[c.group] || []).push(c));
  S.spec.groups.forEach(g => {
    const d = document.createElement("details"); d.open = ["standard", "coupling", "beam", "dpd"].includes(g.id);
    const sm = document.createElement("summary"); sm.innerHTML = `${g.zh} <span class="muted">${g.en}</span>`; d.appendChild(sm);
    let sub = null;
    (groups[g.id] || []).forEach(c => {
      const parts = c.path.split("."); const s = parts.length > 2 ? parts.slice(0, -1).join(".") : (parts.length === 2 ? parts[0] : "");
      if (s !== sub) { sub = s; if (s) { const h = document.createElement("div"); h.className = "sub"; h.textContent = s; d.appendChild(h); } }
      d.appendChild(controlEl(c));
    });
    form.appendChild(d);
  });
  refreshForm();
}
function refreshForm() {
  Object.values(ctlById).forEach(r => r.refresh());
  // a sub-heading with every row under it hidden is hidden too
  document.querySelectorAll("#form .sub").forEach(h => { let e = h.nextElementSibling, any = false;
    while (e && !e.classList.contains("sub")) { if (!e.hidden) any = true; e = e.nextElementSibling; } h.hidden = !any; });
  if (S.values.seed !== undefined) $("seed").value = S.values.seed;
  const n = Object.keys(S.values).filter(isModified).length;
  const chip = $("cfg-chip"); const name = S.loaded && S.loaded.source_path ? S.loaded.source_path.split(/[\\/]/).pop() : t("default_cfg");
  chip.textContent = name + (n ? ` ● ${n} ${t("unsaved")}` : ""); chip.classList.toggle("mod", n > 0); chip.title = S.loaded && S.loaded.source_path || "";
  fillRunSelectors(); fillSweepSelectors();
}
let validateTimer = null;
function onChange(path) {
  if (path === "seed") $("seed").value = S.values.seed;
  Object.values(ctlById).forEach(r => r.refresh());
  clearTimeout(validateTimer);
  validateTimer = setTimeout(validate, 250);
  refreshForm();
}
async function validate() {
  try {
    const v = await api("validate", { values: S.values });
    S.errors = null; S.sha = v.sha256; S.liveProv = v.provenance; S.yaml = v.yaml;
    $("validate").textContent = `${t("valid")} · ${v.diff.length} ${t("differ")} · sha ${v.sha256.slice(0, 8)}`; $("validate").className = "muted small";
    $("btn-run").disabled = false; $("btn-scan").disabled = false;
    Object.values(ctlById).forEach(r => r.refresh());
  } catch (e) {
    S.errors = e.message; $("validate").textContent = "✗ " + e.message; $("validate").className = "small bad";
    $("btn-run").disabled = true; $("btn-scan").disabled = true;
  }
}
function showProvenance(path) {
  S.provPath = path; const p = provenanceOf(path); const c = S.spec.controls.find(x => x.path === path);
  const box = $("prov"); box.className = "prov";
  box.innerHTML = `<b>${path}</b> = ${JSON.stringify(S.values[path])}${c && c.unit ? " " + c.unit : ""}<br>` +
    (p ? `<span class="${p.source === "survey" || p.source === "measured" ? "good" : "bad"}">source: ${p.source}</span><pre>${p.ref || t("none_note")}</pre>` : `<span class='muted'>${t("no_prov")}</span>`) +
    `<div class="muted">${c ? c.help : ""}</div>`;
  if (window.innerWidth <= 760) showPane("side");
}
function fillSweepSelectors() {
  const sp = $("sweep-path"); if (sp.options.length) return;
  S.spec.controls.filter(c => ["int", "float", "bool", "choice", "optional_float"].includes(c.kind)).forEach(c => {
    const o = document.createElement("option"); o.value = c.path; o.textContent = c.path; sp.appendChild(o); });
  sp.value = "array.n_elements";
  const sg = $("sweep-group"); const none = document.createElement("option"); none.value = ""; none.textContent = "—"; sg.appendChild(none);
  S.spec.controls.filter(c => ["int", "float", "bool", "choice"].includes(c.kind)).forEach(c => { const o = document.createElement("option"); o.value = c.path; o.textContent = c.path.split(".").pop(); o.title = c.path; sg.appendChild(o); });
  const ghint = { "beam.steering": "phase, ttd", "dpd.scheme": "none, per_element, array", "element.lo.spurs": "false, true", "metrics.evm_equalize": "scalar, per_tone" };
  sg.addEventListener("change", () => { $("sweep-group-values").placeholder = ghint[sg.value] || "a, b"; });
  const sm = $("sweep-metric");
  ["evm_db", "aclr1_dbc", "aclr2_dbc", "sem_margin_db", "evm_per_tone_db"].forEach(id => { const o = document.createElement("option"); o.value = id; o.textContent = M()[id][LANG] + " [" + M()[id].unit + "]"; sm.appendChild(o); });
  sm.addEventListener("change", renderGrid);
  const hint = { "array.n_elements": "4, 8, 16, 32, 64, 128", "element.lo.spurs": "false, true", "coupling.scale_db": "-inf, -20, -10, -6, 0, 6",
                 "element.lo.clock_profile": S.spec.bundled_profiles.slice(0, 3).map(n => "bundled:" + n).join(", "), "beam.steering": "phase, ttd" };
  const setHint = () => { $("sweep-points").placeholder = hint[sp.value] || "取值列表，逗号分隔"; };
  sp.addEventListener("change", setHint); setHint();
}
function parsePoints(path, text) {
  const c = S.spec.controls.find(x => x.path === path);
  return String(text).split(/[,\n]+/).map(t => t.trim()).filter(Boolean).map(t => {
    const l = t.toLowerCase();
    if (c.kind === "bool") return l === "true" || l === "1" || l === "on";
    if (c.kind === "choice") return l === "null" || l === "none" ? null : t;
    if (l === "-inf") return "-inf"; if (l === "null" || l === "none") return null;
    return c.kind === "int" ? parseInt(t, 10) : parseFloat(t); });
}
function fillRunSelectors() {
  const th = $("run-theta"); const cur = th.value; th.innerHTML = "";
  (S.values["beam.scan_deg"] || []).forEach(t => { const o = document.createElement("option"); o.value = t; o.textContent = `${t > 0 ? "+" : ""}${t}°`; th.appendChild(o); });
  if ([...th.options].some(o => o.value === cur)) th.value = cur;
  const sc = $("run-scheme"); if (!sc.options.length || sc.dataset.lang !== LANG) { const cur = sc.value; sc.innerHTML = ""; sc.dataset.lang = LANG;
    S.spec.schemes.forEach(s => { const o = document.createElement("option"); o.value = s; o.textContent = LABELS[s]; sc.appendChild(o); }); if (cur) sc.value = cur; }
  if (!sc.dataset.touched) sc.value = S.values["dpd.scheme"];
}

/* ---------------------------------------------------------------- jobs */
async function submit(route, body) {
  showError(null);
  try { const j = await api(route, { values: S.values, n_symbols: $("smoke").checked ? 2 : null, ...body }); S.jobs[j.job.id] = j.job; renderQueue();
    S.pollAgain = true; startPolling(); }          // a poll already in flight may have listed the jobs before this one existed
  catch (e) { showError(e); }
}
function startPolling() { if (S.polling) return; S.polling = true; poll(); }
async function poll() {
  try {
    const { jobs } = await api("jobs");
    let active = false;
    for (const j of jobs) {
      const old = S.jobs[j.id]; S.jobs[j.id] = j;
      // a restored copy of a job this host still holds: the live rows replace it
      const dup = S.reports.filter(r => r.restored && String(r.jobId) === String(j.id) && r.sha === j.config_sha256);
      if (dup.length) { S.reports = S.reports.filter(r => !dup.includes(r)); if (dup.some(r => r.key === S.selected)) S.selected = null; delete S.jobs["prev." + j.id]; renderAll(); }
      if (["queued", "running"].includes(j.status)) active = true;
      const seen = S.seenRows[j.id] || 0;
      if (j.n_rows > seen) {                           // new rows landed: fetch them
        const full = (await api("jobs/" + j.id)).job;
        full.rows.slice(seen).forEach((rep, k) => addReport(j, seen + k, rep));
        S.seenRows[j.id] = full.rows.length;
      }
      if (old && old.status !== j.status && j.status === "error") showError(new Error(t("run_failed") + " #" + j.id + "\n" + (j.error || "")));
    }
    renderQueue();
    if (active || S.pollAgain) { S.pollAgain = false; setTimeout(poll, 700); } else S.polling = false;
  } catch (e) { showError(e); S.polling = false; }
}
function addReport(job, i, rep) {
  const key = `${job.id}.${i}`;
  if (S.reports.some(r => r.key === key)) return;
  S.reports.push({ key, jobId: job.id, i, rep, ts: new Date(), sha: job.config_sha256, label: job.label, kind: job.kind });
  if (!S.selected || S.autoFollow !== false) select(key, false);
  renderTable(); renderHistory(); renderGrid(); persist();
}
/* the last reports survive a reload (localStorage, per host port); anything stored is what this page wrote */
const STORE = "arraytx.reports." + location.port;
function persist() {
  try { localStorage.setItem(STORE, JSON.stringify(S.reports.slice(-12))); } catch (e) { /* quota or no storage: the page still works */ }
}
function restore() {
  try { const prev = JSON.parse(localStorage.getItem(STORE) || "[]");
    prev.forEach(r => { r.key = "prev." + r.key; r.restored = true; r.ts = new Date(r.ts); S.reports.push(r); S.jobs["prev." + r.jobId] = S.jobs["prev." + r.jobId] || { id: "prev." + r.jobId, kind: r.kind, label: r.label, status: "done", progress: [0, 0], created: 0 }; });
  } catch (e) { /* ignore a broken store */ }
}
function renderQueue() {
  const q = $("queue"); q.innerHTML = "";
  const jobs = Object.values(S.jobs).sort((a, b) => b.created - a.created);
  const active = jobs.filter(j => ["queued", "running"].includes(j.status)).length;
  $("queue-sub").textContent = active ? `${active} ${t("active")}` : t("idle");
  jobs.slice(0, 8).forEach(j => {
    const d = document.createElement("div"); d.className = "job " + j.status;
    const pct = j.progress[1] ? Math.round(100 * j.progress[0] / j.progress[1]) : 0;
    const st = { queued: t("queued"), running: `${t("running")} ${j.progress[0]}/${j.progress[1]}`, done: `${t("done")} ${j.finished && j.started ? (j.finished - j.started).toFixed(1) + " s" : ""}`, error: t("error"), cancelled: t("cancelled") }[j.status];
    d.innerHTML = `<div class="l"><span>#${j.id} · ${j.label}</span><span class="muted">${st}</span></div><div class="pg"><i style="width:${j.status === "done" ? 100 : pct}%"></i></div>`;
    if (["queued", "running"].includes(j.status)) { const b = document.createElement("button"); b.className = "btn small danger"; b.textContent = t("cancel"); b.style.marginTop = "4px";
      b.addEventListener("click", () => api("jobs/" + j.id + "/cancel", {}).then(poll).catch(showError)); d.appendChild(b); }
    if (j.status === "error" && j.error) { const e = document.createElement("div"); e.className = "err"; e.textContent = j.error.split("\n").slice(-3).join("\n"); d.appendChild(e); }
    q.appendChild(d);
  });
}

/* ------------------------------------------------------------- results */
const M = () => S.spec.metrics;
const f = (v, d) => (v === null || v === undefined || Number.isNaN(v) ? "—" : (+v).toFixed(d));
function get(key) { return S.reports.find(r => r.key === key); }
function select(key, scroll) { S.selected = key; renderAll(); if (scroll && window.innerWidth <= 760) showPane("results"); }
function deltaHtml(id, v, b) {
  const m = M()[id]; if (!b || v === null || b === null || m.better === null) return "";
  const d = v - b; const good = m.better === "lower" ? d < 0 : d > 0; const cls = Math.abs(d) < 0.005 ? "na" : (good ? "good" : "bad");
  return `<span class="${cls}">${Math.abs(d) < 0.005 ? "=" : (good ? "▼" : "▲")} ${t("vs_base")} ${d > 0 ? "+" : ""}${d.toFixed(m.digits)} ${m.unit}</span>`;
}
function renderCards() {
  const r = get(S.selected); const box = $("cards"); box.innerHTML = "";
  if (!r) { box.innerHTML = `<div class='muted'>${t("results_none")}</div>`; return; }
  const b = get(S.baseline); const rep = r.rep, beam = rep.ota.beam, bb = b && b.rep.ota.beam;
  const items = [["evm_db", beam.evm_db, bb && bb.evm_db, `${f(beam.evm_pct, 2)} % · ${t("limit")}`],
    ["aclr1_dbc", beam.aclr1_dbc, bb && bb.aclr1_dbc, ""], ["aclr2_dbc", beam.aclr2_dbc, bb && bb.aclr2_dbc, ""],
    ["sem_margin_db", beam.sem_margin_db, bb && bb.sem_margin_db, (beam.sem_passes ? `<span class='ok'>${t("pass")}</span>` : `<span class='fail'>${t("fail")}</span>`) + " · " + M().sem_margin_db["note_" + LANG]],
    ["evm_per_tone_db", beam.evm_per_tone_db, bb && bb.evm_per_tone_db, t("pertone_note")],
    ["squint_deg", rep.info.squint_deg, null, `${t("bw3")} ${f(rep.info.beamwidth_deg, 2)}° · ${t(rep.steering)}`]];
  items.forEach(([id, v, bv, sub]) => { const m = M()[id]; const c = document.createElement("div"); c.className = "card";
    c.innerHTML = `<div class="t"><span>${m[LANG]}${id === "squint_deg" ? " (+BW/2)" : ""}</span><span class="dom ${m.domain}">${m.domain === "ota" ? "OTA" : t("info")}</span></div>` +
      `<div class="v">${f(v, m.digits)}<small>${m.unit}</small></div><div class="d">${deltaHtml(id, v, bv) || `<span class="muted">${sub}</span>`}</div>` + (deltaHtml(id, v, bv) && sub ? `<div class="d muted">${sub}</div>` : "");
    box.appendChild(c); });
  const sl = rep.ota.sidelobe;
  $("sidelobe").innerHTML = sl ? `${t("highest_sl")} <b>${f(sl.theta_deg, 1)}°</b> <span class="dom">OTA</span> · EVM ${f(sl.evm_db, 2)} dB · ACLR1 ${f(sl.aclr1_dbc, 1)} dBc · ACLR2 ${f(sl.aclr2_dbc, 1)} dBc` : t("no_sidelobe");
  $("res-title").textContent = `${r.restored ? "↺ " + t("prev") + " " : "#"}${String(r.jobId).replace("prev.", "")}.${r.i + 1}${rep.sweep ? ` · ${rep.sweep.path}=${rep.sweep.value}` : ""}${rep.sweep && rep.sweep.group_path ? ` · ${rep.sweep.group_path}=${rep.sweep.group_value}` : ""} · ${t("beam")} ${beam.theta_deg > 0 ? "+" : ""}${f(beam.theta_deg, 1)}° · ${LABELS[rep.scheme]}`;
  $("res-sub").textContent = `${rep.info.n_rows > 1 ? rep.info.n_x + "×" + rep.info.n_rows + (rep.info.plane_phi_deg ? " φ" + rep.info.plane_phi_deg + "°" : "") : rep.info.n_elements + " " + t("elements")} · ${rep.info.f0_ghz} GHz / ${rep.info.bw_mhz} MHz · ${rep.info.coupling_source} ${f(rep.info.coupling_max_offdiag_db, 1)} dB · seed ${rep.repro.seed} · ${rep.info.n_symbols} ${t("symbols")} · ${rep.info.evm_equalize} ${t("eq")} · ${f(rep.seconds, 1)} s`;
  $("engine").textContent = rep.engine_line;
  $("btn-pin").hidden = false; $("btn-unpin").hidden = !S.baseline;
  const chip = $("baseline-chip"); chip.hidden = !b; if (b) chip.textContent = `◆ ${t("baseline")} #${String(b.jobId).replace("prev.", "")}.${b.i + 1} ${LABELS[b.rep.scheme]} @ ${b.rep.theta0_deg}°`;
  const rp = rep.repro; $("repro").className = "repro";
  $("repro").innerHTML = `seed <b>${rp.seed}</b> · cfg sha256 <b>${rp.config_sha256.slice(0, 12)}</b>${rp.config_sha256 !== S.sha && S.sha ? ` <span class='bad'>${t("form_changed")}</span>` : ""}<br>` +
    `vendored ${Object.entries(rp.pins).map(([k, v]) => `${k}@${v}`).join(" · ")}<pre>${rp.call}</pre>`;
  const dg = $("diag");
  dg.innerHTML = `<table><tr><th>${t("element")}</th><th>conducted EVM dB</th><th>conducted ACLR1</th><th>conducted ACLR2</th><th>${t("errors_hdr")}</th></tr>` +
    rep.diagnostic.map(d => `<tr><td>${d.element}</td><td>${f(d.conducted_evm_db, 2)}</td><td>${f(d.conducted_aclr1_dbc, 1)}</td><td>${f(d.conducted_aclr2_dbc, 1)}</td>` +
      `<td>${f(d.errors.gain_db, 2)} dB / ${f(d.errors.phase_deg, 1)}° / ${f(d.errors.delay_ps, 1)} ps / ${f(d.errors.pa_dev, 3)}</td></tr>`).join("") + "</table>";
}
function renderPlots() {
  const r = get(S.selected); if (!r) { ["direction", "spectrum", "constellation"].forEach(id => $("plot-" + id).innerHTML = ""); return; }
  const b = get(S.baseline); const p = r.rep.plots, bp = b && b.key !== r.key && b.rep.plots;
  const d = p.direction, col = COLORS[r.rep.scheme];
  const nulls = []; let s = null; d.theta_deg.forEach((t, i) => { const n = d.aclr1_dbc[i] === null; if (n && s === null) s = t; if (!n && s !== null) { nulls.push({ x0: s - 0.5, x1: t - 0.5 }); s = null; } }); if (s !== null) nulls.push({ x0: s - 0.5, x1: 90 });
  const series = [{ x: d.theta_deg, y: d.aclr1_dbc, color: col, label: LABELS[r.rep.scheme] }];
  if (bp) series.unshift({ x: bp.direction.theta_deg, y: bp.direction.aclr1_dbc, color: "#8a8a85", dash: "5 3", label: t("baseline") + " " + LABELS[b.rep.scheme] });
  const allY = series.flatMap(q => q.y.filter(v => v !== null)); const ylo = Math.floor(Math.min(...allY) / 5) * 5 - 2, yhi = Math.ceil(Math.max(...allY) / 5) * 5;
  Charts.lines($("plot-direction"), { series, xlab: "θ [deg]", ylab: `OTA ACLR1 [dBc] · ${t("low_good")}`, xlim: [-90, 90], ylim: [ylo, yhi], nulls,
    top: { x: d.theta_deg, y: d.pattern_db, ylim: [-40, 0], ylab: "pattern [dB]" },
    vlines: [{ x: d.beam_deg, color: "#eb6834", label: `${t("beam")} ${d.beam_deg > 0 ? "+" : ""}${d.beam_deg}°` }].concat(d.sidelobe_deg !== null ? [{ x: d.sidelobe_deg, color: "#8a8a85", label: t("sidelobe"), dash: "2 2" }] : []),
    tooltip: i => series.map(q => `${q.label}: ${q.y[i] === null ? "null" : q.y[i].toFixed(1) + " dBc"}`).join("\n") + `\npattern ${d.pattern_db[i].toFixed(1)} dB` });
  const sp = p.spectrum;
  const ss = [{ x: sp.f_mhz, y: sp.psd_db, color: col, width: 1.1, label: LABELS[r.rep.scheme] }, { x: sp.f_mhz, y: sp.mask_db, color: "#c0392b", width: 1.2, label: `mask (${sp.mask_source})` }];
  if (bp) ss.unshift({ x: bp.spectrum.f_mhz, y: bp.spectrum.psd_db, color: "#8a8a85", width: 1, dash: "4 3", label: t("baseline") });
  const bw = sp.bw_mhz;
  Charts.lines($("plot-spectrum"), { series: ss, xlab: "f [MHz]", ylab: "PSD [dB]", ylim: [-80, 5], xlim: [-2.25 * bw, 2.25 * bw],
    bands: [{ x0: -bw / 2, x1: bw / 2, fill: "#eef4fb" }, { x0: bw / 2, x1: 1.5 * bw, fill: "#fdf2ec" }, { x0: -1.5 * bw, x1: -bw / 2, fill: "#fdf2ec" }] });
  $("mask-note").textContent = sp.mask_is_conformance ? sp.mask_source : `${t("mask_note")} · RBW ${(sp.rbw_hz / 1e6).toFixed(1)} MHz`;
  const c = p.constellation;
  Charts.scatter($("plot-constellation"), { x: c.i, y: c.q, color: col, lim: 1.6, note: `${c.qam}-QAM · ${c.equalize} ${t("eq")} · ${c.i.length}` });
  $("const-note").textContent = `EVM ${f(r.rep.ota.beam.evm_db, 2)} dB`;
}
function renderSweep(r, box) {
  const same = S.reports.filter(x => x.jobId === r.jobId && x.rep.sweep).sort((a, b) => (a.rep.sweep.group_index || 0) - (b.rep.sweep.group_index || 0) || a.rep.sweep.index - b.rep.sweep.index);
  const sw = r.rep.sweep, path = sw.path, gpath = sw.group_path || null, mid = $("sweep-metric").value || "evm_db", m = M()[mid];
  const n_total = sw.n * (sw.n_groups || 1);
  $("pt-grid").innerHTML = `${t("study")} · ${path}${gpath ? ` ⊗ ${gpath}` : ""} → ${m[LANG]} [${m.unit}] @ ${t("beam")} ${r.rep.theta0_deg}° · ${LABELS[r.rep.scheme]} <span class="muted">${same.length}/${n_total} ${t("points")}</span>`;
  const groups = gpath ? [...new Set(same.map(x => String(x.rep.sweep.group_value)))] : [null];
  const of = g => (g === null ? same : same.filter(x => String(x.rep.sweep.group_value) === g));
  const allVals = same.map(x => x.rep.sweep.value), allY = same.map(x => x.rep.ota.beam[mid]);
  const numeric = allVals.every(v => typeof v === "number" && isFinite(v));
  const b = get(S.baseline), bv = b && b.rep.ota.beam[mid];
  if (numeric && allVals.length > 1) {
    const span = Math.max(...allVals) / Math.max(1e-9, Math.min(...allVals.filter(v => v > 0)));
    const useLog = Math.min(...allVals) > 0 && span >= 8;
    const X = v => (useLog ? Math.log2(v) : v);
    const series = groups.map((g, gi) => { const rows = of(g); return { x: rows.map(x => X(x.rep.sweep.value)), y: rows.map(x => x.rep.ota.beam[mid]),
      color: g === null ? COLORS[r.rep.scheme] : PALETTE[gi % PALETTE.length], marker: true, label: g === null ? LABELS[r.rep.scheme] : `${gpath.split(".").pop()}=${g}`, rows }; });
    const xs = allVals.map(X);
    if (bv !== undefined && bv !== null) series.push({ x: [Math.min(...xs), Math.max(...xs)], y: [bv, bv], color: "#8a8a85", dash: "5 3", label: t("baseline") });
    Charts.lines(box, { series, xlab: useLog ? `${path} (log2)` : path, ylab: `${m[LANG]} [${m.unit}] · ${m.better === "lower" ? t("low_good") : t("high_good")}`, legend: true,
      tooltip: i => series.filter(q => q.rows).map(q => `${q.label}: ${q.y[i] === undefined ? "—" : Charts.fmt(q.y[i]) + " " + m.unit}`).join("\n") + `\n${path} = ${series[0].rows[i] ? series[0].rows[i].rep.sweep.value : ""}` });
    box.querySelector("svg").addEventListener("click", ev => { const rc = box.querySelector("svg").getBoundingClientRect(); const fx = (ev.clientX - rc.left) / rc.width;
      const first = series[0]; let best = 0, bd = 2; first.x.forEach((x, i) => { const px = 42 / 560 + (x - Math.min(...xs)) / (Math.max(...xs) - Math.min(...xs) || 1) * (1 - 52 / 560); const d = Math.abs(px - fx); if (d < bd) { bd = d; best = i; } });
      S.autoFollow = false; select(first.rows[best].key, false); });
  } else {
    const cols = [...new Set(allVals.map(v => String(v)))];
    const cells = groups.map(g => cols.map(c => { const x = of(g).find(y => String(y.rep.sweep.value) === c); return x ? { v: x.rep.ota.beam[mid], text: Charts.fmt(x.rep.ota.beam[mid]), sub: `EVM ${x.rep.ota.beam.evm_db.toFixed(1)}`, sel: x.key === S.selected, base: x.key === S.baseline, key: x.key } : null; }));
    Charts.grid(box, { rows: groups.map(g => (g === null ? m[LANG] : `${gpath.split(".").pop()}=${g}`)), cols, cells,
      lo: Math.min(...allY), hi: Math.max(...allY), onclick: (i, j) => { if (cells[i][j]) { S.autoFollow = false; select(cells[i][j].key, false); } } });
  }
}
function renderGrid() {
  const box = $("plot-grid"); const r = get(S.selected); if (!r) { box.innerHTML = ""; return; }
  if (r.rep.sweep) { renderSweep(r, box); return; }
  $("pt-grid").innerHTML = `${t("grid_title")} <span class="muted">${t("grid_sub")}</span>`;
  const same = S.reports.filter(x => x.jobId === r.jobId); const thetas = [...new Set(same.map(x => x.rep.theta0_deg))].sort((a, b) => a - b);
  const schemes = S.spec.schemes.filter(s => same.some(x => x.rep.scheme === s));
  const all = same.map(x => x.rep.ota.beam.aclr1_dbc);
  const cells = thetas.map(t => schemes.map(s => { const x = same.find(y => y.rep.theta0_deg === t && y.rep.scheme === s); if (!x) return null;
    const bm = x.rep.ota.beam; return { v: bm.aclr1_dbc, text: bm.aclr1_dbc.toFixed(1), sub: `EVM ${bm.evm_db.toFixed(1)} · ${bm.sem_passes ? "✓" : "✗"} mask`, bad: !bm.sem_passes, sel: x.key === S.selected, base: x.key === S.baseline, key: x.key }; }));
  Charts.grid(box, { rows: thetas.map(t => `${t > 0 ? "+" : ""}${t}°`), cols: schemes.map(s => LABELS[s]), cells, lo: Math.min(...all), hi: Math.max(...all),
    onclick: (i, j) => cells[i][j] && select(cells[i][j].key, false) });
}
function renderTable() {
  const tb = $("table").querySelector("tbody"); tb.innerHTML = "";
  S.reports.slice().reverse().forEach(r => { const rep = r.rep, b = rep.ota.beam, sl = rep.ota.sidelobe;
    const tr = document.createElement("tr"); tr.className = (r.key === S.selected ? "sel " : "") + (r.key === S.baseline ? "base" : "");
    tr.innerHTML = `<td>${r.restored ? "↺ " : ""}${String(r.jobId).replace("prev.", "")}.${r.i + 1}${rep.sweep ? ` <span class="muted">${rep.sweep.path.split(".").pop()}=${rep.sweep.value}${rep.sweep.group_path ? " · " + rep.sweep.group_path.split(".").pop() + "=" + rep.sweep.group_value : ""}</span>` : ""}</td><td>${b.theta_deg > 0 ? "+" : ""}${f(b.theta_deg, 0)}°</td><td>${LABELS[rep.scheme]}</td><td>${rep.steering}</td>` +
      `<td>${f(b.evm_db, 2)}</td><td>${f(b.aclr1_dbc, 2)}</td><td>${f(b.aclr2_dbc, 2)}</td><td class="${b.sem_passes ? "ok" : "fail"}">${b.sem_passes ? "✓" : "✗"} ${f(b.sem_margin_db, 2)}</td>` +
      `<td>${sl ? f(sl.theta_deg, 1) + "°" : "—"}</td><td>${sl ? f(sl.aclr1_dbc, 2) : "—"}</td><td>${f(rep.seconds, 1)}</td>`;
    tr.addEventListener("click", () => { S.autoFollow = false; select(r.key, true); });
    tb.appendChild(tr); });
}
function renderHistory() {
  const h = $("history"); h.innerHTML = "";
  S.reports.slice().reverse().slice(0, 30).forEach(r => { const b = r.rep.ota.beam; const d = document.createElement("div"); d.className = "hist" + (r.key === S.selected ? " sel" : "");
    d.innerHTML = `<input type="radio" name="base" title="固定为基线" ${r.key === S.baseline ? "checked" : ""}><span>${r.restored ? "↺" : "#"}${String(r.jobId).replace("prev.", "")}.${r.i + 1} ${b.theta_deg > 0 ? "+" : ""}${f(b.theta_deg, 0)}° ${LABELS[r.rep.scheme]}${r.rep.sweep ? " · " + r.rep.sweep.path.split(".").pop() + "=" + r.rep.sweep.value : ""}</span><span class="m">${f(b.evm_db, 2)} / ${f(b.aclr1_dbc, 1)}</span>`;
    d.querySelector("input").addEventListener("click", ev => { ev.stopPropagation(); S.baseline = r.key; renderAll(); });
    d.addEventListener("click", () => { S.autoFollow = false; select(r.key, true); });
    h.appendChild(d); });
}
function renderAll() { renderCards(); renderPlots(); renderGrid(); renderTable(); renderHistory(); }

/* ------------------------------------------------------------- config io */
function applyLoaded(payload) {
  S.loaded = payload; S.values = JSON.parse(JSON.stringify(payload.values)); S.sha = payload.sha256; S.liveProv = null; S.errors = null;
  refreshForm(); validate();
}
async function openConfig() {
  const p = prompt(t("open_prompt"), S.loaded && S.loaded.source_path || "configs/fr2_4el_survey.yaml");
  if (p === null) return;
  try { applyLoaded(p.trim() ? await api("config/load", { path: p.trim() }) : await api("config/text", { yaml: prompt(t("paste_prompt")) || "" })); }
  catch (e) { showError(e); }
}
async function saveConfig() {
  try {
    const v = await api("validate", { values: S.values });
    const blob = new Blob([v.yaml], { type: "text/yaml" }); const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = (S.loaded && S.loaded.source_path ? S.loaded.source_path.split(/[\\/]/).pop() : "arraytx.yaml"); a.click();
    const p = prompt(t("save_prompt"), S.loaded && S.loaded.source_path || "");
    if (p && p.trim()) applyLoaded(await api("save", { values: S.values, path: p.trim() }));
  } catch (e) { showError(e); }
}
function showPane(name) { document.querySelectorAll(".pane").forEach(p => p.classList.toggle("show", p.id === name));
  document.querySelectorAll("#bottom-nav button").forEach(b => b.classList.toggle("on", b.dataset.pane === name)); }

/* ----------------------------------------------------------------- boot */
(async function boot() {
  try {
    S.spec = await api("spec"); buildForm(); applyLoaded(await api("config"));
    $("seed").addEventListener("change", () => { S.values.seed = parseInt($("seed").value, 10) || 0; onChange("seed"); });
    $("btn-run").addEventListener("click", () => submit("run", { theta0_deg: parseFloat($("run-theta").value), scheme: $("run-scheme").value }));
    $("btn-scan").addEventListener("click", () => submit("scan", {}));
    $("btn-sweep").addEventListener("click", () => { const path = $("sweep-path").value; const pts = parsePoints(path, $("sweep-points").value || $("sweep-points").placeholder);
      const gp = $("sweep-group").value || null; const gv = gp ? parsePoints(gp, $("sweep-group-values").value || $("sweep-group-values").placeholder) : null;
      submit("sweep", { path, points: pts, group_path: gp, group_values: gv, theta0_deg: parseFloat($("run-theta").value), scheme: $("run-scheme").value }); });
    $("lang").addEventListener("click", () => { LANG = LANG === "zh" ? "en" : "zh"; try { localStorage.setItem("arraytx.lang", LANG); } catch (e) { /* ignore */ }
      applyLang(); $("sweep-metric").innerHTML = ""; $("sweep-path").innerHTML = ""; $("sweep-group").innerHTML = ""; fillSweepSelectors(); fillRunSelectors(); renderAll(); renderQueue(); refreshForm(); });
    applyLang();
    restore();
    $("run-scheme").addEventListener("change", () => { $("run-scheme").dataset.touched = "1"; });
    $("btn-open").addEventListener("click", openConfig); $("btn-save").addEventListener("click", saveConfig);
    $("btn-revert").addEventListener("click", () => applyLoaded(S.loaded));
    $("btn-defaults").addEventListener("click", () => { S.spec.controls.forEach(c => { S.values[c.path] = c.default; }); onChange("defaults"); });
    $("btn-pin").addEventListener("click", () => { S.baseline = S.selected; renderAll(); });
    $("btn-unpin").addEventListener("click", () => { S.baseline = null; renderAll(); });
    $("filter").addEventListener("input", () => { const q = $("filter").value.trim().toLowerCase();
      Object.entries(ctlById).forEach(([path, row]) => { const c = S.spec.controls.find(x => x.path === path); const p = provenanceOf(path);
        const hit = !q || path.toLowerCase().includes(q) || c.help.toLowerCase().includes(q) || (p && (p.source + " " + (p.ref || "")).toLowerCase().includes(q));
        row.style.display = hit && visible(c) ? "" : "none"; if (hit && q) row.closest("details").open = true; }); });
    document.querySelectorAll("#bottom-nav button").forEach(b => b.addEventListener("click", () => showPane(b.dataset.pane)));
    showPane("results"); renderAll(); startPolling();
    // deep links (and the browser tests): ?smoke=1  ?run=30,none  ?scan=1
    const q = new URLSearchParams(location.search);
    if (q.get("smoke") === "1") $("smoke").checked = true;
    if (q.get("theta")) $("run-theta").value = q.get("theta");
    if (q.get("scheme")) { $("run-scheme").value = q.get("scheme"); $("run-scheme").dataset.touched = "1"; }
    if (q.get("run")) { const [t, s] = q.get("run").split(","); await validate(); submit("run", { theta0_deg: parseFloat(t), scheme: s || $("run-scheme").value }); }
    if (q.get("scan") === "1") { await validate(); submit("scan", {}); }
    if (q.get("sweep")) { const [path, ...pts] = q.get("sweep").split(","); await validate();
      const g = q.get("group") ? q.get("group").split(",") : null;
      submit("sweep", { path, points: parsePoints(path, pts.join(",")), group_path: g ? g[0] : null, group_values: g ? parsePoints(g[0], g.slice(1).join(",")) : null,
                        theta0_deg: parseFloat($("run-theta").value), scheme: $("run-scheme").value }); }
  } catch (e) { showError(e); }
})();
