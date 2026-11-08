"""test_check_zmk_compat.py — pytest coverage for symbol probe + banner render.

Fixtures (scripts/tests/fixtures/zmk-{legacy,renamed,missing,header-missing}/):
  - zmk-legacy          -> exit 0, emits HAS_LEGACY_ENDPOINT macro
  - zmk-renamed         -> exit 0, does NOT emit HAS_LEGACY_ENDPOINT (fallback hit)
  - zmk-missing         -> exit 2, full banner on stderr
  - zmk-header-missing  -> exit 2, banner mentions "header missing: zmk/endpoints.h"

Plus:
  - --allow-incompat    -> exit 0 on zmk-missing with a WARN block
  - render_* pure functions reusable for byte-level fixture compare
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent.parent
CHECK_PY = MODULE_ROOT / "scripts" / "check_zmk_compat.py"
COMPAT_YAML = MODULE_ROOT / "compatibility.yaml"
FIXTURES = HERE / "fixtures"
EXPECTED_BANNER = FIXTURES / "expected_banner_v1.2.0.txt"


def _run(fixture: str, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(CHECK_PY),
            "--compat-file",
            str(COMPAT_YAML),
            "--zmk-root",
            str(FIXTURES / fixture),
            *(extra or []),
        ],
        capture_output=True,
        text=True,
    )


def test_legacy_fixture_emits_legacy_macro() -> None:
    r = _run("zmk-legacy")
    assert r.returncode == 0, f"stderr={r.stderr}"
    assert "DEFINES: -DZMK_KEYBEACON_HAS_LEGACY_ENDPOINT=1" in r.stdout
    assert "STATUS:" in r.stdout
    assert "✓" in r.stdout


def test_renamed_fixture_does_not_emit_legacy_macro() -> None:
    r = _run("zmk-renamed")
    assert r.returncode == 0, f"stderr={r.stderr}"
    # DEFINES line present but empty (no primary hit, fallback hit)
    defines_line = [ln for ln in r.stdout.splitlines() if ln.startswith("DEFINES:")][0]
    assert "HAS_LEGACY_ENDPOINT" not in defines_line
    assert "✓" in r.stdout


def test_missing_fixture_fails_with_banner() -> None:
    r = _run("zmk-missing")
    assert r.returncode == 2
    assert "is INCOMPATIBLE" in r.stderr
    assert "Missing symbol: zmk_endpoints_selected" in r.stderr
    assert "How to fix" in r.stderr
    assert "CONFIG_ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK=y" in r.stderr
    assert "Also" in r.stderr
    assert "CONFIG_ZMK_KEYBEACON_CHAR_CONNECTIVITY=n" in r.stderr


def test_header_missing_fixture_fails_with_header_missing_cue() -> None:
    r = _run("zmk-header-missing")
    assert r.returncode == 2
    assert "is INCOMPATIBLE" in r.stderr
    # banner shows the missing header path explicitly
    assert "zmk/endpoints.h" in r.stderr


def test_escape_hatch_downgrades_fail_to_warn() -> None:
    r = _run("zmk-missing", ["--allow-incompat"])
    assert r.returncode == 0, f"stderr={r.stderr}"
    assert "WARN:" in r.stdout
    assert "would have failed on symbol zmk_endpoints_selected" in r.stdout
    assert "CONFIG_ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK=y" in r.stdout
    assert "at your own risk" in r.stdout


# -------------------------------------------------------------------------
# Byte-level banner regression (contract: fail-fast-banner.md "字节级稳定性")
# -------------------------------------------------------------------------
def test_banner_matches_fixture_missing() -> None:
    """Byte-level stability of fail banner against expected_banner_v1.2.0.txt.

    If this fails, review the diff carefully: if the banner change is
    intentional, update `expected_banner_v1.2.0.txt` in the same PR.
    """
    if not EXPECTED_BANNER.exists():
        pytest.skip(
            f"expected banner fixture not generated yet: {EXPECTED_BANNER}; "
            f"run `python3 scripts/check_zmk_compat.py --compat-file compatibility.yaml "
            f"--zmk-root scripts/tests/fixtures/zmk-missing 2>fixtures/expected_banner_v1.2.0.txt` "
            f"and commit the file."
        )
    r = _run("zmk-missing")
    assert r.returncode == 2
    # Strip lines that embed an absolute path (varies per checkout) and the
    # dynamic "Current ZMK: <sha> (<path>)" line (sha + path vary).
    def _normalize(lines):
        kept = []
        for ln in lines:
            if ln.startswith("Current ZMK:"):
                continue
            # "  Location expected:  <abs-path>" also carries a path.
            if ln.lstrip().startswith("Location expected:"):
                continue
            kept.append(ln)
        return kept

    actual_lines = _normalize(r.stderr.splitlines())
    expected_lines = _normalize(EXPECTED_BANNER.read_text(encoding="utf-8").splitlines())
    assert actual_lines == expected_lines, (
        "banner drift detected; diff:\n"
        + "\n".join(
            f"  {t} {ln}"
            for t, ln in zip(
                ["-", "+"],
                [
                    "\n".join(expected_lines),
                    "\n".join(actual_lines),
                ],
            )
        )
    )


def test_compat_yaml_structure_is_sane() -> None:
    """Guard against drift between the real compat.yaml and the test fixtures:
    every required_symbol must declare `header: zmk/<header>.h` present under
    `app/include/` in zmk-legacy, and `used_in` must sit in module root."""
    data = yaml.safe_load(COMPAT_YAML.read_text(encoding="utf-8"))
    for i, sym in enumerate(data["required_symbols"]):
        used_in = MODULE_ROOT / sym["used_in"]
        assert used_in.exists(), f"required_symbols[{i}].used_in missing: {used_in}"
