# Patterns: a production GAS layer read end to end

A worked reading of one real Gameplay Ability System layer — roughly 4 900 lines
across 51 files — audited as source.

This file is different in balance from the other reference documents in this
bundle. Most of them are about what a codebase got wrong. **This layer is mostly
worth copying**, and the useful output is a list of the specific decisions that
earn their keep, each with the reason it was made. The defects are in
[failure-modes.md](failure-modes.md) and are fewer than the patterns.

Markers: **[measured]** — read in source; **[derived]** — conclusion from measured
facts; **[open]** — not answerable from source, and left open.

---

## 1. The shape of the layer

Two ability system components, on different owners, for different reasons
**[measured]**:

- one on the **player state**, with the pawn as avatar — so capabilities survive
  the pawn's death;
- one on the **game state**, with itself as avatar — which is what makes match
  phases possible at all (§5).

The only global hooks are three config lines **[measured]**: a replacement
globals class, a cue manager class, and an explicitly empty global curve table.
**[derived]** That is a remarkably small integration surface for a layer this
size, and the reason is that everything else is composed from data assets rather
than registered globally.

---

## 2. The ability set, and why the receipt is the whole idea

An ability set is a primary data asset holding three arrays: abilities, effects,
attribute sets **[measured]**. Grants happen in the order **attributes,
abilities, effects** **[measured]** — not cosmetic, since effects in the third
group may modify attributes created by the first.

Two details make it reusable rather than merely tidy:

**The input tag lives in the grant data, not in the ability** **[measured]**. The
same ability class can be bound to different semantic inputs by different sets,
and the ability itself hides the stock input category entirely **[measured]**.

**The revocation receipt.** The grant function takes an optional out-parameter —
three parallel arrays of handles — and the revoke function removes exactly those
**[measured]**:

```text
GrantedHandles
├─ AbilitySpecHandles          -> ClearAbility
├─ GameplayEffectHandles       -> RemoveActiveGameplayEffect
└─ GrantedAttributeSets        -> RemoveSpawnedAttribute
```

**[derived]** This is a cloakroom ticket. Whoever granted holds the ticket and can
undo exactly their own grant without touching anyone else's. It is the answer to
the question that breaks most modular gameplay implementations — *who removes
this, and how do they know it was theirs?*

Three consumers use it, and their differences are the design **[measured]**:

| Consumer | Receipt | Why |
|---|---|---|
| equipment | stored in the applied-item entry | must reverse on unequip |
| feature action | array per actor | must reverse on deactivation |
| pawn baseline on player state | **passes null** | intended to last as long as the player state |

**[derived]** The optional out-parameter is therefore an API that encodes a
lifetime decision. Passing null means "permanent, deliberately". One such call in
a project is a design; several are GA-01.

Authority is gated at the first line of both grant and revoke **[measured]**, and
invalid entries log with the asset name and index rather than crashing or
silently skipping **[measured]** — a small thing that turns a content error into a
searchable message.

---

## 3. Input as a buffered concern

Enhanced input does not call activation. It sends a semantic tag, the component
records spec handles, and one call per frame from the controller's post-process
input step does the work **[measured]**.

The ordering inside that call is the part to copy, and the reason is in the
authors' own comment **[measured]**: collect held abilities with the
while-input-active policy, then pressed abilities with the on-triggered policy,
**then activate everything in one pass**, and only then process releases. Activate
as you iterate and a held input first activates an ability and then delivers it a
press event it should never have seen.

Two more decisions worth taking:

- **A single global block tag** clears every buffer and returns early
  **[measured]**. Suppressing all ability input during UI, death or stun is one
  tag rather than dozens of disabled input actions.
- **Input events are replicated as events rather than directly** **[measured]**,
  with comments explaining that the wait-for-input ability tasks depend on it. A
  subtle choice that is easy to reverse by accident when copying.

---

## 4. Activation policy and exclusivity

Two small enums replace two large problems.

**Policy — when to activate** **[measured]**: on input triggered, while input
active, on spawn. **[derived]** Automatic fire, single fire and passives become one
enum in class defaults rather than three different implementations.

The spawn policy needs two entry points, not one — the ability granted to a live
avatar, and the avatar appearing for an already-granted ability — and the audited
implementation wires both **[measured]**, while skipping activation when the
avatar is being torn down **[measured]**.

