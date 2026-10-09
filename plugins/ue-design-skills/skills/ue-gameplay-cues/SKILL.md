---
name: ue-gameplay-cues
description: >-
  Design, implement or review the GameplayCue presentation layer in Unreal
  Engine GAS: what a cue is and when it is the right mechanism, Executed versus
  OnActive/WhileActive/OnRemove forms, the three addressing paths, Static versus
  Actor notifies, the dedicated-server rule, cue asset discovery and loading
  cost, registering cue paths from feature plugins, teardown and leaked looping
  cues, and the tag-to-asset validation gap. Use when adding VFX or audio
  feedback to abilities or effects, decoupling presentation from gameplay
  assets, debugging a cue that never fires or never stops, or auditing cue
  loading cost.
---

# UE gameplay cues

The invariant:

> A cue is a one-way, cosmetic, tag-addressed broadcast. Gameplay must produce
> exactly the same result if every cue in the project fails to fire.

Worked analysis of a real cue subsystem, including the parts that were built and
never reached: [patterns](references/patterns.md).
Twenty detection recipes for silent cue failures: [failure modes](references/failure-modes.md).

Read the failure modes before adopting or reviewing a cue-based design. Each entry
names the mechanism, why it stays silent, why the obvious check misses it, and a
command you can run against your own tree.

Related skills: `ue-gas-architecture`, `ue-gameplay-tag-governance`,
`ue-modular-gameplay`, `ue-asset-loading-and-memory`, `ue-gameplay-messaging`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. What a GameplayCue is, and the problem it solves

A GameplayCue is a **presentation event addressed by a GameplayTag** rather than
by an asset reference.

Without it, the chain looks like this:

```text
GE_Fire_Damage  --hard reference-->  NS_Fire_Impact (Niagara)
                                     SW_Fire_Impact (audio)
```

The gameplay asset now owns the VFX and the audio. Loading the effect loads the
particles. A dedicated server, which needs the damage numbers and nothing else,
loads them too. An artist changing the impact effect touches a gameplay asset.

With a cue, the chain is cut:

```text
GE_Fire_Damage  --tag-->  "GameplayCue.Fire.Impact"  <--tag--  GCN_Fire_Impact
```

The gameplay asset references a **string-like identifier**. A separate registry
maps that tag to a notify asset, discovered by scanning content directories. The
gameplay asset has no idea the presentation exists.

What this buys:

- gameplay assets carry no presentation payload, so they are small and
  server-safe;
- presentation can be added, replaced or shipped in a separate plugin without
  touching gameplay;
- the whole presentation layer can be absent on a dedicated server.

What it costs — and this is the part that gets skipped:

- **the join is no longer checked by anything.** A tag with no notify is silence.
  A notify with no matching tag is a never-loaded asset. Neither is an error.
- discovery is directory-scan based, so cue assets must be found, indexed and
  loaded by a manager that has its own lifecycle and its own failure modes;
- the mechanism is one-way and unreliable by design, which makes it wrong for
  anything that must be correct.

Treat cues as an application of `ue-gameplay-tag-governance` with a dedicated
loading subsystem attached. Every rule about tag joins applies here first.

---

## 2. The three forms

| Form | Fires when | Use for |
|---|---|---|
| **Executed** | a one-shot event | impacts, hit reactions, one-off flashes |
| **OnActive** | a duration effect starts, on clients present at that moment | start of a looping effect |
| **WhileActive** | an actor becomes relevant while the effect is already running | joining/relevancy catch-up for the same loop |
| **OnRemove** | the duration effect ends | stopping the loop, cleanup |

### Rules

1. **`OnActive` and `WhileActive` must produce the same visual state.** A client
   who was present and a client who arrived late must see the same thing. Putting
   the "start" logic only in `OnActive` means late joiners see nothing.
2. **Everything `OnActive`/`WhileActive` spawns, `OnRemove` destroys.** Looping
   cues are the main source of leaked VFX in GAS projects.
3. **Never use `Executed` for anything with a duration**, and never use the
   duration forms for a one-shot — the recovery paths differ.
4. **Assume `OnRemove` may run without `OnActive` having run** on that client, and
   the reverse. Write both defensively.

---

## 3. Static versus Actor notifies

| Notify type | Instanced | State | Use for |
|---|---|---|---|
| **Static** | no — a CDO handles the call | none | one-shot effects, sounds, decals |
| **Actor** | yes — an actor is spawned per instance | yes | looping effects, anything requiring cleanup |

### Rules

1. **Default to Static.** It allocates nothing and cannot leak.
2. **A Static notify must not store per-instance state.** It runs on the class
   default object; a member written during one invocation is shared by every
   subsequent one, including other players' invocations.
