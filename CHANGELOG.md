<!--
Copyright (c) 2026 The TOTEM ZMK Contributors
SPDX-License-Identifier: MIT
-->

# Changelog — zmk-keybeacon

All notable changes to the KeyBeacon Zephyr module are documented here. The module follows
[Semantic Versioning](https://semver.org/): consumers pin a tag via `revision` in their `west.yml`.

## Versioning policy

| Change | Example | Version bump |
|--------|---------|--------------|
| Breaking change to the GATT contract | Service/characteristic UUID change, payload layout change | **MAJOR** |
| Backward-compatible addition | A new optional Kconfig symbol | **MINOR** |
| Fix with no interface change | Bug fix in change-detection, doc fix | **PATCH** |

Because consumers pin an exact tag, publishing a new version never affects an existing build
until that consumer bumps its `revision`.

## [1.2.0] — 2026-11-08

**MINOR** release — adds the KBP 1.2 per-connection **Host-Link** characteristic
(`AA440AA4-…`). Purely additive: the service UUID is unchanged and every byte of
the KBP 1.0/1.1 characteristics (AA1/AA2/AA3) is bit-for-bit identical to v1.1.4.

### Added

- **AA4 Host-Link characteristic** (`AA440AA4-F5ED-4C48-84A1-8062D20D3D55`,
  **READ only — no NOTIFY, no CCC**). Its 1-byte payload `[0]` carries
  `local_link_profile` (bits0–6: the profile slot of **this** BLE connection,
  1-based; `0` = not determined; bit7 reserved, 0). Because a GATT read callback
  carries the originating `struct bt_conn *`, the firmware answers **each** host
  with its own slot — so a host can tell "in use on this computer" from "active
  on another computer" with zero configuration. A read is inherently
  per-connection, so (unlike a broadcast NOTIFY) the value is never shared across
  hosts. When the peer cannot be resolved to a bonded profile the firmware emits
  `0` (never a guess) and logs one `hostlink.unresolved` diagnostic at DBG level.
- `CONFIG_ZMK_KEYBEACON_HOST_LINK` (default `y`, `depends on
  ZMK_KEYBEACON_CONNECTIVITY`) — gates the AA4 characteristic. Set it to `n` to
  emit the exact KBP 1.1 GATT shape (no AA4).
- `compatibility.yaml` — `zmk_ble_profile_index` (`zmk/ble.h`) added to
  `required_symbols`; this is the ZMK API that maps a connection's peer address
  to a bonded profile slot. `module_version` bumped `1.1.4` → `1.2.0`.

### Fixed

- `scripts/check_zmk_compat.py` — the `symbol_present` docstring is now a raw
  string, silencing a `SyntaxWarning: invalid escape sequence '\s'` on Python
  3.12+ that otherwise leaked into regenerated banner snapshots.

### Backward compatibility

- **Old host + new firmware**: a host that does not discover AA4 is unaffected;
  AA1/AA2/AA3 parse byte-identically to v1.1.x.
- **New host + old firmware**: a 1.2-aware host that finds no AA4 falls back to
  link-level status and MUST NOT fabricate a slot (host-side obligation).
- Existing `keybeacon_svc` attribute indices are unchanged: AA4 is appended last
  and has no CCC, so the AA1 notify target and the AA2/AA3 notify indices are
  byte-for-byte preserved.

### Design & provenance

- Firmware-producer half of `keybeacon` **specs/005-host-link-profile-awareness**
  (the wire contract's source of truth and the macOS/Windows consumers live in
  the sibling `keybeacon` repo). Implements its firmware obligations FR-001–FR-005,
  FR-011–FR-016.
- All 24 pytest cases green (`scripts/tests/`); `validate_compat.py` and
  `regen_ci.py --check` pass.

---

## [1.2.0] — 2026-11-08（中文）

**MINOR** 版本——新增 KBP 1.2 的「每连接主机上下文」特征（`AA440AA4-…`）。纯加法：
service UUID 不变，KBP 1.0/1.1 既有特征（AA1/AA2/AA3）每一个字节与 v1.1.4 逐字节一致。

### 新增

- **AA4 Host-Link 特征**（`AA440AA4-F5ED-4C48-84A1-8062D20D3D55`，**只读——无
  NOTIFY、无 CCC**）。其 1 字节 payload `[0]` 携带 `local_link_profile`（bits0–6：
  **本** BLE 连接对应的 profile slot，1-based；`0` = 未确定；bit7 保留，为 0）。由于
  GATT 读回调天然带发起连接的 `struct bt_conn *`，固件对**每台**主机回答其自身 slot
  ——主机据此零配置地区分「正在此电脑使用」与「在另一台电脑使用」。读取天然是
  per-connection 的，因此（不同于广播 NOTIFY）该值绝不会跨主机相同。当对端无法解析到
  已绑定 profile 时，固件发 `0`（绝不猜测），并以 DBG 级打印一条 `hostlink.unresolved`
  诊断。
- `CONFIG_ZMK_KEYBEACON_HOST_LINK`（默认 `y`，`depends on
  ZMK_KEYBEACON_CONNECTIVITY`）——门控 AA4 特征。设为 `n` 即输出与 KBP 1.1 完全一致的
  GATT 形状（无 AA4）。
- `compatibility.yaml` —— 把 `zmk_ble_profile_index`（`zmk/ble.h`）纳入
  `required_symbols`；这是把连接对端地址映射到绑定 slot 的 ZMK API。`module_version`
  由 `1.1.4` 升为 `1.2.0`。

### 修复

- `scripts/check_zmk_compat.py` —— `symbol_present` 文档字符串改为 raw 字符串，消除
  Python 3.12+ 下 `SyntaxWarning: invalid escape sequence '\s'`（否则会混入重新生成的
  banner 快照）。

### 向后兼容

- **老主机 + 新固件**：发现不到 AA4 的主机行为不变；AA1/AA2/AA3 与 v1.1.x 逐字节一致。
- **新主机 + 老固件**：支持 1.2 的主机若未发现 AA4，降级到链路级状态，且不得臆造 slot
  （主机侧义务）。
- 既有 `keybeacon_svc` 属性索引不变：AA4 追加在末尾且无 CCC，故 AA1 的 notify 目标与
  AA2/AA3 的 notify 索引逐字节保持。

### 设计与来源

- 为 `keybeacon` 仓库 **specs/005-host-link-profile-awareness** 的固件生产者部分（wire
  契约真相源与 macOS/Windows 消费者在兄弟仓库 `keybeacon`）。实现其固件义务
  FR-001–FR-005、FR-011–FR-016。
- `scripts/tests/` 24 条 pytest 全绿；`validate_compat.py` 与 `regen_ci.py --check` 通过。

## [1.1.4] — 2026-10-13

**PATCH** release — ZMK API forward-compat + build-time revision compatibility contract.
No wire-protocol change (every byte of KBP 1.1 is bit-for-bit identical with v1.1.3).

### Fixed

- `keybeacon.c:243` now compiles against **both** older ZMK revisions and ZMK commit
  [`6e7e0de2`][zmk-6e7e0de2] (2026-02-12, `feat(endpoints): add "no endpoint" value (#3140)`)
  which renamed `zmk_endpoints_selected()` → `zmk_endpoint_get_selected()`. A
  CMake-emitted macro (`ZMK_KEYBEACON_HAS_LEGACY_ENDPOINT`) selects the branch
  at configure time; both branches return the same `struct zmk_endpoint_instance`
  (stable since ZMK commit `860e53b3`, 2024-03-27), so downstream logic is
  untouched.

[zmk-6e7e0de2]: https://github.com/zmkfirmware/zmk/commit/6e7e0de2

### Added

- `compatibility.yaml` — single source of truth declaring the module's current
  ZMK revision window and the four public ZMK symbols it depends on.
- `cmake/zmk_compat.cmake` + `scripts/check_zmk_compat.py` — CMake configure-time
  symbol probe. Mismatch produces a human-readable banner naming the missing
  symbol and three concrete fixes; the C compile is never reached.
- `scripts/validate_compat.py` — three-layer validator (YAML syntax, JSON Schema,
  six semantic rules) for the manifest itself.
- `scripts/regen_ci.py` + `.github/workflows/zmk-main-compat.yml` — daily ZMK
  symbol-probe matrix: for `main` + two frozen pins (`4dd95d7` + `e844eca2`),
  check that every `required_symbols` entry (name **or** fallback) still
  resolves to a header file in the ZMK clone. On cron failure the workflow
  auto-opens a GitHub issue (dedup via label `compat-break`) so maintainers
  see upstream API drift within 24 h instead of waiting for a user bug
  report. The matrix is intentionally **board / shield agnostic** — this
  module's compat guarantee is a symbol-layer contract, not an end-to-end
  firmware build (which belongs to the consuming `zmk-config` repo).
- `scripts/update-readme-table.py` — regenerates the README Compatibility table
  from each released tag's `compatibility.yaml`.
- `CONFIG_ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK` (default `n`) — Kconfig escape
  hatch that downgrades the fail-fast banner to a warning. Enable only as an
  emergency bypass; runtime behaviour is undefined when active.

### Deprecated (consumer-visible)

- Any `CONFIG_ZMK_KEYBEACON_CHAR_*=n` entry a consumer added to a `.conf` as a
  workaround for the v1.1.3 compile failure can now be **removed**. Keeping it
  silently masks the Connectivity / Battery characteristics. See the migration
  guide in the main `keybeacon` repo:
  [`specs/002-zmk-keybeacon-kbp11/upgrade-notes.md`][002-upgrade].

### Design & provenance

- All 23 pytest cases + `smoke-cmake.sh` 4-section smoke green.

[002-upgrade]: https://github.com/ykiewang/keybeacon/blob/main/specs/002-zmk-keybeacon-kbp11/upgrade-notes.md

### Compatibility-troubleshooting

If `west build` prints the "`is INCOMPATIBLE with the current ZMK revision`"
banner, the banner itself lists three concrete fixes. The recommended fix is
to pin ZMK to one of the two frozen revisions in the CI matrix:
`revision: 4dd95d7` (renamed-era) or `revision: e844eca2` (legacy-era).

## [1.1.3] — 2026-10-10

**PATCH** release — bug fix with no wire-contract change. All KBP 1.1 bytes, UUIDs, Kconfig
symbols, and the AA1 KBP 1.0 characteristic remain byte-for-byte identical to v1.1.0–v1.1.2.

### Fixed

- **`right_online` now tracks the actual BLE split link instead of a battery-event TTL.**
  The root cause of the "right half persistently shows offline while typing" bug was that
  `right_online` was derived from a freshness window on `zmk_peripheral_battery_state_changed`
  events. ZMK's `battery.c` only raises that event (and therefore the peripheral BAS notify
  proxy on the central) **when `state_of_charge` changes** — on a keyboard at a stable charge
  the event can be tens of minutes apart, so any TTL eventually expires even while the split
  link is fully healthy.

  The reliable signal is already present in ZMK: `split_central_disconnected()` in
  `app/src/split/bluetooth/central.c` raises `zmk_peripheral_battery_state_changed` with
  `state_of_charge = 0` on every disconnect; the initial BAS read/subscribe after connect
  delivers the real level (`> 0`). `peripheral_battery_slot` gains a `connected` bool that
  is set on `state_of_charge > 0` and cleared on `state_of_charge == 0`. `right_online` now
  reads `peripheral_slots[0].connected`, and the TTL constant `KBP_PERIPHERAL_FRESH_MS` and
  `kbp_peripheral_fresh()` are removed entirely.

  Edge-case accepted: a peripheral that is connected but genuinely at 0 % is
  indistinguishable from the disconnect sentinel; in practice such a peripheral disconnects
  long before its charge reaches 0 %.

  `last_seen_ms` is retained solely by the Battery characteristic (`batt_build_payload`) to
  decide whether any reading has ever been received — its meaning is unchanged for that use.

