"""Guard against Bootstrap 4 markup and jQuery Bootstrap calls creeping back in.

ColdFront 1.1.9 uses Bootstrap 5 and doesn't expose its API: there is no window.bootstrap and no
$.fn.modal / .popover / .tooltip / .collapse, so such calls throw. Bootstrap 5 also ignores the
un-prefixed data-* attributes and the renamed classes below.
"""

import re
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parent.parent
FILES = sorted([*PACKAGE_DIR.joinpath("templates").rglob("*.html"), *PACKAGE_DIR.joinpath("static").rglob("*.js")])

FORBIDDEN = {
    "Bootstrap 4 data attribute (use data-bs-*)": re.compile(
        r"(?<![\w-])data-(toggle|target|dismiss|parent|content|placement|trigger|html|container)="
    ),
    "jQuery Bootstrap plugin call (not available on ColdFront 1.1.9)": re.compile(
        r"\.(modal|popover|tooltip|collapse|dropdown|toast)\("
    ),
    "window.bootstrap (not exposed by ColdFront)": re.compile(r"window\.bootstrap"),
    "Bootstrap 4 class (renamed in Bootstrap 5)": re.compile(
        r"\b(sr-only|float-(left|right)|text-(left|right)|font-weight-\w+|badge-(primary|secondary|success|danger|"
        r"warning|info|light|dark)|form-group|form-inline|btn-block|custom-select|[mp][lr]-(auto|\d))\b"
    ),
}


def test_files_found():
    assert len(FILES) > 10


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(PACKAGE_DIR)))
def test_no_bootstrap4_leftovers(path):
    problems = [
        f"{path.name}:{lineno}: {why}: {line.strip()}"
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for why, pattern in FORBIDDEN.items()
        if pattern.search(line)
    ]
    assert not problems, "\n".join(problems)
