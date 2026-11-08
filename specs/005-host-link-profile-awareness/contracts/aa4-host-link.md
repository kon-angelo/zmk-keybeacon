# Contract: AA4 Host-Link 特征 — 固件生产者投影

**Feature**: `specs/005-host-link-profile-awareness` | **Phase**: 1

**Source of truth**: 上游 `keybeacon/protocol/`（KBP 1.2）与起草区 `keybeacon/specs/005-host-link-profile-awareness/contracts/host-link-context.md`。本文件**引用不复制** wire 真相，仅给出**固件生产者**须满足的可验证投影（宪法 I：本仓库实现、不定义）。

---

## C-AA4-1 版本与兼容

- **KBP MINOR**: `1.1 → 1.2`（服务 UUID 不变）。
- **模块 SemVer**: `zmk-keybeacon 1.1.4 → 1.2.0`。
- **Breaking**: 无。AA0/AA1/AA2/AA3 逐字节不变。
- **双向兼容**：老 host + 新固件 → 不发现 AA4，行为同 1.1；新 host + 老固件 → 不发现 AA4，host 降级不臆造（主机侧）。

## C-AA4-2 特征定义（固件 MUST 满足）

| 项 | 值 |
|----|-----|
| UUID | `AA440AA4-F5ED-4C48-84A1-8062D20D3D55`（挂在既有服务 `AA440AA0-…` 下） |
| 属性 | **`READ` only**（MUST NOT `NOTIFY`；MUST NOT 暴露 CCC `0x2902`） |
| 权限 | `BT_GATT_PERM_READ` |
| Optional | 是——由 `CONFIG_ZMK_KEYBEACON_HOST_LINK` 门控；关闭即 GATT 发现不到 |
| 存在性 | 即 per-link 能力信号（与 1.1 以 AA2/AA3 存在性判能力一致） |

### payload

| Offset | Size | Field | 编码 |
|--------|------|-------|------|
| `[0]` | 1 | `local_link_profile` | bits0–6：本连接 slot（1-based；`0`=未确定）；bit7：reserved MUST 0 |

## C-AA4-3 生产者不变量（固件 MUST）

- **P-L1**：属性恰为 `READ`（无 `NOTIFY`、无 CCC）。
- **P-L2**：对端无法解析到 slot（未绑定/open/RPA 不匹配）→ `[0].bits0–6 = 0`，MUST NOT 猜测。
- **P-L3**：`[0].bits0–6 > 0` 时 MUST ≤ `profile_max_slots`（`ZMK_BLE_PROFILE_COUNT` / AA2 `[3]`）。
- **P-L4**：`[0].bit7` MUST 0。
- **P-L5**：仅 split 中心（host-link）角色暴露。
- **P-L6**：解析失败路径 MUST 输出恰一条结构化诊断，稳态不刷屏（FR-013）。

## C-AA4-4 验收（静态可判，对应上游 C13/C14）

- **C13**：若 AA4 存在 → 属性恰为 `READ`（无 `NOTIFY`/CCC），READ payload ≥ 1 字节且 `[0].bit7 = 0`。
- **C14**：若 AA4 存在 → `[0].bits0–6 ∈ {0} ∪ [1, profile_max_slots]`（不越界；0 表未确定）。

> C13/C14 单次 READ 即可静态验证（上游 conformance 工具）。跨连接差异化（两台电脑分别读到各自 slot）由 quickstart 真机剧本覆盖。

## C-AA4-5 构建期符号契约（固件 MUST）

- `compatibility.yaml.required_symbols` MUST 含 `zmk_ble_profile_index`（header `zmk/ble.h`，used_in `keybeacon.c`）。
- CMake 配置期探针（`check_zmk_compat.py`）与每日 CI MUST 覆盖该符号；缺失时 fail-fast banner 指明。

## C-AA4-6 门控契约（固件 MUST）

- `CONFIG_ZMK_KEYBEACON_HOST_LINK` MUST `depends on ZMK_KEYBEACON_CONNECTIVITY`。
- 关闭该选项时，构建产物 GATT 形状 MUST 与 1.1（无 AA4）逐字节一致。

---

## 可追溯性

| 契约项 | spec FR | 上游对应 |
|--------|---------|----------|
| C-AA4-2 属性/payload | FR-001/002/004 | HW-2 / P-L1 |
| C-AA4-3 P-L2/P-L4 | FR-003 | P-L2/P-L4 |
| C-AA4-3 P-L3 | FR-005 | P-L3 |
| C-AA4-3 P-L6 | FR-013 | FR-013 |
| C-AA4-1 纯加法 | FR-011 | HW-1 |
| C-AA4-6 门控 | FR-012 | — |
| C-AA4-4 静态判定 | FR-014 | C13/C14 |
| C-AA4-5 符号契约 | FR-015 | — |
| C-AA4-1 版本 | FR-016 | HW-1 |