**Group — how to relate to others** **[measured]**: independent, exclusive
replaceable, exclusive blocking. The component keeps per-group counts, cancels
other replaceable exclusives when an exclusive starts, and asserts that no more
than one exclusive is ever active **[measured]**.

**[derived]** Without this you express "firing cancels reloading, but the finisher
cancels nothing" as an N×N matrix of blocking tags on every ability. With it, one
enum plus one behaviour tag.

One invariant is enforced rather than documented: an ability in the replaceable
group **cannot** refuse cancellation — the call logs an error and does nothing
**[measured]**. **[derived]** That combination is a contradiction, and catching it
in code rather than in review is the difference between a rule and a convention.

The death ability is the worked example **[measured]**: on activation it cancels
everything not tagged as surviving death, refuses cancellation, and *moves itself*
into the blocking group for the duration.

---

## 5. Match phases as abilities

The highest return per line in the layer: about 330 lines of C++ for a
hierarchical match state machine **[measured]**.

A phase is an ability running on the game state's ability system component. While
the ability is active, the phase is active. The ability's defaults differ from the
base in exactly the two ways that matter **[measured]**: server-initiated
execution and server-only security. A client cannot start a phase.

**Hierarchy comes from tag nesting, and that is the entire rule** **[measured]**.
On starting a phase, every active phase whose tag does not match the incoming tag
is cancelled:

| Active | Starting | Result |
|---|---|---|
| `Game.Playing` | `Game.Playing.SuddenDeath` | parent stays, child starts |
| `Game.Playing`, `Game.Playing.SuddenDeath` | `Game.Playing.Overtime` | sibling ends, parent stays |
| `Game.Playing.*` | `Game.PostGame` | whole subtree ends |
| `Game.Playing` | second ability, same tag | both run |

**Parents and children coexist; siblings do not.**

What the pattern gets for free, because a phase is an ordinary ability
**[derived]**: ability tasks as phase timers and triggers, effects applied for the
phase's duration, cancellation by the same rules as anything else, and all of the
per-mode logic authored in data rather than in new C++.

One observer detail is worth copying deliberately: subscribing to a phase that is
**already active** fires the callback immediately **[measured]**. That closes the
classic race where a system subscribes after the phase started and waits forever.
The end-observer path has no equivalent **[measured]**, which is consistent —
there is no "already ended" to catch up on.

### And two limitations the authors recorded themselves

- **Observers return no handle** **[measured]**, with two consecutive comments
  above the function saying so — including the honest second thought that a handle
  would not help if callers ignored it. GA-05.
- **The subsystem's creation gate is commented out** **[measured]**, leaving an
  unconditional `return true`. So the subsystem exists on clients, where the
  active-phase map is always empty and the phase query always answers false.
  **[derived]** Client code must learn about phases through replicated tags,
  effects or messages — never through this subsystem. GA-04.

---

## 6. Attribute sets split by direction

Three classes on a clean axis **[measured]**:

- a base providing accessor macros and a six-parameter change delegate whose
  comment honestly warns that some parameters are null on clients;
- a **receiving** set: health, max health, and the meta attributes damage and
  healing;
- a **source** set: base damage, base heal.

The executions make the split structural rather than nominal **[measured]**: they
capture the source set from the instigator and write into the receiving set on the
target. **[derived]** The same actor usually owns both, but their roles in a
calculation are different, and that difference lives in the class layout instead
of a comment.

### The meta-attribute pattern

Incoming damage arrives in a non-replicated attribute, converts to a health change
in post-execution, and resets to zero in the same call **[measured]**.

**[derived]** Damage and healing become one-shot channels rather than state. They
need no replication, no manual reset, and no "current damage" that a reader might
mistake for something durable. Health and damage are additionally marked as hidden
from modifiers **[measured]** — so only an execution can change them, enforced by
the editor rather than by agreement.

### Three interception levels, each doing one job

**[measured]**: a pre-execution veto that can cancel the whole effect (where
damage immunity and a development-only god mode live, both respecting a
self-destruct exception so suicide still works); a post-execution step that
converts meta attributes, broadcasts change delegates and publishes a damage
message; and clamping applied in both change hooks with a shared helper.

A latch flag prevents a duplicate out-of-health broadcast and resets when health
recovers **[measured]** — the correct shape for GA-10.

