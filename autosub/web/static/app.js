const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let sep = "/";
const join = (a, b) => a.replace(/[\\/]+$/, "") + sep + b;

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
  };
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function fmtDur(sec) {
  if (sec == null || !isFinite(sec)) return "";
  sec = Math.round(sec);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60), s = sec % 60;
  if (m < 60) return `${m}m ${String(s).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}

let state = null;
let defaults = { output: "" };

// Add form

let scanResult = null;
let outTouched = false;
let nameTouched = false;

$("in-path").addEventListener("change", () => scanInput($("in-path").value));
$("out-path").addEventListener("input", () => { outTouched = true; updatePreview(); });
$("name").addEventListener("input", () => { nameTouched = true; updatePreview(); });
$("in-browse").onclick = () => openPicker($("in-path").value || "", (p) => { $("in-path").value = p; scanInput(p); });
$("out-browse").onclick = () => openPicker($("out-path").value || defaults.output, (p) => {
  $("out-path").value = p; outTouched = true; updatePreview();
});

async function scanInput(path) {
  scanResult = null;
  $("add-error").textContent = "";
  const box = $("scan");
  if (!path.trim()) { box.textContent = ""; updatePreview(); return; }
  box.textContent = "Scanning…";
  try {
    scanResult = await api("/api/scan?path=" + encodeURIComponent(path));
  } catch (e) {
    box.innerHTML = `<span class="error-text">${esc(e.message)}</span>`;
    updatePreview();
    return;
  }
  const r = scanResult;
  if (!nameTouched) $("name").value = r.name;
  if (!outTouched) $("out-path").value = join(defaults.output, r.name);
  if (r.videos) {
    box.innerHTML = `<b>${r.videos}</b> episode${r.videos === 1 ? "" : "s"} found. They'll be queued as one season.`;
    if (r.seasons.length) box.innerHTML += ` <span class="hint">(Subfolders are ignored.)</span>`;
  } else if (r.seasons.length) {
    box.innerHTML = `This looks like a show with <b>${r.seasons.length}</b> season folder${r.seasons.length === 1 ? "" : "s"}. Each one is queued separately:` +
      `<div class="seasons">` + r.seasons.map((s, i) =>
        `<label><input type="checkbox" data-season="${i}" checked> <span>${esc(s.name)}</span><span class="count">${s.videos} episodes</span></label>`
      ).join("") + `</div>`;
    box.querySelectorAll("input[data-season]").forEach(cb => cb.onchange = updatePreview);
  } else {
    box.innerHTML = `<span class="error-text">No videos found here or in its subfolders.</span>`;
  }
  updatePreview();
}

function selectedSeasons() {
  if (!scanResult || scanResult.videos || !scanResult.seasons.length) return [];
  return [...document.querySelectorAll("input[data-season]")]
    .filter(cb => cb.checked).map(cb => scanResult.seasons[+cb.dataset.season]);
}

function updatePreview() {
  const out = $("out-path").value.trim();
  const multi = scanResult && !scanResult.videos && scanResult.seasons.length;
  $("name-wrap").hidden = !!multi;
  let html = "";
  let ok = false;
  if (out && scanResult) {
    if (multi) {
      const sel = selectedSeasons();
      ok = sel.length > 0;
      html = sel.map(s => `→ ${esc(join(join(out, s.name), "plex"))}`).join("<br>");
    } else if (scanResult.videos) {
      ok = true;
      html = `Plex-ready subtitles → ${esc(join(out, "plex"))}`;
    }
    if (ok) html += `<br>Folders that don't exist yet are created automatically.`;
  }
  $("out-preview").innerHTML = html;
  $("add-btn").disabled = !ok;
}

$("add-btn").onclick = async () => {
  const out = $("out-path").value.trim();
  const force = $("force").checked, sidecar = $("sidecar").checked;
  const jobs = scanResult.videos
    ? [{ name: $("name").value.trim() || scanResult.name, input: scanResult.path, output: out }]
    : selectedSeasons().map(s => ({ name: `${scanResult.name} – ${s.name}`, input: s.path, output: join(out, s.name) }));
  $("add-btn").disabled = true;
  $("add-error").textContent = "";
  try {
    for (const j of jobs) await api("/api/jobs", { ...j, force, sidecar });
    $("in-path").value = ""; $("name").value = ""; $("out-path").value = "";
    $("scan").textContent = `Added ${jobs.length} season${jobs.length === 1 ? "" : "s"} to the queue.`;
    scanResult = null; outTouched = false; nameTouched = false;
    updatePreview();
    refresh();
  } catch (e) {
    $("add-error").textContent = e.message;
    updatePreview();
  }
};

