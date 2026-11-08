# Feature Specification: 每连接主机上下文 — 固件生产者（Per-Link Host Context, Firmware Producer）

**Feature Branch**: `005-host-link-profile-awareness`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "固件生产者：在 zmk-keybeacon 模块中实现 KBP 1.2 的『每连接主机上下文』。新增独立只读 GATT 特征 AA440AA4-…（READ only，无 NOTIFY/CCC），payload[0] 携带 local_link_profile（bits0–6 为本连接 slot，1-based，0=未确定；bit7 保留必须 0）。固件在 GATT read 回调中用对端地址解析出本连接 slot，使每台主机零配置读到『我是 P 几』；无法解析时发 0 而非猜测。既有 AA0/AA1/AA2/AA3 逐字节不变、service UUID 不变，属 MINOR 演进。用 Kconfig 子选项 CONFIG_ZMK_KEYBEACON_HOST_LINK 门控（依赖 CONNECTIVITY），并把 zmk_ble_profile_index 纳入构建期符号契约。"

## 背景与定位（Why）

一把 ZMK 键盘可同时与多台主机保持 BLE 链路（例如 Mac=P1、Windows=P2），但只有**活跃 profile** 真正接收键入。现有 KBP 1.1 Connectivity 特征（AA2）通过**广播 NOTIFY** 下发、各主机字节相同，其 `profile_index` 只报**全局活跃** slot——于是两台主机都读到同一个值，都误判「正在此电脑使用」。

决定性的使能点：GATT **READ 回调天然带发起连接的 `struct bt_conn *`**，固件因此能对**每条链路**回答**不同**的值。本 feature 的固件职责是：新增一个**只读**特征 AA4，让每台主机通过一次 per-connection 读取，**零配置**地得知「本链路对应的是 profile 几」。主机侧（macOS/Windows）再把它与 AA2 广播的全局活跃 slot 比对，派生「在此使用 / 在别处使用 / 无法确定」——主机侧实现属上游 `keybeacon` 仓库，**不在本仓库范围**。

本仓库（`zmk-keybeacon`）是 KBP 的**固件生产者**，只交付 AA4 只读特征的产生逻辑、门控开关、构建期兼容契约与双语模块文档。wire 契约的唯一真相源在上游 `keybeacon/protocol/`（KBP 1.2）；本 feature 对应其固件义务 FR-001~FR-004、FR-011、FR-013。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 每台主机读到属于自己的 slot（Priority: P1）🎯 MVP

键盘同时绑定两台主机（Host A 绑定在 P1、Host B 绑定在 P2）。两台主机各自在建立链路后发起对 AA4 的一次 GATT 读取。**Host A 读到 1，Host B 读到 2**——每条链路拿到的是**自己**对应的 slot，而非全局活跃 slot。无论当前活跃 profile 是哪个、也无论 AA2 广播的内容如何，这个值都只反映「发起读取的这条连接绑定在哪个 slot」。

**Why this priority**: 这是本 feature 存在的全部理由——提供一个**per-connection、不随广播污染**的信号，让主机侧得以消歧义。没有它，上游的五态派生无从谈起。

**Independent Test**: 用一把绑定了两台电脑的参考键盘，在两台电脑上分别对 AA4 发起读取（可用通用 BLE 工具或上游 `conformance` 工具），确认两端读回的字节不同且分别等于各自的绑定 slot（1 与 2）；该结果与当前活跃 profile 无关。

**Acceptance Scenarios**:

1. **Given** 键盘绑定 Host A=P1、Host B=P2 且两条链路均在线，活跃 profile 为 P1，**When** Host A 读取 AA4、Host B 读取 AA4，**Then** Host A 得到 `[0]=0x01`、Host B 得到 `[0]=0x02`。
2. **Given** 同上，**When** 用户在键盘上把活跃 profile 从 P1 切到 P2 后两端再次读取 AA4，**Then** 两端读回值**不变**（Host A 仍 1、Host B 仍 2）——AA4 反映绑定关系而非活跃状态。
3. **Given** AA4 特征存在，**When** 任一主机检视其 GATT 属性，**Then** 该特征**仅有 READ 属性**，不含 NOTIFY，也不暴露 CCC（`0x2902`）描述符。

---

### User Story 2 — 无法解析时诚实发哨兵值（Priority: P2）

当某条连接的对端地址无法匹配到任何已绑定 profile（例如使用可解析私有地址 RPA 且不等于绑定地址、或该 slot 处于「开放等待配对」状态），固件对该连接的 AA4 读取**返回 0**（未确定），**绝不猜测**一个 slot 号。同时在该降级路径上输出恰一条结构化诊断日志。

**Why this priority**: 宪法 IV「可观测降级优于猜测」。一个自信的错误 slot 会让主机误显示「在此使用」，比诚实的「无法确定」更糟。它依赖 US1 的读取路径已存在，故 P2。

