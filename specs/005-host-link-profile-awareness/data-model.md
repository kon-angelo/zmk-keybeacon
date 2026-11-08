# Phase 1 Data Model: 每连接主机上下文 — 固件生产者

**Feature**: `specs/005-host-link-profile-awareness` | **Date**: 2026-11-08 | **Plan**: [plan.md](./plan.md)

本文件是 wire 契约（真相源：上游 `keybeacon/protocol/` KBP 1.2，起草区 `keybeacon/specs/005/contracts/host-link-context.md`）面向**固件实现**的投影。描述 AA4 的字节布局、解析算法、GATT 服务定义位序、Kconfig 与构建期符号契约。**既有 AA0/AA1/AA2/AA3 全部不变。**

---

## 0. UUID 常量

| 名称 | UUID | 属性 | 说明 |
|------|------|------|------|
| service | `AA440AA0-F5ED-4C48-84A1-8062D20D3D55` | — | KBP 服务（不变） |
| status (AA1) | `AA440AA1-…` | READ\|NOTIFY | KBP 1.0 层+修饰键（不变） |
| connectivity (AA2) | `AA440AA2-…` | READ\|NOTIFY | KBP 1.1 连接（不变） |
| battery (AA3) | `AA440AA3-…` | READ\|NOTIFY | KBP 1.1 电量（不变） |
| **host-link (AA4)** | **`AA440AA4-F5ED-4C48-84A1-8062D20D3D55`** | **READ only（无 NOTIFY / 无 CCC）** | **[NEW] 本连接 slot（per-connection）** |

`keybeacon.c` UUID 宏区现有 AA0/AA1/AA2/AA3（`:52–66`）；本 feature 在 AA3 宏后新增 `KEYBEACON_LINK_UUID`，以 `#if IS_ENABLED(CONFIG_ZMK_KEYBEACON_HOST_LINK)` 门控。

---

## 1. AA4 payload（新增，≥ 1 字节）

### 1.1 布局

| Offset | Size | Field | 编码 |
|--------|------|-------|------|
| `[0]` | 1 | `local_link_profile` | bits 0–6：本连接 slot，1-based（`0` = 未确定/不适用）；bit 7：reserved，MUST 0 |
| `[1..N]` | ≥0 | reserved trailing | 未来 MINOR；consumer MUST ignore（本固件只写 1 字节） |

- 本固件实现固定写 **1 字节**。`bt_gatt_attr_read` 负责 offset/MTU 截断，与既有特征一致。

### 1.2 生产者不变量（固件 MUST，对应上游 P-L1..P-L5）

- **P-L1**: AA4 属性恰为 `READ`（无 `NOTIFY`、无 CCC `0x2902`）。
- **P-L2**: 无法把对端解析到 slot（含未绑定/open/RPA 不匹配）→ `[0].bits0–6 = 0`，MUST NOT 猜测。
- **P-L3**: `[0].bits0–6 > 0` 时 MUST ≤ `ZMK_BLE_PROFILE_COUNT`（= `profile_max_slots` = AA2 `[3]`）。
- **P-L4**: `[0].bit7` MUST 0。
- **P-L5**: 仅 split 中心（host-link）角色暴露——由 `keybeacon.cmake`（`CONFIG_ZMK_SPLIT_ROLE_CENTRAL`）与模块整体门控间接保证。

---

## 2. 读取解析算法（纯逻辑，供单测/评审对照）

```text
link_slot_read(conn, attr, buf, len, offset):
    slot = 0                                  # P-L2 默认：未确定
    if conn != NULL:
        peer = bt_conn_get_dst(conn)          # const bt_addr_le_t *
        if peer != NULL:
            idx = zmk_ble_profile_index(peer) # 命中→0-based；未命中→负(-ENODEV)
            if idx >= 0:
                s = idx + 1                    # 1-based（FR-002）
                if 1 <= s <= ZMK_BLE_PROFILE_COUNT:   # P-L3 夹取
                    slot = s & 0x7F            # P-L4 bit7=0
    if slot == 0:
        LOG_DBG("hostlink.unresolved: ...")   # FR-013 恰一条，DBG 不刷屏
    return bt_gatt_attr_read(conn, attr, buf, len, offset, &slot, 1)
```

- **无状态**：无缓存、无全局变量；每次读取实时解析，幂等（spec Edge: 频繁读取）。
- **映射真相**：`zmk_ble_profile_index` 的 peer 比较是 ZMK 权威实现（`zmk/app/src/ble.c:242–249`），固件不复制映射表（research D2）。

---

## 3. GATT 服务定义位序（attr index 保持）

`BT_GATT_SERVICE_DEFINE(keybeacon_svc, …)` 的属性顺序与既有 notify 寻址（data-model §E5，`keybeacon.c:68–95`）：

| index | 属性 | 条件 | 备注 |
|-------|------|------|------|
| 0 | Primary service | 恒 | |
| 1 | AA1 chrc decl | 恒 | AA1 notify 目标 `attrs[1]`（不变） |
| 2 | AA1 value | 恒 | |
| 3 | AA1 CCC | 恒 | |
| 4 | AA2 chrc decl | CONNECTIVITY | `KBP_ATTR_AA2=4`（不变） |
| 5 | AA2 value | CONNECTIVITY | |
| 6 | AA2 CCC | CONNECTIVITY | |
| 7 | AA3 chrc decl | CONN && BATTERY | `KBP_ATTR_AA3=7`（或无 CONN 时 4）（不变） |
| 8/9 | AA3 value/CCC | BATTERY | |
| **末尾** | **AA4 chrc decl** | **HOST_LINK** | **[NEW] READ only；无 value-notify、无 CCC → 不新增索引常量** |

