/* ResumeTeX Web — browser logic.
 *
 * Privacy contract in this file:
 *   1. Contact details live in the page (and optionally in localStorage).
 *   2. Before any AI request, they are redacted out of the text (redact.js).
 *   3. The provider key never leaves this page except to the provider host.
 *   4. The LaTeX document is assembled here, so PII is not part of the AI call.
 */
(function () {
  "use strict";

  var PROVIDERS = [
    { name: "OpenRouter", baseUrl: "https://openrouter.ai/api/v1", model: "openrouter/auto" },
    { name: "OpenAI", baseUrl: "https://api.openai.com/v1", model: "gpt-4o-mini" },
    { name: "Groq", baseUrl: "https://api.openq.ai/openai/v1".replace("openq.ai", "groq.com"), model: "llama-3.3-70b-versatile" },
    { name: "Together AI", baseUrl: "https://api.together.xyz/v1", model: "meta-llama/Llama-3.3-70B-Instruct-Turbo" },
    { name: "DeepSeek", baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat" },
    { name: "Mistral", baseUrl: "https://api.mistral.ai/v1", model: "mistral-small-latest" },
    { name: "Local (Ollama / LM Studio)", baseUrl: "http://localhost:11434/v1", model: "llama3.1" }
  ];

  var STYLES = [
    ["navy", "Navy"], ["minimal", "Minimal"], ["compact", "Compact"],
    ["projects", "Projects"], ["times", "Times"]
  ];
  var TONES = ["Professional", "Concise", "Academic", "Friendly"];
  var EMPHASES = ["Balanced", "Experience", "Projects", "Skills", "Education"];

  var SETTINGS_KEY = "resumetex.settings.v1";
  var KEY_KEY = "resumetex.apikey.v1";

  var state = {
    settings: { provider: "OpenRouter", baseUrl: PROVIDERS[0].baseUrl, model: PROVIDERS[0].model, rememberKey: false, compiler: "local" },
    pii: {},
    body: "",
    tex: "",
    pdfBlob: null,
    templates: [],
    starterData: {},
    houseShells: {},
    promptTemplate: "",
    promptContract: "",
    serverNotice: null,
    progressFromServer: false,
    progressValue: 0,
    compileStarted: 0,
    compileFinished: false,
    compileTicker: null,
    waitStage: -1,
    lastFeedMessage: "",
    lastFeedTime: 0
  };

  // ---------------------------------------------------------------- helpers
  function $(id) { return document.getElementById(id); }
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }
  function setNotice(node, kind, html) {
    node.innerHTML = "";
    if (!kind) return;
    var box = el("div", "notice " + kind);
    box.innerHTML = html;
    node.appendChild(box);
  }
  function logNetwork(entry) {
    var log = $("netLog");
    if (log.querySelector(".small") && log.children.length === 1) log.innerHTML = "";
    var row = el("div");
    row.innerHTML = "<b>" + entry.what + "</b> — " + entry.detail;
    log.insertBefore(row, log.firstChild);
  }
  function api(path, options) {
    return fetch(path, options).then(function (response) {
      var type = response.headers.get("content-type") || "";
      if (type.indexOf("application/json") >= 0) {
        return response.json().then(function (data) {
          if (!response.ok) { var err = new Error(data.error || "Request failed"); err.data = data; throw err; }
          return data;
        });
      }
      if (!response.ok) throw new Error("Request failed: " + response.status);
      return response.blob();
    });
  }
  function postJson(path, payload) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
  }
  function collectPii() {
    return {
      name: $("f_name").value.trim(),
      email: $("f_email").value.trim(),
      phone: $("f_phone").value.trim(),
      location: $("f_location").value.trim(),
      linkedin: $("f_linkedin").value.trim(),
      github: $("f_github").value.trim(),
      portfolio: $("f_portfolio").value.trim()
    };
  }
  function collectOptions() {
    return {
      pageTarget: parseInt($("f_pages").value, 10) || 1,
      tone: $("f_tone").value,
      emphasis: $("f_emphasis").value,
      includeProjects: $("f_projects").checked,
      includeCertifications: $("f_certs").checked,
      includeAchievements: $("f_achievements").checked,
      includeLanguages: $("f_languages").checked,
      customInstructions: $("f_guidance").value.trim()
    };
  }
  function saveSettings() {
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(state.settings)); } catch (e) { /* ignore */ }
  }
  function loadSettings() {
    try {
      var raw = localStorage.getItem(SETTINGS_KEY);
      if (raw) state.settings = Object.assign(state.settings, JSON.parse(raw));
    } catch (e) { /* ignore */ }
  }
  function saveKey() {
    try {
      if (state.settings.rememberKey) localStorage.setItem(KEY_KEY, $("f_key").value.trim());
      else localStorage.removeItem(KEY_KEY);
    } catch (e) { /* ignore */ }
  }
  function loadKey() {
    try {
      var key = localStorage.getItem(KEY_KEY);
      if (key) $("f_key").value = key;
    } catch (e) { /* ignore */ }
  }
  function isLocalUrl(url) {
    try {
      var host = new URL(url).hostname.toLowerCase();
      return host === "localhost" || host === "127.0.0.1" || host === "::1" || host.endsWith(".local");
    } catch (e) { return false; }
  }

  // ------------------------------------------------------------- the prompt
  function buildSystemPrompt(style, options, custom) {
    var pages = options.pageTarget === 2 ? "two pages" : "one page";
    var sections = ["Professional Summary", "Skills", "Professional Experience", "Education"];
    if (options.includeProjects) sections.push("Projects");
    if (options.includeCertifications) sections.push("Certifications");
    if (options.includeAchievements) sections.push("Achievements");
    if (options.includeLanguages) sections.push("Languages");
    var guidance = options.customInstructions || "none";
    var styleName = (STYLES.filter(function (s) { return s[0] === style; })[0] || ["", "Navy"])[1];

    if (custom && custom.trim()) {
      var text = custom;
      var map = {
        "{style}": styleName, "{tone}": options.tone, "{pages}": pages,
        "{emphasis}": options.emphasis, "{sections}": sections.join(", "), "{guidance}": guidance
      };
      Object.keys(map).forEach(function (key) { text = text.split(key).join(map[key]); });
      var settingsBlock = "CURRENT SETTINGS (apply them unless the instructions above already say the same):\n" +
        "- House style: " + styleName + "\n" +
        "- Tone: " + options.tone + "\n" +
        "- Length target: " + pages + "\n" +
        "- Emphasis: " + options.emphasis + "\n" +
        "- Sections to use: " + sections.join(", ") + "\n" +
        "- Additional guidance: " + guidance + "\n";
      return text.trim() + "\n\n" + settingsBlock + "\n" + state.promptContract;
    }

    return state.promptTemplate
      .split("__STYLE__").join(styleName)
      .split("__STYLE_GUIDANCE__").join("Follow the house style exactly.")
      .split("__TONE__").join(options.tone)
      .split("__PAGES__").join(pages)
      .split("__EMPHASIS__").join(options.emphasis)
      .split("__SECTIONS__").join(sections.join(", "))
      .split("__GUIDANCE__").join(guidance);
  }

  // --------------------------------------------------------------- AI call
  function callProvider(systemPrompt, userContent) {
    var baseUrl = $("f_baseurl").value.trim().replace(/\/+$/, "");
    var model = $("f_model").value.trim();
    var key = $("f_key").value.trim();
    var local = isLocalUrl(baseUrl);

    if (!model) throw new Error("No model configured.");
    if (!local && !key) throw new Error("No API key for this provider. Add one, or use canvas mode.");
    if (!local && baseUrl.indexOf("https://") !== 0) throw new Error("Remote providers must use https://.");

    var headers = { "Content-Type": "application/json", "X-Title": "ResumeTeX-Web" };
    if (key && !local) headers.Authorization = "Bearer " + key;

    var url = baseUrl.indexOf("/chat/completions") >= 0 ? baseUrl : baseUrl + "/chat/completions";
    var payload = {
      model: model,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userContent }
      ],
      temperature: 0.4
    };

    logNetwork({ what: "AI request", detail: hostOf(url) + " · model " + model + " · " + userContent.length + " chars (redacted)" });

    return fetch(url, { method: "POST", headers: headers, body: JSON.stringify(payload) })
      .then(function (response) {
        return response.text().then(function (body) {
          if (!response.ok) {
            logNetwork({ what: "AI error", detail: hostOf(url) + " → " + response.status });
            throw new Error("AI service returned " + response.status + ": " + body.slice(0, 200));
          }
          var data;
          try { data = JSON.parse(body); }
          catch (e) { throw new Error("The AI service returned an unexpected response."); }
          var content = data.choices && data.choices[0] && data.choices[0].message
            ? data.choices[0].message.content : "";
          if (!content || !content.trim()) throw new Error("The AI returned an empty response.");
          logNetwork({ what: "AI reply", detail: hostOf(url) + " · " + content.length + " chars" });
          return content;
        });
      });
  }

  function hostOf(url) {
    try { return new URL(url).hostname; } catch (e) { return "unknown"; }
  }

  // -------------------------------------------------------------- rendering
  function setTab(name) {
    Array.prototype.forEach.call(document.querySelectorAll(".tabs button"), function (button) {
      button.classList.toggle("on", button.dataset.tab === name);
    });
    Array.prototype.forEach.call(document.querySelectorAll("section[data-panel]"), function (panel) {
      panel.hidden = panel.dataset.panel !== name;
    });
    var generate = $("mb_generate");
    if (generate) {
      generate.textContent = name === "canvas" ? "Render CV" : (name === "tex" ? "Compile PDF" : "Generate");
    }
  }

  function showAts(report) {
    if (!report) return;
    $("atsScore").textContent = report.score;
    $("atsGrade").textContent = report.grade;
    $("atsGrade").className = "grade " + report.grade;
    $("atsLabel").textContent = report.stats && report.stats.keywordCoverage !== null &&
      report.stats.keywordCoverage !== undefined
      ? "Job keyword coverage " + report.stats.keywordCoverage + "%" : "Local ATS analysis";
    var box = $("atsIssues");
    box.innerHTML = "";
    (report.issues || []).forEach(function (issue) {
      var row = el("div", "issue " + issue.severity);
      row.innerHTML = "<b>" + issue.message + "</b><span class=\"fix\">" + issue.fix + "</span>";
      box.appendChild(row);
    });
    if (!(report.issues || []).length) {
      var emptyRow = el("div", "issue info");
      emptyRow.innerHTML = "<b>Nothing flagged.</b><span class=\"fix\">This CV passes every local ATS check.</span>";
      box.appendChild(emptyRow);
    }
  }

  function scoreAts(body) {
    return postJson("/api/ats/score", { body: body, jobDescription: $("f_jd").value })
      .then(showAts)
      .catch(function (err) { setNotice($("aiWarnings"), "bad", err.message); });
  }

  function setTex(tex) {
    state.tex = tex || "";
    $("texOut").textContent = state.tex || "Nothing generated yet.";
    // A new document makes the previous PDF stale.
    state.pdfBlob = null;
    var box = $("pdfBox");
    if (box) box.innerHTML = '<p class="small">The compiled PDF appears here.</p>';
    if ($("btn_download_pdf")) $("btn_download_pdf").disabled = true;
    if ($("compileProgress")) {
      $("compileProgress").hidden = true;
      if (state.compileTicker) clearInterval(state.compileTicker);
      state.compileTicker = null;
    }
    if ($("engineNote")) $("engineNote").textContent = "";
    if ($("compileStatus")) {
      setNotice($("compileStatus"), null, null);
      // Keep a server limitation (no engine / missing package) visible.
      if (state.serverNotice) compileNotice(state.serverNotice.kind, state.serverNotice.html);
    }
  }

  // --------------------------------------------------------------- AI flow
  function generateWithAi() {
    var warnings = $("aiWarnings");
    setNotice(warnings, null, null);
    var pii = collectPii();
    var details = $("f_details").value;
    if (!details.trim()) { setNotice(warnings, "warn", "Add your resume text first."); return; }

    var redactor = new window.ResumeTexRedact.Redactor(pii);
    var redaction;
    try {
      redaction = redactor.redact(details);
    } catch (err) {
      setNotice(warnings, "bad", "Blocked: " + err.message);
      return;
    }
    logNetwork({ what: "Redaction", detail: redaction.replacementCount + " personal value(s) removed locally" });

    var systemPrompt = buildSystemPrompt($("f_style").value, collectOptions(), null);
    var userContent = "[DETAILS]\n" + redaction.text.trim() + "\n";
    $("payloadSystem").textContent = systemPrompt;
    $("payloadUser").textContent = userContent;
    $("payloadBox").hidden = false;

    $("btn_generate").disabled = true;
    callProvider(systemPrompt, userContent)
      .then(function (raw) {
        return postJson("/api/sanitize", { raw: raw });
      })
      .then(function (data) {
        state.body = data.body;
        return composeAndShow(data.body);
      })
      .catch(function (err) { setNotice(warnings, "bad", err.message); })
      .then(function () { $("btn_generate").disabled = false; });
  }

  function composeAndShow(body) {
    var style = $("f_style").value;
    return api("/api/shell/" + style).then(function (data) {
      state.tex = window.ResumeTexLatex.compose(data.shell, style, collectPii(), body);
      setTex(state.tex);
      setTab("tex");
      return scoreAts(body);
    });
  }

  function offlineGenerate() {
    var warnings = $("aiWarnings");
    setNotice(warnings, null, null);
    postJson("/api/generate/offline", { details: $("f_details").value, style: $("f_style").value })
      .then(function (data) {
        state.body = data.body;
        return composeAndShow(data.body);
      })
      .catch(function (err) { setNotice(warnings, "bad", err.message); });
  }

  // ---------------------------------------------------------- canvas flow
  function fillCanvas(data) {
    $("c_headline").value = data.headline || "";
    $("c_summary").value = data.summary || "";
    $("c_skills").value = (data.skills || []).map(function (group) {
      return (group.label ? group.label + ": " : "") + (group.items || []).join(", ");
    }).join("\n");
    $("c_achievements").value = (data.achievements || []).join("\n");
    $("c_languages").value = (data.languages || []).join(", ");

    var targets = [
      ["#c_experience", data.experience], ["#c_education", data.education],
      ["#c_projects", data.projects], ["#c_certifications", data.certifications],
    ];
    targets.forEach(function (pair) {
      var container = document.querySelector(pair[0]);
      if (!container) return;
      container.innerHTML = "";
      (pair[1] || []).forEach(function (entry) { entryRow(container, entry); });
    });
  }

  function loadIntoCanvas() {
    if (!state.body) {
      setNotice($("aiWarnings"), "warn", "Generate a CV first — then you can edit it on the canvas.");
      return;
    }
    postJson("/api/parse-body", { body: state.body })
      .then(function (result) {
        fillCanvas(result.data || {});
        setTab("canvas");
        logNetwork({ what: "Canvas import", detail: "AI body parsed into editable fields" });
      })
      .catch(function (err) { setNotice($("aiWarnings"), "bad", err.message); });
  }

  function entryRow(target, values) {
    var row = el("div", "cv-row");
    ["role", "company", "location", "dates"].forEach(function (field) {
      var input = document.createElement("input");
      input.type = "text";
      input.placeholder = field;
      input.dataset.field = field;
      input.value = (values && values[field]) || "";
      row.appendChild(input);
    });
    var bullets = document.createElement("textarea");
    bullets.rows = 3;
    bullets.placeholder = "bullets, one per line";
    bullets.dataset.field = "bullets";
    bullets.value = ((values && values.bullets) || []).join("\n");
    row.appendChild(bullets);
    var remove = el("button", "ghost cv-remove", "Remove");
    remove.type = "button";
    remove.onclick = function () { row.remove(); };
    row.appendChild(remove);
    target.appendChild(row);
    return row;
  }

  function readEntries(target) {
    return Array.prototype.map.call(target.children, function (row) {
      var out = { bullets: [] };
      Array.prototype.forEach.call(row.querySelectorAll("[data-field]"), function (input) {
        if (input.dataset.field === "bullets") {
          out.bullets = input.value.split("\n").map(function (line) { return line.trim(); })
            .filter(function (line) { return line.length; });
        } else {
          out[input.dataset.field] = input.value.trim();
        }
      });
      return out;
    });
  }

  function renderCanvas() {
    var skills = $("c_skills").value.split("\n").map(function (line) {
      var trimmed = line.trim();
      if (!trimmed) return null;
      var idx = trimmed.indexOf(":");
      if (idx < 0) return { label: "", items: trimmed };
      return {
        label: trimmed.slice(0, idx).trim(),
        items: trimmed.slice(idx + 1).split(",").map(function (s) { return s.trim(); })
          .filter(function (s) { return s.length; })
      };
    }).filter(function (s) { return s; });

    var data = {
      headline: $("c_headline").value.trim(),
      summary: $("c_summary").value,
      skills: skills,
      experience: readEntries($("c_experience")),
      education: readEntries($("c_education")),
      projects: readEntries($("c_projects")),
      certifications: readEntries($("c_certifications")),
      achievements: $("c_achievements").value.split("\n").map(function (line) { return line.trim(); })
        .filter(function (line) { return line.length; }),
      languages: $("c_languages").value.split(",").map(function (line) { return line.trim(); })
        .filter(function (line) { return line.length; })
    };

    return postJson("/api/canvas/render", {
      data: data,
      presetId: $("f_template").value,
      jobDescription: $("f_jd").value
    }).then(function (result) {
      state.body = result.body;
      var header = window.ResumeTexLatex.buildHeader(
        "navy", collectPii(), result.accent || null,
        data.headline, result.headerStyle || null);
      state.tex = (result.preamble + "\n\\begin{document}\n" + header + "\n" + result.body +
        "\n\\end{document}\n").replace(/\n{3,}/g, "\n\n");
      setTex(state.tex);
      showAts(result.ats);
      var item = templateById($("f_template").value);
      compileNotice("good", "LaTeX is ready" + (item ? " with " + item.name : "") +
        ". Edit more fields or press <b>Compile PDF</b> to build the PDF.");
      return true;
    }).catch(function (err) {
      setNotice($("aiWarnings"), "bad", err.message);
      return false;
    });
  }

  // -------------------------------------------------------------- compiling
  function compileNotice(kind, html) {
    setNotice($("compileStatus"), kind, html);
  }

  var COMPILER_TEXT = {
    local: "Your CV is compiled on this server with pdflatex. No third-party service receives it.",
    auto: "Tries the private server first. Only if that fails is the full document uploaded to a third-party compiler.",
    online: "Your full CV — including name, phone and email — is uploaded to a third-party compiler. Use only if you accept that."
  };

  function compilerMode() {
    var select = $("f_compiler");
    return select && select.value ? select.value : "local";
  }

  function updateCompilerHint() {
    var hint = $("compilerHint");
    if (!hint) return;
    var mode = compilerMode();
    hint.textContent = COMPILER_TEXT[mode] || COMPILER_TEXT.local;
    hint.style.color = mode === "local" ? "" : "#b45309";
  }

  function confirmCompiler(mode) {
    if (mode === "local") return true;
    var message = mode === "auto"
      ? "Automatic mode compiles privately on the server first. If that fails, your full CV (including your name, phone and email) is uploaded to a third-party compiler. Continue?"
      : "Online mode uploads your full CV — including your name, phone and email — to a third-party compiler. Continue?";
    return window.confirm(message);
  }

  // ------------------------------------------------------ compile progress
  var COMPILE_STEPS = ["prepare", "compile", "preview"];
  var COMPILE_ACTIVE_AT = { prepare: 5, compile: 28, preview: 90 };
  var COMPILE_DONE_AT = { prepare: 28, compile: 90, preview: 100 };

  function compileModeLabel(mode) {
    if (mode === "online") return "the online compiler";
    if (mode === "auto") return "automatic mode (server first)";
    return "private server mode";
  }

  function compileFeed(message, tone) {
    var feed = $("compileFeed");
    if (!feed) return;
    var now = Date.now();
    if (message === state.lastFeedMessage && now - state.lastFeedTime < 1200) return;
    state.lastFeedMessage = message;
    state.lastFeedTime = now;
    var row = el("div", "feed-row " + (tone || "info"));
    row.appendChild(el("span", "feed-time", ((now - state.compileStarted) / 1000).toFixed(1) + "s"));
    row.appendChild(el("span", "feed-msg", message));
    feed.appendChild(row);
    while (feed.children.length > 40) feed.removeChild(feed.firstChild);
    feed.scrollTop = feed.scrollHeight;
  }

  function setCompileProgress(progress, label) {
    progress = Math.max(0, Math.min(100, Math.round(progress)));
    state.progressValue = Math.max(state.progressValue, progress);
    var value = state.progressValue;
    var bar = $("progressBar");
    var track = $("progressTrack");
    if (!bar || !track) return;
    bar.style.width = value + "%";
    track.setAttribute("aria-valuenow", String(value));
    if (label && $("progressLabel")) $("progressLabel").textContent = label;
    var steps = $("progressSteps");
    if (!steps) return;
    COMPILE_STEPS.forEach(function (step) {
      var item = steps.querySelector('[data-step="' + step + '"]');
      if (!item) return;
      item.classList.toggle("active", value >= COMPILE_ACTIVE_AT[step] && value < COMPILE_DONE_AT[step]);
      item.classList.toggle("done", value >= COMPILE_DONE_AT[step]);
    });
  }

  function resetCompileProgress(mode) {
    var box = $("compileProgress");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("failed", "complete");
    if ($("compileFeed")) $("compileFeed").innerHTML = "";
    state.progressFromServer = false;
    state.progressValue = 0;
    state.compileStarted = Date.now();
    state.compileFinished = false;
    state.waitStage = -1;
    state.lastFeedMessage = "";
    state.lastFeedTime = 0;
    if ($("progressTime")) $("progressTime").textContent = "0.0s";
    setCompileProgress(5, "Contacting the server…");
    compileFeed("Compile started in " + compileModeLabel(mode) + ".", "info");
    if (state.compileTicker) clearInterval(state.compileTicker);

    // Local clock and stage rotation. The server stream overrides both as soon
    // as its first event arrives, so this is only the waiting experience.
    var stages = [
      [0, "Contacting the server…"],
      [1, "Starting the compiler…"],
      [5, "Compiling with pdflatex…"],
      [15, "Still compiling — a free instance may be waking up…"],
      [45, "Still compiling — almost there…"]
    ];
    state.compileTicker = setInterval(function () {
      if (state.compileFinished) return;
      var seconds = (Date.now() - state.compileStarted) / 1000;
      if ($("progressTime")) $("progressTime").textContent = seconds.toFixed(1) + "s";
      if (state.progressFromServer) return;
      var index = 0;
      for (var i = 0; i < stages.length; i++) if (seconds >= stages[i][0]) index = i;
      if ($("progressLabel")) $("progressLabel").textContent = stages[index][1];
      if (index !== state.waitStage) {
        state.waitStage = index;
        compileFeed(stages[index][1], index >= 3 ? "warn" : "info");
      }
    }, 100);
  }

  function finishCompileProgress(ok, label) {
    state.compileFinished = true;
    if (state.compileTicker) clearInterval(state.compileTicker);
    state.compileTicker = null;
    if ($("progressTime") && state.compileStarted) {
      $("progressTime").textContent = ((Date.now() - state.compileStarted) / 1000).toFixed(1) + "s";
    }
    var box = $("compileProgress");
    if (!box) return;
    if (ok) {
      setCompileProgress(100, label);
      box.classList.add("complete");
    } else {
      box.classList.add("failed");
      if ($("progressLabel")) $("progressLabel").textContent = label;
      var active = $("progressSteps") && $("progressSteps").querySelector("li.active");
      if (active) {
        active.classList.remove("active");
        active.classList.add("failed");
      }
    }
  }

  function base64ToBlob(base64, type) {
    var binary = window.atob(base64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Blob([bytes], { type: type || "application/pdf" });
  }

  // Read newline-delimited JSON from a streaming response, one event at a time.
  function consumeNdjson(response, onEvent) {
    return new Promise(function (resolve, reject) {
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      function dispatch(line) {
        line = line.trim();
        if (!line) return;
        var event;
        try { event = JSON.parse(line); } catch (e) { return; }
        onEvent(event);
      }
      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) {
            buffer += decoder.decode();
            if (buffer.trim()) dispatch(buffer);
            resolve();
            return;
          }
          buffer += decoder.decode(chunk.value, { stream: true });
          var lines = buffer.split("\n");
          buffer = lines.pop();
          lines.forEach(dispatch);
          return pump();
        });
      }
      pump().catch(reject);
    });
  }

  function streamCompile(tex, mode, signal) {
    return fetch("/api/compile/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tex: tex, mode: mode }),
      signal: signal
    }).then(function (response) {
      var type = response.headers.get("content-type") || "";
      if (!response.ok || type.indexOf("application/x-ndjson") < 0) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          var error = new Error(data.error || ("Compile failed (HTTP " + response.status + ")."));
          error.code = (response.status === 404 || response.status === 405)
            ? "stream_unsupported" : (data.code || ("http_" + response.status));
          throw error;
        });
      }
      if (!response.body || !response.body.getReader || typeof TextDecoder === "undefined") {
        var unsupported = new Error("This browser cannot read a streaming compile response.");
        unsupported.code = "stream_unsupported";
        throw unsupported;
      }
      return new Promise(function (resolve, reject) {
        var settled = false;
        function succeed(event) {
          if (settled) return;
          settled = true;
          if (!event.pdf) {
            var missing = new Error("The server finished without sending the PDF.");
            missing.code = "compile_error";
            reject(missing);
            return;
          }
          resolve({
            blob: base64ToBlob(event.pdf),
            pages: event.pages,
            engine: event.engine,
            online: Boolean(event.online),
            bytes: event.bytes
          });
        }
        function fail(error) {
          if (settled) return;
          settled = true;
          reject(error);
        }
        function handle(event) {
          if (event.type === "done") {
            state.progressFromServer = true;
            setCompileProgress(100, event.message || "PDF ready.");
            compileFeed(event.message || "PDF ready.", "good");
            succeed(event);
            return;
          }
          if (event.type === "error") {
            state.progressFromServer = true;
            var error = new Error(event.message || "Compile failed.");
            error.code = event.code || "compile_error";
            fail(error);
            return;
          }
          state.progressFromServer = true;
          setCompileProgress(event.progress || state.progressValue, event.message || "Compiling…");
          if (event.type === "heartbeat") {
            compileFeed((event.message || "Still compiling…") +
              " (" + Number(event.elapsed || 0).toFixed(1) + "s)", "warn");
          } else {
            compileFeed(event.message || "Compiling…", "info");
          }
        }
        consumeNdjson(response, handle)
          .then(function () {
            if (!settled) {
              var ended = new Error("The compile stream ended before the PDF arrived.");
              ended.code = "compile_error";
              fail(ended);
            }
          })
          .catch(fail);
      });
    });
  }

  function legacyCompile(tex, mode, signal) {
    return fetch("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tex: tex, mode: mode }),
      signal: signal
    }).then(function (response) {
      var type = response.headers.get("content-type") || "";
      if (!response.ok || type.indexOf("application/pdf") < 0) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          var error = new Error(data.error || ("Compile failed (HTTP " + response.status + ")."));
          error.code = data.code || ("http_" + response.status);
          throw error;
        });
      }
      return response.blob().then(function (blob) {
        return {
          blob: blob,
          pages: response.headers.get("X-ResumeTeX-Pages") || "",
          engine: response.headers.get("X-ResumeTeX-Engine") || "",
          online: response.headers.get("X-ResumeTeX-Online") === "1"
        };
      });
    });
  }

  function applyCompileSuccess(result) {
    if (!result.blob || result.blob.size < 5) throw new Error("The server did not return a PDF.");
    state.pdfBlob = result.blob;
    if ($("btn_download_pdf")) $("btn_download_pdf").disabled = false;
    var size = Math.max(1, Math.round(result.blob.size / 1024));
    var pages = result.pages ? " · " + result.pages + " page(s)" : "";
    var where = result.online
      ? "Compiled online — your CV was uploaded to a third-party compiler."
      : "Compiled on this server with " + (result.engine || "pdflatex") + " — no third-party upload.";
    compileNotice("good", "PDF ready — " + size + " KB" + pages + ". " + where);
    $("engineNote").textContent = result.engine ? "Engine: " + result.engine : "";
    finishCompileProgress(true, "PDF ready");
    compileFeed("PDF ready — " + size + " KB" + pages + ".", "good");
    renderPdf(result.blob);
    logNetwork({
      what: "Compile",
      detail: (result.online ? "Online compiler" : "Local pdflatex") +
        " produced a " + size + " KB PDF" + pages
    });
  }

  function compilePdf(scrollToOutput) {
    if (scrollToOutput) {
      var card = $("outputCard");
      if (card && card.scrollIntoView) card.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (!state.tex.trim()) {
      var canvasReady = ($("c_summary").value.trim() || $("c_experience").children.length) &&
        currentTab() === "canvas";
      if (canvasReady) {
        // One click from an edited canvas to a PDF: render the fields first.
        var compileButton = $("btn_compile");
        compileButton.disabled = true;
        compileNotice("info", "Rendering the canvas fields, then compiling the PDF…");
        renderCanvas().then(function (ok) {
          compileButton.disabled = false;
          if (ok && state.tex.trim()) compilePdf(scrollToOutput);
          else compileNotice("warn", "The canvas could not be rendered. Add a summary or an experience entry first.");
        });
        return;
      }
      compileNotice("warn", "Generate or render a CV first — there is no LaTeX source yet.");
      return;
    }
    var mode = compilerMode();
    if (!confirmCompiler(mode)) {
      compileNotice("warn", "Compile cancelled. Nothing was uploaded.");
      return;
    }
    var button = $("btn_compile");
    button.disabled = true;
    var startText = mode === "online"
      ? "Uploading to the online compiler…"
      : (mode === "auto" ? "Compiling privately on the server (online fallback allowed)…" : "Compiling with pdflatex…");
    compileNotice("info", startText + " The first compile on a free server can take up to a minute.");
    $("engineNote").textContent = startText;
    $("pdfBox").innerHTML = "";
    resetCompileProgress(mode);

    // A cold free server can be slow, but it must never hang the button forever.
    var controller = window.AbortController ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, 180000) : null;
    var fallbackTried = false;

    function run() {
      return streamCompile(state.tex, mode, controller ? controller.signal : undefined)
        .catch(function (error) {
          if (error.code === "stream_unsupported" && !fallbackTried && !state.progressFromServer) {
            fallbackTried = true;
            compileFeed("Live progress is unavailable here; using the standard compile endpoint.", "warn");
            return legacyCompile(state.tex, mode, controller ? controller.signal : undefined);
          }
          throw error;
        });
    }

    run().then(applyCompileSuccess).catch(function (err) {
      var message = err.name === "AbortError"
        ? "The compile timed out. Try again (a cold free server is slow), or download the .tex file and compile it locally."
        : (err.message || "Compile failed.");
      if (err.code === "compile_disabled") {
        message += " Download the .tex file and compile it locally, or set RESUMETEX_ALLOW_COMPILE=1 on the server.";
      }
      if (err.code === "online_disabled") {
        message += " Pick “Server pdflatex” instead, or set RESUMETEX_ALLOW_ONLINE_COMPILE=1 on the server.";
      }
      compileNotice("bad", message);
      $("engineNote").textContent = "";
      $("pdfBox").innerHTML = '<p class="small">No PDF yet — the message above explains why.</p>';
      finishCompileProgress(false, "Compile failed");
      compileFeed(message, "bad");
      logNetwork({ what: "Compile", detail: "Failed — " + String(message).slice(0, 120) });
    }).then(function () {
      if (timer) clearTimeout(timer);
      button.disabled = false;
    });
  }

  function setCompilerOption(value, enabled) {
    var select = $("f_compiler");
    if (!select) return;
    var option = select.querySelector('option[value="' + value + '"]');
    if (option) option.disabled = !enabled;
  }

  function setServerStatus(text, kind) {
    var pill = $("serverStatus");
    if (!pill) return;
    pill.textContent = text;
    pill.className = "status-pill" + (kind ? " " + kind : "");
  }

  // Shown once at load, so a missing engine is visible before the first click.
  function checkServer() {
    fetch("/api/health").then(function (response) { return response.json(); })
      .then(function (health) {
        var onlineAllowed = Boolean(health.allowOnlineCompile);
        var localAllowed = Boolean(health.allowCompile);
        setCompilerOption("auto", onlineAllowed && localAllowed);
        setCompilerOption("online", onlineAllowed);
        var chosen = state.settings.compiler;
        if ((chosen === "online" && !onlineAllowed) ||
            (chosen === "auto" && (!onlineAllowed || !localAllowed))) {
          state.settings.compiler = "local";
          saveSettings();
        }
        if (state.settings.compiler === "online" || state.settings.compiler === "auto") {
          $("f_compiler").value = state.settings.compiler;
        }
        updateCompilerHint();

        if (!localAllowed) {
          state.serverNotice = {
            kind: "warn",
            html: "Server-side PDF compile is disabled on this instance." +
              (onlineAllowed ? " You can pick the online compiler above, or download the .tex file and compile it locally." :
                " Download the .tex file and compile it locally.")
          };
          setServerStatus(onlineAllowed ? "Online compile only" : "Compile disabled", "warn");
        } else {
          var latex = health.latex || {};
          if (health.pdflatex === false || latex.found === false) {
            state.serverNotice = {
              kind: "warn",
              html: "This server has no LaTeX engine, so server compile cannot run here." +
                (onlineAllowed ? " You can pick the online compiler above, or" : "") +
                " download the .tex file and compile it with pdflatex or Overleaf."
            };
            setServerStatus("No LaTeX engine", "bad");
          } else if (latex.missing && latex.missing.length) {
            state.serverNotice = { kind: "bad", html: "The server LaTeX install is incomplete — missing: " +
              latex.missing.join(", ") + ". Redeploy with the current Dockerfile, or compile the .tex locally." };
            setServerStatus("Missing LaTeX packages", "bad");
          } else {
            $("engineNote").textContent = "Server LaTeX is ready. PDFs are compiled on this server and never sent to a third party.";
            setServerStatus("Server ready · private", "ok");
            return;
          }
        }
        compileNotice(state.serverNotice.kind, state.serverNotice.html);
      })
      .catch(function () {
        setServerStatus("Server unreachable", "bad");
        /* the compile button will report the real error */
      });
  }

  function diagnose() {
    var button = $("btn_diagnose");
    var box = $("diagBox");
    button.disabled = true;
    box.hidden = false;
    box.textContent = "Checking the server LaTeX installation…";
    $("btn_copy_diag").hidden = true;
    var started = Date.now();
    fetch("/api/compile/diagnose", { method: "POST" })
      .then(function (response) {
        return response.json().then(function (data) { return { ok: response.ok, data: data || {} }; });
      })
      .then(function (result) {
        var data = result.data;
        var latex = data.pdflatex || {};
        var probe = data.probe;
        var lines = [
          "ResumeTeX LaTeX diagnostics",
          "Time: " + new Date().toISOString(),
          "Compile allowed: " + (data.allowCompile ? "yes" : "no"),
          "Online compile allowed: " + (data.allowOnlineCompile ? "yes" : "no"),
          "pdflatex found: " + (latex.found ? "yes" : "no"),
          "Path: " + (latex.path || "—"),
          "Version: " + (data.version || "unknown"),
          "Missing packages: " + ((latex.missing && latex.missing.length) ? latex.missing.join(", ") : "none")
        ];
        if (probe) {
          lines.push("Probe compile: " + (probe.ok
            ? "ok — " + probe.pages + " page, " + probe.bytes + " bytes, " + probe.engine
            : "FAILED"));
          if (probe.error) lines.push("Probe error: " + probe.error);
        } else {
          lines.push("Probe compile: not run (no local engine)");
        }
        box.textContent = lines.join("\n");
        $("btn_copy_diag").hidden = false;
        if (probe && probe.ok) {
          compileNotice("good", "LaTeX works — a test document compiled in " +
            ((Date.now() - started) / 1000).toFixed(1) + " s.");
        } else if (!latex.found) {
          compileNotice("warn", "This server has no pdflatex. Use the online compiler (if enabled) or compile the .tex locally.");
        } else {
          compileNotice("bad", "The server LaTeX install could not compile a test document. Copy the diagnostics for a bug report.");
        }
      })
      .catch(function (err) {
        box.textContent = "Diagnostics failed: " + (err.message || err);
        compileNotice("bad", "Could not run the LaTeX check: " + (err.message || err));
      })
      .then(function () { button.disabled = false; });
  }

  var pdfjsReady = null;
  function renderPdf(blob) {
    var box = $("pdfBox");
    box.innerHTML = "";
    if (!pdfjsReady) {
      pdfjsReady = import("/static/vendor/pdfjs/pdf.min.mjs").then(function (pdfjs) {
        pdfjs.GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/pdf.worker.min.mjs";
        return pdfjs;
      });
    }
    pdfjsReady.then(function (pdfjs) {
      return blob.arrayBuffer().then(function (buffer) {
        return pdfjs.getDocument({ data: new Uint8Array(buffer) }).promise;
      });
    }).then(function (pdf) {
      var pageNumber = 1;
      function drawPage() {
        if (pageNumber > pdf.numPages) return Promise.resolve();
        return pdf.getPage(pageNumber).then(function (page) {
          var viewport = page.getViewport({ scale: 1.5 });
          var canvas = document.createElement("canvas");
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          box.appendChild(canvas);
          return page.render({ canvasContext: canvas.getContext("2d"), viewport: viewport }).promise
            .then(function () { pageNumber += 1; return drawPage(); });
        });
      }
      return drawPage();
    }).catch(function (err) {
      box.innerHTML = "";
      var note = el("p", "small", "Preview unavailable: " + err.message + ". The PDF still downloads.");
      box.appendChild(note);
    });
  }

  function downloadBlob(blob, name) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  }

  // ------------------------------------------------------------------- init
  function fillProviders() {
    var select = $("f_provider");
    PROVIDERS.forEach(function (provider) {
      var option = document.createElement("option");
      option.value = provider.name;
      option.textContent = provider.name;
      select.appendChild(option);
    });
    select.value = state.settings.provider;
    select.onchange = function () {
      var chosen = PROVIDERS.filter(function (p) { return p.name === select.value; })[0];
      if (!chosen) return;
      $("f_baseurl").value = chosen.baseUrl;
      $("f_model").value = chosen.model;
      state.settings.provider = chosen.name;
      saveSettings();
      updateKeyStatus();
    };
  }

  function fillSimple(select, values) {
    values.forEach(function (value) {
      var option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
  }

  function updateKeyStatus() {
    var key = $("f_key").value.trim();
    var local = isLocalUrl($("f_baseurl").value);
    var status = $("keyStatus");
    if (local) {
      status.textContent = "Local endpoint — no key needed.";
      status.style.color = "var(--good)";
    } else if (key) {
      status.textContent = "Key set. It is sent only to " + hostOf($("f_baseurl").value) + ".";
      status.style.color = "var(--good)";
    } else {
      status.textContent = "No key — AI generation is off. Canvas mode still builds a complete CV.";
      status.style.color = "var(--muted)";
    }
    $("btn_generate").disabled = !local && !key;
  }

  function templateById(id) {
    return state.templates.filter(function (item) { return item.id === id; })[0] || null;
  }

  function updateTemplateInfo() {
    var select = $("f_template");
    if (!select) return;
    var item = templateById(select.value) || state.templates[0];
    if (!item) return;
    if ($("templateName")) $("templateName").textContent = item.name;
    if ($("templateBest")) {
      $("templateBest").textContent = (item.bestFor || []).length
        ? "Best for: " + item.bestFor.join(", ") : "";
    }
    if ($("templateScore")) {
      var score = typeof item.atsScore === "number" ? item.atsScore : "—";
      $("templateScore").textContent = "ATS " + score +
        (item.atsClass === "creative" ? " · creative" : " · ATS-safe");
    }
    if ($("templateSummary")) {
      $("templateSummary").textContent = [item.summary, item.why].filter(Boolean).join(" ");
    }
    var trigger = $("btn_template_content");
    if (trigger) {
      var canFill = Boolean(item.starter) && Object.keys(state.starterData || {}).length > 0;
      trigger.hidden = !canFill;
      trigger.textContent = "Load starter content";
    }
  }

  function loadStarterContent() {
    var select = $("f_template");
    var item = select ? templateById(select.value) : null;
    if (!item || !item.starter || !Object.keys(state.starterData || {}).length) {
      setNotice($("aiWarnings"), "warn", "This template has no starter content. Pick one of the Starter packs.");
      return;
    }
    fillCanvas(state.starterData);
    var nameField = $("f_name");
    if (nameField && !nameField.value.trim()) nameField.focus();
    logNetwork({ what: "Starter content", detail: item.name + " loaded into the canvas (contacts left blank)" });
    renderCanvas();
  }

  function applyTemplateQuery() {
    var params = new URLSearchParams(window.location.search);
    var wanted = params.get("template");
    var select = $("f_template");
    if (!wanted || !select) return false;
    var item = templateById(wanted);
    if (!item) return false;
    select.value = wanted;
    updateTemplateInfo();
    state.settings.template = wanted;
    saveSettings();

    // A starter link from the gallery should land on a ready-to-edit canvas,
    // not an empty one. Only prefill when the user has not typed anything yet.
    var untouched = !$("c_summary").value.trim() && !$("c_experience").children.length;
    if (item.starter && untouched && Object.keys(state.starterData || {}).length) {
      fillCanvas(state.starterData);
      compileNotice("info", "Starter content loaded. Replace the sample text with your own, " +
        "fill in your contact details, then press <b>Compile PDF</b>.");
      logNetwork({ what: "Template link", detail: item.name + " opened with editable starter content" });
    }
    return true;
  }

  function loadTemplates() {
    return api("/api/templates").then(function (data) {
      state.templates = data.house || [];
      state.starterData = data.starterData || {};
      var select = $("f_template");
      select.innerHTML = "";

      function group(label, items) {
        if (!items.length) return;
        var box = document.createElement("optgroup");
        box.label = label;
        items.forEach(function (item) {
          var option = document.createElement("option");
          option.value = item.id;
          option.textContent = item.name + " · ATS " + item.atsScore;
          box.appendChild(option);
        });
        select.appendChild(box);
      }

      var starters = state.templates.filter(function (item) { return item.starter; });
      var atsSafe = (data.atsSafe || []).filter(function (item) { return !item.starter; });
      var creative = data.creative || [];
      group("Starter packs — editable sample content", starters);
      group("ATS-safe layouts", atsSafe);
      group("Creative layouts (may parse poorly)", creative);

      // Keep a returning user's last choice if it still exists.
      var preferred = state.settings.template;
      if (preferred && templateById(preferred)) select.value = preferred;
      else if (starters.length) select.value = starters[0].id;
      select.onchange = function () {
        state.settings.template = select.value;
        saveSettings();
        updateTemplateInfo();
      };
      updateTemplateInfo();

      logNetwork({
        what: "Templates",
        detail: state.templates.length + " layouts loaded (" + atsSafe.length + " ATS-safe, " +
          starters.length + " starter packs, " + creative.length + " creative)"
      });
    });
  }

  function loadPromptTemplate() {
    return api("/api/prompt/default").then(function (data) {
      state.promptTemplate = data.template;
      state.promptContract = data.contract;
    });
  }

  function loadShellCache() {
    return Promise.all(STYLES.map(function (style) {
      return api("/api/shell/" + style[0]).then(function (data) {
        state.houseShells[style[0]] = data.shell;
      });
    }));
  }

  function bind() {
    Array.prototype.forEach.call(document.querySelectorAll(".tabs button"), function (button) {
      button.onclick = function () { setTab(button.dataset.tab); };
    });

    $("f_provider").onchange = function () {};
    $("f_baseurl").oninput = function () { state.settings.baseUrl = this.value; saveSettings(); updateKeyStatus(); };
    $("f_model").oninput = function () { state.settings.model = this.value; saveSettings(); };
    $("f_key").oninput = function () { saveKey(); updateKeyStatus(); };
    $("f_remember").onchange = function () { state.settings.rememberKey = this.checked; saveKey(); };
    $("f_style").onchange = function () { state.settings.style = this.value; saveSettings(); };

    $("btn_generate").onclick = generateWithAi;
    $("btn_offline").onclick = offlineGenerate;
    $("btn_payload").onclick = function () {
      var pii = collectPii();
      var redaction = new window.ResumeTexRedact.Redactor(pii).redact($("f_details").value || "");
      $("payloadSystem").textContent = buildSystemPrompt($("f_style").value, collectOptions(), null);
      $("payloadUser").textContent = "[DETAILS]\n" + redaction.text.trim() + "\n";
      $("payloadBox").hidden = false;
    };

    $("btn_add_exp").onclick = function () { entryRow($("c_experience"), {}); };
    $("btn_add_edu").onclick = function () { entryRow($("c_education"), {}); };
    $("btn_add_proj").onclick = function () { entryRow($("c_projects"), {}); };
    $("btn_add_cert").onclick = function () { entryRow($("c_certifications"), {}); };
    $("btn_to_canvas").onclick = loadIntoCanvas;
    $("btn_tex_to_canvas").onclick = loadIntoCanvas;
    $("btn_render").onclick = renderCanvas;
    if ($("btn_template_content")) $("btn_template_content").onclick = loadStarterContent;
    $("btn_load_sample").onclick = function () {
      api("/api/sample").then(function (sample) {
        fillCanvas(sample);
        renderCanvas();
      });
    };

    $("btn_compile").onclick = function () { compilePdf(false); };
    $("f_compiler").onchange = function () {
      state.settings.compiler = this.value;
      saveSettings();
      updateCompilerHint();
    };
    $("btn_diagnose").onclick = diagnose;
    $("btn_copy_diag").onclick = function () {
      var text = $("diagBox").textContent || "";
      if (!text) return;
      navigator.clipboard.writeText(text).then(function () {
        $("btn_copy_diag").textContent = "Copied";
        setTimeout(function () { $("btn_copy_diag").textContent = "Copy diagnostics"; }, 1500);
      });
    };
    $("btn_download_pdf").onclick = function () {
      if (!state.pdfBlob) { compileNotice("warn", "Compile the PDF first."); return; }
      downloadBlob(state.pdfBlob, "resume.pdf");
    };
    $("btn_download_tex").onclick = function () {
      if (!state.tex) { setNotice($("aiWarnings"), "warn", "Nothing to download yet."); return; }
      downloadBlob(new Blob([state.tex], { type: "application/x-tex" }), "resume.tex");
    };
    $("btn_copy_tex").onclick = function () {
      navigator.clipboard.writeText(state.tex).then(function () {
        $("btn_copy_tex").textContent = "Copied";
        setTimeout(function () { $("btn_copy_tex").textContent = "Copy .tex"; }, 1500);
      });
    };
    $("btn_fullscreen").onclick = function () {
      var box = $("pdfBox");
      if (document.fullscreenElement) document.exitFullscreen();
      else if (box.requestFullscreen) box.requestFullscreen();
    };
    $("btn_clear_log").onclick = function () { $("netLog").innerHTML = "<div class=\"small\">No requests yet.</div>"; };

    $("btn_test_key").onclick = function () {
      var baseUrl = $("f_baseurl").value.trim().replace(/\/+$/, "");
      var key = $("f_key").value.trim();
      var local = isLocalUrl(baseUrl);
      if (!local && !key) { setNotice($("aiWarnings"), "warn", "Add a key first."); return; }
      var headers = { "Content-Type": "application/json" };
      if (key && !local) headers.Authorization = "Bearer " + key;
      logNetwork({ what: "Key test", detail: hostOf(baseUrl) });
      fetch(baseUrl.indexOf("/chat/completions") >= 0 ? baseUrl : baseUrl + "/chat/completions", {
        method: "POST", headers: headers,
        body: JSON.stringify({ model: $("f_model").value.trim(), messages: [{ role: "user", content: "ping" }], max_tokens: 5 })
      }).then(function (response) {
        logNetwork({ what: "Key test", detail: "HTTP " + response.status });
        setNotice($("aiWarnings"), response.ok ? "good" : "bad",
          response.ok ? "Connection works." : "The provider rejected the key (HTTP " + response.status + ").");
      }).catch(function (err) {
        setNotice($("aiWarnings"), "bad", "Could not reach the provider: " + err.message);
      });
    };

    $("btn_forget_key").onclick = function () {
      $("f_key").value = "";
      state.settings.rememberKey = false;
      $("f_remember").checked = false;
      saveKey();
      updateKeyStatus();
    };

    // mobile action bar
    $("mb_generate").onclick = function () {
      var tab = currentTab();
      if (tab === "canvas") renderCanvas();
      else if (tab === "tex") compilePdf(true);
      else generateWithAi();
    };
    $("mb_compile").onclick = function () { compilePdf(true); };
  }

  function currentTab() {
    var active = document.querySelector(".tabs button.on");
    return active ? active.dataset.tab : "ai";
  }

  function init() {
    loadSettings();
    fillProviders();
    fillSimple($("f_style"), STYLES.map(function (s) { return s[0]; }));
    $("f_style").value = state.settings.style || "navy";
    fillSimple($("f_tone"), TONES);
    fillSimple($("f_emphasis"), EMPHASES);
    $("f_baseurl").value = state.settings.baseUrl || PROVIDERS[0].baseUrl;
    $("f_model").value = state.settings.model || PROVIDERS[0].model;
    $("f_remember").checked = Boolean(state.settings.rememberKey);
    var compiler = state.settings.compiler;
    $("f_compiler").value = (compiler === "auto" || compiler === "online") ? compiler : "local";
    updateCompilerHint();
    loadKey();
    bind();
    updateKeyStatus();
    checkServer();
    setTab("canvas");
    Promise.all([loadTemplates(), loadPromptTemplate(), loadShellCache()])
      .then(function () {
        applyTemplateQuery();
        logNetwork({ what: "Ready", detail: "no personal data sent anywhere yet" });
      })
      .catch(function (err) { setNotice($("aiWarnings"), "bad", err.message); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
