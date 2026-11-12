# zmk-keybeacon source security audit — 2026-11-12

## Fork hardening follow-up

The findings below describe the original upstream commit. The personal fork
now addresses ZKB-01/ZKB-02 in `keybeacon_security.c` and `keybeacon.c`:

- Every characteristic read and CCC read/write requires encryption.
- Status reads/notifications require a connected LE host (keyboard in the
  peripheral role), security level L2 or higher, a stored bond, and a valid
  ZMK host profile. Split peers and unassigned connections are rejected.
- AA1 reads reveal actual input only to the selected BLE typing profile.
  Other authorized hosts receive a fixed `Private` payload with zero modifiers.
- Input notifications go only to the active host. Endpoint changes refresh
  that host and clear inactive displays; ordinary typing sends no notification
  to inactive hosts, including no timing-only placeholder notifications.
- USB output hides input from every Bluetooth client. Battery, connectivity
  and per-host slot information remain available to authorized bonded hosts.
- Notifications use characteristic value attributes, so Zephyr checks the
  encrypted permissions in addition to the explicit connection guard.

The security regression tests compile the production security implementation
with Bluetooth/ZMK API doubles for both old and new endpoint API names.
All **26 module tests pass**, including denied plaintext/unbonded/split-peer
access, profile transitions, USB output, inactive-host polling, notification
isolation, unsubscribed clients and bond/encryption revocation. The manifest
validator and generated-CI check also pass.

The left, right and settings-reset Temper targets were built successfully
against ZMK `4dd95d7840eb3d5a3f59bb29fbf1ab054715ef85` using the ZMK Docker
build image. The left image includes all four KBP characteristics and split
battery fetching; the right/reset images exclude KeyBeacon. The left build
uses 393,712 bytes of flash and 113,746 bytes of RAM. No module compiler
warnings remain; existing display, KSCAN and reset-target warnings are outside
this change.

L2 encryption does not add MITM protection to Just Works pairing. Real-hardware
pairing, switching and reconnection remain to be verified; the tests are not
over-the-air validation.

## Scope and conclusion

Reviewed upstream commit `66f2486ce3d42d56b7a7853f57f988052a35f98b`
(`v1.2.0`), cloned from `kon-angelo/zmk-keybeacon`.

The complete firmware implementation (`keybeacon.c`), Kconfig, Zephyr/CMake
entry points, configure-time Python compatibility probe and development/CI
scripts were reviewed. No ordinary-keycode recording, persistent typing
history, Internet networking, or command/control implementation was found.

**The module is not a full keylogger, but its Bluetooth access controls need
hardening before privacy-sensitive use.** Layer/modifier transitions are
input-related metadata and can reveal activity, timing and shortcut patterns.

This review does not cover all of ZMK/Zephyr or board-specific configuration.
The findings are source-confirmed; exploitability against a particular
keyboard's pairing/connection policy has not been tested over the air.

## What the firmware actually observes and sends

- `keybeacon.c:480-487` subscribes to keycode and layer-change events.
  The callback does not read the event's ordinary keycode; it rebuilds the
  current layer/modifier snapshot and bubbles the event onward.
- `:449-464` builds only `[layer index, explicit modifiers, layer name]`.
  The name copy is bounded to 32 bytes into a 34-byte buffer.
- `:466-477` suppresses identical snapshots. Ordinary typing with unchanged
  layer/modifiers therefore does not emit one KBP notification per key.
- Optional payloads contain connection/profile/output/split-link flags,
  battery percentages and the requesting connection's profile slot.
- Status caches are static RAM buffers; no flash/settings/file write or
  persistent keystroke buffer exists in this file. The only module log call
  is an unresolved-host-slot diagnostic (`:400`).
- GATT characteristic values are read-only (or read/notify). Client writes
  configure notification subscriptions through CCC descriptors; there is
  no KBP command to inject keystrokes or change the keymap.

## Findings

### ZKB-01 — Medium: status service does not require encrypted access

`keybeacon.c:414-443` defines every status characteristic with plain
`BT_GATT_PERM_READ`. CCC descriptors use plain
`BT_GATT_PERM_READ | BT_GATT_PERM_WRITE`. There are no `*_ENCRYPT` or
`*_AUTHEN` permissions and no explicit bonded-host authorization in the
AA1/AA2/AA3 read callbacks or notification path.

