#!/usr/bin/env python3
"""check_zmk_compat.py — CMake configure-time ZMK symbol probe.

Pipeline:
    1. Load compatibility.yaml (via yaml.safe_load).
    2. For each required_symbols[i], grep the ZMK header for `name` first,
       then any fallback. Collect: hit name, missed list, emits_macro to set.
    3. Render output:
         * stdout: machine-readable key=value lines (parsed by cmake/zmk_compat.cmake)
             STATUS: <one-line status for message(STATUS ...)>
             DEFINES: -DMACRO1=1 -DMACRO2=1   (empty line if none)
             WARN: <warn text, only if escape hatch active and probe would fail>
         * stderr: human-readable fail banner (only when exiting 2)
    4. Exit code:
         0 — probe passed (either naturally or by escape hatch)
         2 — probe failed (fail-fast; stderr contains banner)
         3-5 — compatibility.yaml itself is broken (shared with validate_compat.py)

Consumed by:
    cmake/zmk_compat.cmake   (parses stdout, surfaces banner from stderr)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError as e:  # pragma: no cover
    print(f"error: pyyaml not available ({e}); install via scripts/requirements-dev.txt", file=sys.stderr)
    sys.exit(2)


EXIT_OK = 0
EXIT_FAIL_FAST = 2
EXIT_MANIFEST_LOAD = 3


# ---------------------------------------------------------------------------
# T016 symbol_present
# ---------------------------------------------------------------------------
def symbol_present(
    zmk_root: Path, header: str, candidates: Iterable[str]
) -> tuple[bool, str | None]:
    r"""Grep header for the first symbol candidate that is present.

    Returns:
        (True, which_symbol) when any candidate matches `\bsym\s*\(` in the header.
        (False, "header missing: ...") when the header file itself is absent.
        (False, None) when the header exists but no candidate matches.
    """
    header_path = zmk_root / "app" / "include" / header
    if not header_path.exists():
        return False, f"header missing: {header}"
    text = header_path.read_text(encoding="utf-8", errors="replace")
    for sym in candidates:
        if re.search(rf"\b{re.escape(sym)}\s*\(", text):
            return True, sym
    return False, None


# ---------------------------------------------------------------------------
# T017 resolve_zmk_rev
# ---------------------------------------------------------------------------
def resolve_zmk_rev(zmk_root: Path) -> str:
    """Return the short HEAD sha of the ZMK clone, or '<unknown>' on failure."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(zmk_root), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "<unknown>"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProbeFailure:
    """One failing required_symbols[i] entry (populated during probe)."""

    name: str
    header: str
    used_in: str
    tried: list[str]
    reason: str  # "header missing: <path>" or "symbol not found"


def _upper_or_fallback(compat: dict) -> str:
    """Return upper sha, or lower as fallback when upper is null, for display."""
    kg = compat["zmk_known_good"]
    upper = kg.get("upper")
    if upper:
        return str(upper)
    return str(kg["lower"])


def _wrap_72(line: str) -> list[str]:
    """Hard-wrap at 72 chars; preserves blank lines."""
    if not line.strip():
        return [""]
    return textwrap.wrap(line, width=72, break_long_words=False, break_on_hyphens=False)


