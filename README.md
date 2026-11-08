<!--
Copyright (c) 2026 The TOTEM ZMK Contributors
SPDX-License-Identifier: MIT
-->

# zmk-keybeacon — KeyBeacon Zephyr module

[![ZMK compat matrix](https://github.com/ykiewang/zmk-keybeacon/actions/workflows/zmk-main-compat.yml/badge.svg)](https://github.com/ykiewang/zmk-keybeacon/actions/workflows/zmk-main-compat.yml)

**English** · [中文](#zh-kit)

KeyBeacon exposes a ZMK keyboard's **active layer + modifier state** over a custom BLE GATT
service, so a host app (e.g. the macOS KeyBeacon widget) can display it live. It ships as a
**Zephyr module**: a consuming keyboard adds one entry to its `west.yml` and sets one Kconfig
symbol — **no files are copied and no shield wiring is edited**. The shared logic in
`keybeacon.c` is never modified to add the feature.

> **New here?** The step-by-step onboarding guide (both "no `west.yml` yet" and "existing
> `west.yml`" scenarios, build/flash, verify, upgrade) lives in
> [`GETTING-STARTED.md`](./GETTING-STARTED.md).

## Part of the KeyBeacon project

This repo is the **firmware (producer) side** of KeyBeacon — it only reports a ZMK keyboard's state
over BLE. The wire protocol, the desktop app that displays that state, and the conformance kit all
live in the main project repository:

| Resource | What |
|----------|------|
| [**KeyBeacon**](https://github.com/ykiewang/keybeacon) | Project home — the macOS app (menu-bar widget + floating panel) and overview |
| [KeyBeacon Protocol (KBP)](https://github.com/ykiewang/keybeacon/tree/main/protocol) | The versioned wire standard this module implements |
| [Conformance kit](https://github.com/ykiewang/keybeacon/tree/main/conformance) | Guide, checklist, and self-test tool for keyboard authors |
| [Roadmap](https://github.com/ykiewang/keybeacon#roadmap) | Candidate metrics planned for future KBP versions (battery, connection, WPM, …) |

This module implements **KBP 1.2** (service `AA440AA0-…`, layer + modifiers, the optional
Connectivity and Battery characteristics from 1.1, plus the optional per-connection Host-Link
characteristic added in 1.2).

## What's new in 1.2

This release adds **one** optional, **read-only** GATT characteristic on the existing service
`AA440AA0-…` (service UUID unchanged — a MINOR per KBP §9). Every byte of AA1/AA2/AA3 is
identical to v1.1.x.

- **Host-Link** (`AA440AA4-F5ED-4C48-84A1-8062D20D3D55`, 1 byte, **READ only — no NOTIFY/CCC**) —
  `[0]` bits0–6 carry `local_link_profile`, the profile slot of **this** BLE connection (1-based;
  `0` = not determined; bit7 reserved). A GATT read callback carries the originating connection,
  so the firmware answers **each** host with its own slot — letting a host tell "in use on this
  computer" from "active on another computer" with zero configuration. When the peer cannot be
  resolved to a bonded profile, the firmware emits `0` (never a guess). Gated by
  `CONFIG_ZMK_KEYBEACON_HOST_LINK=y` (default `y`, requires `CONFIG_ZMK_KEYBEACON_CONNECTIVITY`).

To keep the exact KBP 1.1 wire shape (no AA4), set `CONFIG_ZMK_KEYBEACON_HOST_LINK=n`. The
firmware-producer design lives in the sibling `keybeacon` repo under
`specs/005-host-link-profile-awareness` (wire contract + macOS/Windows consumers there).

## What's new in 1.1

This release adds two optional GATT characteristics on the existing service `AA440AA0-…`
(service UUID unchanged — this is a MINOR per KBP §9):

- **Connectivity** (`AA440AA2-F5ED-4C48-84A1-8062D20D3D55`, 7 bytes) — host-connection state,
  active profile, split-link, output endpoint, and charging flags. Gated by
  `CONFIG_ZMK_KEYBEACON_CONNECTIVITY=y` (default `y`).
- **Battery** (`AA440AA3-F5ED-4C48-84A1-8062D20D3D55`, 1 byte on integer boards / 2 bytes on
  splits) — left/right percent with `255` sentinel for "temporarily unavailable". Gated by
  `CONFIG_ZMK_KEYBEACON_BATTERY=y` (default `y`).

Backward compatibility is strict: the KBP 1.0 characteristic `AA440AA1-…` is **byte-for-byte
identical** to v1.0.0 (same declaration, same CCC, same emission cadence); existing KBP 1.0
hosts see no behavioural change. A consumer that wants to keep 1.0-equivalent wire output on
a v1.1.0 module can add `CONFIG_ZMK_KEYBEACON_CONNECTIVITY=n` and `CONFIG_ZMK_KEYBEACON_BATTERY=n`
to its central `.conf`.

## What's in the module

| File | Role | Edit to integrate? |
|------|------|--------------------|
| `zephyr/module.yml` | Declares the cmake + Kconfig entry points to Zephyr | **No** |
| `CMakeLists.txt` | Module cmake entry; `include()`s `keybeacon.cmake` | No |
| `keybeacon.c` | Shared GATT logic (service, read, change-detect, notify) | **No** |
| `keybeacon.cmake` | Guarded `zephyr_library` snippet (symbol + BLE + central) | No |
| `Kconfig.keybeacon` | Declares `CONFIG_ZMK_KEYBEACON` plus sub-options `CONFIG_ZMK_KEYBEACON_CONNECTIVITY` / `CONFIG_ZMK_KEYBEACON_BATTERY` / `CONFIG_ZMK_KEYBEACON_HOST_LINK` (all bool; sub-options `default y`) | No |
| `CHANGELOG.md` | Semver history + versioning policy | No |

## Compatibility

Each tagged release of `zmk-keybeacon` is verified against a specific window of ZMK revisions.
The table below is **auto-generated** from each release's `compatibility.yaml` by
`scripts/update-readme-table.py` — do not hand-edit between the markers.

If your consumer firmware's `west.yml` pins ZMK to a revision outside the "known-good" window
of your pinned `zmk-keybeacon` tag, CMake configure stops with a diagnostic banner that
tells you exactly which symbol is missing and which three fixes are available. See the
[`compatibility-troubleshooting`](./CHANGELOG.md#compatibility-troubleshooting) note
in the CHANGELOG.

<!-- COMPAT:BEGIN -->

| zmk-keybeacon tag | Known-good ZMK revision range |
|---|---|
| `v1.0.0` | _(no manifest; pre-v1.1.4)_ |
| `v1.1.0` | _(no manifest; pre-v1.1.4)_ |
| `v1.1.1` | _(no manifest; pre-v1.1.4)_ |
| `v1.1.2` | _(no manifest; pre-v1.1.4)_ |
| `v1.1.3` | _(no manifest; pre-v1.1.4)_ |
| `v1.1.4` | ZMK `e844eca2` .. `4dd95d7` (branch `main`) |

_This table is generated by `scripts/update-readme-table.py` from each tag's `compatibility.yaml`. Do not hand-edit between the markers._

<!-- COMPAT:END -->

## Prerequisites

- **Central BLE role**: the feature compiles **only** for the keyboard's central role. A split
  keyboard's central half qualifies; a peripheral-only or non-BLE keyboard does **not**.
- `CONFIG_ZMK_BLE` must be available (it is a `depends on` of the symbol).

## Quick integration

1. Add the module to your `config/west.yml` (see [`GETTING-STARTED.md`](./GETTING-STARTED.md) for
   the full manifest and the existing-manifest variant):

   ```yaml
   - name: zmk-keybeacon
     remote: ykiewang
     revision: v1.1.2        # pin a tag, never track main
   ```

2. Enable it in the **central** target's `.conf`:

   ```conf
   CONFIG_ZMK_KEYBEACON=y
   ```

   Both 1.1 characteristics (Connectivity and Battery) auto-enable because their sub-options
   `default y`. To keep 1.0-equivalent output on this 1.1.0 module, add
   `CONFIG_ZMK_KEYBEACON_CONNECTIVITY=n` and `CONFIG_ZMK_KEYBEACON_BATTERY=n`.

3. `west update && west build` — done. The module auto-injects its cmake and Kconfig; you add
   **no** `include(...)` and **no** `rsource ...` to your shield.

## Verify

- The central image links `keybeacon.c`; the peripheral and `settings_reset` images do **not**
  (the `.cmake` guard enforces central-only).
- Run the host probe (`tools/probe.py`) or the app: the keyboard is discovered by the custom
  service UUID `AA440AA0-…`, and the status stream decodes.

## Versioning

Semver tags; consumers pin a tag via `revision`. See [`CHANGELOG.md`](./CHANGELOG.md) for the
MAJOR/MINOR/PATCH policy. Publishing a new version never affects an existing build until that
consumer bumps its `revision`.

## Reference consumer

The Corne config (`github.com/ykiewang/zmk-config-corne`) consumes this module via its `west.yml`
as the reference integration — see its `GETTING-STARTED.md` entries for the exact lines.

---

<a id="zh-kit"></a>

# zmk-keybeacon — KeyBeacon Zephyr 模块（中文版）

**English** · [中文](#zh-kit)

KeyBeacon 通过自定义 BLE GATT 服务暴露 ZMK 键盘的**当前层 + 修饰键状态**，使桌面应用（如 macOS
KeyBeacon widget）能实时显示。它以 **Zephyr 模块**形式分发：消费方键盘只需在 `west.yml` 中添加
一个条目并设置一个 Kconfig 符号——**无需复制文件，也无需改动 shield 接线**。接入时**不修改**
`keybeacon.c` 中的共享逻辑。

> **初次接入？** 分步入门指南（含"还没有 `west.yml`"与"已有 `west.yml`"两种场景、构建/烧录、
> 验证、升级）见 [`GETTING-STARTED.md`](./GETTING-STARTED.md)。

## KeyBeacon 项目的一部分

本仓库是 KeyBeacon 的**固件(生产者)端**——只负责在 ZMK 键盘上通过 BLE 上报状态。线上协议、显示该
状态的桌面应用、以及一致性套件都在主项目仓库:

| 资源 | 内容 |
|------|------|
| [**KeyBeacon**](https://github.com/ykiewang/keybeacon) | 项目主页——macOS 应用(菜单栏小组件 + 悬浮面板)与总览 |
| [KeyBeacon 协议(KBP)](https://github.com/ykiewang/keybeacon/tree/main/protocol) | 本模块实现的带版本线上标准 |
| [一致性套件](https://github.com/ykiewang/keybeacon/tree/main/conformance) | 面向键盘作者的指南、清单与自测工具 |
| [路线图](https://github.com/ykiewang/keybeacon#roadmap) | 规划中、面向未来 KBP 版本的候选指标(电量、连接、WPM……) |

本模块实现 **KBP 1.2**（服务 `AA440AA0-…`，层 + 修饰键，1.1 的可选 Connectivity 与 Battery
特征，以及 1.2 新增的可选「每连接 Host-Link」特征）。

## 1.2 版本新增

本次发布在既有服务 `AA440AA0-…` 下新增**一个**可选的**只读** GATT 特征（服务 UUID 保持
不变——按 KBP §9 属于 MINOR）。AA1/AA2/AA3 每一个字节与 v1.1.x 一致。

- **Host-Link**（`AA440AA4-F5ED-4C48-84A1-8062D20D3D55`，1 字节，**只读——无 NOTIFY/CCC**）
  —— `[0]` bits0–6 携带 `local_link_profile`，即**本** BLE 连接对应的 profile slot（1-based；
  `0` = 未确定；bit7 保留）。GATT 读回调天然带发起连接，故固件对**每台**主机回答其自身 slot
  ——使主机零配置地区分「正在此电脑使用」与「在另一台电脑使用」。当对端无法解析到已绑定
  profile 时，固件发 `0`（绝不猜测）。由 `CONFIG_ZMK_KEYBEACON_HOST_LINK=y`（默认 `y`，依赖
  `CONFIG_ZMK_KEYBEACON_CONNECTIVITY`）控制。

若要保留与 KBP 1.1 完全一致的线上形状（无 AA4），设 `CONFIG_ZMK_KEYBEACON_HOST_LINK=n`。
固件生产者设计位于兄弟仓库 `keybeacon` 的 `specs/005-host-link-profile-awareness`（wire 契约
与 macOS/Windows 消费者在那里）。

## 1.1 版本新增

本次发布在既有服务 `AA440AA0-…` 下新增两个可选 GATT 特征（服务 UUID 保持不变——按 KBP §9
属于 MINOR 升级）：

- **Connectivity**（`AA440AA2-F5ED-4C48-84A1-8062D20D3D55`，7 字节）—— 主机连接状态、当前
  profile、分体连接、输出端点、充电标志。由 `CONFIG_ZMK_KEYBEACON_CONNECTIVITY=y`（默认 `y`）
  控制。
- **Battery**（`AA440AA3-F5ED-4C48-84A1-8062D20D3D55`，整数键盘 1 字节 / 分体 2 字节）
  —— 左/右电量百分比，`255` 为"暂不可用"哨兵值。由 `CONFIG_ZMK_KEYBEACON_BATTERY=y`（默认
  `y`）控制。

严格向后兼容：KBP 1.0 的特征 `AA440AA1-…` 相较 v1.0.0 **逐字节一致**（相同的声明、相同的
CCC、相同的发包节奏）；现有 KBP 1.0 主机行为不变。希望在 v1.1.0 模块上保留 1.0 等价行为的
消费方，可在 central `.conf` 中加入 `CONFIG_ZMK_KEYBEACON_CONNECTIVITY=n` 与
`CONFIG_ZMK_KEYBEACON_BATTERY=n`。

## 模块内容

| 文件 | 作用 | 接入时需要编辑？ |
|------|------|----------------|
| `zephyr/module.yml` | 向 Zephyr 声明 cmake + Kconfig 入口 | **不** |
| `CMakeLists.txt` | 模块 cmake 入口；`include()` 调用 `keybeacon.cmake` | 不 |
| `keybeacon.c` | 共享 GATT 逻辑（服务、读取、变化检测、通知） | **不** |
| `keybeacon.cmake` | 带守卫的 `zephyr_library` 片段（符号 + BLE + central） | 不 |
| `Kconfig.keybeacon` | 声明 `CONFIG_ZMK_KEYBEACON` 以及子选项 `CONFIG_ZMK_KEYBEACON_CONNECTIVITY` / `CONFIG_ZMK_KEYBEACON_BATTERY` / `CONFIG_ZMK_KEYBEACON_HOST_LINK`（都是 bool；子选项 `default y`） | 不 |
| `CHANGELOG.md` | semver 历史与版本策略 | 不 |

## 前提条件

- **Central BLE 角色**：本功能**仅**为键盘的 central 角色编译。分体键盘的 central 半符合条件；
  纯 peripheral 或无 BLE 的键盘**不**符合。
- `CONFIG_ZMK_BLE` 必须可用（它是该符号的 `depends on`）。

## 快速接入

1. 把模块加入你的 `config/west.yml`（完整 manifest 与"已有 manifest"变体见
   [`GETTING-STARTED.md`](./GETTING-STARTED.md)）：

   ```yaml
   - name: zmk-keybeacon
     remote: ykiewang
     revision: v1.1.2        # 固定 tag，切勿跟踪 main
   ```

2. 在 **central** 目标的 `.conf` 中启用：

   ```conf
   CONFIG_ZMK_KEYBEACON=y
   ```

   两个 1.1 特征（Connectivity 与 Battery）会自动启用，因为其子选项 `default y`。若想在
   v1.1.0 模块上保留 1.0 等价输出，可追加 `CONFIG_ZMK_KEYBEACON_CONNECTIVITY=n` 与
   `CONFIG_ZMK_KEYBEACON_BATTERY=n`。

3. `west update && west build` —— 完成。模块自动注入 cmake 和 Kconfig；你的 shield **无需**
   `include(...)`，**无需** `rsource ...`。

## 验证

- central 镜像链接 `keybeacon.c`；peripheral 和 `settings_reset` 镜像**没有**（`.cmake` 守卫
  强制 central-only）。
- 运行主机探针（`tools/probe.py`）或应用：键盘通过自定义服务 UUID `AA440AA0-…` 被发现，状态流
  可正常解码。

## 版本

semver tag；消费方通过 `revision` 固定 tag。MAJOR/MINOR/PATCH 策略见
[`CHANGELOG.md`](./CHANGELOG.md)。在消费方亲手升级 `revision` 之前，发布新版本绝不影响其现有构建。

## 参考消费者

Corne 配置（`github.com/ykiewang/zmk-config-corne`）通过其 `west.yml` 消费本模块，作为参考接入
——确切条目见其 `GETTING-STARTED.md`。