---

## [1.1.3] — 2026-10-10（中文）

**PATCH** 版本——修复一个 bug，无线上协议变动。所有 KBP 1.1 字节、UUID、Kconfig 符号以及
AA1（KBP 1.0）特征与 v1.1.0–v1.1.2 逐字节一致。

### 修复

- **`right_online` 现在追踪真实的 BLE 分体链路，而非电量事件的 TTL。**
  "右手持续显示离线、但实际正常使用"这一问题的根因：`right_online` 依赖
  `zmk_peripheral_battery_state_changed` 事件的新鲜度窗口。而 ZMK 的 `battery.c` 仅在
  `state_of_charge` **发生变化时**才触发该事件（从而触发 central 上的 BAS notify 代理）——
  电量稳定的键盘可以数十分钟不发送此事件，任何时间窗口都会在链路健在时过期。

  可靠的信号已存在于 ZMK 中：`central.c` 的 `split_central_disconnected()` 在每次断连时
  以 `state_of_charge = 0` 触发 `zmk_peripheral_battery_state_changed`；连接后的首次 BAS
  读/订阅会返回真实电量（`> 0`）。`peripheral_battery_slot` 新增 `connected` bool：收到
  `> 0` 置 true，收到 `0` 置 false。`right_online` 改为读取
  `peripheral_slots[0].connected`，TTL 常量 `KBP_PERIPHERAL_FRESH_MS` 与
  `kbp_peripheral_fresh()` 已彻底移除。

  已知边界情况：真实在线但电量恰好为 0% 的 peripheral 与断连哨兵无法区分；实践中此类
  peripheral 在电量到零前早已断连。

  `last_seen_ms` 仅保留用于 Battery 特征（`batt_build_payload`）判断是否曾收到过任何读数，
  其语义不变。

