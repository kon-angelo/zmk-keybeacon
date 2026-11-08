# Phase 0 Research: 每连接主机上下文 — 固件生产者

**Feature**: `specs/005-host-link-profile-awareness` | **Date**: 2026-11-08 | **Plan**: [plan.md](./plan.md)

本文件固化固件 producer 的技术决策。spec 无遗留 NEEDS CLARIFICATION；以下逐项给出 Decision / Rationale / Alternatives，并附实证引用（行号以调研当时为准）。

---

## D1. 承载方式：独立只读特征 AA4（方案 A）

- **Decision**: 新增独立特征 `AA440AA4-…`，属性**仅 `READ`**（无 `NOTIFY`、无 CCC `0x2902`），`payload[0]` 携带 `local_link_profile`。
- **Rationale**:
  - GATT read 回调天然带发起连接的 `struct bt_conn *conn`，可对每条链路返回不同值——这是 per-connection 语义的根基（FR-001/FR-004）。
  - 只读特征**物理上不推送 NOTIFY**，故 host 读到的**必然**是本连接 READ 响应，彻底消除「广播帧污染」——CoreBluetooth 等平台 READ 与 NOTIFY 共用回调，这是被否决方案的最大脆弱点（上游 research 同源结论）。
  - 纯加法：service UUID 不变、AA0/AA1/AA2/AA3 字节级不变（宪法 II / FR-011）。
- **Alternatives considered**:
  - **AA2 尾部追加字段 + 继续 NOTIFY**：广播帧跨主机相同，host 须区分「READ 帧 vs NOTIFY 帧」才能取本连接值，竞态脆弱；且改动既有特征的长度语义，兼容风险更高。否决。
  - **能力位/新 service**：能力位无法承载 per-connection 值；新 service 改变 MAJOR 信号，违背 MINOR。否决。

## D2. ZMK API：对端地址 → 绑定 slot

- **Decision**: 读取回调中 `const bt_addr_le_t *peer = bt_conn_get_dst(conn);` → `int idx = zmk_ble_profile_index(peer);`，`idx >= 0` 时 `slot = idx + 1`（1-based）。
- **Rationale / 实证**:
  - `zmk/ble.h` 声明 `int zmk_ble_profile_index(const bt_addr_le_t *addr);`（本地 ZMK 工作副本 `app/include/zmk/ble.h:31`）。
  - 实现（`zmk/app/src/ble.c:242–249`）：遍历 `profiles[i].peer` 与 `addr` 做 `bt_addr_le_cmp`，命中返回 **0-based** `i`，未命中返回 **`-ENODEV`**（负值）。故固件把 0-based 转 1-based，并以 0 作「未确定」哨兵。
  - `bt_conn_get_dst(conn)` 返回 `const bt_addr_le_t *`，与 API 入参类型精确匹配。
- **Alternatives considered**: 自行维护 conn→slot 映射表。否决——重复 ZMK 已有权威映射，且需跟踪 bond 变更，徒增状态与出错面。

## D3. 边界与越界夹取

- **Decision**: 仅当 `1 <= slot <= ZMK_BLE_PROFILE_COUNT` 时写入 `slot & 0x7F`（保证 `bit7=0`）；否则（含 `idx<0`、越界）写 0。
- **Rationale**: FR-002/FR-003/FR-005——1-based、0=未确定、不越界 `profile_max_slots`（与 AA2 `[3]` 同口径，既有 `conn_build_payload` 用同一 `ZMK_BLE_PROFILE_COUNT` clamp，见 `keybeacon.c:227–234`）。`bit7` 保留位恒 0。
- **Alternatives**: 不夹取直接回传。否决——可能越界，违反上游 C14。

## D4. 降级诊断

- **Decision**: `slot == 0`（解析失败）分支打印**一条** `LOG_DBG("hostlink.unresolved: ...")`；日志 module 用 `LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL)`。
- **Rationale**:
  - FR-013「降级恰一条结构化诊断、稳态不刷屏」。`keybeacon.c` 当前无日志；复用 ZMK 已注册的 `zmk` log module（`LOG_MODULE_DECLARE`，非 `REGISTER`）避免新增 module 依赖，`CONFIG_ZMK_LOG_LEVEL` 由 ZMK 提供（ZMK 源广泛使用，如 `zmk/app/src/ble.c:32`）。
  - 用 `LOG_DBG` 而非 `WRN`：AA4 只读可能被 host 轮询，解析失败在 RPA 隐私场景属正常，DBG 级别默认不输出、不刷屏；`CONFIG_LOG` 关闭时整体编译期消除，零开销。
- **Alternatives**: `LOG_WRN` 每次读取打印。否决——轮询下刷屏，违反「稳态不刷屏」。按 conn 去重仅发一次：过度工程，固件侧不值当。

## D5. 服务定义位序（既有逻辑零改动的结构保证）

- **Decision**: 在 `BT_GATT_SERVICE_DEFINE(keybeacon_svc, …)` **末尾**（AA3 块之后）追加 AA4 的 `BT_GATT_CHARACTERISTIC`，**不加** `BT_GATT_CCC`。
- **Rationale**: 既有 notify 目标按固定 attr 索引寻址——AA1 用 `keybeacon_svc.attrs[1]`（`keybeacon.c:407`），AA2/AA3 用 `KBP_ATTR_AA2/AA3`（`keybeacon.c:86–95`、431、481）。在末尾追加只读特征（无 CCC）**不改变**任何既有索引，且 AA4 自身无 notify 故无需新索引常量。这是「AA1/AA2/AA3 逻辑零改动」的关键。
- **Alternatives**: 插在 AA2/AA3 之间。否决——会移位既有 `KBP_ATTR_*`，需改既有 notify 代码，违反零改动目标且增兼容风险。