### Where the damage number comes from

Four multiplications **[measured]**: base damage, distance attenuation, physical
material attenuation, and a team multiplier that is **0 or 1 rather than a
branch**. The two attenuation curves come from an interface implemented by the
damage *source* — the weapon — rather than from the execution. **[derived]** Falloff
therefore lives in weapon data where a designer owns it, and the execution stays
generic.

---

## 7. The death seam: three responsibilities, three classes

```text
effect execution changes Health
→ receiving set broadcasts out-of-health
→ health component sends a death gameplay event
→ death ability runs the sequence
→ health component enters DeathStarted, then DeathFinished
```

**[measured]** throughout. The division is the point:

- **GAS owns the number** — how much health, and the signal that it reached zero;
- **the health component owns the state** — a replicated enum with its own
  replication callback that can roll back a predicted transition and logs invalid
  ones;
- **the death ability owns the sequence** — what plays, when control returns.

**[derived]** None of the three knows the others' internals; they communicate
through delegates and a gameplay event.

Three details worth taking:

- the death trigger is configured in the ability's **class defaults**
  **[measured]**, so exactly one path can start it;
- the ability's end path **always** calls the finish transition **[measured]** —
  insurance against a designer-authored sequence that does not reach the end;
- death state is neither an attribute nor a tag but a replicated enum
  **[measured]**; the tags exist too, set loosely, because the state is already
  replicated by other means.

Alongside, a damage message and an elimination message go out over a message bus
**[measured]**, so kill feeds, statistics and accolades never reference GAS.

---

## 8. Two more things worth copying

**Composable costs.** The stock system offers one cost effect. Here, an ability
holds a list of inline cost objects, each with its own check, its own application,
its own failure tag, and an optional "only charge on hit" rule whose hit
determination is computed once, cached, and only on authority **[measured]**.
**[derived]** Ammunition, inventory items and player resources become three small
classes rather than three special cases.

**Failure reasons that reach the player.** The stock system swallows why an
activation failed. Here the component notifies the owning client when the avatar
is not locally controlled, the ability maps failure tags to user-facing text and
to animations through two data maps, and delivery goes over a message bus
**[measured]**. **[derived]** "Out of ammo" on the HUD costs no bespoke RPC, and
the UI never learns that GAS exists. GA-14.

---

## 9. Copy carefully

Two places where the audited implementation is explicitly provisional, and says so:

- **The relationship mapping is a linear array walk**, consulted on every
  activation and on every block-and-cancel application, with the same "simple
  iteration for now" comment in three separate functions **[measured]**.
  **[derived]** Fine at the size measured; profile before assuming it scales.
  GA-08.
- **Three function-static containers** are used as scratch space in a function on
  the activation path **[measured]**. **[derived]** Correct on one thread, not
  reentrant, and nothing at the call site says so. GA-07.

And one thing that reads as finished and is not: attribute initialization is a
placeholder that assigns health from max health in code, with a comment saying a
data-driven source will replace it **[measured]**. The global curve table is
configured to none **[measured]**, and the initialization-data field on the grant
structure has no traced consumer **[open]**. GA-11.

---

## 10. What source reading could not settle

- **Binary assets were not read.** The concrete phase abilities, the ability sets,
  the contents of the relationship mapping for each archetype, and the activation
  groups configured on real abilities are all **[open]**.
- **Who starts the first phase is unknown** **[open]**. A search for the start
  call finds only the subsystem itself, so the caller is in a scripted asset.
- **One field could not be classified from this layer alone**: a
  cancellation-logging flag is declared and assigned in the constructor and read
  nowhere in the audited directories **[measured]**. Whether something outside them
  reads it is **[open]** — though its own comment describes it as temporary,
  added while tracking a bug. GA-06.

---

## Provenance

Measured against the GAS layer of Epic's Lyra Starter Game on Unreal Engine 5.6,
read as source in a single workspace. Source addresses stay in the research
archive that produced this skill; each `GA-` identifier resolves back to the
audited location there, so any specific claim above can be produced on request.

## Evidence boundary

One project, one engine version, one workspace. Binary assets were not read, so
every statement about authored content is marked open rather than concluded. The
architecture is transferable; the specific defects are evidence, not guarantees
about other versions. Re-run the recipes in
[failure-modes.md](failure-modes.md) against your own tree before acting on
anything here.
