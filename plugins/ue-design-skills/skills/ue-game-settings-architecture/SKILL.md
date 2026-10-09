---
name: ue-game-settings-architecture
description: >-
  Design or review game settings and performance architecture in Unreal Engine:
  setting model trees separated from widgets, reflection-backed property paths,
  declarative edit conditions, apply and cancel as a transaction, machine-local
  versus player-shared persistence, scalability and console variables and device
  profiles, hardware benchmark wiring, and sampled performance statistics. Use
  when adding video, audio, input or accessibility settings, cloud saves,
  quality presets, frame-rate modes, device tuning or performance overlays.
---

# UE game settings architecture

The invariant:

> A setting is a **model** with persistence, validation and application
> semantics. A widget is one view of that model.

Measured patterns from a reference product: [patterns](references/patterns.md).
Detection recipes: [failure modes](references/failure-modes.md).

Settings look like the least architectural part of a game and are one of the
most: they span a UI framework, a reflection layer, two persistence stores, the
console-variable system, device profiles and the engine's scalability tables.
Every one of those boundaries fails silently.

Related skills: `ue-data-driven-architecture`, `ue-ui-architecture`,
`ue-input-architecture`, `ue-modular-gameplay`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Separate model, registry and presentation

```text
registry (per local player)
└─ collections and pages
   └─ setting models
      ├─ data source: getter and setter
      ├─ display text and description
      ├─ edit conditions
      ├─ options and validation
      └─ apply / store-initial / restore lifecycle

visual data asset
└─ setting model class → entry widget class
```

The screen renders a tree of models through a class-to-widget map; it does not
hand-build a widget per option. The payoff: one model renders in several screens,
search and grouping operate on models, edit conditions are testable without any
UI, and settings code depends on no concrete widget class.

Resolve the widget by walking the model's **superclass chain**, so mapping one
base class covers every derived setting and a specific override remains possible.

---

## 2. Reflection-backed data sources, and their one cost

A setting stores a **path** to a getter and setter rooted at the local player,
and resolves it through reflection:

```text
local player → GetLocalSettings() → GetShadowQuality / SetShadowQuality
```

This removes a class per setting. It also removes the compiler from the
relationship.

### The cost, stated precisely

A macro that stringifies a function name checks that the **name** exists. It does
not check the return type, the parameter count, or constness. Those failures
surface as a runtime assertion during registry initialization — **and assertions
are compiled out of shipping**, so in a shipping build a broken path is a setting
that silently does nothing.

Three consequences worth designing around:

1. validate every path during registry initialization and **fail loudly with the
   setting's developer name**, not with a reflection error;
2. run that validation in an automated test, not only when a developer opens the
   screen;
3. prefer explicit binding where conversion is complex, where several values
   change atomically, or where the setter has side effects worth reading.

Recipe: GS-01.

---

## 3. Edit conditions are declarative dependencies

Availability depends on platform traits, primary-player status, other settings,
capabilities, privileges, input device and build configuration. Express it in the
model, never in widget visibility.

Return more than a boolean:

```text
editable
disabled (reason shown to the player)
hidden (reason recorded for the developer)
option disabled (one entry removed from a list)
killed (hidden, not resettable, not reported)
```

A condition also declares which settings it depends on, so that changing one
setting re-evaluates the others.

**The two-reason split is the part worth copying.** A disabled setting shows the
player why; a hidden one records why for whoever later asks where it went. Most
hand-built settings screens have neither.

---

## 4. Persistence: machine-local versus player-shared

| | Machine-local | Player-shared |
|---|---|---|
| Holds | resolution, quality, frame rate, device profile, benchmark result | accessibility, sensitivities, subtitles, language, bindings |
| Backed by | engine user settings, local ini | per-player save game, cloud-syncable |
| Scope | one per machine | one per player |

### The ownership test

1. Should this follow the user to another machine?
2. Can two local players need different values at once?
3. Does it change global renderer or audio device state?
4. Can a secondary local player safely apply it?

### The leak to watch for

A per-player accessor that returns a **process-global singleton** is the standard
way this abstraction breaks. It compiles, it reads naturally at every call site,
and it silently makes split-screen impossible for every value behind it. The
symptom in a codebase that has it: a proliferation of "only the primary player
may edit this" conditions, which is the architecture apologising for itself.

Recipe: GS-03. If you find it, the fix is not to remove the conditions.

---

## 5. Apply and cancel is a transaction

1. store initial values on open;
2. edits update the model, and optionally preview;
3. apply commits and invokes application;
4. cancel restores initial values **and reapplies the prior runtime state**;
5. reset-to-defaults is another staged mutation, not an immediate save.

### Classify application timing deliberately

| Setting | Timing |
|---|---|
| volume, UI preview | immediate, restored on cancel |
| scalability channel | preview or apply, per policy |
| resolution and window mode | apply with a confirmation countdown |
| key binding | staged profile plus collision check |
| restart-required | save now, mark pending |

