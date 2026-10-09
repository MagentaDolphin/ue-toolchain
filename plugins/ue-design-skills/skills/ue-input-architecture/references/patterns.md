# Patterns: tag-addressed input in a measured reference product

A worked example of the three-layer architecture from `SKILL.md`, measured in one
reference project. It exists to answer the question the norms cannot: **what does
this architecture actually cost, and what does it actually buy?**

The short version, and it is the reason this file is worth reading: the
architecture works, the composition benefits are real and measurable, and the
teardown half was never finished. Those three facts are not in tension. They are
what a reference project looks like.

Markers: **[measured]** — read in source or config; **[derived]** — conclusion
from measured facts; **[open]** — not answerable from source alone.

---

## 1. The shape, in one chain

```text
key
→ mapping context
→ input action
→ [payload: input tag]  handler on the hero component
→ ability system component buffers the spec handle
~~~ end of the input-processing step ~~~
→ controller post-process input
→ activation policy decides
→ activate
```

Seven hops, five of them across assets **[measured]**. That count is the whole
trade: it is why a feature plugin can add controls without touching the base
module, and it is why a broken binding takes an afternoon to diagnose.

---

## 2. What the split actually buys, with numbers

| Benefit | Measured evidence |
|---|---|
| Code cost per new ability control | **zero lines** — one loop binds every row of the config **[measured]** |
| Code cost per new native control | one explicit line; the project has exactly five and they have not changed **[measured]** |
| Feature-plugin controls without base-module edits | one plugin ships 11 input actions and its own config, and the base module contains no reference to them **[measured]** |
| One switch to suppress all ability input | a single tag on the ability system component clears the buffers and returns early **[measured]** |
| Same action, different ability per character | the join is a string in two assets; no code path is per-character **[derived]** |

The fourth row is the one most often underestimated. Without a semantic layer,
suppressing input during a menu means either a flag consulted in every handler or
unbinding and rebinding at runtime. Here it is one tag, checked once per frame,
in one place.

---

## 3. What it costs, also with numbers

**Compile-time errors become runtime silence.** The native path logs an error
when a tag cannot be resolved at bind time. The ability path has **no error case
at all** — the pressed tag is compared against granted specs, and no match is
indistinguishable from not having the ability **[measured]**. This asymmetry is
worth internalising as a triage rule: a silent native control is a config
problem; a silent ability control could be anywhere along the chain in §1.

**The lookup is exact, and everything around it looks hierarchical.** Both lookup
sites use exact tag matching **[measured]**, while the editor picker filters by
category and the vocabulary is a tree. A spec tagged with a parent is never found
by a press of its child. Nothing at either end of the join states this. Recipe:
IN-01.

**Two declaration sources for one namespace.** Native tags are C++ symbols;
ability tags are config strings; the two sets do not overlap **[measured]**. Both
are defensible individually. Together they mean no single artefact lists the input
vocabulary. Recipe: IN-02.

**Linear scans on every press.** The lookup iterates all activatable specs
**[measured]**. At the scale of this project that is free; it is proportional to
ability count times presses per frame, and neither number is bounded by the
design.

---

## 4. Teardown: the half that was not finished

This is the cluster worth studying, because the four findings compound into one
outcome and each looks minor alone.

| Finding **[measured]** | Alone | In combination |
|---|---|---|
| Bind handles declared as locals at two call sites and discarded | a missed `TArray` member | removal has no data to work with |
| The removal function's body is a single TODO comment | an unimplemented method | the feature action's teardown calls into it and returns successfully |
| A working `RemoveBinds` helper exists with **zero callers** | dead code | the mechanism was built and could never be reached |
| The context action's tracking list is read, iterated and removed from — and never written | an empty loop | contexts come off only reactively, so behaviour depends on teardown order |

**[derived]** Deactivating a feature leaves its ability bindings on a live pawn.
The practical damage is limited because pawns are recreated between matches and
because an orphan binding sends a tag that matches no spec — but the leak is real,
and a later re-grant of the same ability resurrects phantom input.

The instructive part is the third row. Someone wrote the removal helper. It is
correct. It has never been called, because the handles it needs were thrown away
one function earlier. **A correct utility that nothing can call is
indistinguishable from a utility that does not exist** — and it is worse, because
its presence answers "is removal supported?" with a yes.

The original authors had also left a comment on the broken tracking line noting
that the container is never modified **[measured]**. That is a known defect that
shipped, which is the most honest possible evidence for the general rule: *finding
a defect and fixing a defect are different projects, and reference code shows you
the first.*

