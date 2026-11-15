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
    settings: { provider: "OpenRouter", baseUrl: PROVIDERS[0].baseUrl, model: PROVIDERS[0].model, rememberKey: false },
    pii: {},
    body: "",
    tex: "",
    pdfBlob: null,
    templates: [],
    houseShells: {},
    promptTemplate: "",
    promptContract: ""
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
      box.appendChild(el("div", "issue info", "<b>Nothing flagged.</b><span class=\"fix\">This CV passes every local ATS check.</span>"));
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

  // ----------------------------------------------------------- canvas flow
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
      summary: $("c_summary").value,
      skills: skills,
      experience: readEntries($("c_experience")),
      education: readEntries($("c_education"))
    };

    postJson("/api/canvas/render", {
      data: data,
      presetId: $("f_template").value,
      jobDescription: $("f_jd").value
    }).then(function (result) {
      state.body = result.body;
      var header = window.ResumeTexLatex.buildHeader(
        "navy", collectPii(), result.accent || null);
      state.tex = (result.preamble + "\n\\begin{document}\n" + header + "\n" + result.body +
        "\n\\end{document}\n").replace(/\n{3,}/g, "\n\n");
      setTex(state.tex);
      showAts(result.ats);
      setTab("tex");
    }).catch(function (err) { setNotice($("aiWarnings"), "bad", err.message); });
  }

  // -------------------------------------------------------------- compiling
  function compilePdf() {
    if (!state.tex.trim()) { setNotice($("aiWarnings"), "warn", "Generate or render a CV first."); return; }
    $("btn_compile").disabled = true;
    $("engineNote").textContent = "Compiling with pdflatex…";
    postJson("/api/compile", { tex: state.tex, mode: "local" })
      .catch(function (err) {
        if (err.data && err.data.code === "compile_disabled") {
          return fetch("/api/compile", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tex: state.tex, mode: "local" })
          });
        }
        throw err;
      })
      .then(function (blob) {
        if (blob instanceof Blob) {
          state.pdfBlob = blob;
          $("engineNote").textContent = "Compiled locally with pdflatex. The PDF never left this machine.";
          renderPdf(blob);
        } else {
          throw new Error("Compile failed.");
        }
      })
      .catch(function (err) {
        $("engineNote").textContent = "";
        var message = (err.data && err.data.error) || err.message;
        setNotice($("aiWarnings"), "bad", message);
      })
      .then(function () { $("btn_compile").disabled = false; });
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

  function loadTemplates() {
    return api("/api/templates").then(function (data) {
      state.templates = data.house || [];
      var select = $("f_template");
      select.innerHTML = "";
      state.templates.forEach(function (item) {
        var option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.name + " · ATS " + item.atsScore;
        select.appendChild(option);
      });
      var ats = (data.atsSafe || []).length;
      logNetwork({ what: "Templates", detail: data.house.length + " layouts loaded (" + ats + " ATS-safe)" });
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
    $("btn_render").onclick = renderCanvas;
    $("btn_load_sample").onclick = function () {
      api("/api/sample").then(function (sample) {
        $("c_summary").value = sample.summary;
        $("c_skills").value = sample.skills.map(function (group) {
          return group.label + ": " + group.items.join(", ");
        }).join("\n");
        $("c_experience").innerHTML = "";
        $("c_education").innerHTML = "";
        sample.experience.forEach(function (entry) { entryRow($("c_experience"), entry); });
        sample.education.forEach(function (entry) { entryRow($("c_education"), entry); });
        renderCanvas();
      });
    };

    $("btn_compile").onclick = compilePdf;
    $("btn_download_pdf").onclick = function () {
      if (!state.pdfBlob) { setNotice($("aiWarnings"), "warn", "Compile the PDF first."); return; }
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
      else if (tab === "tex") compilePdf();
      else generateWithAi();
    };
    $("mb_compile").onclick = compilePdf;
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
    loadKey();
    bind();
    updateKeyStatus();
    setTab("ai");
    Promise.all([loadTemplates(), loadPromptTemplate(), loadShellCache()])
      .then(function () { logNetwork({ what: "Ready", detail: "no personal data sent anywhere yet" }); })
      .catch(function (err) { setNotice($("aiWarnings"), "bad", err.message); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