---



**PATCH** release — bug fix with no wire-contract change. All KBP 1.1 bytes, UUIDs, Kconfig
symbols, and the AA1 KBP 1.0 characteristic remain byte-for-byte identical to v1.1.0 / v1.1.1.

### Fixed

- **AA3 `right_percent` no longer flaps between the last-known value and `255`.** Even with
  the v1.1.1 TTL extension to 75 s, independent 1 Hz work queues for AA2 and AA3 could cross
  the freshness boundary at slightly different wall-clock moments, producing a visible skew
  where the floating panel showed `●R72` → `●R—` → `●R72` while the online dot stayed green.
  The underlying design mistake was coupling the battery byte to the TTL at all: the TTL is a
  liveness proxy and belongs on `AA2.split_flags.right_online`, not on the electrochemical
  state-of-charge value. The battery byte should hold the last-known reading until either (a)
  the module boots without ever receiving an event, or (b) the peripheral explicitly reports
  an unavailable sample. v1.1.2 removes the TTL coupling in `batt_build_payload`, so the byte
  tracks `peripheral_slots[0].last_percent` whenever `last_seen_ms > 0`.
- A follow-up to `contracts/battery-characteristic.md §6` ("Peripheral sync-bus temporarily
  lost: `right_percent` stays at last-known value for up to 10 s, then transitions to `255`")
  is pending in the main `keybeacon` repository to reflect the corrected semantics.

## [1.1.1] — 2026-10-09

**PATCH** release — bug fix with no wire-contract change. All KBP 1.1 bytes, UUIDs, Kconfig
symbols, and the AA1 KBP 1.0 characteristic remain byte-for-byte identical to v1.1.0.

### Fixed

- **Peripheral freshness window** (`KBP_PERIPHERAL_FRESH_MS`) raised from 10 s to **75 s**. The
  10 s value in v1.1.0 was derived from `research.md §R1` under the (incorrect) assumption
  that the peripheral emits events on split-sync state changes. In practice the
  `zmk_peripheral_battery_state_changed` proxy event is triggered by the standard periodic BAS
  notify, whose default cadence is `CONFIG_ZMK_BATTERY_REPORT_INTERVAL=60 s`. With a 10 s TTL
  the central would therefore mark the peripheral offline ~50 s out of every 60 s window even
  on a fully healthy split keyboard; AA2.split_flags.right_online would flip to `0` and
  AA3.right_percent would fall back to the unavailable sentinel (`255`). 75 s gives a 1.25×
  margin on the default report interval, tolerating a single missed notify without flipping
  the online bit. Keyboard authors who shorten `BATTERY_REPORT_INTERVAL` keep working
  unchanged; those who lengthen it should bump this proportionally in a fork.

### Documentation note

`specs/002-zmk-keybeacon-kbp11/research.md §R1` and `contracts/connectivity-characteristic.md`
in the main `keybeacon` repository will be updated in a follow-up to describe the correct
notify-based event model.

## [1.1.0] — 2026-10-09

Additive **MINOR** release implementing KBP 1.1 Connectivity + Power. Service UUID unchanged;
the KBP 1.0 characteristic `AA440AA1-…` is **byte-for-byte identical** to v1.0.0 (same
declaration, same CCC, same emission cadence). KBP 1.0 hosts continue to work unchanged.

### Added

- **AA2 Connectivity characteristic** `AA440AA2-F5ED-4C48-84A1-8062D20D3D55` (optional,
  READ|NOTIFY + CCC, 7-byte payload per `protocol/README.md §14.3.1`): capability_bits,
  host_state, profile_byte, profile_max_slots, split_link_flags, output_endpoint,
  charging_flags.
- **AA3 Battery characteristic** `AA440AA3-F5ED-4C48-84A1-8062D20D3D55` (optional,
  READ|NOTIFY + CCC, 1-byte on integer boards / 2-byte on splits per `protocol/README.md
  §14.4.1`): `[overall]` or `[left, right]` with `255` as "temporarily unavailable" sentinel.
- Two new Kconfig sub-options under `CONFIG_ZMK_KEYBEACON` (both `default y` so a consumer
  simply bumps `revision: v1.0.0 → v1.1.0` to pick up the new characteristics with zero
  `.conf` edits):
  - `CONFIG_ZMK_KEYBEACON_CONNECTIVITY` — gates AA2.
  - `CONFIG_ZMK_KEYBEACON_BATTERY` — gates AA3.
- ZMK event subscriptions: `zmk_ble_active_profile_changed`, `zmk_endpoint_changed`,
  `zmk_battery_state_changed`, `zmk_peripheral_battery_state_changed` (last one is gated on
  `CONFIG_ZMK_SPLIT_BLE`).
- 1 Hz `k_work_delayable` worker to satisfy the §14.4.5 OR-relation `≥ 1 s` floor for the
  Battery characteristic's throttling policy.
- `BUILD_ASSERT`s guarding the Connectivity payload length (7 bytes) and the Battery payload
  length (1 or 2 bytes depending on `IS_ENABLED(CONFIG_ZMK_SPLIT)`).
- `has_left_charging` and `has_right_charging` capability bits — both wired to `0` in this
  release. A follow-up (`v1.2.x` or board-overlay-driven) can read a per-board charger GPIO.

### Backward compatibility

- Service UUID `AA440AA0-F5ED-4C48-84A1-8062D20D3D55` unchanged.
- Characteristic `AA440AA1-F5ED-4C48-84A1-8062D20D3D55` unchanged (same `BT_GATT_CHARACTERISTIC`
  + `BT_GATT_CCC` block, same `bt_gatt_notify(…, &keybeacon_svc.attrs[1], …)` call site, same
  change-detect suppression).
- The combination `CONFIG_ZMK_KEYBEACON=y, CONFIG_ZMK_KEYBEACON_CONNECTIVITY=n,
  CONFIG_ZMK_KEYBEACON_BATTERY=n` on this v1.1.0 module produces GATT output that is
  **byte-indistinguishable** from a `revision: v1.0.0` build.

### Versioning rationale

Semver **MINOR**: additive new characteristics (KBP §9 "adding a new optional characteristic
or descriptor; service UUID unchanged"). Existing consumers are unaffected until they bump
`revision` in their `west.yml`.

## [1.0.0] — 2026-10-07

Initial release as a standalone Zephyr module, extracted unchanged from the Totem firmware repo's
`config/keybeacon_kit/`.

### Added

- `zephyr/module.yml` + `CMakeLists.txt` wrapper so the feature integrates through `west.yml`
  with no `include()`/`rsource` wiring in the consuming shield.
- `keybeacon.c` — custom GATT service exposing the active layer index, modifier flags, and layer
  name as a notify-on-change snapshot `[layer_index][mods][layer_name]`.
- `Kconfig.keybeacon` — `CONFIG_ZMK_KEYBEACON` (bool, `depends on ZMK_BLE`, `default n`).
- `keybeacon.cmake` — central-only guard
  (`CONFIG_ZMK_KEYBEACON AND CONFIG_ZMK_BLE AND CONFIG_ZMK_SPLIT_ROLE_CENTRAL`).

### Contract

- GATT service UUID `AA440AA0-F5ED-4C48-84A1-8062D20D3D55`, characteristic
  `AA440AA1-F5ED-4C48-84A1-8062D20D3D55`. Unchanged from the pre-module kit — no protocol bump.