Recipes: IN-03, IN-04, IN-05.

---

## 5. One flag, two operations — the sharpest single finding

In the base initialization path, the call that makes a mapping context **active**
sits *inside* the branch that checks whether the context should be registered with
the player's settings **[measured]**.

In the feature-plugin path for the same data structure, the two are separate: the
settings registration is skipped by the flag, and the activation call runs
unconditionally **[measured]**.

**[derived]** So the same checkbox means "expose this for rebinding" in one place
and "expose this for rebinding **and also make it work at all**" in another. Clear
the flag on a base mapping and the controls go silent, with no error and no
obvious connection between cause and effect.

Two properties make this the best example in the file:

1. **It is verifiable in ten seconds** by reading the two files side by side, and
   invisible in any amount of reading of either file alone.
2. **The correct version exists in the same codebase**, which removes any argument
   about intent. This is not a design decision applied inconsistently; one of the
   two is wrong.

Recipe: IN-06. The same initialization path carries a second nesting defect: the
loop over default mapping contexts is nested inside a check for the pawn's input
config, so a pawn with no config gets no contexts either and is completely mute
**[measured]** — two unrelated features disabled by one condition. Recipe: IN-07.

---

## 6. Initialization order as a broadcast dependency

Initialization clears **every** mapping on the subsystem before adding its own
**[measured]**. That includes contexts added by features that activated earlier.

Recovery works, and it works by broadcast: the component sets its readiness flag
and then sends a semantic "bind inputs now" event, which both feature actions
listen for alongside the generic extension event **[measured]**. Features re-add
what was just removed.

**[derived]** This is correct and it is fragile in a specific way: correctness is a
property of *event ordering* rather than of stored state. Nothing reconciles what
was cleared against what was restored, and a feature that is active but not
listening for the ready event loses its contexts permanently.

Worth copying from this: the readiness flag is set **before** the broadcast, not
after **[measured]**. A handler that checks readiness during the broadcast sees
true. That ordering is one line and it is the difference between the pattern
working and not. Recipe: IN-08.

---

## 7. Sediment: things that exist and do nothing

A reference project accumulates these, and each one costs a reader time:

- two mapping-management functions whose bodies contain only a check and a comment,
  called from the initialization path, doing nothing **[measured]** — the remains of
  a superseded settings API;
- a user-settings class and a key-profile class registered in config, both of which
  are empty overrides **[measured]** — extension points presented as features;
- a legacy axis-configuration block sitting beside the modern input system, whose
  deadzone and sensitivity values are overridden by modifiers that read player
  settings **[measured]**. A reader tuning the legacy values changes nothing.
  Recipe: IN-09;
- a settings-driven modifier that resolves a property **by name through
  reflection** **[measured]**, so renaming the underlying setting breaks it
  silently with no compiler involvement. Recipe: IN-10.

**[derived]** None of these is a bug. Collectively they are the reason "read the
reference and copy what it does" is a bad adoption strategy: a meaningful share of
what it does is nothing.

---

## 8. What the reference got right

1. **The payload trick.** Passing the semantic tag as a bound-delegate payload is
   what makes one function pair serve unlimited abilities **[measured]**. It is
   the single most portable idea in this file.
2. **Buffer then activate in one batch.** Collecting handles and activating after
   all input is processed removes event-order dependence, and the authors left a
   comment explaining precisely why — held input would otherwise activate an
   ability and then deliver a press event to it **[measured]**.
3. **Setting readiness before broadcasting it** (§6).
4. **Separate actions for mouse look and stick look**, with different tags and
   different handlers, because the stick needs frame-time scaling and the mouse
   does not **[measured]**. This is semantic distinction done correctly — not
   device sniffing in gameplay code, but two genuinely different commands.
5. **Device switching kept entirely out of the input layer.** The input module
   contains no reference to input-device types at all **[measured]**; device
   changes affect icons, haptics and UI style, and never gameplay bindings.

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6, read as source and
config in a single workspace: roughly 870 lines across the input module, plus the
hero component, two feature actions and the input configuration file. Blueprint
assets — the mapping contexts and input actions themselves — are binary and were
not read, so every statement here about which keys map to what is **[open]**.

Source addresses stay in the research archive that produced this skill; each
`IN-` identifier resolves back to the audited location there.

## Evidence boundary

These are examples and failure evidence from one project on one engine version,
not guarantees about others. The counts are properties of that project on that
day and are quoted to show the shape of a contrast, not to be imported. Re-run the
recipes against your own tree.
