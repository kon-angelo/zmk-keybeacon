# Implementation Plan: 每连接主机上下文 — 固件生产者（Per-Link Host Context, Firmware Producer）

**Branch**: `005-host-link-profile-awareness` | **Date**: 2026-11-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-host-link-profile-awareness/spec.md`

## Summary

在 `zmk-keybeacon` 模块中新增 **AA4 只读 GATT 特征**（`AA440AA4-F5ED-4C48-84A1-8062D20D3D55`，`READ` only，无 NOTIFY/CCC），其 `payload[0].bits0–6` 返回**发起该读取的 BLE 连接**对应的 profile slot（1-based，0=未确定），`bit7` 保留为 0。固件在 GATT read 回调中通过 `bt_conn_get_dst(conn)` 取对端地址，调用 ZMK 公共 API `zmk_ble_profile_index(addr)` 解析 slot：命中则转 1-based 并 clamp 到 `ZMK_BLE_PROFILE_COUNT`，未命中则发 0 并打一条结构化诊断。新增 Kconfig 子选项 `CONFIG_ZMK_KEYBEACON_HOST_LINK`（依赖 `CONNECTIVITY`，`default y`）门控整只特征；既有 AA0/AA1/AA2/AA3 逐字节不变、service UUID 不变，属合法 **KBP MINOR**（模块 1.1.4→1.2.0）。把 `zmk_ble_profile_index` 纳入 `compatibility.yaml` 构建期符号契约（含 fixtures 与 banner 快照同步、模块版本 bump），并双语更新 `README.md` / `CHANGELOG.md`。

承载方式沿用上游 `keybeacon/specs/005` 的**方案 A**：独立只读特征。只读特征物理上不推送 NOTIFY，host 的任何读取**必然**是本连接 READ 响应，从根上杜绝「广播帧污染」，这正是相对「在 AA2 尾部加字段」方案的核心优势（FR-004）。

## Technical Context

**Language/Version**: C（C11，Zephyr/ZMK out-of-tree 模块；遵循 `keybeacon.c` 既有风格，无注释、`IS_ENABLED` 门控）

**Primary Dependencies**:
- Zephyr Bluetooth GATT（`<zephyr/bluetooth/gatt.h>`、`<zephyr/bluetooth/conn.h>`：`BT_GATT_CHARACTERISTIC`、`bt_gatt_attr_read`、`bt_conn_get_dst`）
- ZMK `zmk/ble.h`：`int zmk_ble_profile_index(const bt_addr_le_t *addr)`（命中→0-based，未命中→负值）、`ZMK_BLE_PROFILE_COUNT`
- Zephyr logging：`LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL)`（复用 ZMK 已注册的 `zmk` log module，避免引入新 module 依赖）

**Storage**: N/A（无状态；每次读取按当前绑定实时解析，幂等）

**Testing**:
- `scripts/tests/`（pytest）：构建期符号契约（`check_zmk_compat.py`）、manifest 校验（`validate_compat.py`）、fixtures（`zmk-legacy/renamed/missing/header-missing`）、banner 字节级快照
- wire 静态判定：上游 `conformance` 工具 C13/C14（上游仓库执行，本仓库使交付满足）
- 端到端：`quickstart.md` Given/When/Then（参考键盘 + 两台电脑，依赖上游 1.2 主机）

**Target Platform**: ZMK 固件（nRF52 系 split **中心/host-link** 角色；`keybeacon.cmake` 仅在 `CONFIG_ZMK_KEYBEACON && CONFIG_ZMK_BLE && CONFIG_ZMK_SPLIT_ROLE_CENTRAL` 时编译）

**Project Type**: 单一 Zephyr 固件模块（非前后端/移动端）

**Performance Goals**: 读取回调为 O(profile_count) 的地址比较（ZMK 内部循环 ≤ `ZMK_BLE_PROFILE_COUNT`，通常 5），无堆分配、无锁；对发包节奏与功耗无影响（只读、无额外 NOTIFY）

**Constraints**:
- 向后兼容：service UUID 不变；AA0/AA1/AA2/AA3 字节/属性/CCC/发包节奏逐字节不变（宪法 II / FR-011）
- AA4 **MUST NOT** 带 NOTIFY 或 CCC（FR-004）；追加在服务定义**末尾**以不扰动既有 attr 索引（AA1 的 `attrs[1]`、`KBP_ATTR_AA2/AA3`）
- 无法解析 → 发 0，不猜测（FR-003）；降级恰一条诊断、稳态不刷屏（FR-013，用 `LOG_DBG`）
- 构建期符号契约：新依赖符号纳入 `compatibility.yaml` 并被探针/CI 覆盖（宪法 VI / FR-015）

**Scale/Scope**: 新增约 1 个 UUID 宏、1 个 read 回调（~20 行）、1 条服务定义项、1 个 Kconfig 子选项；`compatibility.yaml` 增 1 个 `required_symbols` 条目并 bump 版本；4 个 fixture 各加 1 行符号声明；1 份 banner 快照重生成；`README.md`/`CHANGELOG.md` 双语增量。**既有 AA1/AA2/AA3 逻辑零改动。**

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

依据 `.specify/memory/constitution.md v1.0.0`（6 原则 + Delivery Scope & Platform + Testing & Verification Discipline + Governance）逐条评估。

| 原则 | 结论 | 证据 |
|------|------|------|
| **I. Wire-Contract Is Upstream** | ✅ PASS | AA4 的 UUID/属性/payload 真相源在上游 `keybeacon/protocol/`（KBP 1.2）与其 `specs/005/contracts/host-link-context.md`；本仓库仅**实现**，不定义。本 feature 的 `contracts/` 为面向固件的实现投影（引用不另立真相源）。 |
| **II. Backward Compatibility** | ✅ PASS | 纯加法：service UUID 不变、AA0/AA1/AA2/AA3 字节级不变、AA4 为新增可选只读特征，且由 Kconfig 子选项门控可退回 1.1 形状（FR-011/012，SC-003）。 |
| **III. Keyboard-Independent, Capability-Structural** | ✅ PASS | AA4 产生逻辑与键盘型号无关；由 Kconfig + ZMK 能力（BLE/central）门控；per-link 能力由**特征存在性**结构化暴露，无型号白名单。 |
| **IV. Observable Degradation Over Guessing** | ✅ PASS | 解析失败发 0 哨兵（FR-003），降级恰一条 `LOG_DBG` 诊断（FR-013）；只读无状态推送，不产生多余 NOTIFY。 |
| **V. Spec-First Development** | ✅ PASS | 本 feature 正走 specify→plan→tasks→analyze→implement；代码改动均挂在本 spec/plan 之下。 |
| **VI. Build-Time Compatibility Contract** | ✅ PASS | `zmk_ble_profile_index` 纳入 `required_symbols`（header `zmk/ble.h`、used_in `keybeacon.c`），CMake 探针 + 每日 CI 覆盖；README COMPAT/CI yaml 为派生物不手改（仅经 `module_version` bump 影响）。 |
| **Delivery Scope & Platform** | ✅ PASS | 仅 split 中心（host-link）角色编译/暴露（`keybeacon.cmake` 既有门控）；参考键盘 + 两台电脑端到端（quickstart）；conformance 仅在 wire 判定。 |
| **Testing & Verification Discipline** | ✅ PASS | `scripts/` 行为变更同步更新 `scripts/tests/`、fixtures 与 banner 快照；向后兼容/降级路径有脚本化验证（符号探针、fixtures、quickstart 负测）。 |
| **Governance** | ✅ PASS | 本 plan 即 Constitution Check；触达 `keybeacon.c`/`Kconfig.keybeacon`/`compatibility.yaml`/`specs/*/contracts/**` 的提交附本 Check；`/speckit-analyze` 要求 CRITICAL=0、HIGH=0。 |

**Verdict**: 6 原则 + 3 过程 gate 全部 PASS，无 Complexity Tracking 需求。

## Project Structure

### Documentation (this feature)

```text
specs/005-host-link-profile-awareness/
├── spec.md              # /speckit-specify 输出
├── plan.md              # 本文件
├── research.md          # Phase 0：技术决策（方案 A、符号契约、诊断、版本）
├── data-model.md        # Phase 1：AA4 payload、读取解析、服务定义位序、Kconfig
├── quickstart.md        # Phase 1：构建/验证 + Given/When/Then + 负测矩阵
├── contracts/
│   └── aa4-host-link.md # AA4 wire 增量契约（引用上游真相源，固件投影）
├── checklists/
│   └── requirements.md  # spec 质量清单（已由 specify 生成）
└── tasks.md             # Phase 2 输出（/speckit-tasks，本命令不创建）
```

### Source Code (repository root)

```text
keybeacon.c              # [MODIFIED] 新增 AA4 UUID 宏、link_slot_read 回调、服务定义末尾追加 AA4、include conn.h + logging、扩展 zmk/ble.h include 守卫
Kconfig.keybeacon        # [MODIFIED] 新增 CONFIG_ZMK_KEYBEACON_HOST_LINK（depends on ZMK_KEYBEACON_CONNECTIVITY，default y）
compatibility.yaml       # [MODIFIED] module_version 1.1.4→1.2.0；required_symbols 增 zmk_ble_profile_index
cmake/zmk_compat.cmake   # [UNCHANGED] 既有探针逻辑自动覆盖新符号
scripts/
├── check_zmk_compat.py  # [UNCHANGED] 逐 required_symbols 探测（新符号自动纳入）
├── validate_compat.py   # [UNCHANGED] manifest 语义校验（新符号须 used_in 命中 keybeacon.c）
└── tests/
    ├── fixtures/
    │   ├── zmk-legacy/app/include/zmk/ble.h          # [MODIFIED] 增 zmk_ble_profile_index 声明（使探针通过）
    │   ├── zmk-renamed/app/include/zmk/ble.h         # [MODIFIED] 同上
    │   ├── zmk-missing/app/include/zmk/ble.h         # [MODIFIED] 同上（missing 仅指 endpoints.h）
    │   ├── zmk-header-missing/app/include/zmk/ble.h  # [MODIFIED] 同上
    │   └── expected_banner_v1.2.0.txt               # [NEW] 重生成的 banner 快照（版本串变化）
    └── test_check_zmk_compat.py                      # [MODIFIED] EXPECTED_BANNER 指向 v1.2.0 快照
CHANGELOG.md             # [MODIFIED] 增 [1.2.0] 条目（What's new：AA4 + Kconfig，既有字节不变）
README.md                # [MODIFIED] 双语：实现版本/能力段新增 AA4、Kconfig 表、"What's new in 1.2"
Kconfig.keybeacon        # (见上)

# 上游（不在本仓库改动）：keybeacon/protocol/（KBP 1.2 真相源）、keybeacon/conformance/（C13/C14）、keybeacon app（五态消费者）
```

**Structure Decision**: 单一 Zephyr 固件模块，无需多项目布局。核心改动集中在 `keybeacon.c` + `Kconfig.keybeacon`；其余为构建期兼容契约（`compatibility.yaml` + fixtures + banner 快照 + 对应 pytest）与双语模块文档。严格遵循宪法 I（协议真相源在上游、本仓库只实现）与 II（纯加法、可门控退回 1.1）。AA4 追加在 `BT_GATT_SERVICE_DEFINE` **末尾**，确保既有 `keybeacon_svc.attrs[1]`（AA1 notify）与 `KBP_ATTR_AA2/AA3`（AA2/AA3 notify 目标）索引不变——这是「既有逻辑零改动」的结构保证。

## Complexity Tracking

> Constitution Check 无 gate 违规，本节为空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| —         | —          | —                                    |