Applying a heavyweight global change from inside a change notification is a
decision, not a default. If it is done because staging was not written yet, mark
it as such — and treat a comment saying "for now" on a global apply path as a
finding rather than a note. Recipe: GS-05.

---

## 6. From setting to console variable

The preferred path keeps a typed object in the middle:

```text
model → typed settings setter → staged quality levels
→ apply → engine scalability API → expanded console variables
→ clamped by device profile
```

A typed object gives range validation, persistence, transactional restore,
platform clamping, change notification and a test seam. A widget writing a
console variable directly gives none of them.

When a setting genuinely maps to a custom variable: resolve and cache safely,
set a defined priority source, clamp, restore on cancel, and document shipping
availability. Never write to a read-only variable and assume it took.

---

## 7. Device profiles are constraints, not presets

```text
platform default → base profile → mode suffix → user request
→ platform clamp → effective value
```

Keep **requested** and **effective** separate, and be able to explain to the
player why a request was clamped.

Profile selection commonly composes a name from parts — base, mode, user choice —
and falls back through progressively shorter combinations until one exists. That
is a good pattern with one specific hazard: a composition part that is declared,
read, and never assigned. The fallback then silently always takes the shorter
branch, and the feature the part represents does not exist while appearing to.
Recipe: GS-07.

---

## 8. Wire the benchmark, do not merely implement it

```text
can run? → run benchmark → map indices through thresholds
→ set quality and resolution scale → save and apply
```

A function named "should this run at startup" with **no caller** means startup
autodetection does not exist, however complete the rest of the pipeline is.

Decide explicitly: automatic on first launch or manual only; how hardware changes
are detected; whether user overrides survive; what happens on failure. Then add a
**call-site test**, not only a unit test of the threshold mapping — the mapping
was never the part that was missing. Recipe: GS-08.

---

## 9. Performance statistics: collect once, present many

```text
engine frame data → one consumer → latest values + sampled ring buffers → widgets
```

Rules that keep this honest:

- one collector, never one per widget;
- a fixed-capacity ring buffer with a **documented sample cadence** — a buffer
  size without a cadence describes no window at all;
- units written down: milliseconds, frames per second, bytes per second, percent;
- an unavailable statistic returns *unavailable*, never zero;
- availability in shipping is a deliberate setting.

A frame-rate counter is not evidence about rendering cost. Use it to notice, not
to conclude.

---

## 10. Reapply after composition changes

Global scalability and frame pacing may need reapplying after a game mode or
feature set finishes loading, because features can change device profile,
console variables and frontend policy.

Do it **once, at one named lifecycle point, after the composition is fully
known** — not from each feature. The same entry point should serve the other
trigger that changes the same state, such as a hotfixed device profile. Two
causes, one reaction, one idempotent function.

---

## 11. Guard engine-struct assumptions

Code that enumerates every member of an engine struct — copying, clamping or
maxing quality levels field by field — should carry a compile-time size guard
with a message telling the upgrader what to review.

A failing size assertion after an engine upgrade is a **feature**. It is the only
thing standing between a newly added quality channel and being silently ignored
by five functions. Update the guard only after reviewing every one of them, and
know how many there are before you start. Recipe: GS-09.

---

## 12. Review checklist

- [ ] Setting is a model; the widget is a view.
- [ ] Stable developer name is separate from localized display text.
- [ ] Every property path is validated at initialization and in a test.
- [ ] Machine-local versus player-shared ownership is explicit per value.
- [ ] No per-player accessor returns a global singleton.
- [ ] Apply and cancel restore runtime state, not only stored values.
- [ ] Expensive apply operations have deliberate, documented timing.
- [ ] Requested and effective values are distinguishable.
- [ ] Direct console-variable writes are justified and restorable.
- [ ] The benchmark has a real caller and a stated policy.
- [ ] Statistics are collected once, sampled at a documented cadence.
- [ ] Unavailable is distinct from zero.
- [ ] Reapplication after composition change is centralized and idempotent.
- [ ] Engine-struct assumptions carry compile-time guards.

---

## 13. When to simplify

A prototype can bind widgets straight to engine user settings. Adopt a model
registry when at least one holds: platforms hide or clamp settings differently;
apply and cancel are required; several local users need separate preferences;
search, categories or dynamic conditions matter; gamepad navigation needs
reusable rows; settings span ini, save games, console variables and subsystems.

Do not adopt a five-thousand-line framework for three toggles. Adopt it when the
settings screen has become an application subsystem rather than a panel.

---

## Provenance

The findings come from a source audit of Epic's Lyra Starter Game on Unreal
Engine 5.6 and the settings plugin it ships with — roughly 5700 lines of
framework plus 2100 of project-specific settings backends, read rather than run.
The framework itself contains no reference to the game and is the most portable
component examined in the whole research project; the findings below are about
its **wiring**, not its design.

Source addresses stay in the research archive. Each entry carries a stable
identifier (`GS-01`, `GS-03`, …) resolving back to the audited location there.

## Evidence boundary

One project, one engine version. Concrete widget assets are binary and were not
read, so claims here concern the model layer and its bindings. Values quoted from
configuration describe that project on that day.
