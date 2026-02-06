import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "web-manager" / "templates"
JS_DIR = ROOT / "web-manager" / "static" / "js"
ALLOWLIST_PATH = ROOT / "tests" / "i18n_allowlist.json"


def _load_allowlist():
    data = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return [re.compile(p) for p in data.get("patterns", [])]


def _is_allowed(text, patterns):
    return any(p.search(text) for p in patterns)


def test_no_hardcoded_ui_strings_in_templates():
    patterns = _load_allowlist()
    issues = []

    for html_file in TEMPLATES_DIR.glob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        for match in re.finditer(r">([^<>]+)<", content):
            raw = match.group(1)
            text = raw.strip()
            if not text:
                continue
            if "{{" in text or "{%" in text:
                continue
            if _is_allowed(text, patterns):
                continue
            if re.fullmatch(r"[\W_]+", text):
                continue
            issues.append(f"{html_file.relative_to(ROOT)}: '{text}'")

    assert not issues, "Hardcoded UI strings found in templates:\n" + "\n".join(issues)


def test_no_hardcoded_toast_alert_strings_in_js():
    patterns = _load_allowlist()
    issues = []

    js_files = list(JS_DIR.rglob("*.js"))
    for js_file in js_files:
        content = js_file.read_text(encoding="utf-8")

        for pattern in [
            r"showToast\(\s*(['\"])(?P<text>.+?)\1",
            r"alert\(\s*(['\"])(?P<text>.+?)\1",
            r"confirm\(\s*(['\"])(?P<text>.+?)\1",
        ]:
            for match in re.finditer(pattern, content):
                text = match.group("text").strip()
                if not text:
                    continue
                if "t(" in text:
                    continue
                if _is_allowed(text, patterns):
                    continue
                issues.append(f"{js_file.relative_to(ROOT)}: '{text}'")

    assert not issues, "Hardcoded UI strings found in JS:\n" + "\n".join(issues)
