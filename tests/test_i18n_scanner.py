# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT_DIR / "web-manager" / "templates",
    ROOT_DIR / "web-manager" / "static" / "js",
]

# Best-effort patterns to ignore (technical strings, protocol, ids)
IGNORE_PATTERNS = [
    re.compile(r"^https?://"),
    re.compile(r"^rtsp://"),
    re.compile(r"^/api/"),
    re.compile(r"^[A-Z0-9_\-:.]+$"),
]


def _should_ignore(text: str) -> bool:
    text = text.strip()
    if not text:
        return True
    return any(p.search(text) for p in IGNORE_PATTERNS)


@pytest.mark.skipif(
    os.environ.get("I18N_SCAN") != "1",
    reason="Enable with I18N_SCAN=1 to run the i18n string scan"
)
def test_i18n_scan_for_untranslated_strings():
    violations = []

    for target in TARGETS:
        for path in target.rglob("*"):
            if path.suffix not in {".html", ".js"}:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")

            # Simple detection of raw text between tags in HTML
            if path.suffix == ".html":
                for match in re.finditer(r">([^<]{2,})<", content):
                    text = match.group(1).strip()
                    if _should_ignore(text):
                        continue
                    if "data-i18n" in match.group(0):
                        continue
                    if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text):
                        violations.append((path, text))

            # Simple detection of string literals in JS
            if path.suffix == ".js":
                for match in re.finditer(r"(['\"])(.*?)(\1)", content):
                    text = match.group(2).strip()
                    if _should_ignore(text):
                        continue
                    if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text):
                        violations.append((path, text))

    if violations:
        sample = "\n".join([f"{p}: {t}" for p, t in violations[:20]])
        pytest.fail(f"Potential untranslated strings found (sample):\n{sample}")
