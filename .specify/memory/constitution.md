<!--
SYNC IMPACT REPORT
=================================================================================
Version change: [unfilled scaffold] → 1.0.0
Bump rationale: First ratification of a constitution for the zmk-keybeacon
  firmware-module repository. The copied seed file was an unfilled template;
  this instantiates six principles + two standing sections + governance,
  tailored to this repo's role as a KBP *producer* (firmware), distinct from
  the sibling keybeacon repo (protocol source-of-truth + host app consumers).

Principles (scaffold → concrete):
  [PRINCIPLE_1] → I. Wire-Contract Is Upstream — Firmware Implements, Never Defines
  [PRINCIPLE_2] → II. Backward Compatibility Is Non-Negotiable
  [PRINCIPLE_3] → III. Keyboard-Independent, Capability-Structural
  [PRINCIPLE_4] → IV. Observable Degradation Over Guessing
  [PRINCIPLE_5] → V. Spec-First Development (NON-NEGOTIABLE)
  (added sixth) → VI. Build-Time Compatibility Contract

Sections:
  - Delivery Scope & Platform
  - Testing & Verification Discipline
  - Governance

Templates / artefacts consistency:
  OK .specify/templates/plan-template.md — generic Constitution Check gate; no
     principle-name coupling, no edit required.
  OK CHANGELOG.md / README.md — already bilingual EN/中文 (Principle VI honoured).
  OK compatibility.yaml + cmake/zmk_compat.cmake + scripts/ — already implement
     the Build-Time Compatibility Contract (Principle VI).

Deferred / TODO: none. Ratified 2026-11-08.
=================================================================================
-->

# zmk-keybeacon Constitution

This repository is the **ZMK firmware module** that *produces* the KeyBeacon
Protocol (KBP) on the air. It is one of two siblings: the `keybeacon` repo owns
the normative wire contract (`protocol/`), the conformance suite, and the host
app consumers (macOS/Windows); **this** repo owns the firmware that implements
that contract. These principles govern changes here.

## Core Principles

### I. Wire-Contract Is Upstream — Firmware Implements, Never Defines

The single source of truth for everything observable on the air is the sibling
`keybeacon/protocol/` document. This repository is a **producer**: it implements
KBP on ZMK and MUST NOT invent, redefine, or fork wire semantics. Service and
characteristic UUIDs, byte offsets, field encodings, and notify rules are taken
*from* the protocol document, never originated here. When a wire addition must be
led from the firmware side, its contract text is drafted under the feature's
`specs/NNN-*/contracts/` and ratified into upstream `keybeacon/protocol/` before
or alongside the firmware release — so the firmware never becomes a second,
drifting source of truth.

**Rationale**: A third party must be able to build a conforming producer from the
protocol document alone. Keeping definition upstream and implementation here is
what keeps the standard portable and the firmware a faithful mirror.

### II. Backward Compatibility Is Non-Negotiable

The service UUID is the MAJOR-version signal. A MINOR firmware change MUST keep
the service UUID unchanged, MUST keep every previously published characteristic
byte-identical in layout and meaning, and MAY only *add* optional characteristics
(or append reserved-tolerant trailing bytes). Both directions MUST keep working:
an old host against new firmware, and a new host against old firmware. A new
characteristic MUST be independently optional (gated by a Kconfig sub-option) so
a build can emit the prior GATT shape. Removing or redefining a published field,
or repurposing the service UUID, is a MAJOR change requiring explicit
justification in the spec that introduces it.

**Rationale**: Keyboards and apps ship on independent timelines. Honest additive
evolution is the only way heterogeneous producer/consumer pairs interoperate
without coordinated upgrades.

### III. Keyboard-Independent, Capability-Structural

`keybeacon.c` is keyboard-agnostic and MUST stay so — it MUST NOT be edited to
special-case a particular board, and MUST NOT carry a model whitelist or match on
vendor/make/model. What the firmware exposes is gated structurally: by Kconfig
sub-options and by genuine ZMK capabilities (e.g. `CONFIG_ZMK_BLE`, split /
central role), never by branding. Capability a host can discover MUST be
discoverable structurally — characteristic presence and capability bits.

**Rationale**: KeyBeacon is implementation-neutral. One portable module serving
any ZMK keyboard beats per-board forks; branding checks would fracture that
universality.

### IV. Observable Degradation Over Guessing

When the firmware cannot resolve a value, it MUST emit the protocol's defined
sentinel (e.g. a per-link slot of `0` = not-determined, a battery byte of `255` =
unavailable) rather than a fabricated or guessed value. An unchanged snapshot
MUST suppress its notification (keep an idle keyboard at zero BLE traffic). Each
degradation path SHOULD emit exactly one structured diagnostic via the ZMK log,
at a level that does not spam steady-state operation.

