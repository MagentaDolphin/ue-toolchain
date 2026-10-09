# Patterns: platform budgets in a measured reference product

A worked reading of one shipped platform-budget configuration: scalability
buckets, device profile tiers, streaming pools and the code that applies them.

This file is almost entirely about **configuration**, which makes it unlike the
others in this bundle in one important way: none of the findings below are bugs
in the usual sense. Every value is valid, every file parses, and the game runs.
What the audit produced is a list of places where the configuration says
something the runtime does not do — and the only reason any of it is findable is
that someone read the engine's own configuration alongside the project's.

Markers: **[measured]** — read in project or engine configuration and source;
**[derived]** — conclusion from measured facts; **[open]** — requires hardware.

**No number here is a memory measurement.** Nothing was profiled. Everything is
a declared budget, which is exactly the distinction the skill is about.

---

## 1. The single most useful table in the audit

What the project declares about the texture streaming pool, per mobile tier
**[measured]**:

| Tier | Pool declared by the project | Effective source |
|---|---:|---|
| Low | — | engine scalability bucket |
| **Mid** | **85 MB** | **device profile** |
| High | — | engine scalability bucket |
| Epic | — | engine scalability bucket |

The project sets the pool in exactly two lines — the mid tier of each mobile
platform — and declares **no** per-tier texture-quality sections of its own
**[measured]**. Every other tier inherits engine values, which on this engine
version run from several hundred megabytes to a gigabyte, with the
video-memory clamp disabled at the top **[measured]**.

**[derived]** Two consequences, and the second is the one that matters:

1. The tier with the smallest declared budget is the only tier the project
   actually configured. The rest are engine defaults that nobody chose.
2. Because a device profile applies at a higher priority than scalability, the
   mid tier's pool **cannot be changed by the in-game texture setting**, while
   on every other tier the same setting works. One control, opposite behaviour,
   no explanation anywhere in the UI.

That asymmetry is the reason ST-01 leads the failure modes. It is not a mistake
in either file; it is a mistake that only exists between them.

---

## 2. Priority, in one paragraph you can act on

Device profiles apply variables whose names carry the scalability prefix at
**scalability** priority, and every other variable at **device-profile**
priority — which outranks everything the settings system does **[measured, from
engine source]**.

**[derived]** So the same file produces two completely different mutability
outcomes depending on a naming convention:

- a prefixed quality bucket set in a profile is a **default** the player can
  override;
- an unprefixed variable set in a profile is a **lock**.

Nothing in the ini syntax distinguishes them. The audited project uses both
forms, mostly correctly and once consequentially (§1).

**The practical rule:** you cannot determine effective configuration by reading
files. Dump the variables with their source on the target device. That command is
the only authoritative answer, and it takes ten seconds.

---

## 3. Automatic detection promotes on the wrong axis

Promotion thresholds are expressed against a GPU performance index, for every
quality group, with **no memory term anywhere** **[measured]**. The texture group
reaches its top level at a low index value, and that top level is the one where
the engine disables the video-memory clamp on the pool **[measured]**.

**[derived]** A fast chip with modest memory therefore lands in the bucket that
grants the largest pool and removes the guard against it. The two decisions were
made in different files by different reasoning, and each is defensible alone.

The project's own comment on the thresholds is honest about their intent — tuning
so a specific generation of hardware lands in a specific mix **[measured]** — and
that intent is about throughput, which is exactly the axis that misses this.
Recipe: ST-02.

---

## 4. Dead configuration, and how much of it there is

Four independent instances, all silent, all reviewed at some point:

| Finding **[measured]** | What it means |
|---|---|
| A top-tier device profile section defined in full, absent from the profile registry and from the engine's base profiles | Every value in it is unreachable |
| Comment banners grouping devices under tier labels that contradict the base profile named two lines below | The documentation and the behaviour disagree; several devices sit under the wrong banner |
| A user-facing profile variant list read in three places and set in no configuration file | The profile override never applies; the console preset UI never appears |
| Optional mip levels configured in every mobile texture group, with chunk acquisition disabled | A high-resolution optional tier that cannot be delivered |