A peer that obtains an unencrypted GATT connection is not rejected by this
service when reading status or enabling notifications. Whether such a peer
can connect, or how long it remains connected, depends on the consuming
keyboard's ZMK/Bluetooth policy. This does **not** prove that every nearby
device can observe an already-encrypted bonded connection.

The exposed data includes layer names, modifier changes, profile changes,
output destination and battery state. AA4 returning slot `0` for an
unresolved peer (`:378-403`) is diagnostic behavior, not an access denial;
it does not protect AA1-AA3.

Recommendation: require encrypted characteristic reads and CCC reads/writes,
authorize intended bonded host connections, and verify that notifications
also enforce the selected security level in the consuming Zephyr version.
Choose authenticated pairing where the hardware supports it. Test unpaired,
unencrypted, reconnect, re-pair and multi-host cases on real hardware.

### ZKB-02 — Medium privacy/design issue: input metadata reaches inactive hosts

`keybeacon.c:477,501-502,551-552` calls `bt_gatt_notify(NULL, ...)`, which
addresses subscribed connections rather than just the active HID host.
The AA1 read callback (`:125-127`) also returns the same global snapshot
to every reader. Neither path checks the selected HID endpoint/profile.

If another paired computer keeps a subscribed connection open, it can
observe layer/modifier changes while the keyboard types on a different host
or outputs to USB. Encryption alone does not solve this because the other
host can be legitimately bonded. The companion app's "active elsewhere"
indicator is informational; it does not enforce firmware authorization.

Recommendation: restrict AA1 reads and notifications to the active authorized
typing host, or make cross-host input-status sharing a clearly documented
opt-in. Non-input battery/connectivity sharing can use a separate policy.
Returning a sanitized snapshot for other hosts must apply to both READ and
NOTIFY paths.

## Build and maintenance observations

- `Kconfig.keybeacon:4-7` leaves the module disabled by default. Optional
  characteristics default on once their parent feature is enabled.
- `keybeacon.cmake:13-17` only compiles the implementation with BLE,
  KeyBeacon and `CONFIG_ZMK_SPLIT_ROLE_CENTRAL`. Despite broader documentation,
  unibody support needs confirmation against the target's Kconfig values.
- `cmake/zmk_compat.cmake` runs the local `scripts/check_zmk_compat.py`.
  It uses `yaml.safe_load`, reads ZMK headers, and invokes `git rev-parse`
  with an argument list; no download or shell-evaluated header content was
  found in that configure path.
- The compatibility probe is a header-symbol check, not a firmware build
  or enforcement of a precise tested revision interval. Passing it cannot
  establish ABI/runtime compatibility or Bluetooth security.
- `scripts/one-time-setup.sh` creates a GitHub issue label; it is a manual
  maintainer helper and was not run. CI's scheduled failure handler creates
  an issue in its own repository. No hidden firmware-upload path was found.
- Python development requirements and GitHub Actions references are not
  locked by artifact hash/commit. Future dependency updates need separate
  review; their full implementations were outside this audit.

## Validation and fork integration

The initial Python suite produced **23 passes and one documentation failure**:
the generated README compatibility table omitted the existing `v1.2.0` tag.
The missing row was synchronized with generator output as a local change.
The previously failing test then passed on a targeted rerun.
No firmware behavior or Bluetooth permissions were changed during this audit.

The compatibility manifest validator, CI regeneration check, and all four
fixture-based compatibility smoke scenarios passed. These checks do not
compile `keybeacon.c` or test a physical keyboard.

For a future consuming `west.yml`, point the module project at the fork,
not the upstream URL, and pin a reviewed full commit:

```yaml
- name: zmk-keybeacon
  url: https://github.com/kon-angelo/zmk-keybeacon
  revision: 66f2486ce3d42d56b7a7853f57f988052a35f98b
```

That pin identifies the audited **unhardened** source. After addressing
ZKB-01/ZKB-02 and validating the target keyboard, replace it with the
reviewed hardening commit. Existing keyboard manifests were not changed.
The desktop application audit/build record is in
[`../keybeacon/SECURITY-AUDIT.md`](../keybeacon/SECURITY-AUDIT.md).
