---

description: "Task list for 005-host-link-profile-awareness (firmware producer)"
---

# Tasks: 每连接主机上下文 — 固件生产者（Per-Link Host Context, Firmware Producer）

**Input**: Design documents from `specs/005-host-link-profile-awareness/`

**Prerequisites**: plan.md ✅、spec.md ✅、research.md ✅、data-model.md ✅、contracts/aa4-host-link.md ✅、quickstart.md ✅

**Tests**: 本仓库无 C 单测 harness；可执行测试 = `scripts/tests/`（pytest，覆盖构建期符号契约/fixtures/banner）+ 上游 `conformance` 的 C13/C14 静态判定（上游仓库执行）。故“测试任务”体现为 fixtures/banner 同步与 pytest 全绿（宪法 Testing Discipline、SC-005），不新建 C 测试框架。

**Organization**: 按用户故事 US1/US2/US3 分组。承载方式 = 方案 A（新增独立只读特征 `AA440AA4-…`）。

> **跨仓库说明**：wire 契约真相源与主机消费者/`conformance` 向量在上游 `keybeacon` 仓库，不在本 tasks。本仓库交付：AA4 只读特征（keybeacon.c）+ Kconfig 门控 + compatibility.yaml 符号契约/版本 + fixtures/banner + 双语模块文档。端到端真机（quickstart C 层）依赖上游 1.2 主机，列为外部依赖。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: US1 / US2 / US3（Setup/Foundational/Polish 无标签）

## Path Conventions

- 固件：`keybeacon.c`、`Kconfig.keybeacon`（仓库根）
- 构建期契约：`compatibility.yaml`、`scripts/tests/fixtures/zmk-*/app/include/zmk/ble.h`、`scripts/tests/fixtures/expected_banner_*.txt`、`scripts/tests/test_check_zmk_compat.py`
- 文档：`CHANGELOG.md`、`README.md`

---

## Phase 1: Setup（基线）

**Purpose**: 建立回归基线

- [X] T001 建立回归基线：运行 `python3 -m pytest scripts/tests/ -q` 并确认全绿，作为 SC-003/SC-005 的向后兼容对照基线（记录当前 banner fixture 为 `expected_banner_v1.1.4.txt`）

---

## Phase 2: Foundational（阻塞前置 —— 门控、符号契约、脚手架）

**Purpose**: 门控开关、构建期符号契约与 keybeacon.c 脚手架是所有 US 的前置

**⚠️ CRITICAL**: 本阶段完成前，US1/US2/US3 的特征逻辑不得开始

- [X] T002 在 `Kconfig.keybeacon` 新增 `config ZMK_KEYBEACON_HOST_LINK`：`bool "KeyBeacon 1.2: expose per-connection Host-Link characteristic (AA440AA4-…)"`、`depends on ZMK_KEYBEACON_CONNECTIVITY`、`default y`、help 文案（READ-only、per-connection、0=未确定、无 NOTIFY/CCC），紧随既有 `ZMK_KEYBEACON_BATTERY` 之后（依 data-model §4）
- [X] T003 在 `keybeacon.c` 加脚手架：include `<zephyr/bluetooth/conn.h>` 与 `<zephyr/logging/log.h>`；加 `LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);`；把 `zmk/ble.h` 的 include 守卫扩展为 `CONNECTIVITY || BATTERY || HOST_LINK`；在 AA3 UUID 宏后新增 `#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_HOST_LINK)` 门控的 `KEYBEACON_LINK_UUID`（`0xAA440AA4,0xF5ED,0x4C48,0x84A1,0x8062D20D3D55`）；文件头注释补 KBP 1.2 一行（依 data-model §0、research D4/D5）
- [X] T004 在 `compatibility.yaml`：`required_symbols` 增条目 `{name: zmk_ble_profile_index, header: zmk/ble.h, used_in: keybeacon.c}`（无 fallback/emits_macro，附注释指向 keybeacon.c 的 link_slot_read）；`module_version: 1.1.4 → 1.2.0`（依 data-model §5、research D7/D8）
- [X] T005 [P] 在 4 个 fixture 的 `app/include/zmk/ble.h` 各加一行 `int zmk_ble_profile_index(const bt_addr_le_t *addr);`：`scripts/tests/fixtures/zmk-legacy`、`zmk-renamed`、`zmk-missing`、`zmk-header-missing`（使真实 manifest 的新符号在探针下成立；missing/header-missing 仍仅缺 endpoints，依 data-model §5.1）

**Checkpoint**: 门控、符号契约、UUID/日志脚手架就绪；US 逻辑可开工

---

