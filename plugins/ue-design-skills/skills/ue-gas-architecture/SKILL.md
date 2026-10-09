---
name: ue-gas-architecture
description: >-
  Design or review production Gameplay Ability System architecture in Unreal
  Engine: ability packages and revocation receipts, buffered ability input on
  the ability system component, activation policies and exclusivity groups,
  attribute set responsibility boundaries, gameplay effect contexts, tag
  relationship policy, match phases as abilities, and the health/death seam.
  Use when adding combat, abilities, equipment-granted powers, phases or rounds,
  damage and healing, or diagnosing ability activation and lifecycle bugs.
---

# UE GAS architecture

The invariant:

> GAS owns capabilities and effects; domain components own durable gameplay
> state; data packages compose capabilities; every temporary grant keeps a
> receipt.

Worked analysis of a production GAS layer, including the parts worth copying
verbatim: [patterns](references/patterns.md).
Detection recipes for silent GAS failures: [failure modes](references/failure-modes.md).

Related skills: `ue-data-driven-architecture`, `ue-input-architecture`,
`ue-modular-gameplay`, `ue-cosmetics-and-teams`, `ue-multiplayer-authority`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Package grants as ability sets

Do not scatter calls to grant abilities, apply effects and add attribute sets
across pawns, equipment and modes. Define one immutable capability package:

```text
AbilitySet
├─ abilities: class + level + optional semantic input tag
├─ gameplay effects: class + level
└─ attribute sets: class
```

The same package can be granted by pawn data at spawn, by an equipment
definition while equipped, by a feature action for a mode, by a pickup, or by a
test fixture.

### Grant order is not cosmetic

Attributes, then abilities, then effects. Effects in the third group may modify
attributes created by the first; the reverse order silently applies modifiers to
attributes that do not exist yet.

### Grant only on authority

The package's grant function must reject non-authority mutation at its first
line. Clients receive replicated specs, effects and attributes; they do not
author grants.

### Return a grant receipt

```text
GrantedHandles
├─ AbilitySpecHandles
├─ ActiveGameplayEffectHandles
└─ GrantedAttributeSet pointers
```

The revoke function removes exactly those resources. This is what prevents one
equipment item from revoking another owner's grants — and it is the single most
reusable piece of a GAS layer.

### Decide permanence explicitly

Passing no receipt means "grant for the lifetime of the ability system
component". That is a legitimate design choice, and it must be a choice rather
than an omission. Review every caller:

| Caller | Receipt required? |
|---|---|
| pawn baseline from pawn data | optional, permanent by design |
| equipment | yes |
| feature action | yes, per actor and per activation context |
| temporary pickup | yes, or rely on effect duration handles |
| test or cheat command | yes |

A single reference implementation demonstrates both: the pawn baseline passes
nothing because it is meant to last as long as the player state, and equipment
passes a receipt stored in its own applied-item entry.

---

## 2. Treat input as a buffered concern of the ability system component

Input events should not call activation directly. Send a semantic input tag to
the ability system component and process once per frame after player input:

```text
InputAction
→ InputTag pressed/released
→ ASC records spec handles
→ PlayerController.PostProcessInput
→ ASC.ProcessAbilityInput
→ activation policy chooses the activation set
→ TryActivateAbility
```

What this buys:

- simultaneous inputs resolve together instead of in binding order;
- held input is distinguishable from newly pressed input;
- activation can be suppressed globally for a frame;
- activation policy belongs to the ability rather than to each binding site.

### Required buffers

Held spec handles, pressed this frame, released this frame. Clear the transient
buffers after processing, and drop stale handles when specs are removed.

### Order within the frame matters

Collect held abilities first, then pressed, then activate everything in one pass,
and only then process releases. Activating as you iterate means a held input can
activate an ability and then immediately deliver it a press event it should never
have seen.

### Add a global input block tag

When a project-defined "ability input blocked" tag is present on the component:
clear the buffers, activate nothing, and define explicitly whether already-active
held abilities receive a release or a cancel. One tag is cheaper and far more
reviewable than disabling dozens of input actions during UI, death or stun.

---

## 3. Put activation rules on the ability

### Activation policy — when

- `OnInputTriggered` — activate once when pressed;
- `WhileInputActive` — activate and retry while held;
- `OnSpawn` — activate when granted and the avatar is ready.

Do not infer these from the input event type at the binding site. The ability
knows its own lifecycle; the binding does not.

`OnSpawn` needs two entry points, not one: the ability may be granted to a live
avatar, or the avatar may appear for an already-granted ability. Handle both, and
skip activation when the avatar is being torn down.

### Activation group — concurrency