**Independent Test**: 构造一条对端无法解析到绑定 slot 的连接（或在无任何绑定时读取），确认 AA4 读回 `[0]=0x00`；确认日志恰好出现一条结构化降级记录。

**Acceptance Scenarios**:

1. **Given** 一条连接的对端地址不匹配任何绑定 profile，**When** 该连接读取 AA4，**Then** 返回 `[0]=0x00`（bits0–6=0），且 bit7=0。
2. **Given** 解析失败发生，**When** 读取回调执行降级分支，**Then** 输出恰一条结构化诊断（不在稳态下刷屏）。
3. **Given** 任意成功解析，**When** 固件写出 slot 值，**Then** 该值 1-based 且 ≤ `profile_max_slots`（与 AA2 `[3]` 口径一致），bit7=0。

---

### User Story 3 — 纯加法、向后兼容、可门控（Priority: P3）

AA4 是**可选**特征：由 Kconfig 子选项 `CONFIG_ZMK_KEYBEACON_HOST_LINK` 门控（依赖 `CONFIG_ZMK_KEYBEACON_CONNECTIVITY`）。启用时在既有服务下**追加** AA4；关闭时 GATT 形状与 1.1 完全一致。无论启停，既有 AA0/AA1/AA2/AA3 的声明、字节布局、CCC 与发包节奏**逐字节不变**，service UUID 不变。老主机发现不到 AA4 即按 1.1 工作；新主机遇到不实现 AA4 的老固件时按降级处理（主机侧职责）。

**Why this priority**: 向后兼容是宪法 II 的硬约束，但对已升级的新组合不新增能力，属保护混合版本群体，故 P3。

**Independent Test**: (a) 关闭 `CONFIG_ZMK_KEYBEACON_HOST_LINK` 构建 → GATT 中无 AA4，且 AA1/AA2/AA3 属性/字节与 1.1 一致；(b) 开启构建 → 新增且仅新增 AA4，既有特征索引与 notify 行为不变（AA1 notify 目标、AA2/AA3 notify 目标正确）。

**Acceptance Scenarios**:

1. **Given** `CONFIG_ZMK_KEYBEACON_HOST_LINK=n`，**When** 主机发现服务，**Then** 不存在 AA4，其余特征与 1.1 完全一致。
2. **Given** `CONFIG_ZMK_KEYBEACON_HOST_LINK=y`、`CONNECTIVITY=y`，**When** 主机发现服务，**Then** 存在 AA4（READ only），且 AA1/AA2/AA3 字节级不变。
3. **Given** `CONNECTIVITY=n`，**When** 配置构建，**Then** AA4 不被启用（依赖关系保证不会出现「有 AA4 无 AA2」的异常组合）。

---

### Edge Cases

- **对端为可解析私有地址（RPA）且不等于绑定地址**：解析失败 → 发 0（US2）。
- **slot 处于开放等待配对**：无稳定对端身份 → 发 0，而非臆造 slot。
- **单主机键盘**：该连接解析到唯一绑定 slot，读回其 1-based 值（通常为 1）。
- **非中心/非 BLE 构建**：模块仅在 split 中心（host-link）角色且 `CONFIG_ZMK_BLE` 下构建（既有 `keybeacon.cmake` 门控），AA4 随之只在该角色暴露。
- **频繁读取**：AA4 为只读、无状态缓存推送；每次读取按当前绑定实时解析，重复读取幂等。
- **GATT 读取带 offset / 超短 MTU**：读取回调须经标准 `bt_gatt_attr_read` 处理 offset 与长度截断，行为与既有特征一致。

## Requirements *(mandatory)*

### Functional Requirements

> **范围**：以下均为**固件生产者**义务，对应上游 `keybeacon/specs/005` 的 FR-001~FR-004、FR-011、FR-013。主机消费者（五态派生/UI/诊断）与协议/一致性文档更新属上游仓库，不在此。

