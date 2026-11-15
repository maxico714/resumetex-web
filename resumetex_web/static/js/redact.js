/* PII redaction — browser-side port of ResumeTex.Core/Privacy/PiiRedactor.cs and
 * resumetex_web/core/pii.py.
 *
 * This runs before anything is sent to an AI provider. The same rules are
 * implemented server-side; tests/test_parity.py asserts both agree.
 */
(function (global) {
  "use strict";

  var REDACT = {
    name: "the candidate",
    email: "the candidate's email",
    phone: "the candidate's phone number",
    location: "the candidate's location",
    linkedin: "the candidate's LinkedIn profile",
    github: "the candidate's GitHub profile",
    portfolio: "the candidate's portfolio link",
    profile: "the candidate's profile"
  };

  var EMAIL_RE = /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/g;
  var PHONE_RE = /(?<![\d])\+?\d[\d\s().\-]{6,}\d(?![\d])/g;
  var YEAR_RANGE_RE = /^\s*\+?\s*(19|20)\d{2}\s*[-–—]{1,2}\s*(19|20)\d{2}\s*$/;
  var DECIMAL_RE = /^\d+(\.\d+)+$/;

  function escapeRe(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function wordPattern(value) {
    return "(?<![\\p{L}\\p{N}])" + escapeRe(value) + "(?![\\p{L}\\p{N}])";
  }

  function hasWord(text, term) {
    return new RegExp(wordPattern(term), "iu").test(text);
  }

  function splitTerms(value) {
    var seen = Object.create(null);
    var out = [];
    (String(value || "").split(/[^\p{L}\p{N}]+/u) || []).forEach(function (part) {
      if (!part || part.length < 2) return;
      var key = part.toLowerCase();
      if (seen[key]) return;
      seen[key] = true;
      out.push(part);
    });
    return out;
  }

  function linkHandles(value) {
    var raw = String(value || "").trim();
    if (!raw) return [];
    var path = raw;
    var scheme = raw.indexOf("://");
    if (scheme >= 0) {
      var after = raw.slice(scheme + 3);
      var slash = after.indexOf("/");
      path = slash >= 0 ? after.slice(slash) : "";
    }
    var cut = path.length;
    ["?", "#"].forEach(function (ch) {
      var idx = path.indexOf(ch);
      if (idx >= 0) cut = Math.min(cut, idx);
    });
    path = path.slice(0, cut);
    var parts = path.split("/").filter(Boolean);
    if (!parts.length) return [];
    var last = parts[parts.length - 1].replace(/^@/, "");
    if (last.length < 2) return [];
    if (last.toLowerCase() === raw.toLowerCase()) return [];
    return [last];
  }

  function digitsOnly(value) {
    return (String(value || "").match(/\d/g) || []).join("");
  }

  function countDigits(value) {
    return (String(value || "").match(/\d/g) || []).length;
  }

  function filledFields(pii) {
    pii = pii || {};
    var out = [];
    [["name", pii.name], ["email", pii.email], ["phone", pii.phone],
     ["location", pii.location], ["LinkedIn", pii.linkedin],
     ["GitHub", pii.github], ["portfolio", pii.portfolio]].forEach(function (pair) {
      var value = (pair[1] || "").trim();
      if (value) out.push([pair[0], value]);
    });
    return out;
  }

  function buildReplacements(pii) {
    var out = [];
    filledFields(pii).forEach(function (pair) {
      var label = pair[0];
      var value = pair[1];
      if (label === "name") {
        if (value.length >= 2) out.push([value, wordPattern(value), REDACT.name]);
        splitTerms(value).forEach(function (part) {
          out.push([part, wordPattern(part), REDACT.name]);
        });
      } else if (label === "email") {
        out.push([value, escapeRe(value), REDACT.email]);
      } else if (label === "phone") {
        out.push([value, escapeRe(value), REDACT.phone]);
      } else if (label === "location") {
        if (value.length >= 2) out.push([value, wordPattern(value), REDACT.location]);
        splitTerms(value).forEach(function (part) {
          out.push([part, wordPattern(part), REDACT.location]);
        });
      } else if (label === "LinkedIn") {
        out.push([value, escapeRe(value), REDACT.linkedin]);
      } else if (label === "GitHub") {
        out.push([value, escapeRe(value), REDACT.github]);
      } else if (label === "portfolio") {
        out.push([value, escapeRe(value), REDACT.portfolio]);
      }
      linkHandles(value).forEach(function (handle) {
        out.push([handle, escapeRe(handle), REDACT.profile]);
      });
    });
    return out;
  }

  function PiiLeakError(message) {
    this.name = "PiiLeakError";
    this.message = message;
  }
  PiiLeakError.prototype = Object.create(Error.prototype);

  function Redactor(pii) {
    this.pii = pii || {};
  }

  Redactor.prototype.verifyNoPii = function (text) {
    var self = this;
    filledFields(this.pii).forEach(function (pair) {
      var label = pair[0];
      var value = pair[1];
      if (label === "email" || label === "LinkedIn" || label === "GitHub" || label === "portfolio") {
        if (value.length >= 2 && text.toLowerCase().indexOf(value.toLowerCase()) >= 0) {
          throw new PiiLeakError("The " + label + " value is still present after redaction.");
        }
        linkHandles(value).forEach(function (handle) {
          if (text.toLowerCase().indexOf(handle.toLowerCase()) >= 0) {
            throw new PiiLeakError("The " + label + " handle is still present after redaction.");
          }
        });
      } else if (label === "phone") {
        var digits = digitsOnly(value);
        if (digits.length >= 7 && digitsOnly(text).indexOf(digits) >= 0) {
          throw new PiiLeakError("The phone number is still present after redaction.");
        }
      } else {
        if (value.length < 2) return;
        if (hasWord(text, value)) {
          throw new PiiLeakError("The " + label + " value is still present after redaction.");
        }
        splitTerms(value).forEach(function (term) {
          if (hasWord(text, term)) {
            throw new PiiLeakError("The " + label + " value is still present after redaction.");
          }
        });
      }
    });
    if (EMAIL_RE.test(text)) {
      EMAIL_RE.lastIndex = 0;
      throw new PiiLeakError("An email address is still present after redaction.");
    }
    EMAIL_RE.lastIndex = 0;
  };

  Redactor.prototype.redact = function (input) {
    var text = input || "";
    var count = 0;
    var details = [];

    var replacements = buildReplacements(this.pii).sort(function (a, b) {
      return b[0].length - a[0].length;
    });

    replacements.forEach(function (item) {
      var regex = new RegExp(item[1], "giu");
      var matches = text.match(regex);
      if (matches && matches.length) {
        count += matches.length;
        details.push(item[0] + " -> " + item[2] + " (" + matches.length + "x)");
      }
      text = text.replace(regex, function () { return item[2]; });
    });

    var emails = text.match(EMAIL_RE);
    if (emails && emails.length) {
      count += emails.length;
      details.push(emails.length + " email(s) -> " + REDACT.email);
    }
    text = text.replace(EMAIL_RE, REDACT.email);

    text = text.replace(PHONE_RE, function (match) {
      var digits = countDigits(match);
      if (digits < 8 || digits > 15) return match;
      if (YEAR_RANGE_RE.test(match)) return match;
      if (DECIMAL_RE.test(match)) return match;
      count += 1;
      return REDACT.phone;
    });

    this.verifyNoPii(text);
    return { text: text, replacementCount: count, details: details };
  };

  global.ResumeTexRedact = {
    Redactor: Redactor,
    PiiLeakError: PiiLeakError,
    REDACT: REDACT,
    splitTerms: splitTerms,
    linkHandles: linkHandles,
    digitsOnly: digitsOnly
  };
})(typeof window !== "undefined" ? window : globalThis);