- `Independent` — unaffected by others;
- `Exclusive_Replaceable` — exclusive, but another exclusive may displace it;
- `Exclusive_Blocking` — exclusive and prevents other exclusives from starting.

The component tracks active counts per group and enforces transitions. This
replaces an N×N web of per-ability blocking tags for broad concurrency rules.

Rules:

- an ability may enter a group only if not blocked;
- entering an exclusive group cancels other replaceable exclusives;
- group counts must balance across activate and end;
- an ability in a replaceable group must not be able to refuse cancellation —
  that combination is a contradiction and should log rather than obey;
- changing group at runtime is explicit and validated.

Death is the clearest worked example: on activation it cancels everything not
explicitly marked as surviving death, refuses cancellation, and moves itself into
the blocking group for the duration.

---

## 4. Move tag relationships into a policy asset

Abilities carry their intrinsic tags. A pawn or archetype selects a relationship
map:

```text
AbilityTag
├─ tags to block
├─ tags to cancel
├─ activation required tags
└─ activation blocked tags
```

This removes repeated policy from N ability defaults and lets the same ability
classes run under different archetype rules. It matters most when abilities
arrive from separate feature plugins that must not know about each other.

### Relationship validation

- [ ] the key tag is valid and appropriately scoped;
- [ ] parent-tag matching is intentional, not incidental;
- [ ] block and cancel are not confused with each other;
- [ ] required and blocked sets are not contradictory;
- [ ] cycles are documented and tested;
- [ ] every archetype that needs policy actually selects a map.

A linear scan is acceptable for a small matrix. Profile before assuming it scales:
in the measured reference the lookup is a linear array walk performed on every
activation and on every block/cancel application, and its authors marked it as
provisional in three separate places.

---

## 5. Split attribute sets by direction of responsibility

Do not create one character-attributes dumping ground.

**Receiving set.** Health, max health, the meta attributes damage and healing,
clamping, and the out-of-health signal. Damage and healing are transient inputs
to execution, not durable replicated state: they arrive, convert into a health
change, and reset to zero in the same call.

**Source set.** Base damage, base heal, outgoing coefficients — the values
captured *from the instigator*.

Execution calculations capture the source set from the instigator and the
receiving set from the target. The split makes "who contributes this value"
structural rather than a comment.

### Gates on the receiving set

- clamp in the correct hook, and in all of them that can change the value;
- guard against duplicate out-of-health events with an explicit flag that resets
  when the value recovers;
- record pre-execution values when messages need a before-and-after;
- notify domain components through delegates;
- keep game-flow state — death started, death finished — out of the attribute set
  entirely.

### Mark what modifiers must not touch

Attributes that may only be changed by an execution should say so in metadata.
This is the difference between "we agreed not to modify health directly" and a
rule the editor enforces.

---

## 6. Extend the gameplay effect context for combat metadata

When damage needs source or target data beyond the stock context, derive a
project context and implement allocation, script-struct identity, duplication and
network serialization.

Store only what must survive execution and replication. A context is not a place
to hang a mutable combat object graph.

Validation:

- [ ] the context survives duplication with its custom fields intact;
- [ ] custom fields serialize deterministically;
- [ ] object references are network-safe, and fields that are deliberately not
      replicated are documented as server-only at their declaration;
- [ ] execution calculations handle absent hit data;
- [ ] script exposure does not permit invalid mutation.

---

## 7. Separate numeric death detection from the death lifecycle

```text
effect execution changes Health
→ receiving set emits out-of-health
→ health component sends a death gameplay event
→ death ability starts
→ health component enters DeathStarted, then DeathFinished
→ game mode handles respawn
```

Responsibilities: GAS owns the *number*; the health component owns the *state*
and its replication; the death ability owns the *sequence*; the game mode owns
the player lifecycle.

Do not represent death only as "health is zero". Consumers need a monotonic state
they can observe over the network, and a predicted transition needs somewhere to
be corrected.

### The death trigger must be unambiguous

Configure it in the ability's class defaults so exactly one path can start it, and
have the ability's end path force the final transition — insurance against a
designer-authored sequence that does not reach the end.

---

## 8. Model match phases as abilities when the lifecycle fits

A phase ability runs on the ability system component of the game state:

```text
Game.Playing
├─ Game.Playing.Warmup
├─ Game.Playing.SuddenDeath
└─ Game.PostGame
```

Starting a phase grants and activates the ability, registers its tag, cancels
incompatible siblings, and notifies observers. Ending the ability ends the phase.

Hierarchical tags give the rule for free: **parents and children coexist, siblings
do not.** Starting `Game.Playing.SuddenDeath` while `Game.Playing` is active
leaves the parent running; starting `Game.PostGame` ends the whole subtree.