- **FR-001**: 固件 MUST 暴露一个**每连接可读**的 slot 值：任一主机在其链路上对 AA4 发起一次 GATT 读取，即可得到**本连接**对应的 profile slot，无需任何预先配置。
- **FR-002**: 该 slot 值 MUST 为 **1-based**（与既有 `profile_index` 口径一致），并保留单一值 **0** 表示「未确定 / 不适用」。编码于 payload `[0]` 的 bits0–6；bit7 为保留位，MUST 为 0。
- **FR-003**: 当固件无法把连接对端解析到某个已绑定 profile 时，MUST 发出 **0**（未确定），MUST NOT 发出一个猜测的 slot。
- **FR-004**: 该 per-link 信号 MUST **独立于 AA2 广播 NOTIFY**：即便广播内容跨主机相同，每条链路仍能通过 AA4 读到**自己**的 slot。承载方式 MUST 为一个**只读**特征（无 NOTIFY、无 CCC），以在物理上杜绝广播帧污染。
- **FR-005**: 成功解析时写出的 slot MUST ≤ `profile_max_slots`（即 ZMK profile 总数，与 AA2 `[3]` 同口径），不得越界。
- **FR-011**: 本变更 MUST 为 **KBP MINOR** 演进：service UUID 不变；既有 AA0/AA1/AA2/AA3 的每一个字节、属性、CCC、发包节奏保持不变；新信息 MUST 仅承载于**新增的可选只读特征** AA4。
- **FR-012**: AA4 MUST 由 Kconfig 子选项 `CONFIG_ZMK_KEYBEACON_HOST_LINK` 门控，且 MUST 依赖 `CONFIG_ZMK_KEYBEACON_CONNECTIVITY`；关闭该子选项时构建产物的 GATT 形状 MUST 与未含本 feature 时一致。
- **FR-013**: FR-003 的降级路径 MUST 输出恰一条结构化诊断（经 ZMK 日志），且稳态运行下不刷屏。
- **FR-014**: AA4 的 UUID、属性集合、payload 长度与 `[0].bit7=0` MUST 可被上游一致性工具静态判定（对应上游 checklist C13/C14）；本仓库交付须使该静态判定通过。
- **FR-015**: 固件对 AA4 所依赖的 ZMK 公共符号 `zmk_ble_profile_index`（取对端地址→绑定 slot）MUST 纳入 `compatibility.yaml` 的 `required_symbols` 构建期契约，并被符号探针 CI 覆盖。
- **FR-016**: 模块版本 MUST 按 SemVer 升 **MINOR**：`compatibility.yaml` 的 `module_version` 由 `1.1.4` → `1.2.0`；`CHANGELOG.md` 增 1.2.0 条目；根 `README.md` 的中英双语能力描述同步新增 AA4（宪法 VI）。

### Key Entities *(include if feature involves data)*

- **Local Link Profile（AA4 payload）**: 本 BLE 连接对应的 profile slot。属性：`[0].bits0–6` = slot（1-based；0=未确定），`[0].bit7` = 保留(0)，`[1..]` = 保留尾部（消费者须忽略）。来源：对发起读取的连接的对端地址做绑定查找。
- **AA4 Characteristic**: UUID `AA440AA4-F5ED-4C48-84A1-8062D20D3D55`，属性仅 `READ`，无 NOTIFY、无 CCC，挂在既有服务 `AA440AA0-…` 下；存在性即「per-link 能力」信号。
- **Build-Time Symbol Contract**: `compatibility.yaml` 中新增的 `zmk_ble_profile_index` 依赖项（header `zmk/ble.h`，used_in `keybeacon.c`），用于构建期探测与每日 CI。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 在绑定两台主机的参考键盘上，两台主机对 AA4 的读取分别返回各自绑定 slot（1 与 2），且该结果在活跃 profile 任意切换下保持不变——≥ 10 次交替验证 100% 符合。
- **SC-002**: 对无法解析到 slot 的连接（含无绑定/开放/地址不匹配），AA4 读取 100% 返回 0，且**从不**返回一个不属于该连接的 slot。
- **SC-003**: 关闭 `CONFIG_ZMK_KEYBEACON_HOST_LINK` 的构建，其 GATT 服务的特征集合、各特征字节布局与属性与当前 1.1 发布**逐字节一致**（既有解析器零回归）。
- **SC-004**: 开启构建时，AA4 的静态属性（READ only、无 CCC、payload ≥ 1 字节、`[0].bit7=0`、`bits0–6 ∈ {0}∪[1,profile_max_slots]`）通过上游一致性工具 C13/C14，无新增失败。
- **SC-005**: `scripts/tests/` 全部通过（含更新后的符号契约、fixtures 与 banner 快照）；构建期符号探针对 `zmk_ble_profile_index` 解析成功。

## Assumptions

- ZMK 公共 API `int zmk_ble_profile_index(const bt_addr_le_t *addr)` 可把一条在线连接的对端地址映射到绑定 slot（命中返回 0-based 索引，未命中返回负值）；本 feature 把 0-based 转 1-based 并以 0 作未确定哨兵。该符号在 known-good ZMK 窗口内稳定存在。
- 连接对端地址经标准 `bt_conn_get_dst(conn)` 获取；GATT 读取回调由平台保证携带发起读取的连接句柄。
- AA4 与 AA2 同在（由 Kconfig 依赖保证），使主机得以用 AA2 的活跃 slot/输出端点与 AA4 的本连接 slot 做比较；「有 AA4 无 AA2」的异常组合在本仓库通过依赖关系被排除。
- 主机侧五态派生、UI、双语文案、诊断，以及 `keybeacon/protocol/` 与 `conformance/` 的规范与向量更新，均属上游 `keybeacon` 仓库，本 feature 的端到端验收依赖其 1.2 主机就绪。
- 模块仅在 split 中心（host-link）角色且启用 BLE 时构建（既有 `keybeacon.cmake` 约束），故 AA4 只从面向主机的一侧暴露，符合宪法 Delivery Scope。
