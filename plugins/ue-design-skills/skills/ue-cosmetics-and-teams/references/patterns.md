# Patterns: cosmetics and teams in a measured reference product

A worked example of both halves of `SKILL.md` against one reference project read
as source. The two systems are presented together because the audit found what
the skill claims: they touch at exactly one point, and both are well built on
either side of it.

This file is unusually positive. That is the finding, not a tone: the
architecture here is the strongest in the audited project, and the defects are
narrow and specific. Separating "this design is worth copying" from "this
implementation is finished" is the entire job.

Markers: **[measured]** — read in source; **[derived]** — conclusion from
measured facts; **[open]** — not answerable from source, because the call site is
in a binary asset.

---

## 1. The two-level split, and what it buys

```text
controller component     owns the desired part list, survives respawn
      │  on possession change: remove from old, apply to new, keep handles
      ▼
pawn component           replicated list, spawns presentation, computes tags
```

The controller component subscribes to possession changes **only on the
authority**, and if a pawn already exists at subscription time it invokes its own
handler with a null previous pawn **[measured]**. That second detail is the
pattern's whole robustness: the same code path handles "pawn already here" and
"pawn arrives later", so ordering stops mattering.

Transfer removes by handle from the old pawn and re-applies to the new, guarding
against double-add by checking whether the handle is already valid **[measured]**.

**[derived]** This generalises well beyond appearance. Any state that belongs to
the *player* and is realized on the *body* — loadouts, perks, temporary buffs —
has the same shape and the same failure mode if you skip it: the state dies with
the pawn.

The link from controller to pawn is found dynamically each time, with no cache
**[measured]**. If the pawn has no cosmetics component the lookup returns null and
nothing happens, silently — a tolerance that is correct for optional cosmetics and
would be wrong for anything required.

---

## 2. Replicating intent, with the split declared in the type

One structure carries both server-only and client-only fields, distinguished by
annotation rather than by having two types **[measured]**:

| Field | Replicated | Lives on |
|---|---|---|
| the part itself: class plus socket | yes | server → clients |
| the handle returned to the caller | **no** | server only |
| the spawned presentation component | **no** | client only |

**[derived]** This is the cleanest available demonstration of "replicate intent,
realize locally". The wire carries a class reference and a socket name; the
receiving machine reconstructs the appearance. Late join is deterministic because
the state is compact and complete.

Change handling is deliberately coarse: the change callback destroys and respawns
rather than propagating a diff, and the authors say so in a comment
**[measured]**. Recipe: CT-02.

Part identity is defined as the pair (class, socket) and deliberately **excludes**
the collision mode from the comparison **[measured]** — so two requests differing
only in collision are the same part. **[derived]** That is a real decision about
what identity means, made once, in the comparison function where it belongs.

---

## 3. The isolation guarantee, stated precisely

One line excludes presentation from the dedicated server, and it is the only such
line in the module **[measured]**.

**[derived]** The consequence is strong and worth stating exactly: on a dedicated
server the cosmetic actors do not exist, so they cannot collide, block a trace,
tick, or influence the authoritative simulation in any way. That is a real
architectural guarantee obtained for one `if`.

It is also narrower than the sentence people repeat. On a listen server or in
standalone the parts exist on the authority, with whatever their class contains,
and nothing in the type system prevents a part class from carrying an ability
system or enabled collision. The other protections — collision defaulting to off,
authority-only mutators, no ability-system includes anywhere in the module
**[measured]** — are conventions and content discipline. Recipe: CT-01.

**The honest form:** *not present on a dedicated server*, not *cannot affect
gameplay*.

---

## 4. The ten-line pattern worth stealing

An array of rules, each an asset plus a set of required tags, plus a default.
Gather tags, walk the rules in order, first rule whose tags are **all** present
wins, otherwise the default **[measured]**.

It appears at least three times in the audited project — body mesh, forced
physics asset, and weapon animation layer **[measured]** — and costs roughly ten
lines each time.

**[derived]** Its sharp edge is that priority is array order, with no weights and
no specificity ranking. A broad rule above a narrow one silently shadows it, and
the failure produces a plausible wrong asset rather than an error. Recipe: CT-03.

The tag namespace is declared in config and is deliberately small — a body style
and two animation styles **[measured]**. **[derived]** Small is the right size:
every tag in this namespace multiplies the rule matrix that has to be reasoned
about.

---

## 5. Where the two systems touch

Exactly one place, and the code says so. The cosmetics component broadcasts a
change with a comment noting that observers may need to apply team colouring
**[measured]**; the team display asset applies material parameters to an actor
**and its child actors by default** **[measured]** — and cosmetic parts are child
actors.

**[derived]** That default is what carries team colour onto modular parts. It is
one boolean default, and it is the seam.

**[open]** The actual call is made from a Blueprint: the applying function has no
C++ caller. Which leads to the most important methodological point in this file.

---

## 6. What could not be answered, and why that matters

Four things in this subsystem have **no C++ call site** **[measured]**:

- who applies team colours to an actor;
- who selects the weapon animation layer from cosmetic tags;
- where the cosmetics component is added to a pawn;
- where the controller component is added to a controller.

All four are wired in Blueprint or data assets, which are binary and were not
read.

**[derived]** The correct conclusion is *"the wiring is in a place this audit
cannot see"*, and the incorrect one — available, tempting, and wrong — is *"this
function is unused"*. Both components are marked as spawnable from Blueprint
**[measured]**, which is positive evidence for the first reading.