// Folder picker

let pickerPath = "";
let pickerDone = null;

async function openPicker(start, onChoose) {
  pickerDone = onChoose;
  $("pk-error").textContent = "";
  $("pk-newname").value = "";
  if (!$("pk-roots").children.length) {
    const roots = await api("/api/roots");
    $("pk-roots").innerHTML = roots.map(r =>
      `<button class="small" data-path="${esc(r.path)}">${esc(r.label)}</button>`).join("");
    $("pk-roots").querySelectorAll("button").forEach(b => b.onclick = () => go(b.dataset.path));
  }
  $("picker").showModal();
  await go(start, true);
}

async function go(path, fallback = false) {
  $("pk-error").textContent = "";
  try {
    const r = await api("/api/browse?path=" + encodeURIComponent(path));
    pickerPath = r.path;
    $("pk-path").value = r.path;
    $("pk-up").disabled = !r.parent;
    $("pk-up").onclick = () => go(r.parent);
    $("pk-info").textContent = r.videos ? `${r.videos} video${r.videos === 1 ? "" : "s"} in this folder` : "";
    $("pk-list").innerHTML = r.dirs.length
      ? r.dirs.map(d => `<button data-d="${esc(d)}"><span>📁</span><span>${esc(d)}</span></button>`).join("")
      : `<div class="empty">No subfolders</div>`;
    $("pk-list").querySelectorAll("button").forEach(b => b.onclick = () => go(join(r.path, b.dataset.d)));
  } catch (e) {
    if (fallback && path) {
      const parent = path.replace(/[\\/]+$/, "").replace(/[\\/][^\\/]*$/, "");
      return go(parent && parent !== path ? parent : "", true);
    }
    $("pk-error").textContent = e.message;
  }
}

$("pk-go").onclick = () => go($("pk-path").value);
$("pk-path").addEventListener("keydown", e => { if (e.key === "Enter") go($("pk-path").value); });
$("pk-cancel").onclick = () => $("picker").close();
$("pk-choose").onclick = () => { $("picker").close(); pickerDone && pickerDone(pickerPath); };
async function createFolder() {
  const name = $("pk-newname").value.trim();
  if (!name) return;
  try {
    const r = await api("/api/mkdir", { path: join(pickerPath, name) });
    $("pk-newname").value = "";
    await go(r.path);
  } catch (e) { $("pk-error").textContent = e.message; }
}
$("pk-create").onclick = createFolder;
$("pk-newname").addEventListener("keydown", e => { if (e.key === "Enter") createFolder(); });

// Queue

const expanded = new Set();
const ICON = { pending: "", running: "", done: "✓", skipped: "–", failed: "!" };
const EP_LABEL = { pending: "Waiting", running: "Transcribing…", done: "", skipped: "Already done", failed: "Failed" };

function counts(job) {
  const c = { total: job.episodes.length, done: 0, skipped: 0, failed: 0, running: 0, pending: 0 };
  for (const ep of job.episodes) c[ep.status]++;
  c.finished = c.done + c.skipped;
  return c;
}

function avgEpisodeSeconds() {
  const times = state.jobs.flatMap(j => j.episodes.filter(e => e.status === "done" && e.seconds).map(e => e.seconds));
  return times.length ? times.reduce((a, b) => a + b, 0) / times.length : null;
}

function remainingSeconds(job, avg) {
  if (!avg) return null;
  let rem = 0;
  for (const ep of job.episodes) {
    if (ep.status === "pending") rem += avg;
    if (ep.status === "running") rem += Math.max(avg - (Date.now() / 1000 - ep.started), avg * 0.1);
  }
  return rem;
}

