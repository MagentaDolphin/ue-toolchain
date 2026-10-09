# Patterns: a measured settings and performance layer

A worked example of `SKILL.md` against one reference product. The conclusion is
unusual enough to state at the top, because it changes what you should do with
the rest of the file:

> **The framework is the best thing in the audited project. The wiring around it
> is where every defect is.**

Roughly 5700 lines of settings framework contain no reference to the game that
ships it, and no finding in this file is about its design. The nine failure modes
are all in the 2100 lines of project-specific backend and registry that bind it —
paths that the compiler cannot check, a pipeline with no caller, a composition
part with no writer. That distinction is the adoption advice: **take the
framework, audit the wiring**.

Markers: **[measured]** — read in source; **[derived]** — conclusion from
measured facts; **[open]** — not answerable from source.

---

## 1. What the framework gives you, concretely

| Capability **[measured]** | Why it is hard to rebuild |
|---|---|
| Setting model fully separated from widgets | The separation is what makes search, grouping and testing possible at all |
| Widget resolved by walking the model's **superclass chain** | Map one base class, cover every derived setting, keep specific overrides |
| Apply / cancel / reset as a real transaction over a dirty set | Correct restore of *runtime* state, not only stored values |
| Edit conditions with five outcomes, not a boolean | disabled-with-player-reason, hidden-with-developer-reason, single option disabled, killed |
| Cascading dependencies between settings | Changing one setting re-evaluates the others without hand-written wiring |
| Full-text search over rich text reduced to plain text | Falls out of the model separation |
| Asynchronous readiness before the screen renders | Audio device lists and cloud values arrive late; the screen waits |
| A debug mode that shows developer names and classes in the UI | Makes every other finding in this file findable |

**[derived]** The five-outcome edit condition is the piece most worth
internalising even if you write your own framework. Hand-built settings screens
almost universally have a boolean, and the two missing things — *tell the player
why it is disabled* and *tell the developer why it is hidden* — are exactly the
two questions asked later at cost.

---

## 2. The trade the framework makes, and where it lands

Bindings are **string paths resolved by reflection** — a getter and setter path
rooted at the local player **[measured]**. That removes a class per setting and
removes the compiler from the relationship.

The failure mode is precise: the stringification macro checks that a function
*name* exists, not its type, arity or constness; mismatches surface as an
assertion at registry initialization; **assertions are compiled out of shipping**
**[measured]**.

**[derived]** So the worst case is a shipping build where a setting reads a
default and writes nowhere, with no diagnostic anywhere. That is not an argument
against the design — it is an argument for one automated test that walks the
registry and resolves every path. Recipes: GS-01, GS-02.

---

## 3. The ownership split, and the leak inside it

The design is a clean two-store split **[measured]**:

| | Machine-local | Player-shared |
|---|---|---|
| Base | engine user settings, ini | per-player save game, cloud-syncable |
| Holds | resolution, quality, frame limits, device profile, benchmark result | colour-blind mode, sensitivities, subtitles, language, haptics |

The authors state the rationale in a comment: shared settings are safe to put in
the cloud and are stored per player, so controller preferences belong there
rather than in local settings where every user would receive them **[measured]**.

Then the accessor breaks it. The per-player getter for local settings returns a
**process-global singleton** **[measured]**.

**[derived]** "This player's local settings" is a fiction; there is one object per
process. The corroborating evidence is structural rather than a second defect:
the registry is dense with "only while playing as the primary player" conditions,
which is the architecture apologising for the accessor. Recipe: GS-03.

A second, milder leak in the same area: audio volumes live in machine-local
storage **[measured]** — a pure player preference placed by where the applying
subsystem reads, not by what the value means. The audio registry reaches into
both stores from adjacent lines. Recipe: GS-04.

**[derived]** Both are worth seeing together, because they are the same mistake at
two scales: **storage placed by implementation convenience rather than by
semantics**, then papered over at the call sites.

---

## 4. Three findings that are the same shape

This is the most transferable observation in the file. Three unrelated features,
one structure:

| Feature | Present **[measured]** | Missing **[measured]** |
|---|---|---|
| Automatic quality detection at first launch | capability check, benchmark, threshold mapping, apply, save | **any caller** of the decision function |
| Per-game-mode device profiles | name composition, fallback chain, four candidate forms, logging | **any writer** of the mode suffix |
| Input sensitivity application | storage, dirty tracking, save, load, an apply function | **a body** in the apply function |

**[derived]** Each is complete except for one link, and in each case the missing
link is invisible to every check that the rest of the feature passes. The
decision function has two occurrences — its declaration and its definition. The
suffix has six occurrences, of which one is a log line printing it and none is an
assignment. The apply function is called correctly from the right place and
contains nothing.