**Rationale**: A screenless keyboard's whole value is trustworthy state. A
confident wrong reading is worse than an honest "unknown"; silence on "no change"
protects battery and airtime.

### V. Spec-First Development (NON-NEGOTIABLE)

Any change to wire-affecting firmware (`keybeacon.c`, `Kconfig.keybeacon`),
to the compatibility contract (`compatibility.yaml` and its derived artefacts),
or to the helper scripts that enforce them, MUST originate from a feature
specification under `specs/NNN-*/` produced through the Spec Kit workflow
(specify → clarify → plan → tasks → analyze → implement). Contracts are authored
before implementation; derived/published artefacts are regenerated from the
ratified source, not hand-edited to match code after the fact. Code that lands
without a traceable spec/plan is a process violation and MUST be reworked through
the workflow.

**Rationale**: The producer's behaviour is part of a durable public contract.
Writing the spec first — and analysing it before code — keeps the wire format
deliberate rather than emergent.

### VI. Build-Time Compatibility Contract

The module's ZMK dependency surface is declared in `compatibility.yaml` as the
single source of truth. Every ZMK symbol the firmware calls MUST be declared in
`required_symbols` (with `header`, `used_in`, and any `fallback`), MUST be probed
at CMake configure time (`cmake/zmk_compat.cmake` + `scripts/check_zmk_compat.py`,
fail-fast with an actionable banner), and MUST be covered by the daily
symbol-probe CI. Derived artefacts — the README `COMPAT` block, the CI workflow
YAML, Kconfig defaults — are generated from this manifest and MUST NOT be
hand-edited. An escape hatch (`CONFIG_ZMK_KEYBEACON_ALLOW_INCOMPATIBLE_ZMK`)
exists for emergencies only and defaults off.

**Rationale**: ZMK is a moving upstream. A declared, machine-checked dependency
surface turns silent API drift into a configure-time error with a fix, instead of
a cryptic C link failure or undefined runtime behaviour.

## Delivery Scope & Platform

- The firmware reference stack is **ZMK**; the module ships as a Zephyr module a
  consuming `zmk-config` pins by exact tag via `revision` in `west.yml`.
- Split keyboards expose KeyBeacon **only from the half holding the central
  (host-link) role**; peripheral and recovery images MUST NOT advertise the
  service. The build gate (`keybeacon.cmake`) enforces the central-role
  precondition.
- A **reference keyboard** (Totem; Corne where a split/peripheral path is needed)
  MUST exist for end-to-end verification; at least one scenario per wire-affecting
  feature MUST be reproducible on it.
- Conformance is judged **solely at the wire** by the upstream conformance suite,
  never by firmware internals. Firmware API names cited in docs are non-normative.

## Testing & Verification Discipline

- Every Python helper under `scripts/` MUST keep its `scripts/tests/` coverage
  green; changing a script's behaviour MUST update its tests in the same change.
- Fixtures that mirror the real `compatibility.yaml` (e.g. `scripts/tests/
  fixtures/zmk-*`) and byte-stable banner snapshots MUST be kept in sync when the
  manifest or banner changes — in the same change, with the regeneration command
  recorded.
- Wire-affecting changes MUST be covered by: (a) the upstream conformance
  checklist items for the affected characteristic, and (b) a `specs/NNN/
  quickstart.md` with explicit Given/When/Then mapped to FR/SC identifiers.
- Backward-compatibility and degradation paths MUST each have an executable or
  scripted verification (a test, a conformance vector, or a quickstart scenario),
  not prose alone.

## Governance

This constitution supersedes ad-hoc convention; where guidance conflicts, the
constitution wins.

- **Amendments** are made by editing this file, MUST record a Sync Impact Report,
  and MUST carry a semantic-version bump: MAJOR for backward-incompatible
  principle removals/redefinitions, MINOR for a newly added or materially
  expanded principle/section, PATCH for clarifications.
- **Compliance review**: any change touching `keybeacon.c`, `Kconfig.keybeacon`,
  `compatibility.yaml` (or its derived artefacts), or `specs/*/contracts/**` MUST
  include an explicit Constitution Check in its PR description, and the feature's
  `/speckit-analyze` pass MUST report CRITICAL = 0 and HIGH = 0 before merge.
- **Bilingual normative docs**: the repository root `README.md` and `CHANGELOG.md`
  MUST present English and 中文, with RFC 2119 terms rendered stably
  (MUST → 必须, SHOULD → 应, MAY → 可). The normative *wire* documents live
  upstream in `keybeacon/protocol/` and are bilingual there; `specs/*` internal
  working documents are exempt.
- **Runtime guidance** for day-to-day work lives in `AGENTS.md` and each feature's
  `plan.md` Constitution Check, which MUST stay consistent with the principles
  above.

**Version**: 1.0.0 | **Ratified**: 2026-11-08 | **Last Amended**: 2026-11-08
