(() => {
  "use strict";

  // ------------------------------------------------------------------
  // API client
  // ------------------------------------------------------------------

  let TOKEN = localStorage.getItem("deblaot_token") || "";

  async function api(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    const hadToken = !!TOKEN;
    if (TOKEN) headers["Authorization"] = "Bearer " + TOKEN;
    let resp;
    try {
      resp = await fetch(path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      throw new Error("Can't reach deblaot. Check you're on the same Wi-Fi as your Mac.");
    }
    if (resp.status === 401) {
      TOKEN = "";
      localStorage.removeItem("deblaot_token");
      showTokenScreen(hadToken
        ? "That token isn't valid anymore. Enter it again."
        : "Enter the access token shown in your Mac's terminal.");
      throw new Error("Access token required.");
    }
    let data = null;
    const text = await resp.text();
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = null; }
    }
    if (!resp.ok) {
      const detail = (data && data.detail) || `Request failed (${resp.status})`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  const Api = {
    categories: () => api("GET", "/categories"),
    tweaks: (categoryId) => api("GET", `/tweaks?category=${encodeURIComponent(categoryId)}`),
    presets: () => api("GET", "/presets"),
    applyTweak: (id, param, confirmExperimental) =>
      api("POST", `/tweaks/${encodeURIComponent(id)}/apply`, { param: param || null, confirm_experimental: !!confirmExperimental }),
    applyCategory: (id) => api("POST", `/categories/${encodeURIComponent(id)}/apply`),
    applyPreset: (id) => api("POST", `/presets/${encodeURIComponent(id)}/apply`),
    historyRuns: () => api("GET", "/history/runs?limit=30"),
    revert: (runId) => api("POST", "/history/revert", runId ? { run_id: runId } : {}),
  };

  // ------------------------------------------------------------------
  // App state
  // ------------------------------------------------------------------

  const state = {
    currentTab: "tweaks",
    categories: [],
    tweaksCache: new Map(),
    currentCategoryId: null,
  };

  const el = (id) => document.getElementById(id);
  const contentArea = () => el("content-area");

  // ------------------------------------------------------------------
  // Toast + Action sheet
  // ------------------------------------------------------------------

  let toastTimer = null;
  function showToast(message) {
    const t = el("toast");
    t.textContent = message;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
  }

  function confirmSheet(title, message, confirmLabel) {
    return new Promise((resolve) => {
      const overlay = el("action-sheet-overlay");
      el("sheet-title").textContent = title;
      el("sheet-message").textContent = message;
      el("sheet-confirm").textContent = confirmLabel || "Continue";
      overlay.hidden = false;

      const cleanup = (result) => {
        overlay.hidden = true;
        confirmBtn.removeEventListener("click", onConfirm);
        cancelBtn.removeEventListener("click", onCancel);
        resolve(result);
      };
      const confirmBtn = el("sheet-confirm");
      const cancelBtn = el("sheet-cancel");
      const onConfirm = () => cleanup(true);
      const onCancel = () => cleanup(false);
      confirmBtn.addEventListener("click", onConfirm);
      cancelBtn.addEventListener("click", onCancel);
    });
  }

  // ------------------------------------------------------------------
  // Navigation chrome (title / back button) per tab+view
  // ------------------------------------------------------------------

  function setNav(title, showBack, backLabel) {
    el("nav-title").textContent = title;
    el("nav-back").hidden = !showBack;
    el("nav-back-label").textContent = backLabel || "Back";
  }

  function render() {
    if (state.currentTab === "tweaks") renderTweaksTab();
    else if (state.currentTab === "presets") renderPresetsTab();
    else if (state.currentTab === "history") renderHistoryTab();
  }

  // ------------------------------------------------------------------
  // Tweaks tab: category list -> category detail
  // ------------------------------------------------------------------

  async function renderTweaksTab() {
    if (state.currentCategoryId) {
      renderCategoryDetail(state.currentCategoryId);
      return;
    }
    setNav("deblaot", false);
    if (state.categories.length === 0) {
      contentArea().innerHTML = `<div class="spinner-row">Loading categories…</div>`;
      try {
        state.categories = await Api.categories();
      } catch (err) {
        contentArea().innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
        return;
      }
    }
    const rows = state.categories.map(cat => `
      <button class="list-row" data-open-category="${cat.id}">
        <span class="list-row-title">${escapeHtml(cat.title)}</span>
        <span class="list-row-count">${cat.tweak_count}</span>
        <svg viewBox="0 0 8 14" class="list-row-chevron"><path d="M1 1 L7 7 L1 13" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>`).join("");
    contentArea().innerHTML = `
      <p class="section-label">Categories</p>
      <div class="list-group">${rows}</div>`;
    contentArea().querySelectorAll("[data-open-category]").forEach(btn => {
      btn.addEventListener("click", () => {
        state.currentCategoryId = btn.dataset.openCategory;
        renderTweaksTab();
      });
    });
  }

  async function renderCategoryDetail(categoryId) {
    const cat = state.categories.find(c => c.id === categoryId);
    setNav(cat ? cat.title : "Category", true, "Categories");

    if (!state.tweaksCache.has(categoryId)) {
      contentArea().innerHTML = `<div class="spinner-row">Loading tweaks…</div>`;
      try {
        state.tweaksCache.set(categoryId, await Api.tweaks(categoryId));
      } catch (err) {
        contentArea().innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
        return;
      }
    }
    const tweakList = state.tweaksCache.get(categoryId);
    const applicable = tweakList.filter(t => !t.parameters && !t.experimental).length;

    contentArea().innerHTML = `
      <button class="btn btn-primary btn-block" id="apply-category-btn" ${applicable === 0 ? "disabled" : ""}>
        Apply all in this category
      </button>
      <p class="section-note">
        ${tweakList.length} tweak(s) -- "Apply all" covers ${applicable} of them
        (the rest need a choice or a confirmation).
      </p>
      <div id="tweak-cards"></div>
    `;
    const cardsEl = el("tweak-cards");
    tweakList.forEach(t => cardsEl.appendChild(buildTweakCard(t)));

    el("apply-category-btn").addEventListener("click", async () => {
      const ok = await confirmSheet("Apply category?", `Apply every applicable tweak in "${cat ? cat.title : categoryId}"?`, "Apply");
      if (!ok) return;
      const btn = el("apply-category-btn");
      btn.disabled = true;
      try {
        const result = await Api.applyCategory(categoryId);
        result.results.forEach(r => setCardResult(r.id, r.message, r.success));
        const succeeded = result.results.filter(r => r.success).length;
        showToast(`${succeeded}/${result.results.length} applied`);
      } catch (err) {
        showToast(err.message);
      } finally {
        btn.disabled = applicable === 0;
      }
    });
  }

  function buildTweakCard(tweak) {
    const card = document.createElement("div");
    card.className = "tweak-card";
    card.dataset.tweakId = tweak.id;

    const badges = [
      tweak.requires_admin ? `<span class="badge badge-admin">ADMIN</span>` : "",
      tweak.experimental ? `<span class="badge badge-experimental">EXPERIMENTAL</span>` : "",
    ].join("");

    const select = tweak.parameters
      ? `<select class="param-select">${tweak.parameters.map(p => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join("")}</select>`
      : "";

    card.innerHTML = `
      <div class="tweak-card-top">
        <div class="tweak-title">${escapeHtml(tweak.title)}</div>
        ${badges}
      </div>
      <div class="tweak-description">${escapeHtml(tweak.description)}</div>
      <div class="tweak-actions">
        <div class="tweak-result info" id="result-${cssEscape(tweak.id)}"></div>
        ${select}
        <button class="btn btn-primary btn-small" data-apply="${tweak.id}">Apply</button>
      </div>
    `;

    card.querySelector("[data-apply]").addEventListener("click", () => onApplyTweakClicked(tweak, card));
    return card;
  }

  function setCardResult(tweakId, message, success) {
    const label = document.getElementById(`result-${cssEscape(tweakId)}`);
    if (!label) return;
    label.textContent = message;
    label.className = "tweak-result " + (success ? "success" : "error");
  }

  async function onApplyTweakClicked(tweak, card) {
    const select = card.querySelector(".param-select");
    const param = select ? select.value : null;

    if (tweak.experimental) {
      const ok = await confirmSheet("Experimental tweak", `"${tweak.title}": ${tweak.description}`, "Continue anyway");
      if (!ok) return;
    }
    if (tweak.id === "remove-bundled-apps") {
      const ok = await confirmSheet(
        "Move apps to Trash?",
        "Pages, Numbers, Keynote, iMovie, and GarageBand (whichever are installed) move to the Trash -- not permanently deleted until you empty it.",
        "Move to Trash"
      );
      if (!ok) return;
    }

    const btn = card.querySelector("[data-apply]");
    btn.disabled = true;
    setCardResult(tweak.id, "Applying…", true);
    try {
      const result = await Api.applyTweak(tweak.id, param, tweak.experimental);
      setCardResult(tweak.id, result.message, result.success);
      if (!result.success) showToast(result.message);
    } catch (err) {
      setCardResult(tweak.id, err.message, false);
      showToast(err.message);
    } finally {
      btn.disabled = false;
    }
  }

  // ------------------------------------------------------------------
  // Presets tab
  // ------------------------------------------------------------------

  function renderPresetsTab() {
    setNav("Presets", false);
    contentArea().innerHTML = `
      <div class="preset-card">
        <h2>Recommended Preset</h2>
        <p>Privacy & clutter fixes most people want: disable Mac analytics and personalized ads, opt out of Siri data sharing, hide Siri Suggestions in Spotlight, and tidy up the Dock and Finder. Nothing destructive.</p>
        <button class="btn btn-primary btn-block" id="btn-preset-recommended">Run Recommended Preset</button>
      </div>
      <div class="preset-card">
        <h2>Run Everything</h2>
        <p>Every non-parameterized tweak across every category, including the experimental Apple Intelligence toggle and moving bundled apps to the Trash. A lot of changes at once.</p>
        <button class="btn btn-danger-outline btn-block" id="btn-preset-all">Run Everything</button>
      </div>
      <div id="preset-results"></div>
    `;
    el("btn-preset-recommended").addEventListener("click", () => runPreset("recommended", "Run the recommended preset now?"));
    el("btn-preset-all").addEventListener("click", () => runPreset("all", "This applies every tweak, including experimental ones and app removal. Continue?"));
  }

  async function runPreset(id, confirmMessage) {
    const ok = await confirmSheet(id === "all" ? "Run EVERYTHING?" : "Run recommended preset?", confirmMessage, "Run it");
    if (!ok) return;
    const resultsEl = el("preset-results");
    resultsEl.innerHTML = `<div class="spinner-row">Applying…</div>`;
    try {
      const result = await Api.applyPreset(id);
      const succeeded = result.results.filter(r => r.success).length;
      resultsEl.innerHTML = `<p class="section-note"><strong>${succeeded}/${result.results.length} succeeded.</strong></p>` +
        result.results.map(r => `<p class="section-note">${r.success ? "✓" : "✗"} ${escapeHtml(r.id)}: ${escapeHtml(r.message)}</p>`).join("");
      showToast(`${succeeded}/${result.results.length} applied`);
    } catch (err) {
      resultsEl.innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
    }
  }

  // ------------------------------------------------------------------
  // History tab
  // ------------------------------------------------------------------

  async function renderHistoryTab() {
    setNav("History & Revert", false);
    contentArea().innerHTML = `<div class="spinner-row">Loading…</div>`;
    let runs;
    try {
      runs = await Api.historyRuns();
    } catch (err) {
      contentArea().innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
      return;
    }
    if (runs.length === 0) {
      contentArea().innerHTML = `<div class="empty-state">No runs yet. Apply a tweak and it'll show up here.</div>`;
      return;
    }
    contentArea().innerHTML = `
      <p class="section-note">Each row is one apply. Reverting puts every change from that run back the way it was.</p>
      <div id="history-list"></div>`;
    const list = el("history-list");
    runs.forEach(run => {
      const fullyReverted = run.action_count > 0 && run.reverted_count >= run.action_count;
      const card = document.createElement("div");
      card.className = "tweak-card";
      card.innerHTML = `
        <div class="tweak-title">${escapeHtml(run.started || run.run_id)}</div>
        <div class="tweak-description">${run.action_count} change(s)${run.reverted_count ? ` -- ${run.reverted_count} reverted` : ""}</div>
        <div class="tweak-actions">
          <div class="tweak-result info"></div>
          <button class="btn btn-danger-outline btn-small" ${fullyReverted ? "disabled" : ""}>Revert</button>
        </div>`;
      card.querySelector("button").addEventListener("click", async () => {
        const ok = await confirmSheet("Revert this run?", `Undo every change made in run ${run.run_id}?`, "Revert");
        if (!ok) return;
        try {
          const result = await Api.revert(run.run_id);
          showToast(`Reverted ${result.reverted_count} change(s)`);
          renderHistoryTab();
        } catch (err) {
          showToast(err.message);
        }
      });
      list.appendChild(card);
    });
  }

  // ------------------------------------------------------------------
  // Tabs
  // ------------------------------------------------------------------

  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      state.currentTab = btn.dataset.tab;
      if (state.currentTab === "tweaks") state.currentCategoryId = null;
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b === btn));
      render();
    });
  });
  document.querySelector('.tab-btn[data-tab="tweaks"]').classList.add("active");

  el("nav-back").addEventListener("click", () => {
    state.currentCategoryId = null;
    render();
  });

  // ------------------------------------------------------------------
  // Token screen
  // ------------------------------------------------------------------

  function showTokenScreen(errorMessage) {
    el("screen-main").hidden = true;
    el("screen-token").hidden = false;
    if (errorMessage) {
      el("token-error").textContent = errorMessage;
      el("token-error").hidden = false;
    }
  }

  function showMainScreen() {
    el("screen-token").hidden = true;
    el("screen-main").hidden = false;
    render();
  }

  el("token-submit").addEventListener("click", async () => {
    const value = el("token-input").value.trim();
    if (!value) return;
    TOKEN = value;
    try {
      await Api.categories();
      localStorage.setItem("deblaot_token", TOKEN);
      el("token-error").hidden = true;
      showMainScreen();
    } catch (err) {
      TOKEN = "";
      el("token-error").textContent = "That token didn't work -- double-check it and try again.";
      el("token-error").hidden = false;
    }
  });

  // ------------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------------

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function cssEscape(str) {
    return String(str).replace(/[^a-zA-Z0-9_-]/g, "_");
  }

  async function boot() {
    try {
      await Api.categories();
      showMainScreen();
    } catch (err) {
      // api() already switches to the token screen with its own message
      // on a 401; for anything else (e.g. the backend is unreachable),
      // surface that reason instead of implying it's a token problem.
      if (el("screen-token").hidden) {
        showTokenScreen(err.message);
      }
    }
  }

  boot();
})();