This is the general rule from `ue-reference-project-adoption`, met in its natural
habitat: **absence of a C++ caller is not absence of a caller.** Anyone deleting
"dead" code in a project with a large Blueprint surface needs the editor's
reference viewer, not a text search.

---

## 7. Teams: one source, mirrors that refuse loudly

Membership lives on the player state, replicated push-based, authority-only, with
a non-authority write logged as an error **[measured]**.

Every mirror — controller, bot controller, local player, pawn — reads through to
the source, and their setters **log an error naming the real owner** rather than
silently doing nothing **[measured]**.

**[derived]** This is the single most copyable line in the team system. A silent
no-op setter on a mirror is indistinguishable from a working one until something
depends on it; an error line converts an invisible failure into a searchable one,
at a cost of one statement. Recipe: CT-06.

The pawn mirror is more subtle and also correct: it accepts a direct write **only
while unpossessed**, and refuses with an explanatory error once a controller owns
it **[measured]**. On possession it takes the controller's value and subscribes to
its change delegate; on unpossession it unsubscribes and calls an overridable hook
whose default is "no team" **[measured]**.

**[derived]** That hook is an extension point placed exactly where a neutral
faction would need it, which is the difference between a design and an
implementation that happens to work.

---

## 8. Resolution, comparison, and the one permissive branch

Resolution is a four-step cascade — interface, instigator, team-info actor,
associated player state **[measured]**. **[derived]** The instigator step is what
lets projectiles and area effects carry the shooter's team without owning one; a
design that omits it grows a team field on every projectile.

Comparison returns three states rather than a boolean **[measured]**, which is
correct and is what makes the next finding visible at all.

The damage rule permits four ways **[measured]**, and the third is the finding:
when the relationship is indeterminate, damage is allowed if the target has an
ability system component — with an author's comment marking it temporary until a
training dummy gets a team assignment.

**[derived]** It exists to make one specific actor damageable and it generalises
to every unassigned actor with an ability system. Harmless while the only such
actor is a dummy; a rule violation the moment a neutral faction or a destructible
objective exists. **Solve it in data — give the dummy a team — rather than in the
rule.** Recipe: CT-08.

Friendly fire is promised by a header comment and implemented nowhere: a
project-wide search for any friendly-fire symbol returns **zero** **[measured]**.
Allies are unconditionally safe. Recipe: CT-07.

---

## 9. One policy function, two consumers — the pattern to copy

The same permission function is called by the authoritative damage calculation
and by the client-side decision to show a hit marker **[measured]**.

**[derived]** This removes an entire bug class by construction. "The client showed
a hit and the server dealt no damage" requires two implementations of one rule to
disagree, and here there is only one implementation. Any project with predicted
feedback should copy this arrangement before copying anything else in the team
system.

The damage calculation consumes the result as a **0-or-1 multiplier** in the
formula rather than as an early return **[measured]**. **[derived]** The team rule
becomes an ordinary participant in the arithmetic, alongside distance and surface
attenuation, which keeps the execution pipeline uniform and makes the rule easy to
soften later — a scalar between zero and one is already expressible.

---

## 10. Presentation as named parameters

The display asset is a bag of named material parameters — scalars, colours,
textures, a short name — not a set of assets **[measured]**. Materials are
authored to expect the names, so adding a team costs one asset rather than a
duplicated material tree.

Two defects in the applying code, both narrow:

- **Alpha is dropped** by the material paths, which convert a four-channel colour
  to a three-element vector, while the effects path preserves all four
  **[measured]**. The same asset therefore behaves differently in two consumers.
  Recipe: CT-09.
- **A viewer identity parameter is accepted and ignored**, with a comment saying
  so **[measured]**. The signature and header describe viewer-relative colouring;
  the implementation returns the absolute asset. Recipe: CT-10.

Reactive binding is done well: an observation action broadcasts **immediately on
activation** so a late subscriber gets current state rather than waiting for the
next change, and a second action re-subscribes correctly when the observed team
changes **[measured]**. **[derived]** Both are small patterns that eliminate a
race, and both are reusable anywhere state is observed through a key that can
itself change.

---

## 11. What to copy, in order

1. **One policy function for authority and prediction** (§9). Highest value,
   lowest cost, removes a whole bug class.
2. **Loud mirrors** (§7). One log line per setter.
3. **Controller-owned intent, pawn-owned realization** (§1), including the
   already-possessed case.
4. **Non-replicated fields inside a replicated entry** (§2) — one type instead of
   two.
5. **Rules-plus-default selection** (§4), with a shadowing check added.
6. **Immediate first broadcast on subscription** (§10).

What to fix while copying: the indeterminate branch (CT-08), the friendly-fire
gap (CT-07), the alpha conversion (CT-09), the ignored viewer parameter (CT-10),
and the privacy that is a name rather than a mechanism (CT-11).

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6: roughly 1300
lines of cosmetics across 11 files and 1800 lines of teams across 22, read as
source in a single workspace. Source addresses stay in the research archive that
produced this skill; each `CT-` identifier resolves back to the audited location
there.

## Evidence boundary

Four wiring call sites are in Blueprint or data assets and were not read; they are
marked open above and nothing here depends on them. Everything else describes one
project on one engine version. Re-run the recipes against your own tree before
trusting any specific claim.