# ---------------------------------------------------------------------------
# T018 render_banner_fail
# ---------------------------------------------------------------------------
def render_banner_fail(
    compat: dict,
    current_sha: str,
    missing: list[ProbeFailure],
    zmk_root: Path,
    releases_url: str = "https://github.com/ykiewang/zmk-keybeacon/releases",
) -> str:
    """Render the full fail-fast banner (contracts/fail-fast-banner.md)."""
    assert missing, "render_banner_fail called with no failures"
    first = missing[0]
    kg = compat["zmk_known_good"]
    upper_for_display = kg["upper"] if kg.get("upper") else "HEAD-at-release"
    upper_or_lower = _upper_or_fallback(compat)
    escape_hatch = compat["escape_hatch"]["kconfig"]
    module_version = compat["module_version"]

    # 72-char-wide box
    top = "╔" + "═" * 70 + "╗"
    bottom = "╚" + "═" * 70 + "╝"
    title_lines = _wrap_72(
        f"zmk-keybeacon {module_version} is INCOMPATIBLE with the current ZMK revision"
    )
    boxed_title = []
    for line in title_lines:
        padded = line.ljust(66)
        boxed_title.append(f"║  {padded}  ║")

    lines: list[str] = []
    lines.append(top)
    lines.extend(boxed_title)
    lines.append(bottom)
    lines.append("")
    lines.append(f"Current ZMK:    {current_sha}  ({zmk_root})")
    lines.append(
        f"Known-good:    [{kg['lower']} .. {upper_for_display}]  (as of zmk-keybeacon {module_version} release)"
    )
    lines.append("")
    lines.append(f"Missing symbol: {first.name}")
    lines.append(f"  Location expected:  {zmk_root}/app/include/{first.header}")
    lines.append(f"  Called from:        {first.used_in}")
    lines.append(
        f"  Likely cause:       upstream ZMK renamed/removed this symbol after"
    )
    lines.append(
        f"                      {upper_or_lower} (see ZMK main-HEAD history)."
    )

    if len(missing) > 1:
        rest = ", ".join(f"`{m.name}`" for m in missing[1:])
        lines.append("")
        lines.append(f"Also missing: {rest} (see --verbose for details)")

    lines.append("")
    lines.append("─── How to fix ─────────────────────────────────────────────────────────")
    lines.append("")
    lines.append("Pick ONE of the following:")
    lines.append("")
    lines.append("[1] Pin ZMK back to a known-good revision (recommended):")
    lines.append("      In your zmk-config's west.yml, under `projects:` → `zmk`:")
    lines.append(f"          revision: {upper_or_lower}")
    lines.append("      Then:")
    lines.append("          west update && west build -p")
    lines.append("")
    lines.append("[2] Upgrade zmk-keybeacon to a tag that supports newer ZMK:")
    lines.append(f"      Check {releases_url}")
    lines.append("      for a tag released after your current ZMK revision landed")
    lines.append("      on ZMK main (see 'Current ZMK' sha above).")
    lines.append("")
    lines.append("[3] Opt out of the compatibility check (NOT RECOMMENDED — build may")
    lines.append("    still fail with cryptic C errors, and runtime behaviour is undefined):")
    lines.append("      In your prj.conf / <your_shield>.conf, add:")
    lines.append(f"          {escape_hatch}=y")
    lines.append("")
    lines.append("─── Also ───────────────────────────────────────────────────────────────")
    lines.append("")
    lines.append("Please DO NOT disable individual characteristics in your .conf as a")
    lines.append("workaround (e.g. CONFIG_ZMK_KEYBEACON_CHAR_CONNECTIVITY=n). That path")
    lines.append("silently removes host-side features and masks the real issue.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# T019 render_banner_warn
# ---------------------------------------------------------------------------
def render_banner_warn(
    compat: dict,
    current_sha: str,
    missing: list[ProbeFailure],
) -> str:
    """Render the escape-hatch warning (US1 Scenario 3)."""
    first = missing[0]
    escape_hatch = compat["escape_hatch"]["kconfig"]
    return (
        f"[zmk-keybeacon {compat['module_version']}] ZMK revision check: {current_sha}\n"
        f"   (would have failed on symbol {first.name}, continuing because\n"
        f"    {escape_hatch}=y — build and runtime at your own risk)"
    )


# ---------------------------------------------------------------------------
# T020 render_status_ok
# ---------------------------------------------------------------------------
def render_status_ok(compat: dict, current_sha: str) -> str:
    """Render the single-line success status (US1 Scenario 1)."""
    kg = compat["zmk_known_good"]
    upper = kg["upper"] if kg.get("upper") else "HEAD"
    return (
        f"[zmk-keybeacon {compat['module_version']}] ZMK revision check: "
        f"{current_sha} ∈ [known-good: {kg['lower']}..{upper}) ✓"
    )


# ---------------------------------------------------------------------------
# Probe engine
# ---------------------------------------------------------------------------
def _probe(compat: dict, zmk_root: Path) -> tuple[list[str], list[ProbeFailure]]:
    """Walk required_symbols; return (defines, failures)."""
    defines: list[str] = []
    failures: list[ProbeFailure] = []
    for sym in compat["required_symbols"]:
        candidates = [sym["name"], *sym.get("fallback", [])]
        hit, which = symbol_present(zmk_root, sym["header"], candidates)
        if hit:
            # emits_macro only when the primary name matched (not a fallback)
            if which == sym["name"] and sym.get("emits_macro"):
                defines.append(f"-D{sym['emits_macro']}=1")
        else:
            reason = which or "symbol not found"
            failures.append(
                ProbeFailure(
                    name=sym["name"],
                    header=sym["header"],
                    used_in=sym["used_in"],
                    tried=candidates,
                    reason=reason,
                )
            )
    return defines, failures


# ---------------------------------------------------------------------------
# T021 main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    default_compat = Path(__file__).resolve().parent.parent / "compatibility.yaml"
    parser.add_argument("--compat-file", type=Path, default=default_compat)
    parser.add_argument("--zmk-root", type=Path, required=True)
    parser.add_argument(
        "--allow-incompat",
        action="store_true",
        help="If set, downgrade FATAL to WARNING (maps to CONFIG_ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK=y)",
    )
    args = parser.parse_args()

    try:
        with args.compat_file.open("r", encoding="utf-8") as fh:
            compat = yaml.safe_load(fh)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        print(f"error: cannot load {args.compat_file}: {exc}", file=sys.stderr)
        return EXIT_MANIFEST_LOAD

    zmk_root = args.zmk_root.resolve()
    current_sha = resolve_zmk_rev(zmk_root)

    defines, failures = _probe(compat, zmk_root)
    defines_line = " ".join(defines)

    if not failures:
        print(f"STATUS: {render_status_ok(compat, current_sha)}")
        print(f"DEFINES: {defines_line}")
        return EXIT_OK

    if args.allow_incompat:
        warn = render_banner_warn(compat, current_sha, failures)
        print(f"STATUS: {render_status_ok(compat, current_sha).replace(' ✓', ' (bypassed)')}")
        print(f"DEFINES: {defines_line}")
        # emit WARN as a multi-line field; cmake side joins with newline
        print("WARN:")
        for ln in warn.splitlines():
            print(f"  {ln}")
        return EXIT_OK

    # fail-fast
    banner = render_banner_fail(compat, current_sha, failures, zmk_root)
    print(banner, file=sys.stderr)
    return EXIT_FAIL_FAST


if __name__ == "__main__":
    sys.exit(main())
