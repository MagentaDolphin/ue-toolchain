---
name: ue-streaming-and-platform-budgets
description: >-
  Design or audit GPU and streaming budgets in Unreal Engine: texture, mesh and
  virtual texture streaming, streaming pool sizing, texture LOD groups,
  scalability buckets, device profiles and console-variable priority, world
  partition and level instance lifetime, and the boundary between disk, CPU
  memory and video memory. Use when targeting a platform memory ceiling, tuning
  quality tiers, adding a background or preview level, or investigating why a
  quality setting has no effect.
---

# UE streaming and platform budgets

The invariant:

> A streaming pool is a **permission**, not a measurement. A quality setting is a
> **request**, not an outcome. Both are arbitrated by device profiles and
> console-variable priority before anything reaches the GPU.

Measured patterns from a reference product: [patterns](references/patterns.md).
Detection recipes: [failure modes](references/failure-modes.md).

Related skills: `ue-asset-loading-and-memory`, `ue-game-settings-architecture`,
`ue-runtime-allocation-and-caching`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Four budgets, four instruments

| Budget | What it physically is | Instrument |
|---|---|---|
| **A. Disk / cook** | bytes in the shipped package | build and chunk sizes |
| **B. CPU memory** | object graph plus bulk data in system RAM | memory report, object listing |
| **C. Video memory** | live render resources: textures, buffers, render-target pool, virtual-texture pool, shadow pages, ray-tracing structures | platform GPU profiler |
| **D. Streaming pool** | an accounting **ceiling** the streamer tries to stay under | streaming stat |

Four rules that prevent most wrong conclusions:

- **A is not D.** Clamping a texture group's maximum size shrinks what is cooked.
  The pool is unchanged.
- **D is not C.** The pool covers streamable mips only. Render targets, virtual
  texture pools, shadow pages and acceleration structures are in C and invisible
  to the streaming stat.
- **B is not C.** A loaded texture object need not have any resident mips.
- **Never report a pool size as memory used.** It is the single most common
  error in this area, and it makes every downstream number meaningless.

---

## 2. Console-variable priority is the real arbiter

Effective value is not "last write wins"; sources are ranked. In practice:

```text
command line > console > device profile > system ini > project ini
             > game setting > scalability > constructor
```

with one exception that matters enormously: a device profile applies variables
whose names begin with the scalability prefix at **scalability** priority, and
everything else at **device-profile** priority.

### The consequence

A value set by a device profile **cannot be changed** by anything the
scalability system does afterwards — which includes every in-game quality
setting. The same setting is therefore mutable on one tier and frozen on
another, with nothing in the UI explaining the difference. Recipe: ST-01.

### Gates

- [ ] every quality-affecting variable has a documented intended priority source;
- [ ] prefixed and unprefixed names are used deliberately, not by habit;
- [ ] per-tier overrides are complete across tiers, or partial with a comment
      saying why;
- [ ] the settings UI can express "clamped by platform" rather than silently
      failing;
- [ ] requested and effective values are both observable at runtime.

**The one command that settles it:** dump variables with their source. Anything
else is inference.

---

## 3. Pool sizing, and its detachment from real memory

Two knobs interact: the pool size, and whether the pool is clamped by actual
video memory.

The trap is structural rather than accidental: **the highest quality buckets
commonly disable the video-memory clamp**, and automatic detection promotes
hardware to the top bucket on a compute benchmark that does not consider memory
size at all. A fast card with modest memory therefore lands in the bucket where
the pool budget is largest and least constrained. Recipe: ST-02.

Rules:

- decide per platform whether the pool is derived from memory or fixed;
- if fixed, write down the assumed memory floor;
- benchmark thresholds must consider memory, not only throughput;
- test the top bucket on a low-memory card, not only on the reference machine.

### Sharing the pool

If mesh streaming is enabled and no separate mesh pool is configured, geometry
and textures compete inside one budget. That is a legitimate choice; it is not a
legitimate surprise. Check both values on every platform. Recipe: ST-03.

---

## 4. Texture groups are the per-content lever

Scalability moves everything at once; groups shape individual content classes.
Use them to encode intent: hero content larger, world content platform-scaled,
UI unstreamed and sized exactly, debug content excluded from cook.

Gates: every group has a stated purpose; mobile tiers override group caps rather
than only global quality; no content relies on a group it does not belong to;
streaming-exempt content is deliberate and small.

Watch for group settings that describe a delivery mechanism the project does not
have — optional mip levels configured with no chunk installation, for instance.
Configuration that cannot take effect is worse than absent configuration,
because it reads as a decision. Recipe: ST-08.

---

## 5. Build-level decisions that look like runtime knobs

Some streaming variables are read-only: their value is fixed at startup and
influences what is cooked. Changing them at runtime, or from a device profile,
does nothing and says nothing.

Before treating any streaming variable as tunable, check its flags. And never
A/B a read-only variable mid-session and compare the numbers — you are comparing
one configuration with itself. Recipe: ST-04.