**[derived]** The common structure is worth naming, because it generalises far
beyond streaming: **configuration that names a mechanism the project does not
have.** It reads as a decision, survives review indefinitely, and produces
nothing. It is the configuration-file form of the stub described in
`ue-reference-project-adoption`.

Recipes: ST-05, ST-06, ST-07, ST-08.

---

## 5. Two arithmetic defects in the clamp layer

**A comparison between a percentage and a level.** A frame-rate compatibility
check obtains a resolution-quality limit — a percentage defaulting to one hundred
— and compares it against an overall quality level in the range zero to three
**[measured]**. The comparison is always satisfied, so the constraint never
binds.

**[derived]** What makes this findable rather than invisible is that the sibling
function two hundred lines away uses the correct accessor for the same purpose
**[measured]**. One of the two is wrong, and the codebase contains its own
counterexample.

**A remap with no guard on its denominator.** A normalisation between two
resolution ranges divides by the difference between a maximum and a minimum, with
no check that they differ, and the degenerate case is reachable from device
profile data **[measured]**.

Recipes: ST-09, ST-10. Both are three-line fixes and both would be caught by one
unit test each — which is the argument for testing clamps at their range
boundaries rather than at their typical values.

---

## 6. What the project got right

Worth stating, because the list above is long and the configuration is not bad:

1. **Cook-time budget levers are used deliberately.** Mobile texture groups clamp
   the maximum size sixteen-fold on a side, animation key stripping is enabled,
   and unused detail-mode components and emitters are pruned at cook
   **[measured]**. These are budget-A decisions, correctly separated from
   runtime budgets.
2. **Foliage density was moved between scalability groups deliberately**, with the
   old group's keys removed and a different curve applied in the new one
   **[measured]**. That is a real understanding of how the groups compose.
3. **Per-device resolution overrides on specific hardware** rather than a blanket
   platform value **[measured]**.
4. **Dynamic resolution configured for one mobile platform** with an explicit
   comment stating the target frame rate and output resolution **[measured]** —
   the kind of comment that makes a number reviewable.
5. **A rich set of runtime diagnostics** already wired: the profile selection
   logs its inputs and its chosen result, frame pacing logs its target, quality
   clamping logs both the before and after values **[measured]**. Someone
   arriving on a device has the answers available.

**[derived]** Point 5 deserves emphasis. Most of the findings in this file are
detectable in ten seconds on a device by reading log lines the project already
prints. The failure is not instrumentation; it is that nobody read the output.

---

## 7. What to copy, and what to check first

Copy: the four-budget separation as a documentation convention; cook-time levers
used per platform; the diagnostic logging around profile selection and clamping;
per-device overrides for outlier hardware.

Check first, in this order, on your own project:

1. **Dump variables with their source** on each target. Everything else is
   inference. (ST-01)
2. **Diff declared profiles against defined sections.** One command. (ST-05)
3. **Separate reads from writes** for every data-driven selection list. (ST-07)
4. **Unit-test every clamp** at both ends of its range. (ST-09, ST-10)
5. **Check both pool values** — texture and mesh — on every platform. (ST-03)

**[derived]** Steps 1 and 2 take minutes and would have found the two largest
findings in this file. That ratio is the argument for doing configuration audits
at all.

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6, read as project
configuration and source, cross-referenced against the engine's own scalability
and device-profile configuration and streaming source in the same installation.
Source addresses and engine paths stay in the research archive that produced this
skill; each `ST-` identifier resolves back to the audited location there.

## Evidence boundary

**Nothing here was profiled.** No device was measured, no memory figure is an
observation, and every quantity is a declared budget or a configured threshold.
Engine values describe one engine version and will drift. The recipes exist
precisely because these numbers must be re-derived on your project and your
hardware before they mean anything.
