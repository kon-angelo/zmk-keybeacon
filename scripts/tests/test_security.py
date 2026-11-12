"""Compile and run the production security implementation with BLE/ZMK API doubles."""
from pathlib import Path
import os
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent


@pytest.mark.parametrize("legacy", [False, True])
def test_host_access_and_notification_isolation(tmp_path: Path, legacy: bool) -> None:
    binary = tmp_path / "security-test"
    command = [
        os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-I", str(TESTS / "stubs"), "-I", str(ROOT),
    ]
    if legacy:
        command.append("-DZMK_KEYBEACON_HAS_LEGACY_ENDPOINT=1")
    command.extend([
        str(ROOT / "keybeacon_security.c"), str(TESTS / "security_test.c"),
        "-o", str(binary),
    ])
    subprocess.run(command, check=True, capture_output=True, text=True)
    subprocess.run([str(binary)], check=True, capture_output=True, text=True)