## D6. Kconfig 门控与依赖

- **Decision**: 新增 `config ZMK_KEYBEACON_HOST_LINK`，`depends on ZMK_KEYBEACON_CONNECTIVITY`，`default y`。`keybeacon.c` 用 `#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_HOST_LINK)` 门控 UUID/回调/服务项。
- **Rationale**:
  - 与既有 `CONNECTIVITY`/`BATTERY` 子选项同构（`Kconfig.keybeacon:9–25`），`default y` 让 1.2 headline 能力默认开启，同时保留关闭即退回 1.1 形状（FR-012 / SC-003）。
  - **依赖 CONNECTIVITY**：上游 HW-5 规定「有 AA4 无 AA2」属异常；per-link 需 AA2 的 active/output 供主机比较。依赖关系从构建期排除该异常组合（spec US3 场景 3）。
  - `zmk/ble.h` 的 include 守卫扩展为 `CONNECTIVITY || BATTERY || HOST_LINK`（虽因依赖关系 CONNECTIVITY 必开，仍显式列出以自洽）。
- **Alternatives**: 独立于 CONNECTIVITY。否决——会允许异常组合，增加 host 侧处理负担。无门控始终暴露：否决——剥夺「退回 1.1 形状」能力，违反 II。

## D7. 构建期符号契约（compatibility.yaml）

- **Decision**: `required_symbols` 增条目 `{ name: zmk_ble_profile_index, header: zmk/ble.h, used_in: keybeacon.c }`（无 fallback、无 emits_macro）。
- **Rationale / 实证**:
  - 宪法 VI / FR-015：固件新调用的 ZMK 公共符号须纳入清单。探针 `check_zmk_compat.py` 对每条目 grep `header` 中 `\bname\s*\(`（`scripts/check_zmk_compat.py:49–66`、`235–257`），`zmk/ble.h` 现含该符号；`validate_compat.py` Rule 4 要求 `used_in`（keybeacon.c）能 grep 命中 name/fallback（`scripts/validate_compat.py:138–145`）——本 feature 将在 keybeacon.c 真正调用，满足。
  - 该符号长期稳定（随 ZMK profile 功能存在），与既有 `zmk_ble_active_profile_*` 同处 `zmk/ble.h`。
- **连带影响（fixtures）**: 探针按真实 manifest 对 fixtures grep。4 个 fixture（`zmk-legacy/renamed/missing/header-missing`）的 `app/include/zmk/ble.h` 当前**无** `zmk_ble_profile_index`，须各加一行声明，否则：
  - `zmk-legacy`/`zmk-renamed` 测试期望 `returncode==0`（`test_check_zmk_compat.py:47–61`）会因新符号缺失转为失败；
  - `zmk-missing`/`zmk-header-missing` 期望首个缺失符号仍是 `zmk_endpoints_selected`（`:64–80`），应保持 ble.h 完整、仅 endpoints 缺失 → 为这两个 fixture 也补上该声明，避免产生额外「Also missing」行污染 banner。
- **Alternatives**: 不纳入清单。否决——违反宪法 VI；上游 API 漂移将退化为 C 链接错误而非配置期可诊断失败。

## D8. 版本与 banner 快照

- **Decision**: `module_version: 1.1.4 → 1.2.0`；`expected_banner_v1.1.4.txt` 重生成为 `expected_banner_v1.2.0.txt`，`test_check_zmk_compat.py` 的 `EXPECTED_BANNER` 常量与 skip 提示同步改名。
- **Rationale**:
  - MINOR（新增可选特征/Kconfig）→ `1.2.0`（`CHANGELOG.md:11–17` 的 versioning policy：Backward-compatible addition = MINOR）。
  - banner 文案内嵌 `module_version`（`check_zmk_compat.py:139`、153、213、227），版本串变化使 `test_banner_matches_fixture_missing`（`test_check_zmk_compat.py:95–137`）字节级比对失败；须用真实 manifest 对 `zmk-missing` fixture 重生成快照并提交。
  - 协议层面为 KBP 1.1→1.2（上游 `keybeacon/protocol/`），本仓库 README/CHANGELOG 双语描述对齐；`module_version`（zmk-keybeacon 模块 SemVer）与 KBP 协议版本是两个维度，巧合同为 x.2.x。
- **Alternatives**: 保持 1.1.4（PATCH）。否决——新增 wire 可见特征必为 MINOR。保留旧 banner 文件名：可行但语义漂移，改名更清晰且符合「fixtures 与变更同步」纪律。

## D9. 兼容方向（双向）

- **Decision / Rationale**:
  - **老 host + 新固件**：host 发现不到 AA4（或不读），AA1/AA2/AA3 字节级不变 → 行为同 1.1（FR-012，SC-003）。
  - **新 host + 老固件**：GATT 无 AA4 → host 降级 `cannot-determine`，不臆造（主机侧职责，上游 C-L2）。
  - 本仓库通过「末尾追加 + Kconfig 门控 + 既有字节不变」保证固件侧两个方向都成立。

---

## 结论

全部决策收敛，无遗留 NEEDS CLARIFICATION。关键风险（fixtures/banner 连带）已在 D7/D8 识别并纳入 tasks 范围，确保 `scripts/tests/` 绿（SC-005）。
