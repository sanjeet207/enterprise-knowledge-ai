"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const TOKEN_KEY = "eka_token";
  const LEVELS = { 1: "Analyst", 2: "Manager", 3: "Director", 4: "Partner" };
  const DEMO = [
    ["analyst@acme.test", "Analyst (level 1)"],
    ["manager@acme.test", "Manager (level 2)"],
    ["director@acme.test", "Director (level 3)"],
    ["manager_titan@acme.test", "Manager, Project Titan team"],
    ["director_titan@acme.test", "Director, Project Titan team"],
    ["partner_titan@acme.test", "Partner, Project Titan team"],
    ["partner_outsider@acme.test", "Partner, not on Titan"],
    ["admin@acme.test", "Administrator (knowledge team), uploads and manages"],
    ["globex_analyst@globex.test", "Other company: Globex analyst"]
  ];
  const DEMO_PASSWORD = "DemoPass2026x";
  const SUGGESTIONS = [
    "How many days of annual leave do I get?",
    "Do I need approval to travel to an international conference?",
    "How quickly must I report a security incident?",
    "What is the compensation band for a manager?",
    "What is the weather in Delhi today?"
  ];
  const OUTCOME_LABEL = {
    answered: "Answered", general: "General knowledge", refused: "Not available", no_answer: "Not in documents",
    unverified: "Could not verify", error: "Error"
  };

  let token = null, me = null, busy = false;

  function store(get, val) {
    try { return get ? sessionStorage.getItem(TOKEN_KEY) : (val ? sessionStorage.setItem(TOKEN_KEY, val) : sessionStorage.removeItem(TOKEN_KEY)); }
    catch (e) { return null; }
  }
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  async function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({}, opts.headers || {});
    if (token) opts.headers.Authorization = "Bearer " + token;
    const res = await fetch(path, opts);
    if (res.status === 401 && token) { signOut(); throw new Error("Session expired. Please sign in again."); }
    return res;
  }

  function show(view) {
    $("login-view").hidden = view !== "login";
    $("app-view").hidden = view !== "app";
  }

  function signOut() {
    token = null; me = null; convId = null; store(false, null);
    $("messages").querySelectorAll(".msg").forEach((m) => m.remove());
    $("empty").hidden = false;
    clearSources();
    show("login");
  }

  async function enter() {
    const res = await api("/auth/me");
    if (!res.ok) throw new Error("Could not load your profile.");
    me = await res.json();
    $("who-email").textContent = me.email;
    $("who-role").textContent = (LEVELS[me.level] || "Level " + me.level) + " · L" + me.level + (me.is_admin ? " · Admin" : "");
    $("tab-audit").hidden = me.level < 4;
    $("tab-docs").hidden = !(me.is_admin || me.level >= 2);
    $("tab-admin").hidden = !me.is_admin;
    selectTab("chat");
    show("app");
    resetChat(); loadConversations("");
    $("question").focus();
  }

  async function login(email, password) {
    const err = $("login-error");
    err.hidden = true;
    $("login-button").disabled = true;
    try {
      const body = new URLSearchParams({ username: email, password: password });
      const res = await fetch("/auth/login", { method: "POST", body: body });
      if (!res.ok) throw new Error(res.status === 401 ? "Incorrect email or password." : "Sign-in failed (" + res.status + ").");
      token = (await res.json()).access_token;
      store(false, token);
      await enter();
    } catch (e) {
      err.textContent = e.message; err.hidden = false;
    } finally {
      $("login-button").disabled = false;
    }
  }

  /* ---------- chat ---------- */
  function clearSources() {
    $("sources-list").replaceChildren();
    $("sources-hint").hidden = false;
    $("sources-hint").textContent = "Documents cited by the latest answer appear here.";
  }

  function renderSources(sources, msgId) {
    const list = $("sources-list");
    list.replaceChildren();
    if (!sources || !sources.length) { clearSources(); return; }
    $("sources-hint").hidden = true;
    sources.forEach((s) => {
      const li = el("li", "source");
      li.id = "src-" + msgId + "-" + s.number;
      const top = el("div");
      top.append(el("span", "n", String(s.number)), el("span", "t", s.title));
      const bar = el("div", "bar"), fill = el("span");
      const pct = Math.max(2, Math.min(100, Math.round((s.score || 0) * 100)));
      fill.style.width = pct + "%";
      bar.append(fill);
      li.append(top, bar, el("div", "s", "Relevance " + (s.score || 0).toFixed(2)));
      list.append(li);
    });
  }

  function highlightSource(msgId, n) {
    const target = document.getElementById("src-" + msgId + "-" + n);
    if (!target) return;
    document.querySelectorAll(".source.hl").forEach((x) => x.classList.remove("hl"));
    target.classList.add("hl");
    target.scrollIntoView({ block: "nearest" });
  }

  function renderAnswerText(container, text, msgId, sources) {
    const valid = new Set((sources || []).map((s) => s.number));
    const parts = String(text).split(/(\[\d+\])/g);
    parts.forEach((p) => {
      const m = /^\[(\d+)\]$/.exec(p);
      if (m && valid.has(Number(m[1]))) {
        const b = el("button", "cite", m[1]);
        b.type = "button";
        b.title = "Show source " + m[1];
        b.addEventListener("click", () => { renderSources(sources, msgId); highlightSource(msgId, Number(m[1])); });
        container.append(b);
      } else if (p) {
        container.append(document.createTextNode(p));
      }
    });
  }

  function addMessage(role, cls) {
    $("empty").hidden = true;
    const m = el("div", "msg " + role + (cls ? " " + cls : ""));
    $("messages").append(m);
    $("messages").scrollTop = $("messages").scrollHeight;
    return m;
  }

  let counter = 0, convId = null;

  function renderBot(bot, data, msgId) {
    bot.replaceChildren();
    bot.append(tag(data.outcome));
    if (data.corrected_query) bot.append(el("span", "note", "Searched for: " + data.corrected_query));
    const b = el("span", "body");
    if (data.outcome === "answered") renderAnswerText(b, data.answer, msgId, data.sources);
    else b.textContent = data.answer;
    bot.append(b);
    if (data.outcome === "general") bot.append(el("span", "note", "General knowledge, not from company documents. Check it before relying on it."));
    if (data.outcome === "answered") renderSources(data.sources, msgId); else clearSources();
    if (data.message_id && (data.outcome === "answered" || data.outcome === "general" || data.outcome === "no_answer")) bot.append(feedbackBar(data.message_id, data.rating));
  }

  function feedbackBar(messageId, current) {
    const bar = el("div", "feedback");
    const up = el("button", current === 1 ? "on" : "", "Helpful"), down = el("button", current === -1 ? "on" : "", "Not helpful");
    up.type = down.type = "button";
    const send = async (rating, comment) => {
      const r = await api("/chat/messages/" + messageId + "/feedback", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rating: rating, comment: comment || null })
      });
      bar.replaceChildren(el("span", "thanks", r.ok ? "Thanks, your feedback was recorded." : "Could not save feedback."));
    };
    up.addEventListener("click", () => send(1));
    down.addEventListener("click", () => {
      const box = el("input"); box.type = "text"; box.maxLength = 500; box.placeholder = "What was wrong? (optional)";
      const go = el("button", null, "Send"); go.type = "button";
      go.addEventListener("click", () => send(-1, box.value));
      bar.replaceChildren(box, go); box.focus();
    });
    bar.append(up, down);
    return bar;
  }

  async function ask(question) {
    if (busy || !question.trim()) return;
    busy = true; $("send").disabled = true;
    const msgId = ++counter;
    addMessage("user").textContent = question;
    const bot = addMessage("bot", "thinking");
    bot.textContent = "Searching documents you are allowed to see...";
    try {
      const res = await api("/chat/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: question, top_k: 3, conversation_id: convId })
      });
      bot.classList.remove("thinking");
      bot.replaceChildren();
      if (!res.ok) {
        const msg = res.status === 503 ? "The language model is not reachable right now. Please try again shortly."
          : res.status === 429 ? "You are asking too quickly. Please wait a moment."
          : res.status === 422 ? "That question could not be processed. Keep it under 1000 characters."
          : "Something went wrong (" + res.status + ").";
        bot.append(tag("error"), body(msg));
      } else {
        const data = await res.json();
        convId = data.conversation_id;
        renderBot(bot, data, msgId);
        loadConversations(convId);
      }
    } catch (e) {
      bot.classList.remove("thinking");
      bot.replaceChildren(tag("error"), body(e.message || "Network error."));
    } finally {
      busy = false; $("send").disabled = false;
      $("messages").scrollTop = $("messages").scrollHeight;
      $("question").focus();
    }
  }
  function tag(outcome) { return el("span", "tag " + outcome, OUTCOME_LABEL[outcome] || outcome); }
  function body(t) { return el("span", "body", t); }

  /* ---------- saved conversations ---------- */
  function resetChat() {
    convId = null;
    $("messages").querySelectorAll(".msg").forEach((m) => m.remove());
    $("empty").hidden = false;
    clearSources();
  }
  async function loadConversations(selectId) {
    const res = await api("/chat/conversations");
    if (!res.ok) return;
    const list = (await res.json()).conversations;
    const sel = $("conv-select");
    sel.replaceChildren();
    const fresh = el("option", null, "New conversation"); fresh.value = ""; sel.append(fresh);
    list.forEach((c) => { const o = el("option", null, c.title); o.value = c.id; sel.append(o); });
    sel.value = selectId || "";
    $("del-chat").hidden = !sel.value;
  }
  async function openConversation(id) {
    if (!id) { resetChat(); $("del-chat").hidden = true; return; }
    const res = await api("/chat/conversations/" + id);
    if (!res.ok) { resetChat(); return; }
    resetChat();
    convId = id;
    $("del-chat").hidden = false;
    (await res.json()).messages.forEach((m) => {
      const msgId = ++counter;
      if (m.role === "user") { addMessage("user").textContent = m.content; return; }
      renderBot(addMessage("bot"), { outcome: m.outcome, answer: m.content, sources: m.sources, message_id: m.id, rating: m.rating }, msgId);
    });
    clearSources();
    $("messages").scrollTop = $("messages").scrollHeight;
  }

  /* ---------- audit ---------- */
  async function loadAudit() {
    const tbody = $("audit-table").querySelector("tbody");
    tbody.replaceChildren();
    $("audit-empty").hidden = true;
    const res = await api("/audit/events");
    if (!res.ok) { $("audit-empty").textContent = res.status === 403 ? "Only partners can view the audit log." : "Could not load audit log."; $("audit-empty").hidden = false; return; }
    const data = await res.json();
    const rows = Array.isArray(data) ? data : (data.events || data.items || []);
    if (!rows.length) { $("audit-empty").textContent = "No events yet."; $("audit-empty").hidden = false; return; }
    rows.forEach((r) => {
      const tr = el("tr");
      const when = r.created_at ? new Date(r.created_at).toLocaleString() : "";
      const score = typeof r.top_score === "number" ? r.top_score.toFixed(3) : "";
      const q = el("td", "q", r.query || "");
      const oc = el("td"); oc.append(tag(r.outcome));
      tr.append(el("td", null, when), el("td", null, r.user_email || ""), el("td", null, r.role_level != null ? "L" + r.role_level : ""),
        q, oc, el("td", null, score), el("td", null, r.latency_ms != null ? String(r.latency_ms) : ""), el("td", "q", r.rewritten_query || ""),
        el("td", "q", (r.trace || []).map((x) => x.agent + " " + x.ms + "ms" + (x.detail ? " (" + x.detail + ")" : "")).join(" > ")));
      tbody.append(tr);
    });
  }

  /* ---------- documents ---------- */
  let upOptions = null;
  function note(id, text, ok) {
    const n = $(id);
    n.textContent = text; n.hidden = !text;
    n.className = "small " + (ok ? "ok-text" : "bad-text");
  }
  async function errText(res) {
    try { const j = await res.json(); return typeof j.detail === "string" ? j.detail : "Request failed (" + res.status + ")."; }
    catch (e) { return "Request failed (" + res.status + ")."; }
  }
  function fillSelect(sel, items) {
    sel.replaceChildren();
    items.forEach(([v, label]) => { const o = el("option", null, label); o.value = v; sel.append(o); });
  }
  async function loadDocs() {
    const optRes = await api("/documents/options");
    upOptions = optRes.ok ? await optRes.json() : { can_upload: false, teams: [], max_level: 0 };
    $("upload-form").parentElement.hidden = !upOptions.can_upload;
    if (upOptions.can_upload) {
      const levels = [];
      for (let l = 1; l <= upOptions.max_level; l++) levels.push([String(l), "Level " + l + " and above (" + LEVELS[l] + ")"]);
      fillSelect($("up-level"), levels);
      const teams = upOptions.company_wide ? [["", "Company-wide (no team restriction)"]] : [];
      upOptions.teams.forEach((t) => teams.push([t.id, t.name]));
      fillSelect($("up-team"), teams);
      $("upload-hint").textContent = upOptions.company_wide
        ? "You publish documents for the whole company. Choose who may read the document; a team adds a second restriction."
        : "You can add documents to the engagement teams you belong to, up to your own level. Company-wide documents are published by the administrators.";
      $("up-button").disabled = !teams.length;
      if (!teams.length) note("upload-msg", "You are not a member of any engagement team yet. Ask an administrator to add you.", false);
    }
    const isAdmin = me.is_admin;
    $("docs-title").textContent = isAdmin ? "All company documents" : "Documents you added";
    $("docs-hint").textContent = isAdmin ? "You see titles and settings, not the content. Reading follows each person's own level." : "";
    const tbody = $("docs-table").querySelector("tbody");
    tbody.replaceChildren(); $("docs-empty").hidden = true;
    const res = await api("/documents");
    if (!res.ok) { $("docs-empty").textContent = "Could not load documents."; $("docs-empty").hidden = false; return; }
    const rows = (await res.json()).documents;
    fillSelect($("up-version"), [["", "No, a new document"]].concat(rows.filter((d) => d.status === "published")
      .map((d) => [d.document_id, "Yes, replaces: " + d.title + " (v" + d.version + ")"])));
    syncVersionChoice();
    if (!rows.length) { $("docs-empty").hidden = false; return; }
    rows.forEach((d) => {
      const tr = el("tr");
      const del = el("button", "danger", "Delete");
      del.type = "button";
      del.addEventListener("click", async () => {
        if (!window.confirm('Delete "' + d.title + '" and remove it from search?')) return;
        const r = await api("/documents/" + d.document_id, { method: "DELETE" });
        if (!r.ok) note("upload-msg", await errText(r), false); else { note("upload-msg", 'Deleted "' + d.title + '".', true); loadDocs(); }
      });
      const last = el("td");
      if (me.is_admin && d.status === "pending") {
        const ok = el("button", "primary", "Approve"); ok.type = "button";
        ok.addEventListener("click", async () => {
          const r = await api("/admin/documents/" + d.document_id + "/approve", { method: "POST" });
          note("upload-msg", r.ok ? '"' + d.title + '" is now searchable.' : await errText(r), r.ok);
          loadDocs();
        });
        last.append(ok, document.createTextNode(" "));
        del.textContent = "Reject";
      }
      last.append(del);
      if (d.supersedes) {
        const cmp = el("button", "secondary", "What changed?"); cmp.type = "button";
        cmp.addEventListener("click", () => compareDocs(d.supersedes, d.document_id));
        last.append(document.createTextNode(" "), cmp);
      }
      const st = el("td"); st.append(el("span", "tag " + d.status, d.status === "pending" ? "Waiting for approval" : d.status === "archived" ? "Replaced" : "Live"));
      tr.append(el("td", "q", (d.title || "") + (d.version > 1 ? "  (v" + d.version + ")" : "")), st, el("td", null, "L" + d.level), el("td", null, d.team || "Company-wide"), reviewCell(d.review_by),
        el("td", null, String(d.sections)), el("td", null, d.uploaded_by || "(seeded)"),
        el("td", null, d.created_at ? new Date(d.created_at).toLocaleDateString() : ""), last);
      tbody.append(tr);
    });
  }

  function syncVersionChoice() {
    const replacing = $("up-version").value !== "";
    $("up-level").disabled = replacing; $("up-team").disabled = replacing;
  }

  async function compareDocs(oldId, newId) {
    const box = $("compare-box");
    box.hidden = false;
    $("compare-title").textContent = "Comparing...";
    $("compare-changes").replaceChildren(); $("compare-summary").hidden = true; $("compare-note").hidden = true;
    box.scrollIntoView({ block: "nearest" });
    const r = await adminCall("/documents/compare", "POST", { document_a: oldId, document_b: newId });
    if (!r.ok) { $("compare-title").textContent = "Could not compare"; $("compare-meta").textContent = await errText(r); return; }
    const d = await r.json();
    $("compare-title").textContent = d.old.title + ": v" + d.old.version + " to v" + d.new.version;
    $("compare-meta").textContent = d.total_changes + " change(s), " + d.unchanged + " sentence(s) unchanged." + (d.total_changes > d.changes.length ? " Showing the first " + d.changes.length + "." : "");
    if (d.summary) { $("compare-summary").textContent = d.summary; $("compare-summary").hidden = false; }
    if (d.note) { $("compare-note").textContent = d.note; $("compare-note").hidden = false; }
    d.changes.forEach((c) => {
      const box2 = el("div", "change " + c.type);
      box2.append(el("b", null, c.type));
      if (c.before) box2.append(el("div", c.type === "changed" ? "before" : null, c.before));
      if (c.after) box2.append(el("div", null, c.after));
      $("compare-changes").append(box2);
    });
  }

  function reviewCell(day) {
    const td = el("td");
    if (!day) { td.textContent = "-"; return td; }
    const overdue = day < new Date().toISOString().slice(0, 10);
    td.append(el("span", overdue ? "bad-text" : null, day + (overdue ? " (overdue)" : "")));
    return td;
  }

  async function upload(e) {
    e.preventDefault();
    const f = $("up-file").files[0];
    if (!f) return;
    const form = new FormData();
    form.append("file", f);
    form.append("title", $("up-title").value);
    form.append("classification_level", $("up-level").value);
    form.append("engagement_id", $("up-team").value);
    form.append("review_by", $("up-review").value);
    form.append("new_version_of", $("up-version").value);
    $("up-button").disabled = true;
    note("upload-msg", "Reading and indexing " + f.name + "...", true);
    try {
      const res = await api("/documents/upload", { method: "POST", body: form });
      if (!res.ok) { note("upload-msg", await errText(res), false); return; }
      const d = await res.json();
      note("upload-msg", d.status === "pending"
        ? '"' + d.title + '" was received and waits for an administrator to approve it before anyone can search it.'
        : '"' + d.title + '" is now searchable (' + d.parents_created + " sections).", true);
      $("upload-form").reset();
      loadDocs();
    } catch (err) { note("upload-msg", err.message, false); }
    finally { $("up-button").disabled = false; }
  }

  /* ---------- administration ---------- */
  async function adminCall(path, method, payload) {
    const opts = { method: method };
    if (payload) { opts.headers = { "Content-Type": "application/json" }; opts.body = JSON.stringify(payload); }
    return api(path, opts);
  }
  function levelSelect(value, onChange) {
    const sel = el("select");
    fillSelect(sel, [1, 2, 3, 4].map((l) => [String(l), "L" + l + " " + LEVELS[l]]));
    sel.value = String(value);
    sel.addEventListener("change", () => onChange(Number(sel.value)));
    return sel;
  }
  function checkbox(value, disabled, onChange) {
    const c = el("input"); c.type = "checkbox"; c.checked = value; c.disabled = disabled;
    c.addEventListener("change", () => onChange(c.checked));
    return c;
  }
  async function patchUser(id, change) {
    const r = await adminCall("/admin/users/" + id, "PATCH", change);
    note("user-msg", r.ok ? "Saved." : await errText(r), r.ok);
    loadAdmin();
  }
  async function loadAdmin() {
    const [uRes, tRes, eRes, iRes] = await Promise.all([api("/admin/users"), api("/admin/teams"), api("/admin/events"), api("/admin/insights")]);
    if (iRes.ok) {
      const i = await iRes.json();
      const box = $("stats"); box.replaceChildren();
      const stat = (v, label) => { const d = el("div", "stat"); d.append(el("b", null, String(v)), el("span", null, label)); box.append(d); };
      stat(i.total, "questions");
      stat(i.reviews_overdue || 0, "documents past their review date");
      stat(i.answered_rate === null ? "n/a" : Math.round(i.answered_rate * 100) + "%", "answered from documents");
      stat(i.outcomes.refused || 0, "not available to the asker");
      stat(i.outcomes.no_answer || 0, "not in the documents");
      stat(i.median_latency_ms === null ? "n/a" : (i.median_latency_ms / 1000).toFixed(1) + " s", "median answer time");
      stat((i.feedback.helpful) + " / " + (i.feedback.not_helpful), "helpful / not helpful ratings");
      const ub = $("unhelpful-table").querySelector("tbody"); ub.replaceChildren();
      i.unhelpful_questions.forEach((g) => { const tr = el("tr"); tr.append(el("td", "q", g.question), el("td", null, String(g.times))); ub.append(tr); });
      const gb = $("gaps-table").querySelector("tbody"); gb.replaceChildren();
      i.content_gaps.forEach((g) => { const tr = el("tr"); tr.append(el("td", "q", g.question), el("td", null, String(g.times))); gb.append(tr); });
      $("gaps-empty").hidden = i.content_gaps.length > 0;
    }
    if (!uRes.ok) { note("user-msg", await errText(uRes), false); return; }
    const users = (await uRes.json()).users;
    const tbody = $("users-table").querySelector("tbody");
    tbody.replaceChildren();
    users.forEach((u) => {
      const self = u.email.toLowerCase() === me.email.toLowerCase();
      const lockedMark = u.locked ? " (locked after failed sign-ins: reset the password to unlock)" : "";
      const pw = el("input"); pw.type = "password"; pw.placeholder = "Set new password"; pw.autocomplete = "new-password";
      const set = el("button", "secondary", "Reset"); set.type = "button";
      set.addEventListener("click", () => { if (pw.value) patchUser(u.id, { password: pw.value }); });
      const pwCell = el("td"); pwCell.append(pw, document.createTextNode(" "), set);
      const lv = el("td"), ad = el("td"), ac = el("td");
      if (self) { lv.textContent = "L" + u.level; ad.textContent = u.is_admin ? "Yes" : "No"; ac.textContent = "Yes (you)"; }
      else {
        lv.append(levelSelect(u.level, (v) => patchUser(u.id, { level: v })));
        ad.append(checkbox(u.is_admin, false, (v) => patchUser(u.id, { is_admin: v })));
        ac.append(checkbox(u.is_active, false, (v) => patchUser(u.id, { is_active: v })));
      }
      const tr = el("tr"); tr.append(el("td", null, u.email + lockedMark), lv, ad, ac, pwCell);
      tbody.append(tr);
    });
    // teams
    const list = $("teams-list");
    list.replaceChildren();
    if (tRes.ok) {
      (await tRes.json()).teams.forEach((t) => {
        const box = el("div", "team"); box.append(el("h3", null, t.name));
        const chips = el("div", "chips");
        t.members.forEach((m) => {
          const c = el("span", "chip", m.email);
          const x = el("button", null, "×"); x.type = "button"; x.title = "Remove " + m.email;
          x.addEventListener("click", async () => { await adminCall("/admin/teams/" + t.id + "/members/" + m.user_id, "DELETE"); loadAdmin(); });
          c.append(x); chips.append(c);
        });
        if (!t.members.length) chips.append(el("span", "muted small", "No members yet."));
        const add = el("div", "team-add");
        const sel = el("select");
        const taken = new Set(t.members.map((m) => m.user_id));
        fillSelect(sel, users.filter((u) => !taken.has(u.id) && u.is_active).map((u) => [u.id, u.email]));
        const btn = el("button", "secondary", "Add member"); btn.type = "button";
        btn.addEventListener("click", async () => { if (sel.value) { await adminCall("/admin/teams/" + t.id + "/members", "POST", { user_id: sel.value }); loadAdmin(); } });
        add.append(sel, btn);
        box.append(chips, add); list.append(box);
      });
    }
    const ebody = $("events-table").querySelector("tbody");
    ebody.replaceChildren();
    if (eRes.ok) (await eRes.json()).events.forEach((ev) => {
      const tr = el("tr");
      tr.append(el("td", null, new Date(ev.created_at).toLocaleString()), el("td", null, ev.actor_email), el("td", null, ev.action), el("td", "q", ev.target));
      ebody.append(tr);
    });
  }

  async function addUser(e) {
    e.preventDefault();
    const r = await adminCall("/admin/users", "POST", {
      email: $("nu-email").value, password: $("nu-pass").value, level: Number($("nu-level").value), is_admin: $("nu-admin").value === "yes"
    });
    if (r.ok) { $("user-form").reset(); note("user-msg", "Person added.", true); loadAdmin(); }
    else note("user-msg", await errText(r), false);
  }
  async function addTeam(e) {
    e.preventDefault();
    const r = await adminCall("/admin/teams", "POST", { name: $("nt-name").value });
    if (r.ok) { $("team-form").reset(); loadAdmin(); } else note("user-msg", await errText(r), false);
  }

  const PANELS = { chat: "chat-panel", docs: "docs-panel", admin: "admin-panel", audit: "audit-panel" };
  function selectTab(name) {
    Object.keys(PANELS).forEach((k) => {
      $(PANELS[k]).hidden = k !== name;
      $("tab-" + k).classList.toggle("active", k === name);
      $("tab-" + k).setAttribute("aria-selected", String(k === name));
    });
    const fail = (id) => (e) => { $(id).textContent = e.message; $(id).hidden = false; };
    if (name === "audit") loadAudit().catch(fail("audit-empty"));
    if (name === "docs") loadDocs().catch(fail("docs-empty"));
    if (name === "admin") loadAdmin().catch((e) => note("user-msg", e.message, false));
  }

  /* ---------- wiring ---------- */
  DEMO.forEach(([email, label]) => {
    const b = el("button");
    b.type = "button";
    b.append(el("span", null, label), el("span", "lvl", email));
    b.addEventListener("click", () => login(email, DEMO_PASSWORD));
    $("demo-list").append(b);
  });
  SUGGESTIONS.forEach((q, i) => {
    const b = el("button", i === SUGGESTIONS.length - 1 ? "try" : "", q);
    b.type = "button";
    b.addEventListener("click", () => ask(q));
    $("suggestions").append(b);
  });

  $("login-form").addEventListener("submit", (e) => { e.preventDefault(); login($("email").value.trim(), $("password").value); });
  $("logout").addEventListener("click", signOut);
  $("my-data").addEventListener("click", async () => {
    const r = await api("/me/data");
    if (!r.ok) return;
    const url = URL.createObjectURL(await r.blob());
    const a = el("a"); a.href = url; a.download = "my-data.json"; document.body.append(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  });
  $("tab-chat").addEventListener("click", () => selectTab("chat"));
  $("conv-select").addEventListener("change", (e) => openConversation(e.target.value));
  $("new-chat").addEventListener("click", () => { resetChat(); loadConversations(""); $("question").focus(); });
  $("del-chat").addEventListener("click", async () => {
    if (!convId || !window.confirm("Delete this conversation?")) return;
    await api("/chat/conversations/" + convId, { method: "DELETE" });
    resetChat(); loadConversations("");
  });
  $("tab-audit").addEventListener("click", () => selectTab("audit"));
  $("tab-docs").addEventListener("click", () => selectTab("docs"));
  $("tab-admin").addEventListener("click", () => selectTab("admin"));
  $("upload-form").addEventListener("submit", upload);
  $("docs-refresh").addEventListener("click", () => loadDocs());
  $("up-version").addEventListener("change", syncVersionChoice);
  $("compare-close").addEventListener("click", () => { $("compare-box").hidden = true; });
  $("user-form").addEventListener("submit", addUser);
  $("team-form").addEventListener("submit", addTeam);
  fillSelect($("nu-level"), [1, 2, 3, 4].map((l) => [String(l), "L" + l + " " + LEVELS[l]]));
  $("audit-refresh").addEventListener("click", () => loadAudit());
  $("chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("question").value;
    $("question").value = ""; $("question").style.height = "auto";
    ask(q);
  });
  $("question").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("chat-form").requestSubmit(); }
  });
  $("question").addEventListener("input", (e) => {
    e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
  });

  async function startup() {
    // Single sign-on returns here with the session token (or an error flag) in the address fragment.
    const hash = new URLSearchParams(window.location.hash.slice(1));
    const ssoToken = hash.get("sso_token"), ssoError = hash.get("sso_error");
    if (ssoToken || ssoError) history.replaceState(null, "", window.location.pathname);
    let cfg = { sso: false, password: true };
    try { const r = await fetch("/auth/config"); if (r.ok) cfg = await r.json(); } catch (e) { /* keep defaults */ }
    $("sso-block").hidden = !cfg.sso;
    $("sso-or").hidden = !cfg.password;
    if (!cfg.password) { $("email").closest("form").querySelectorAll("label, input, #login-button, .demo").forEach((n) => { n.hidden = true; }); }
    if (ssoToken) { token = ssoToken; store(false, token); enter().catch(() => signOut()); return; }
    if (ssoError) { show("login"); $("login-error").textContent = "Single sign-on failed. Ask your administrator to check that your account exists."; $("login-error").hidden = false; return; }
    token = store(true);
    if (token) enter().catch(() => signOut()); else show("login");
  }
  startup();
})();
