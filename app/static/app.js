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
    answered: "Answered", refused: "Not available", no_answer: "Not in documents",
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
    token = null; me = null; store(false, null);
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
    $("who-role").textContent = (LEVELS[me.level] || "Level " + me.level) + " · L" + me.level;
    $("tab-audit").hidden = me.level < 4;
    selectTab("chat");
    show("app");
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

  let counter = 0;
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
        body: JSON.stringify({ query: question, top_k: 3 })
      });
      bot.classList.remove("thinking");
      bot.replaceChildren();
      if (!res.ok) {
        const msg = res.status === 503 ? "The language model is not reachable right now. Please try again shortly."
          : res.status === 422 ? "That question could not be processed. Keep it under 1000 characters."
          : "Something went wrong (" + res.status + ").";
        bot.append(tag("error"), body(msg));
      } else {
        const data = await res.json();
        bot.append(tag(data.outcome));
        if (data.corrected_query) bot.append(el("span", "note", "Searched for: " + data.corrected_query));
        const b = el("span", "body");
        if (data.outcome === "answered") renderAnswerText(b, data.answer, msgId, data.sources);
        else b.textContent = data.answer;
        bot.append(b);
        if (data.outcome === "answered") renderSources(data.sources, msgId); else clearSources();
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

  function selectTab(name) {
    const chat = name === "chat";
    $("chat-panel").hidden = !chat; $("audit-panel").hidden = chat;
    $("tab-chat").classList.toggle("active", chat); $("tab-audit").classList.toggle("active", !chat);
    $("tab-chat").setAttribute("aria-selected", String(chat)); $("tab-audit").setAttribute("aria-selected", String(!chat));
    if (!chat) loadAudit().catch((e) => { $("audit-empty").textContent = e.message; $("audit-empty").hidden = false; });
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
  $("tab-chat").addEventListener("click", () => selectTab("chat"));
  $("tab-audit").addEventListener("click", () => selectTab("audit"));
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

  token = store(true);
  if (token) enter().catch(() => signOut()); else show("login");
})();