## Phase 3: User Story 1 - 每台主机读到属于自己的 slot（Priority: P1）🎯 MVP

**Goal**: AA4 只读特征存在，GATT read 回调按发起连接的对端地址返回其 1-based slot，使每台主机零配置读到自己的 slot。

**Independent Test**: 绑两台电脑的参考键盘，两端分别读 AA4 得各自 slot（1 与 2），与活跃 profile 无关（quickstart S1/S2/S3）。

### Implementation for User Story 1

- [X] T006 [US1] 在 `keybeacon.c` 新增 `link_slot_read(conn, attr, buf, len, offset)` 读回调（`#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_HOST_LINK)` 块，置于 AA3 batt 段之后、`BT_GATT_SERVICE_DEFINE` 之前）：`bt_conn_get_dst(conn)` 取对端 → `zmk_ble_profile_index(peer)`；`idx>=0` 且 `1<=idx+1<=ZMK_BLE_PROFILE_COUNT` 时 `slot=(idx+1)&0x7F`，否则 `slot=0`；`return bt_gatt_attr_read(conn, attr, buf, len, offset, &slot, 1)`（依 data-model §2，P-L2/P-L3/P-L4；诊断在 US2 加）
- [X] T007 [US1] 在 `BT_GATT_SERVICE_DEFINE(keybeacon_svc, …)` **末尾**（AA3 块之后）追加 `#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_HOST_LINK)` 的 `BT_GATT_CHARACTERISTIC(KEYBEACON_LINK_UUID, BT_GATT_CHRC_READ, BT_GATT_PERM_READ, link_slot_read, NULL, NULL)`，其后**不加** `BT_GATT_CCC`（P-L1；保持既有 attr 索引不变，依 data-model §3）
- [X] T008 [US1] 复核既有 notify 寻址不受影响：`keybeacon_svc.attrs[1]`（AA1）、`KBP_ATTR_AA2`/`KBP_ATTR_AA3` 索引与 `keybeacon_init` 均无需改动且未改动（SC-003 的结构保证；git diff 确认 AA1/AA2/AA3 段零改动）

**Checkpoint**: US1 可独立验收 —— 两机各读到自身 slot（SC-001）

---

## Phase 4: User Story 2 - 无法解析时诚实发哨兵值（Priority: P2）

**Goal**: 对端无法解析到绑定 slot 时返回 0、绝不猜测，并在降级路径打印恰一条结构化诊断。

**Independent Test**: 构造不可解析连接（无绑定/open/地址不匹配），AA4 读回 0；开启 DBG 日志见恰一条 `hostlink.unresolved`（quickstart S4 + 负测矩阵）。

### Implementation for User Story 2

- [X] T009 [US2] 在 `keybeacon.c` 的 `link_slot_read` 中，`slot == 0` 分支加恰一条 `LOG_DBG("hostlink.unresolved: conn peer not bonded to any profile slot");`（FR-013，DBG 级稳态不刷屏；依 research D4）
- [X] T010 [US2] 确认哨兵/边界不变量在代码中显式成立：默认 `slot=0`、`idx<0`→0、越界（`>ZMK_BLE_PROFILE_COUNT`）→0、`bit7` 恒 0（`&0x7F`）；在回调上方加简短注释标注 P-L2/P-L3/P-L4 对应关系（FR-002/003/005）

**Checkpoint**: US2 可独立验收 —— 不可解析恒 0、无假阳、恰一条诊断（SC-002）

---

## Phase 5: User Story 3 - 纯加法、向后兼容、可门控（Priority: P3）

**Goal**: HOST_LINK=n 时 GATT 退回 1.1 形状；既有特征字节级不变；依赖 CONNECTIVITY 排除异常组合。

**Independent Test**: (a) `CONFIG_ZMK_KEYBEACON_HOST_LINK=n` 构建→无 AA4、AA1/AA2/AA3 与 1.1 一致；(b) `=y` 构建→仅新增 AA4（quickstart S5）。

### Implementation for User Story 3

- [X] T011 [US3] 复核门控与依赖：`Kconfig.keybeacon` 中 `ZMK_KEYBEACON_HOST_LINK` `depends on ZMK_KEYBEACON_CONNECTIVITY`（排除「有 AA4 无 AA2」）；`keybeacon.c` 所有 AA4 相关代码（UUID 宏、回调、服务项）均在 `CONFIG_ZMK_KEYBEACON_HOST_LINK` 门控内，关闭即编译期消除、GATT 形状等同 1.1（FR-012/SC-003）
- [X] T012 [US3] 回归确认：对 `keybeacon.c` 做 `git diff` 核对 AA1/AA2/AA3 的声明/CCC/notify/payload 逻辑**逐字节未改**；仅新增 AA4 相关块与 include/LOG 脚手架（SC-003）