The suffix case deserves emphasis because it is the canonical shape from
`ue-reference-project-adoption` appearing in a subsystem where the consequence is
architectural: **a variable read four times and written zero times**, with the
authors' own comment noting that nothing sets it. Any search asking "is this
used?" answers yes, loudly. Recipes: GS-06, GS-07, GS-08.

---

## 5. Where the transaction leaks

Video settings apply **immediately from inside a change notification**, not on
apply, and the code says so with a comment reading "for now" **[measured]**.

**[derived]** Cancel still restores the value, so the transaction is not broken —
it is leaky in a way the player sees: a preview they did not ask for, on a global
apply path, potentially once per slider tick.

The comment is what turns this from a judgement call into a finding. **A "for
now" on a global apply path is a scheduled item.** Recipe: GS-05.

---

## 6. The upgrade guard, and the number it does not tell you

Manual enumeration of an engine struct's members — copying, clamping and
maximising quality levels field by field — is protected by a compile-time
assertion on the struct's size, at **five separate sites** for one struct
**[measured]**.

**[derived]** This is good practice and it works: after an engine upgrade adds a
quality channel, the build breaks rather than silently ignoring it. The gap is
procedural. The person who hits the assertion during an upgrade needs to know
*how many functions* must be reviewed, and that number is nowhere near the
message. Recipe: GS-09.

**Put the count in the assertion text.** A guard is only as useful as the
instruction it gives the person it stops.

---

## 7. The reapplication point, and why it is where it is

Global scalability is reapplied at the **last line** of the mode-load completion,
after the load state is set and after all three waves of load notification
**[measured]**. The same function serves the other trigger that changes the same
state — a hotfixed device profile **[measured]**.

Four reasons, all measured, and together they are a small lesson in ordering:

1. feature plugins activated by the mode can change console variables and
   frontend policy, so effective values are unknown until they have all run;
2. the device profile itself may change, and the reapplication reselects it;
3. scalability is process-global, not per world — the authors note this in a
   comment explaining why they do not track it per world in multi-instance
   editor play;
4. it is guarded off for servers, where render settings are meaningless.

**[derived]** Two different causes — mode loaded, profile hotfixed — reduced to
one idempotent reaction at one named point. That arrangement is worth copying
directly, and it is the opposite of letting each feature reapply what it thinks
it changed.

---

## 8. Performance statistics: one collector, and the honest limits

Statistics come from the engine's own frame-data consumer interface rather than
from hand-rolled timers **[measured]**, feeding a ring buffer for graphing.
Eighteen statistics, with a compile-time count assertion in three places
**[measured]**.

**[derived]** The design point worth copying is that presentation and collection
are separate: widgets read a cache, and no widget collects. The design point worth
questioning before copying is that a buffer size is meaningless without a
documented sample cadence — a hundred-odd samples describes a window only once you
know the interval.

Two hard couplings to be aware of before lifting the subsystem: one statistic
reads a game-specific state class, and latency statistics are gated on a specific
GPU vendor because the project integrates one vendor's plugin **[measured]**.
Both are small and both are visible; neither is a reason to rewrite the rest.

---

## 9. What to copy, in order

1. **The framework itself**, if the UI dependency is acceptable. Five-outcome edit
   conditions, superclass-chain widget resolution, the change tracker, async
   readiness.
2. **The reapplication point** (§7) — one idempotent function, two causes.
3. **The two-store split** (§3) — but decide placement by semantics and check
   your accessor's body before trusting the word "local".
4. **The size-guard discipline** (§6), improved by writing the count into the
   message.
5. **Collector/presenter separation** for statistics (§8).

Audit before shipping: every property path resolves (GS-01, GS-02); the accessor
is not a singleton (GS-03); every apply function has a body (GS-06); every
composition part has a writer (GS-07); every pipeline has a caller (GS-08).

**[derived]** That list is short, mechanical, and would have caught every defect
in this file. None of it requires understanding the framework — which is the
point of shipping recipes rather than conclusions.

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6 and the settings
plugin shipped with it: roughly 5700 lines of framework, 2100 of project settings
backends, 2000 of registry, and 800 of performance code, read as source in a
single workspace. Source addresses stay in the research archive that produced
this skill; each `GS-` identifier resolves back to the audited location there.

## Evidence boundary

Widget assets are binary and were not read, so nothing here describes the
presentation layer beyond its base classes. Configuration values quoted describe
that project on that day. Re-run the recipes against your own tree.