function bar(c) {
  const pct = (n) => c.total ? (n / c.total * 100) : 0;
  return `<span class="b-done" style="width:${pct(c.finished)}%"></span>` +
         `<span class="b-fail" style="width:${pct(c.failed)}%"></span>` +
         `<span class="b-run" style="width:${pct(c.running)}%"></span>`;
}

function renderOverall() {
  const active = state.jobs.filter(j => ["queued", "running"].includes(j.status));
  const all = { total: 0, finished: 0, failed: 0, running: 0, done: 0, skipped: 0, pending: 0 };
  for (const j of state.jobs) {
    const c = counts(j);
    for (const k in all) all[k] += c[k];
  }
  const avg = avgEpisodeSeconds();
  const rem = active.reduce((s, j) => s + (remainingSeconds(j, avg) || 0), 0);
  const runningEp = state.jobs.flatMap(j => j.episodes.filter(e => e.status === "running").map(e => ({ j, e })))[0];
  $("overall").innerHTML = `
    <div class="stat"><div class="v">${active.length}</div><div class="k">Season${active.length === 1 ? "" : "s"} in queue</div></div>
    <div class="stat"><div class="v">${all.finished} / ${all.total}</div><div class="k">Episodes finished</div></div>
    <div class="stat"><div class="v">${active.length && avg ? "~" + fmtDur(rem) : "–"}</div><div class="k">Estimated time left</div></div>
    <div class="stat"><div class="v">${avg ? fmtDur(avg) : "–"}</div><div class="k">Avg. per episode</div></div>`;
  $("overall-bar").innerHTML = bar(all);
  $("overall-bar").hidden = !all.total;
  document.title = runningEp ? `${all.finished}/${all.total} · AutoSub` : "AutoSub";
}

function jobButtons(job) {
  const b = [];
  const idx = state.jobs.indexOf(job);
  b.push(`<button class="small ghost" data-act="up" ${idx === 0 ? "disabled" : ""} title="Move up">↑</button>`);
  b.push(`<button class="small ghost" data-act="down" ${idx === state.jobs.length - 1 ? "disabled" : ""} title="Move down">↓</button>`);
  if (job.status === "running") b.push(job.stop_requested
    ? `<button class="small" disabled>Stopping after this episode…</button>`
    : `<button class="small" data-act="stop">Stop after this episode</button>`);
  if (job.status === "queued") b.push(`<button class="small" data-act="stop">Pause</button>`);
  if (["failed", "stopped"].includes(job.status)) b.push(`<button class="small" data-act="retry">${job.status === "stopped" ? "Resume" : "Retry failed"}</button>`);
  b.push(`<button class="small" data-act="reveal">Open output</button>`);
  if (job.status !== "running") b.push(`<button class="small ghost" data-act="remove">Remove</button>`);
  b.push(`<button class="small ghost" data-act="toggle">${expanded.has(job.id) ? "Hide episodes" : "Show episodes"}</button>`);
  return b.join("");
}

function renderJobs() {
  const box = $("jobs");
  if (!state.jobs.length) {
    box.innerHTML = `<div class="empty">Nothing queued yet. Add a season above.</div>`;
    return;
  }
  const avg = avgEpisodeSeconds();
  box.innerHTML = state.jobs.map(job => {
    const c = counts(job);
    const rem = ["queued", "running"].includes(job.status) ? remainingSeconds(job, avg) : null;
    const statusText = { queued: "Queued", running: "Running", done: "Done", failed: "Has failures", stopped: "Paused" }[job.status];
    const parts = [`${c.finished} of ${c.total} episodes`];
    if (c.skipped) parts.push(`${c.skipped} already done`);
    if (c.failed) parts.push(`${c.failed} failed`);
    let right = "";
    if (job.status === "running" && rem != null) right = `~${fmtDur(rem)} left`;
    else if (job.status === "done" && job.started && job.finished) right = `Took ${fmtDur(job.finished - job.started)}`;
    const eps = expanded.has(job.id) ? `<div class="episodes">` + job.episodes.map(ep => {
      let t = EP_LABEL[ep.status];
      if (ep.status === "done") t = fmtDur(ep.seconds);
      if (ep.status === "running" && ep.started) t = `Transcribing… ${fmtDur(Date.now() / 1000 - ep.started)}`;
      return `<div class="ep ${ep.status}">
        <span class="icon i-${ep.status}">${ICON[ep.status]}</span>
        <span class="name" title="${esc(ep.name)}">${esc(ep.name)}</span>
        <span class="t" ${ep.status === "running" && ep.started ? `data-started="${ep.started}"` : ""}>${esc(t)}</span>
        ${ep.error ? `<div class="err">${esc(ep.error)}</div>` : ""}
      </div>`;
    }).join("") + `</div>` : "";
    return `<div class="job" data-id="${job.id}">
      <div class="job-head">
        <div class="job-title"><strong>${esc(job.name)}</strong><span class="chip s-${job.status}">${statusText}</span></div>
        <div class="paths">
          <div><b>From</b> ${esc(job.input)}</div>
          <div><b>To</b> ${esc(job.output)}${job.sidecar ? " &nbsp;·&nbsp; also next to videos" : ""}${job.force ? " &nbsp;·&nbsp; redo all" : ""}</div>
        </div>
        <div class="bar">${bar(c)}</div>
        <div class="job-meta"><span>${parts.join(" · ")}</span><span>${right}</span></div>
        <div class="job-buttons">${jobButtons(job)}</div>
      </div>
      ${eps}
    </div>`;
  }).join("");
  box.querySelectorAll("[data-act]").forEach(btn => btn.onclick = () => onJobAction(btn));
}

