"""Build-time LaTeX smoke test for the Docker image.

The deployed instance must be able to compile a real resume, not just start
Flask. This script compiles every gallery preset with the same code path as
``/api/compile``. Run it during ``docker build`` so a missing TeX package fails
the build instead of shipping an image whose Compile PDF button cannot work.

    python -m resumetex_web.docker_check
"""

import sys

from .core import PiiFields, render_document, sample_data
from .core.compile import compile_local, latex_status
from .core.gallery import GALLERY

# Obviously fake data: the check never touches a real person's details.
CHECK_PII = PiiFields(
    name="Docker Check",
    email="docker-check@example.com",
    phone="+1 555 0100",
    location="Container",
)


def main() -> int:
    status = latex_status()
    if not status["found"]:
        print("FAIL: pdflatex was not found in the image PATH.")
        return 1
    print(f"pdflatex: {status['path']}")
    if status["missing"]:
        print("FAIL: LaTeX packages missing from the image: " + ", ".join(status["missing"]))
        return 1

    data = sample_data()
    failures = []
    for preset_id in sorted(GALLERY):
        tex = render_document(data, GALLERY[preset_id], CHECK_PII)
        try:
            result = compile_local(tex, timeout=120)
        except Exception as exc:  # CompileError, but report anything at all
            failures.append((preset_id, str(exc).splitlines()[0]))
            print(f"FAIL  {preset_id}: {failures[-1][1]}")
            continue
        if result.pages < 1 or len(result.pdf) < 1000:
            failures.append((preset_id, "empty PDF"))
            print(f"FAIL  {preset_id}: empty PDF")
            continue
        print(f"ok    {preset_id}: {result.pages} page(s), {len(result.pdf) // 1024} KB")

    if failures:
        print(f"\nFAIL: {len(failures)} of {len(GALLERY)} templates did not compile.")
        print("Install the missing Debian packages listed above, then rebuild the image.")
        return 1
    print(f"\nOK: all {len(GALLERY)} gallery templates compiled to PDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