- **关键**：AA4 追加在**末尾**，不移位任何既有索引；AA4 无 notify 故无需 `KBP_ATTR_AA4`。这保证 AA1/AA2/AA3 代码零改动（research D5 / SC-003）。
- AA4 服务项形如 `BT_GATT_CHARACTERISTIC(KEYBEACON_LINK_UUID, BT_GATT_CHRC_READ, BT_GATT_PERM_READ, link_slot_read, NULL, NULL)`，其后**不跟** `BT_GATT_CCC`。

---

## 4. Kconfig（门控实体）

```kconfig
config ZMK_KEYBEACON_HOST_LINK
    bool "KeyBeacon 1.2: expose per-connection Host-Link characteristic (AA440AA4-…)"
    depends on ZMK_KEYBEACON_CONNECTIVITY
    default y
    help
      Expose a READ-only characteristic whose value is THIS BLE connection's
      profile slot (1-based; 0 = not determined). A read is inherently
      per-connection, so each bonded host learns its own slot with zero
      configuration. No NOTIFY/CCC. See KBP 1.2 §14 (host-link context).
```

- `depends on ZMK_KEYBEACON_CONNECTIVITY`：排除「有 AA4 无 AA2」异常（research D6）。
- `default y`：1.2 headline 默认开启；设 `n` 可退回 1.1 GATT 形状（FR-012 / SC-003）。

---

## 5. 构建期符号契约（compatibility.yaml 实体）

新增 `required_symbols` 条目：

```yaml
  # keybeacon.c link_slot_read — per-connection peer→slot 解析
  - name: zmk_ble_profile_index
    header: zmk/ble.h
    used_in: keybeacon.c
```

- 无 `fallback`（符号稳定）、无 `emits_macro`。
- `module_version: 1.1.4 → 1.2.0`。
- 探针（`check_zmk_compat.py`）自动纳入新条目；`validate_compat.py` Rule 1（name 唯一）、Rule 4（used_in 命中）均满足。

### 5.1 fixtures 连带（测试真相源对齐）

4 个 fixture 的 `app/include/zmk/ble.h` 各加一行（使探针对真实 manifest 的新符号成立）：

```c
int zmk_ble_profile_index(const bt_addr_le_t *addr);
```

| fixture | 加符号后预期 |
|---------|--------------|
| `zmk-legacy` | 全符号命中 → `returncode==0`（含既有 legacy-endpoint 宏） |
| `zmk-renamed` | 全符号命中（endpoints 走 fallback）→ `returncode==0` |
| `zmk-missing` | ble.h 齐全、仅 `endpoints.h` 缺 → 首个缺失仍是 `zmk_endpoints_selected`（banner 单一缺失） |
| `zmk-header-missing` | `endpoints.h` 文件缺 → banner 提示 header missing |

### 5.2 banner 快照

- 重生成 `scripts/tests/fixtures/expected_banner_v1.2.0.txt`（版本串 1.1.4→1.2.0 导致两行变化）。
- `test_check_zmk_compat.py` 常量 `EXPECTED_BANNER` 与 skip 提示改指向 v1.2.0。

---

## 6. 与既有实体的关系

| 既有实体 | 关系 |
|----------|------|
| AA1 payload（层+修饰键） | **不变** |
| AA2 `conn_payload`（连接） | **不变**（AA4 与之同口径使用 `ZMK_BLE_PROFILE_COUNT`，但不读写 AA2 缓存） |
| AA3 battery payload | **不变** |
| `keybeacon_svc` attr 索引 | **不变**（AA4 末尾追加） |
| **AA4 read 回调** | **新增**，无状态 |
| `compatibility.yaml` required_symbols | **新增**一条 + 版本 bump |

---

## 7. FR / 边界映射

| spec 条目 | 数据模型体现 |
|-----------|--------------|
| FR-001 per-connection 可读 | §2 回调用 `conn`→`bt_conn_get_dst`→解析 |
| FR-002 1-based + 0 哨兵 + bit7=0 | §1.1 布局 + §2 `s=idx+1`、`&0x7F` |
| FR-003 未解析发 0 | §2 默认 slot=0 + `idx<0` 分支 |
| FR-004 独立于广播 | §0 READ only 无 NOTIFY/CCC |
| FR-005 不越界 | §2 `s<=ZMK_BLE_PROFILE_COUNT` 夹取（P-L3） |
| FR-011 纯加法 | §3 末尾追加、既有不变 |
| FR-012 Kconfig 门控+依赖 | §4 |
| FR-013 恰一条诊断 | §2 `LOG_DBG` 单条 |
| FR-014 静态可判（C13/C14） | §1.1/§1.2 属性与范围 |
| FR-015 符号契约 | §5 |
| FR-016 版本 bump | §5 module_version + §5.2 banner |