**Checkpoint**: 三个 US 均可独立验收；兼容方向（双向）成立

---

## Phase 6: Polish & Cross-Cutting（文档、版本、验证）

**Purpose**: 双语文档、版本与端到端验证

- [X] T013 重生成 banner 快照：`python3 scripts/check_zmk_compat.py --zmk-root scripts/tests/fixtures/zmk-missing 2> scripts/tests/fixtures/expected_banner_v1.2.0.txt`；`git rm` 旧 `expected_banner_v1.1.4.txt`；更新 `scripts/tests/test_check_zmk_compat.py` 的 `EXPECTED_BANNER` 常量与 skip 提示文案指向 v1.2.0（依 data-model §5.2、research D8；依赖 T004）
- [X] T014 [P] `CHANGELOG.md` 增 `[1.2.0]` 条目（英中双语，§VI）：**MINOR** —— 新增可选只读特征 AA4（per-connection host-link），新增 `CONFIG_ZMK_KEYBEACON_HOST_LINK`（default y），既有 AA0/AA1/AA2/AA3 字节不变、service UUID 不变；compatibility.yaml 增 `zmk_ble_profile_index` 符号
- [X] T015 [P] `README.md` 英中双语：实现版本/能力段落新增 AA4（READ-only、per-connection slot）、`What's new in 1.2` 小节、Kconfig/特征表加 `CONFIG_ZMK_KEYBEACON_HOST_LINK` 与 `AA440AA4-…`（§VI；不手改自动生成的 COMPAT 区块）
- [X] T016 运行 `python3 scripts/validate_compat.py` 与 `python3 scripts/check_zmk_compat.py --zmk-root scripts/tests/fixtures/zmk-legacy`（及 zmk-renamed / zmk-missing）确认符号探针与 manifest 校验通过（SC-005；依赖 T004/T005）
- [X] T017 运行 `python3 -m pytest scripts/tests/ -q` 确认全绿（含更新后的 banner 比对与 fixtures；SC-005；依赖 T005/T013）
- [X] T018 执行 quickstart A 层（本仓库无硬件部分）；在文末标注 B 层（上游 conformance C13/C14）与 C 层（真机 S1–S5 + 负测矩阵）依赖上游 1.2 主机与参考键盘，列为外部验收（SC-001/002/004）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**：无依赖，立即开始
- **Foundational (P2)**：依赖 Setup；**阻塞所有 US**（门控/符号契约/脚手架）
- **US1 (P3)**：依赖 Foundational；MVP
- **US2 (P4)**：依赖 US1（同一 `link_slot_read` 函数，加诊断与哨兵注释）
- **US3 (P5)**：依赖 Foundational + US1（门控/回归基于已存在的 AA4 块）
- **Polish (P6)**：依赖所需 US 完成；T018 的 B/C 层额外依赖上游仓库与硬件

### Within Each User Story

- `keybeacon.c` 的 AA4 回调（T006）先于服务定义追加（T007）先于索引复核（T008）
- US2 的诊断/哨兵（T009/T010）在 US1 的回调骨架之后（同文件，顺序执行）
- 文档（T014/T015）可与代码并行；banner 重生成（T013）依赖版本 bump（T004）

### Parallel Opportunities

- Foundational：T005（fixtures，多文件）可与 T002/T003/T004 并行启动（不同文件）
- Polish：T014（CHANGELOG）∥ T015（README）
- 其余因集中在 `keybeacon.c` 单文件，多为顺序执行

---

## Implementation Strategy

### MVP First（US1）

1. Phase 1 Setup → 2. Phase 2 Foundational（门控+符号契约+脚手架，CRITICAL）→ 3. Phase 3 US1 → **STOP & VALIDATE**：两机各读自身 slot（SC-001）→ 可演示 MVP。

### Incremental Delivery

Setup+Foundational → US1（MVP，per-connection 读）→ US2（哨兵+诊断）→ US3（门控+兼容回归）→ Polish（文档+版本+验证）。每步不破坏前序（既有 AA1/AA2/AA3 零改动）。

---

## Notes

- [P] = 不同文件、无未完成依赖
- 主机消费者、`keybeacon/protocol/` 与 `conformance/` 向量在上游仓库，不在本 tasks；T018 的真机端到端依赖其 1.2 主机
- 「既有 AA1/AA2/AA3 逻辑零改动」是方案 A 的硬约束，T008/T012 专门回归确认
- 每个任务或逻辑组完成后提交