Virtual textures belong in the same category. They change residency
characteristics fundamentally, their pool is separate from the streaming budget,
and a pool that does not grow on over-subscription produces thrashing rather
than an allocation. Enabling them for some content and not other content makes
budget comparisons invalid.

---

## 6. Device profiles: reachability before content

A profile hierarchy usually encodes platform base → tier → device. Three
failures recur, and all three are silent:

**A section that is never selected.** Defining a profile section does not make it
reachable; something must map to it. A tier section absent from the registry is
configuration that reviewers read as live. Recipe: ST-05.

**Headers that contradict assignment.** Comment banners grouping devices under a
tier label, while the devices beneath resolve to a different base profile. The
comment is documentation; the base profile is behaviour. Recipe: ST-06.

**An override list that no configuration populates.** A user-facing profile
variant list declared in code and set in no file means the selection logic
composes an empty name, the override is never applied, and the preset UI never
appears. Recipe: ST-07.

Gates: every profile section is reachable from the registry; tier assignment is
asserted by a dump, not read from comments; unknown hardware has a documented
fallback; every override hook has a real caller and real data.

---

## 7. Requested versus effective quality

A settings screen showing the user's request while a device profile clamps the
result is lying by omission. Model it explicitly:

```text
requested quality → platform clamp → effective quality → applied variables
```

Expose both, and give a reason when they differ.

### Unit-test every clamp at its range boundaries

The measured defect worth guarding against: a compatibility check comparing a
quality **level** (0–3) against a resolution **percentage** (default 100), so the
constraint can never fire. Its sibling function used the correct accessor, which
is what makes this findable — and what makes it invisible to review, since both
lines read identically. Recipe: ST-09.

Also check every normalisation for a zero denominator. A remap between two
ranges divides by their difference; a configuration that makes those equal is
reachable from data. Recipe: ST-10.

---

## 8. World content lifetime

### Level instances, not second worlds

Background and preview content is usually a level instanced into the **current**
world, not a second world. The cost is duplicated level content in one scene:
actors, components, primitives and their render resources.

Measure by scene composition — actor and primitive counts, visible material slots
— not by counting world contexts. "There is only one world" is true and
irrelevant.

### Ownership rules

Every streamed-in instance has one owner and an unload path; async handles are
retained and cancellable; failure surfaces a reason rather than a permanent wait;
teardown runs on travel, mode change and error.

### Hidden render targets

Scene-capture preview systems allocate render targets per capture object and may
keep rendering state resident between captures. Budget them explicitly: count ×
resolution × format, and verify release. A subsystem with no callers that still
instantiates per world and installs a ticker is paying for a feature nobody uses
— unused systems must decline creation.

### If runtime layer state is never set, it is not runtime streaming

Shipping editor-authored initial state is a valid choice. Describing it as
dynamic streaming is not, and a team that believes it has a reference
implementation will look for one that does not exist.

---

## 9. Review checklist

- [ ] Four budgets separated in every claim and every report.
- [ ] Pool settings never presented as consumption.
- [ ] Variable priority documented per quality knob, verified by a source dump.
- [ ] Tier overrides complete, or partial with a stated reason.
- [ ] Memory-clamp policy explicit per platform.
- [ ] Mesh and texture pool split decided per platform.
- [ ] Read-only variables identified before anyone tries to tune them.
- [ ] Every profile section reachable; assignment asserted, not commented.
- [ ] Requested and effective quality both visible, with a reason on divergence.
- [ ] Clamp logic unit-tested at both ends of its real range.
- [ ] Level instances owned, released and counted.
- [ ] Preview and capture render targets budgeted and released.
- [ ] Unused subsystems decline creation.

---

## 10. Measurement plan

Static first — cheap, and finds the structural problems:

1. Dump effective variables **with their source** per device profile, and diff
   against intent.
2. Verify every profile section is reachable from the registry.
3. List texture groups and their per-tier caps.
4. Search for runtime streaming and layer-state calls to confirm what is
   actually dynamic.

Runtime, on target hardware, in a packaged build:

- streaming stat for pool budget versus used and over-budget;
- platform GPU profiler for real video memory — the streaming stat cannot see
  most of it;
- **fixed camera poses** for any comparison; view-dependent metrics are otherwise
  noise;
- one run per tier on real devices, not emulated profiles alone;
- scene composition counts for level-instance cost.

**Do not compare numbers taken at different camera poses, different tiers, or
between editor and packaged builds.** Those comparisons look quantitative and
mean nothing.

---

## Provenance

The findings come from a configuration and source audit of Epic's Lyra Starter
Game on Unreal Engine 5.6, cross-read against the engine's own scalability and
device-profile configuration. Source addresses stay in the research archive that
produced this skill; each entry carries a stable identifier (`ST-01`, `ST-02`, …)
resolving back to the audited location there.

## Evidence boundary

Static configuration analysis only: no profiler was run, no device was measured,
and no number in the failure modes is a memory measurement. Engine defaults
quoted describe one engine version. The recipes are written to be re-run against
your own project and engine, which is the only way any of these values become
true for you.
