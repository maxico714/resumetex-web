"""End-to-end check against a running server: every gallery preset renders and
compiles to a real PDF, and the AI path composes a document with the contact
header inserted locally."""

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5099"

def post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read(), response.headers

def post_status(path, payload):
    try:
        post(path, payload)
        return 200, b""
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))

PII = {"name": "Rehan Khan", "email": "rehan@leadsgp.tech", "phone": "+91 98765 43210",
       "location": "Indore, India", "linkedin": "linkedin.com/in/rehankhan",
       "github": "github.com/rehankhan"}

DATA = {
    "summary": "Data analyst with 5 years of experience in Python, SQL and Power BI dashboards.",
    "skills": [{"label": "Languages", "items": ["Python", "SQL"]},
               {"label": "Tools", "items": ["Power BI", "Excel"]}],
    "experience": [{"role": "Senior Data Analyst", "company": "Infosys",
                    "location": "Bengaluru, India", "dates": "2022 - Present",
                    "bullets": ["Built a Power BI dashboard used by 300 people, cutting reporting time by 30%."]}],
    "education": [{"role": "B.Tech Computer Science", "company": "RGPV University",
                    "location": "Bhopal", "dates": "2016 - 2020", "bullets": ["CGPA 8.4/10.0"]}],
}

templates = get("/api/templates")["house"]
ok = fail = 0

# Diagnostics: the server must be able to compile a harmless test document.
diagnostics = json.loads(post("/api/compile/diagnose", {})[0].decode())
engine = diagnostics.get("pdflatex") or {}
probe = diagnostics.get("probe") or {}
if not diagnostics.get("allowCompile"):
    print("SKIP | diagnose (compiling disabled on this instance)")
elif engine.get("found") and probe.get("ok"):
    print(f"PASS | diagnose        {diagnostics.get('version')}  "
          f"missing={engine.get('missing') or 'none'}  probe={probe.get('bytes')} bytes")
    ok += 1
else:
    print(f"FAIL | diagnose        found={engine.get('found')} missing={engine.get('missing')} "
          f"probe={probe.get('error') or probe}")
    fail += 1

# Online compile stays opt-in; when it is off the API must refuse it.
if diagnostics.get("allowOnlineCompile"):
    print("SKIP | online-gate (online compiling is enabled on this instance)")
else:
    status, body = post_status("/api/compile", {"tex": "\\documentclass{article}", "mode": "online"})
    detail = json.loads(body.decode() or "{}").get("code", "")
    if status == 403 and detail == "online_disabled":
        print("PASS | online-gate     403 online_disabled")
        ok += 1
    else:
        print(f"FAIL | online-gate     HTTP {status} {detail}")
        fail += 1

for template in templates:
    rendered = json.loads(post("/api/canvas/render", {"presetId": template["id"], "data": DATA})[0].decode())
    header = json.loads(post("/api/header", {
        "style": "navy", "accent": rendered["accent"],
        "headerStyle": template["headerStyle"], "pii": PII})[0].decode())["header"]
    document = (rendered["preamble"] + "\n\\begin{document}\n" + header + "\n"
                + rendered["body"] + "\n\\end{document}\n")
    try:
        pdf, headers = post("/api/compile", {"tex": document, "mode": "local"})
        assert pdf[:4] == b"%PDF", "not a pdf"
        print(f"PASS | {template['id']:<16} ATS {template['atsScore']}/{template['atsGrade']} "
              f"{len(pdf):>7} bytes  engine={headers.get('X-ResumeTeX-Engine')}")
        ok += 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL | {template['id']:<16} {exc}")
        fail += 1

# AI path: compose with the contact header, then compile.
body = ("\\section{Professional Summary}\nData analyst with 5 years of experience in Python and SQL.\n"
        "\\section{Skills}\n\\textbf{Languages:} Python, SQL\\\\\n"
        "\\section{Professional Experience}\n"
        "\\textbf{Data Analyst, Infosys} \\hfill 2022 - Present\\\\\n"
        "\\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]\n"
        "\\item Built a Power BI dashboard used by 300 people, cutting reporting time by 30\\%.\n"
        "\\end{itemize}\n"
        "\\section{Education}\nB.Tech Computer Science, RGPV University \\\\ 2016 - 2020")
for style in ("navy", "minimal", "compact", "projects", "times"):
    composed = json.loads(post("/api/compose", {"style": style, "pii": PII, "body": body})[0].decode())
    assert "Rehan Khan" in composed["tex"], "header missing"
    try:
        pdf, headers = post("/api/compile", {"tex": composed["tex"], "mode": "local"})
        assert pdf[:4] == b"%PDF"
        print(f"PASS | ai-path/{style:<9} {len(pdf):>7} bytes  pages={headers.get('X-ResumeTeX-Pages')}")
        ok += 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL | ai-path/{style:<9} {exc}")
        fail += 1

print(f"\n=== ok={ok} fail={fail} ===")
sys.exit(1 if fail else 0)
