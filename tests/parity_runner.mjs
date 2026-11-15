/* Runs the browser redactor over a corpus and prints JSON, so the Python test
 * can assert the browser and the server redact identically.
 * Reads the corpus from stdin: [{text, pii}, ...]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const script = path.join(here, "..", "resumetex_web", "static", "js", "redact.js");
const source = fs.readFileSync(script, "utf8");

// Run the browser file with a fake window so it registers itself there.
const fakeWindow = {};
const fn = new Function("window", "globalThis", source);
fn(fakeWindow, fakeWindow);
const win = fakeWindow;

const input = fs.readFileSync(0, "utf8");
const corpus = JSON.parse(input);
const out = corpus.map((item) => {
  const redactor = new win.ResumeTexRedact.Redactor(item.pii);
  const result = redactor.redact(item.text);
  return { text: result.text, replacementCount: result.replacementCount };
});
process.stdout.write(JSON.stringify(out));