3. **Use an Actor notify only when there is something to tear down** — a looping
   particle system, an attached component, a timeline.
4. **Actor notifies are actors**: they have relevancy, they cost replication
   consideration if not marked otherwise, and they can outlive their owner if
   removal is missed.

---

## 4. The three ways a cue gets addressed

```text
1. GameplayEffect         GE lists cue tags; ASC fires them with the effect
2. Direct ASC call        ExecuteGameplayCue / AddGameplayCue / RemoveGameplayCue
3. IGameplayCueInterface  the actor handles cue tags itself
```

### Rules

1. **Prefer route 1 for anything tied to an effect's lifetime.** The effect and
   its presentation then start and stop together by construction.
2. **Route 2 is for presentation with no effect behind it** — a UI-driven flash, a
   client-local confirmation. It is manual, so its removal is manual too.
3. **Route 3 is for actor-specific handling** that no generic notify can express.
   It couples the actor to the cue vocabulary; use sparingly.
4. **Do not mix routes for one cue tag.** Two owners of the same presentation
   produces double effects that appear only when both paths trigger.

---

## 5. The network rule

**Cues never run on a dedicated server.** The presentation layer does not exist
there.

Consequences that must be designed for, not discovered:

1. **A cue may not carry gameplay side effects.** Damage, score, state changes,
   spawning — none of it may live in a notify, because on a dedicated server that
   code never executes. This is the single most important rule in this document.
2. **Cue parameters are a lossy channel.** They are packed for replication;
   whatever your conversion helper drops is dropped silently on every client.
   Verify the round trip for every field you rely on, especially tag containers.
3. **Cue delivery is unreliable.** Packet loss, relevancy changes and joining
   mid-effect all produce missed cues. Design for a missed cue being invisible,
   not desynchronising.
4. **Cue assets belong in the client asset bundle only.** Putting them in the
   server bundle loads presentation content on a machine that will never use it.

### Test that the rule holds

Run the feature on a dedicated server with the presentation content deliberately
absent. Gameplay results must be byte-identical.

---

## 6. Registering cue paths from feature plugins

A feature plugin that ships cue assets must register its content directory with
the cue manager, or its cues are invisible.

The important structural point: **cue path registration must happen earlier than
feature activation.** The manager builds its tag-to-asset index during its object
library scan; a path added after that scan is not indexed until the next rescan.
This is earlier than any of the standard activation hooks.

The pattern that solves it:

> **The feature action is a pure data declaration; a lifecycle observer is the
> executor.**

The action object declares only the directory list and validates it in the
editor. A separate observer, registered with the feature policy, listens for the
earliest lifecycle phase and performs the registration for every action of that
type it finds.

### Rules

1. **Register on the earliest available phase**, not on activation.
2. **Batch the rescan.** Add all paths, then rebuild the index once — one rescan
   per feature, not one per directory.
3. **Refresh the primary-asset registration when the path set changes**, on the
   way in *and* on the way out. Skipping it on removal leaves the asset manager
   describing directories that no longer exist.
4. **Implement removal and assert it.** Count the paths removed and compare
   against the paths added; a mismatch means the registry is drifting across
   activation cycles.
5. **Use the same manager instance on both sides of the lifecycle.** Registering
   through your subclassed manager and unregistering through the engine base
   class is a silent asymmetry — it compiles, runs, and leaves entries behind.

---

## 7. Loading and cost

Cue assets are discovered by scanning directories and are, by default, loaded on
demand — which means a hitch the first time each cue fires.

The mitigation is preloading, and it is where most complexity in a cue manager
lives: async library loading, a preload set, always-loaded tags, reference
tracking, and hooks for GC and map transitions.

### Rules

1. **Decide the load policy explicitly and verify it is reachable.** A load-mode
   switch that short-circuits every branch renders the entire preload subsystem
   dead code — the machinery exists, is maintained, is never executed, and any
   diagnostic command reports zero because there is genuinely nothing there.
2. **A constant is not a knob.** A local `const bool` inside a namespace whose
   name ends in `Cvars` is not a console variable and cannot be changed at
   runtime. If a policy must be tunable, register it as an actual console
   variable; otherwise do not imply that it is one.
3. **Preload the small set that must never hitch** — the cues on the critical
   path, hit feedback above all — and let the rest load on demand.
4. **Put cue paths in the client bundle only** (see §5).
5. **Measure the cue set size before optimising it.** Discovery cost scales with
   the number of scanned directories; load cost scales with the assets actually
   referenced.

---

## 8. Teardown

