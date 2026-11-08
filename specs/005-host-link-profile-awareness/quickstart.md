# Quickstart: 每连接主机上下文 — 固件生产者验证

**Feature**: `specs/005-host-link-profile-awareness` | **Phase**: 1 | **Plan**: [plan.md](./plan.md)

本文件给出**可执行/可复现**的验证步骤，映射到 spec 的 FR/SC。分三层：A 构建期符号契约与单测（本仓库、无硬件）、B GATT 形状静态判定（上游 conformance）、C 端到端真机剧本（参考键盘 + 两台电脑，依赖上游 1.2 主机）。

---

## 前置

- 本仓库 Python 开发依赖：`pip install -r scripts/requirements-dev.txt`（pyyaml、pytest 等）。
- 一份可被探针读取的 ZMK 克隆（或使用 `scripts/tests/fixtures/zmk-*`，无需真实 ZMK）。
- 端到端另需：支持本模块的 `zmk-config`、参考键盘（Totem/Corne split 中心）、两台电脑、上游 `keybeacon` 1.2 主机 app 或 `conformance/conformance_tool.py`。

---

## A. 构建期符号契约与单测（本仓库，无需 BLE 硬件）→ SC-005

### A1. manifest 校验

```bash
cd /Users/wangyuting19/kbd/zmk-keybeacon
python3 scripts/validate_compat.py
```

**预期**: 通过（required_symbols 含新 `zmk_ble_profile_index`，name 唯一、used_in `keybeacon.c` 命中）。

### A2. 符号探针（对 fixtures）

```bash
python3 scripts/check_zmk_compat.py --zmk-root scripts/tests/fixtures/zmk-legacy
python3 scripts/check_zmk_compat.py --zmk-root scripts/tests/fixtures/zmk-renamed
```

**预期**: 均 `STATUS: … ✓`、`returncode==0`（新符号在 fixture ble.h 中可见）。

```bash
python3 scripts/check_zmk_compat.py --zmk-root scripts/tests/fixtures/zmk-missing; echo "rc=$?"
```

**预期**: `rc=2`，stderr banner 首个缺失仍为 `zmk_endpoints_selected`（ble.h 齐全、仅 endpoints 缺）。

### A3. pytest 全绿

```bash
python3 -m pytest scripts/tests/ -q
```

**预期**: 全通过。含 banner 字节级比对（指向重生成的 `expected_banner_v1.2.0.txt`）、manifest 结构校验、fixtures 探针。

### A4. banner 快照重生成（仅当 A3 的 banner 用例因版本串失败时）

```bash
python3 scripts/check_zmk_compat.py --zmk-root scripts/tests/fixtures/zmk-missing \
  2> scripts/tests/fixtures/expected_banner_v1.2.0.txt
```

提交该文件；确认 `test_check_zmk_compat.py` 的 `EXPECTED_BANNER` 指向 v1.2.0。

---

## B. GATT 形状静态判定（上游 conformance，连真机或模拟）→ SC-004

> 工具在上游 `keybeacon/conformance/`；此处为验收口径。

- **C13**: 发现 AA4 → 属性恰为 `READ`（无 NOTIFY、无 CCC `0x2902`），READ payload ≥ 1 字节、`[0].bit7 = 0`。
- **C14**: `[0].bits0–6 ∈ {0} ∪ [1, profile_max_slots]`（`profile_max_slots` 取自 AA2 `[3]`）。

**预期**: C1–C14 无新增失败。

---

## C. 端到端真机剧本（参考键盘 + 两台电脑）→ SC-001/SC-002/SC-003

### 准备

1. 在 `zmk-config` 的 `west.yml` 把 `zmk-keybeacon` 的 `revision` 指向本 feature 的构建（含 `CONFIG_ZMK_KEYBEACON_HOST_LINK=y`，默认开启）。
2. `west build -p` 刷入参考键盘（split 中心半）。
3. 键盘绑定 Host A→P1、Host B→P2。

### S1. 每台主机读到自己的 slot（FR-001/US1，SC-001）

- **Given** 两条链路在线，活跃 profile=P1。
- **When** 在 Host A 读取 AA4；在 Host B 读取 AA4（用上游 app 或 BLE 工具）。
- **Then** Host A 读回 `[0]=0x01`；Host B 读回 `[0]=0x02`。

### S2. 切换活跃 profile 后 AA4 不变（US1 场景 2）

- **When** 在键盘上把活跃 profile 切到 P2，两端重读 AA4。
- **Then** Host A 仍 `0x01`、Host B 仍 `0x02`——AA4 反映绑定而非活跃。

### S3. 只读属性（US1 场景 3，C13）

- **When** 检视 AA4 的 GATT 属性与描述符。
- **Then** 仅 `READ`；无 `NOTIFY`；无 CCC。

### S4. 无法解析发 0（FR-003/US2，SC-002）

- **Given** 构造一条对端无法解析到绑定 slot 的连接（如清除该 slot 绑定后仍连接、或 RPA 不匹配）。
- **When** 该连接读取 AA4。
- **Then** `[0]=0x00`；（可选）在键盘串口日志开启 `CONFIG_LOG`+DBG 时见恰一条 `hostlink.unresolved`。

### S5. 关闭门控退回 1.1（US3，SC-003）

- **When** 以 `CONFIG_ZMK_KEYBEACON_HOST_LINK=n` 重新构建刷入。
- **Then** GATT 中无 AA4；AA1/AA2/AA3 属性与字节与 1.1 一致；既有主机行为无回归。

### 负测矩阵（SC-002：从不假阳）

| 场景 | AA4 读回 | 断言 |
|------|----------|------|
| 未绑定任何 profile | `0x00` | 不返回任意非 0 slot |
| slot open（等待配对） | `0x00` | 不臆造 slot |
| 单主机（仅 P1 绑定） | `0x01` | 等于唯一绑定 slot |
| 正常双机 | A=`0x01` / B=`0x02` | 各得自身 slot |

---

## 验收汇总

| 层 | 覆盖 | 产物 |
|----|------|------|
| A | SC-005、FR-015/FR-016 | `scripts/tests/` 绿、探针 ✓ |
| B | SC-004、FR-014 | 上游 C13/C14 通过 |
| C | SC-001/002/003、FR-001~005/011/012 | 真机剧本 S1–S5 + 负测矩阵 |