async function onJobAction(btn) {
  const id = btn.closest(".job").dataset.id;
  const job = state.jobs.find(j => j.id === id);
  const act = btn.dataset.act;
  try {
    if (act === "toggle") { expanded.has(id) ? expanded.delete(id) : expanded.add(id); renderJobs(); return; }
    if (act === "reveal") { await api("/api/reveal", { path: job.output }); return; }
    if (act === "remove" && !confirmRemove(job)) return;
    await api("/api/action", { id, action: act });
    refresh();
  } catch (e) { alertInline(btn, e.message); }
}

function confirmRemove(job) {
  return job.status === "done" || window.confirm(`Remove "${job.name}" from the queue? Subtitles already written are kept.`);
}

function alertInline(btn, msg) {
  const meta = btn.closest(".job").querySelector(".job-meta span");
  meta.innerHTML = `<span class="error-text">${esc(msg)}</span>`;
}

$("clear-btn").onclick = async () => { await api("/api/clear", {}); refresh(); };

// Status + polling

function renderEngine() {
  const b = state.backend;
  const el = $("engine");
  const color = { idle: "var(--muted)", loading: "var(--warn)", ready: "var(--ok)", error: "var(--bad)" }[b.status];
  const text = {
    idle: `${b.name === "mlx" ? "MLX" : "ONNX Runtime"} · model loads when the first job starts`,
    loading: "Loading model… (first run downloads it)",
    ready: b.label,
    error: "Model failed to load: " + b.error,
  }[b.status];
  el.style.color = color;
  el.lastElementChild.textContent = text;
  el.title = text;
  const tb = $("tools-banner");
  tb.hidden = !state.missing_tools.length;
  tb.textContent = `${state.missing_tools.join(" and ")} not found. Install FFmpeg (see README) and restart AutoSub.`;
}

let lastJson = "";
async function refresh() {
  try {
    const s = await api("/api/state");
    state = s;
    if (!defaults.output) defaults.output = s.default_output;
    sep = s.path_sep;
    if (!$("out-path").value && !outTouched && !scanResult) $("out-path").placeholder = s.default_output;
    renderEngine();
    renderOverall();
    const json = JSON.stringify(s.jobs) + [...expanded].join();
    // Only re-render on change so buttons aren't replaced mid-click.
    if (json !== lastJson) {
      lastJson = json;
      renderJobs();
    }
  } catch (e) {
    $("engine").style.color = "var(--bad)";
    $("engine").lastElementChild.textContent = "Can't reach AutoSub. Is it still running?";
  }
}

function tickTimers() {
  document.querySelectorAll(".t[data-started]").forEach(el => {
    el.textContent = `Transcribing… ${fmtDur(Date.now() / 1000 - +el.dataset.started)}`;
  });
}

refresh();
setInterval(refresh, 1500);
setInterval(tickTimers, 1000);