Cues attach to an avatar. When the avatar changes — death, possession change,
respawn — cues that are still active belong to nothing.

The correct teardown sequence when unbinding an ability system from an avatar:

```text
1. verify the ASC's avatar is actually this actor
2. cancel abilities
3. clear ability input bindings
4. remove all gameplay cues
5. clear the avatar
```

### Rules

1. **Check avatar identity before tearing down.** A component that unbinds
   unconditionally can rip the ASC away from an avatar it no longer owns.
2. **Remove all cues explicitly.** Do not rely on the removal of the effects that
   added them; direct-call cues (route 2) have no effect behind them.
3. **Test the cycle twice.** Leaks and duplicates appear on the second respawn,
   not the first.

---

## 9. The validation gap, and what to do about it

Nothing in the engine checks that:

- a cue tag referenced by an effect has a notify asset;
- a notify asset's tag is referenced by anything;
- a cue tag is spelled the way the notify expects.

All three failures present identically: no visual, no log, no error.

### Minimum guardrails

1. **Constrain cue tag properties** with `meta=(Categories="GameplayCue")` so
   authoring uses a dropdown.
2. **Write a content validator** that resolves every cue tag in every effect
   against the manager's index, and reports both directions of orphan.
3. **Log once, in development builds, when a cue fires with no handler.** This
   converts the silent case into a searchable one.
4. **Keep cue tags in one namespace with one owner.** A cue tag placed in the
   wrong namespace because "the notify happens to live there" is a rename waiting
   to happen — and renames need redirects (see `ue-gameplay-tag-governance`).

---

## 10. Review checklist

- [ ] No gameplay logic inside any notify.
- [ ] Feature works identically with all cue assets absent.
- [ ] `OnActive` and `WhileActive` converge on the same visual state.
- [ ] Everything spawned in the duration forms is destroyed in `OnRemove`.
- [ ] Static notifies hold no per-instance state.
- [ ] Actor notifies exist only where there is something to tear down.
- [ ] One addressing route per cue tag.
- [ ] Cue assets are in the client bundle only.
- [ ] Cue parameter round-trip verified for every field used.
- [ ] Feature-plugin cue paths registered at the earliest lifecycle phase.
- [ ] Path removal implemented, asserted, and using the same manager instance.
- [ ] Load policy is reachable, and any "knob" is a real console variable.
- [ ] Teardown checks avatar identity and removes all cues.
- [ ] A validator reports orphan tags and orphan notifies.

---

## 11. Tests

### Behaviour

- one-shot cue fires once per execution, not per client-side prediction retry;
- looping cue starts on `OnActive`, is matched by `WhileActive` for a late
  joiner, and stops on `OnRemove`;
- `OnRemove` without a preceding `OnActive` does not crash or leak;
- cue with no registered notify produces no error and no side effect.

### Network

- dedicated server + remote client: gameplay results identical with and without
  cue content;
- client joining mid-effect sees the same state as a client present at the start;
- relevancy lost and regained during a looping cue converges to the correct state.

### Lifecycle

- death and respawn twice: no duplicated or orphaned cues;
- feature plugin activate, deactivate, activate: cue path count returns to its
  original value;
- possession change mid-cue.

### Cost

- first-fire hitch measured for a non-preloaded cue;
- preloaded set size and residency reported by a diagnostic command that has been
  verified to read a live code path.

---

## 12. When not to use a cue

Use something else when:

- the effect must be guaranteed — it is gameplay, not presentation;
- the receiver needs a return value or acknowledgement — direct call;
- the event drives UI state that must survive a missed message — replicated
  state plus a local message (`ue-gameplay-messaging`);
- exactly one known actor reacts, in the same module — direct call or delegate.

A cue earns its cost when presentation is genuinely optional, genuinely
many-to-many, and genuinely absent on the server. Used for anything else, it is a
tag join with no validation and unreliable delivery — which is a description of a
bug that has not happened yet.

---

## Provenance

The failure modes and the worked analysis in `references/` come from a
line-by-line audit of Epic's Lyra Starter Game on Unreal Engine 5.6, read as
source rather than run. The cue subsystem there is unusually instructive because
much of its preload machinery is present, maintained, and unreachable in the
shipped configuration — a shape that reading the class list will never reveal.

Source addresses stay in the research archive that produced this skill; what ships
is the detection recipe. Each entry carries a stable identifier (`GC-01` and up)
that resolves back to the audited location, so any specific claim can be produced
on request.

## Evidence boundary

The measured material refers to one project on one engine version. It is evidence
of failure modes, not a guarantee about other versions. Re-run the detection
recipes against your own tree before acting on any specific claim.