### Use this pattern when

- the phase has a real enter/active/exit lifecycle;
- ability tasks, effects and tags are natural fits for its logic;
- the server owns transitions;
- observers want tag-based matching rather than an enum switch.

### Do not use it when

- a replicated enum fully describes the state;
- the phase must never be cancellable;
- clients must query authoritative phase state and no replication path has been
  designed for it. This is the trap: if the phase abilities are server-only, a
  client-side query of "is this phase active" answers false forever, and it
  answers it without an error.

### Observer handles are mandatory

Registration returns a handle and supports unsubscribe. An array of callbacks
with no handles grows until the world resets, and every entry pins whatever it
captured.

---

## 9. Failure feedback belongs at the ability system seam

Activation failure should produce structured tags, not a log line:

```text
Ability.ActivateFail.Cooldown
Ability.ActivateFail.Cost
Ability.ActivateFail.TagsBlocked
Ability.ActivateFail.IsDead
```

For a locally controlled avatar, route them straight to feedback. For a
server-side rejection of a locally predicted action, notify the owning client with
the ability and the failure tags. Map tags to user-facing text and to animations
in data, and deliver them over a message bus so the UI never learns about GAS.

Never parse log strings in UI.

### Compose costs rather than accepting one

A single cost effect is rarely enough. A list of inline cost objects — each with
its own check, its own application, its own failure tag, and an optional
"only charge on hit" rule — turns cost into data. The hit determination should be
computed once and cached, on authority only.

---

## 10. Equipment and feature integration

Equipment grants ability sets when equipped and retains the receipt in its
applied-item entry. Unequip reverses exactly that receipt.

A feature action that grants abilities retains, per actor: direct ability handles,
attribute instances, ability-set receipts, and the extension request handle.

Every integration answers:

- Who owns the ability system component — the pawn or the player state?
- Which object is the source object for the spec?
- When is avatar info initialized?
- Is the grant permanent or reversible?
- What happens if the actor is destroyed before the feature deactivates?

See `ue-modular-gameplay` for actor-extension timing and rollback.

---

## 11. Review checklist

### Ability set

- [ ] authority-only grant, checked at the top of the function;
- [ ] grant order is attributes, abilities, effects;
- [ ] every class reference non-null and of the expected type;
- [ ] semantic input tag valid and constrained;
- [ ] receipt retained for every temporary grant;
- [ ] revoke removes only owned resources;
- [ ] source object deliberately chosen.

### Ability system component

- [ ] input buffers processed once per frame, after player input;
- [ ] blocked-input behaviour explicit for held abilities;
- [ ] activation group counters balance;
- [ ] avatar change activates spawn-policy abilities exactly once;
- [ ] relationship map selected per archetype;
- [ ] failure tags reach local feedback.

### Attributes and damage

- [ ] source and target responsibilities separated into different sets;
- [ ] meta attributes are not treated as durable state;
- [ ] clamping occurs in every path that can change the value;
- [ ] team and friendly-fire rules applied in one authoritative calculation;
- [ ] out-of-health cannot fire twice for one death;
- [ ] custom effect context serializes.

### Phases and death

- [ ] the server owns transitions;
- [ ] observers can unregister;
- [ ] sibling and parent tag semantics are tested, not assumed;
- [ ] clients have a defined observation path that does not depend on a
      server-only subsystem;
- [ ] death start and finish are durable states, not health comparisons.

---

## 12. Decision summary

Use GAS for a concern when at least one is true: it is a grantable and revocable
capability; prediction or networked activation matters; it is naturally expressed
through effects, tags, cost and cooldown; it benefits from task-based lifecycle
with cancel and end.

Keep it out of GAS when the concern is durable domain state better served by a
replicated component, presentation only, static definition composition, or a
global lifecycle with no ability semantics.

A production GAS architecture is not "everything is an ability". It is a clean
seam between capability lifecycle, numeric effects, domain state and data-driven
composition.

---

## Provenance

The patterns and failure modes in `references/` come from a line-by-line audit of
the GAS layer of Epic's Lyra Starter Game on Unreal Engine 5.6 — roughly 4 900
lines across 51 files — read as source rather than run.

Source addresses stay in the research archive that produced this skill; what ships
is the detection recipe. Each entry carries a stable identifier (`GA-01` and up)
that resolves back to the audited location, so any specific claim can be produced
on request.

## Evidence boundary

One project, one engine version, one workspace. The architecture described here
is transferable; the specific defects are evidence, not guarantees about other
versions. Re-run the detection recipes against your own tree before acting on any
specific claim.
