/* Local LaTeX composition. The contact header is built here, in the browser,
 * so personal data is never part of an AI request and never leaves the page
 * until the user asks for a PDF (which runs pdflatex on their own machine).
 *
 * Port of ResumeTex.Core/Latex/HeaderBuilder.cs and LatexEscaper.cs.
 */
(function (global) {
  "use strict";

  var TEXT_ESCAPES = {
    "\\": "\\textbackslash{}",
    "{": "\\{",
    "}": "\\}",
    "$": "\\$",
    "&": "\\&",
    "#": "\\#",
    "_": "\\_",
    "%": "\\%",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}"
  };

  function normalizeTypography(value) {
    if (!value) return "";
    return String(value)
      .replace(/[\u2018\u2019]/g, "'")
      .replace(/[\u201C\u201D]/g, '"')
      .replace(/[\u2013\u2014]/g, "-")
      .replace(/\u2026/g, ".")
      .replace(/\u00A0/g, " ")
      .replace(/\u200B/g, "");
  }

  function escapeText(value) {
    if (!value) return "";
    var source = normalizeTypography(value).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    var out = "";
    for (var i = 0; i < source.length; i++) {
      var ch = source[i];
      out += Object.prototype.hasOwnProperty.call(TEXT_ESCAPES, ch) ? TEXT_ESCAPES[ch] : ch;
    }
    return out;
  }

  function escapeUrl(value) {
    if (!value) return "";
    var s = String(value).trim().replace(/\\/g, "/");
    s = s.replace(/\{/g, "%7B").replace(/\}/g, "%7D").replace(/\$/g, "%24")
         .replace(/\^/g, "%5E").replace(/~/g, "%7E").replace(/ /g, "%20");
    return s.replace(/%/g, "\\%").replace(/#/g, "\\#").replace(/&/g, "\\&").replace(/_/g, "\\_");
  }

  function displayUrl(value) {
    if (!value || !String(value).trim()) return "";
    var s = String(value).trim();
    s = s.replace(/^https:\/\//i, "").replace(/^http:\/\//i, "");
    return s.replace(/\/+$/, "");
  }

  function normalizeUrl(value, fallbackHost) {
    if (!value || !String(value).trim()) return "";
    var s = String(value).trim();
    if (/^https?:\/\//i.test(s)) return s;
    if (s.indexOf(".") >= 0 && s.indexOf(" ") < 0) return "https://" + s.replace(/^\/+/, "");
    return "https://" + fallbackHost + "/" + s.replace(/^\/+/, "");
  }

  function link(url, display) {
    return "\\href{" + escapeUrl(url) + "}{\\underline{" + escapeText(display) + "}}";
  }

  /* Build the contact header for a house style or a gallery preset.
   * accent overrides the colour name (the gallery presets carry their own).
   * headline is the optional professional title; headerStyle mirrors the
   * preset's centered/left/executive/two-column layout. */
  function buildHeader(style, pii, accent, headline, headerStyle) {
    pii = pii || {};
    var name = (pii.name || "").trim() || "Name";
    var title = escapeText((headline || "").trim());
    var colorName = accent || null;
    var layout = headerStyle || "centered";

    function nameLine(size) {
      if (colorName) {
        return "{\\color{" + colorName + "}" + size + "\\bfseries " + escapeText(name) + "}";
      }
      if (style === "times" && !headerStyle) {
        return "{\\color{linkcolour}\\Large\\bfseries " + escapeText(name) + "}";
      }
      return "{" + size + "\\bfseries " + escapeText(name) + "}";
    }

    function titleLine() {
      if (!title) return "";
      if (colorName) {
        return "{\\large\\itshape\\color{" + colorName + "} " + title + "}";
      }
      return "{\\large\\itshape " + title + "}";
    }

    var primary = [];
    var links = [];
    if ((pii.location || "").trim()) primary.push(escapeText(pii.location.trim()));
    if ((pii.email || "").trim()) primary.push(link("mailto:" + pii.email.trim(), pii.email.trim()));
    if ((pii.phone || "").trim()) primary.push(escapeText(pii.phone.trim()));
    if ((pii.linkedin || "").trim()) {
      links.push(link(normalizeUrl(pii.linkedin, "linkedin.com/in"), displayUrl(pii.linkedin)));
    }
    if ((pii.github || "").trim()) {
      links.push(link(normalizeUrl(pii.github, "github.com"), displayUrl(pii.github)));
    }
    if ((pii.portfolio || "").trim()) {
      links.push(link(normalizeUrl(pii.portfolio, "example.com"), displayUrl(pii.portfolio)));
    }

    var separator = style === "times" ? " \\,$\\cdot$\\, " : " $|$ ";

    if (layout === "left") {
      var leftParts = primary.concat(links);
      var left = ["\\begin{flushleft}", nameLine("\\LARGE") + "\\\\[1pt]"];
      if (title) left.push(titleLine() + "\\\\[2pt]");
      if (leftParts.length) left.push("\\small " + leftParts.join(separator));
      left.push("\\end{flushleft}");
      return left.join("\n");
    }

    if (layout === "executive") {
      var exec = ["\\noindent"];
      if (title) {
        exec.push(nameLine("\\Huge") + "\\hfill" + titleLine() + "\\par");
      } else {
        exec.push(nameLine("\\Huge") + "\\par");
      }
      exec.push("\\vspace{3pt}");
      if (colorName) {
        exec.push("{\\color{" + colorName + "}\\rule{\\linewidth}{1.4pt}}\\par");
        exec.push("\\vspace{1.5pt}");
        exec.push("{\\color{" + colorName + "}\\rule{\\linewidth}{0.4pt}}\\par");
      } else {
        exec.push("\\rule{\\linewidth}{1.4pt}\\par");
        exec.push("\\vspace{1.5pt}");
        exec.push("\\rule{\\linewidth}{0.4pt}\\par");
      }
      exec.push("\\vspace{2pt}");
      var execParts = primary.concat(links);
      if (execParts.length) {
        exec.push("\\begin{center}\\small " + execParts.join(separator) + "\\end{center}");
      }
      return exec.join("\n");
    }

    var lines = [];
    if (primary.length) lines.push(primary.join(separator));
    if (links.length) lines.push(links.join(separator));

    if (layout === "two-column") {
      var right = primary.concat(links).join(separator);
      var rows = [nameLine("\\LARGE") + " & " + right + " \\\\"];
      if (title) rows.push(titleLine() + " & \\\\");
      return "\\begin{tabular*}{\\textwidth}{l@{\\extracolsep{\\fill}}r}\n" +
        rows.join("\n") + "\n\\end{tabular*}";
    }

    var out = ["\\begin{center}", nameLine("\\LARGE") + "\\\\[1pt]"];
    if (title) out.push(titleLine() + "\\\\[2pt]");
    lines.forEach(function (line, index) {
      out.push("\\small " + line + (index < lines.length - 1 ? "\\\\" : ""));
    });
    out.push("\\end{center}");
    return out.join("\n");
  }

  /* Compose preamble (or a %%HEADER%%/%%BODY%% shell) with header + body. */
  function compose(shellText, style, pii, body) {
    var header = buildHeader(style, pii);
    var text = shellText;
    if (text.indexOf("%%HEADER%%") >= 0) {
      text = text.replace("%%HEADER%%", header);
    } else {
      text = text + "\n" + header;
    }
    if (text.indexOf("%%BODY%%") >= 0) {
      text = text.replace("%%BODY%%", (body || "").trim());
    } else {
      text = text + "\n" + (body || "").trim();
    }
    return text.replace(/\n{3,}/g, "\n\n").trim() + "\n";
  }

  /* LaTeX body -> plain text, for the page editor. */
  function bodyToPlainText(body) {
    if (!body || !body.trim()) return "";
    var text = String(body).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    text = text.replace(/\\section\{([^}]*)\}/g, function (_, t) { return "\n" + t.trim() + "\n"; });
    text = text.replace(/\\begin\{itemize\}(\[[^\]]*\])?/g, "");
    text = text.replace(/\\end\{itemize\}/g, "");
    text = text.replace(/\\item\s*/g, "- ");
    text = text.replace(/\\hfill/g, " | ");
    text = text.replace(/[ \t]*\|[ \t]*/g, " | ");
    ["textbf", "textit", "emph", "underline", "small"].forEach(function (cmd) {
      text = text.replace(new RegExp("\\\\" + cmd + "\\{([^{}]*)\\}", "g"), "$1");
    });
    text = text.replace(/\\href\{[^}]*\}\{([^}]*)\}/g, "$1");
    text = text.replace(/\\url\{([^}]*)\}/g, "$1");
    text = text.replace(/\\textbar\{\}/g, "|");
    text = text.replace(/\\%/g, "%").replace(/\\&/g, "&").replace(/\\#/g, "#")
               .replace(/\\_/g, "_").replace(/\\\$/g, "$").replace(/\\\{/g, "{").replace(/\\\}/g, "}");
    text = text.replace(/\\\\/g, "\n");
    text = text.replace(/\\[a-zA-Z]+\*?(\[[^\]]*\])?/g, "");
    text = text.replace(/\{/g, "").replace(/\}/g, "");
    text = text.replace(/[ \t]+\n/g, "\n");
    text = text.replace(/\n{3,}/g, "\n\n");
    return text.trim();
  }

  global.ResumeTexLatex = {
    escapeText: escapeText,
    escapeUrl: escapeUrl,
    displayUrl: displayUrl,
    normalizeUrl: normalizeUrl,
    buildHeader: buildHeader,
    compose: compose,
    bodyToPlainText: bodyToPlainText,
    normalizeTypography: normalizeTypography
  };
})(typeof window !== "undefined" ? window : globalThis);
