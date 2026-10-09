---
name: ue-modular-gameplay
description: >-
  Design or review modular gameplay in Unreal Engine: experience definitions,
  feature plugins, reusable action sets, feature actions, actor extension
  handlers, component init-state chains, primary asset bundles, and runtime
  activation and deactivation. Use when adding game modes, seasonal or
  downloadable features, modular components, abilities, input or UI, or when
  fixing initialization-order and feature teardown bugs.
---

# UE modular gameplay

The invariant:

> A feature may select and attach behaviour without modifying the receiving base
> class, but it owns every resource it adds and must remove exactly that
> resource.

Measured patterns from a reference product: [patterns](references/patterns.md).
Eighteen detection recipes for silent modularity failures:
[failure modes](references/failure-modes.md).

Read the failure modes before adopting this architecture. Nearly all of them are
teardown defects, and teardown defects share one property: **activation is what
gets tested, so the half that is broken is the half nobody exercises.**

Related skills: `ue-data-driven-architecture`, `ue-input-architecture`,
`ue-ui-architecture`, `ue-gas-architecture`, `ue-multiplayer-authority`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Separate the four layers

```text
Playlist / session entry
└─ Experience definition
   ├─ feature plugins to activate
   ├─ reusable action sets
   ├─ mode-specific actions
   └─ default pawn data

Feature data asset
└─ lifecycle and asset scanning of one plugin

Action set
└─ reusable composition slice

Feature action
└─ one apply/rollback operation
```

Do not merge them:

- the playlist owns map, session and menu metadata, not gameplay composition;
- the experience owns one runtime composition, not plugin lifecycle policy;
- the feature data asset owns plugin registration and scanning, not a game mode;
- an action set expresses reuse; it is not an inherited base experience;
- an action performs one focused mutation and owns its rollback state.

### Prefer composition over experience inheritance

A mode should read as a sum:

```text
SharedInput + StandardComponents + StandardHUD + ModeDelta
```

not as a hidden defaults chain:

```text
Base -> Shooter -> Team -> TeamDeathmatch
```

Flat action sets keep dependencies, asset loading and teardown auditable. A
reference product measured for this skill goes further and *forbids* the second
form in validation, pointing authors at composition instead.

---

## 2. Experience loading is a state machine

```text
Unloaded
→ LoadingAssets
→ LoadingGameFeatures
→ ExecutingActions
→ Loaded
→ Deactivating
→ Unloaded
```

Each transition needs an explicit completion criterion. Never track this with a
handful of booleans — `bAssetsReady && bPluginsReady && bActionsDone` cannot
express "failed", and failure is the state you will need most.

### The server selects; every peer realises locally

Replicate the selected definition, never the result of loading it:

```text
server selects experience ID
→ replicated definition reaches the client
→ server and client run the same load pipeline
→ role-specific bundles and actions decide their local work
```

This is "replicate intent, realise presentation locally" applied to composition.

### Document selection precedence

If an experience can come from matchmaking, a URL, developer settings, the
command line, world settings and a default, define the exact precedence, log the
winning source, validate the asset ID before loading, and provide an explicit
fallback.

### Delay only for a named dependency

Deferring selection by one frame so that startup settings can initialise is
legitimate **because the dependency has a name**. A next-tick timer with no
identified prerequisite is initialization-order debt with a timer wrapped around
it. Recipe: MG-12.

---

## 3. Bundle and role boundaries

Collect the experience plus every action set as primary assets, then request
named bundles: a shared bundle always, the client bundle when a client exists,
the server bundle when authority exists.

Mark soft references at their declaration:

```cpp
meta=(AssetBundles="Client")
meta=(AssetBundles="Client,Server")
```

| Action target | Expected role |
|---|---|
| HUD, layout, input icons | Client |
| scoring authority, bots, team assignment | Server |
| replicated scoring component | Client + Server |
| ability classes and effects needed for prediction | usually both |

**A client/server flag on an action does not guarantee correct cook bundles.**
Validate both, separately.

### Editor bundle loading is not shipping

A policy that loads client data when not a dedicated server and server data when
not a client-only build loads **both** in the editor. Every memory and load-time
figure taken in-editor therefore describes a configuration that ships to nobody.
Use it for direction of change only. Recipe: MG-18.

---

## 4. Extend actors through receivers and extension handlers

Do not scan the world for actors and patch them. Use the component manager's
extension protocol:

```text
receiver actor registers itself
action registers an extension handler for a target class
manager invokes the handler for existing AND future receivers
returned request handle owns the subscription
```

The receiver lifecycle is symmetric and belongs in the base class:

```text
PreInitializeComponents : add receiver
BeginPlay               : send ready events
EndPlay                 : remove receiver
```

Note what this buys: base gameplay classes register as receivers and **know
nothing about features**. If a class does not inherit the modular base, those
three calls are written by hand — and forgetting the third is a leak with no
symptom until the second activation.

### Use semantic readiness events

A generic "extension added" event means only that the actor is known to the
manager. It may not yet have its pawn data, ability system, controller or input.
Emit named events at the real dependency boundary — abilities ready, bind inputs
now, actor ready — and have handlers accept both the generic event and the
semantic one, so activation order stops mattering. Recipe: MG-13.

### Retain request handles

Handler registration and component requests return ownership handles that are
reference counted. **Dropping the handle is the unsubscribe operation**; there is
no explicit removal call. Storing them per activation context is therefore not
bookkeeping, it is the only teardown mechanism that exists.

---

## 5. Use an init-state chain

Networked actor composition has non-deterministic arrival order. Replace
scattered checks in `BeginPlay`, possession callbacks and replication callbacks
with a monotonic chain:

```text
Spawned → DataAvailable → DataInitialized → GameplayReady
```

- **Spawned** — the actor and component exist.
- **DataAvailable** — required replicated and config data exist.
- **DataInitialized** — every participating feature reached DataAvailable and
  cross-feature initialisation ran.
- **GameplayReady** — safe for active gameplay.

The load-bearing barrier is "have all features on this actor reached
DataAvailable", which synchronises components without any of them naming the
others.

### Rules

- states only advance; they reset with the actor's lifecycle, not by backtracking;
- every transition has an observable prerequisite;
- replication callbacks re-enter the same check rather than duplicating init;
- feature-specific work runs once, at a named transition;
- test server, owning client and simulated proxy separately — a proxy never
  acquires a controller, and a gate that waits for one deadlocks it while working
  perfectly in a single-process test.

---

## 6. Action design contract

An action class implements behaviour; its instance stores targets and
configuration. A world-aware base action should filter to game worlds, handle
worlds that already exist at activation, subscribe for future ones, and release
its world delegates on deactivation — leaving resource tracking to the concrete
action.

### State must be keyed by activation context

One action object can be active in several contexts at once — client and server
in a single-process test are the common case. **State in plain member fields is a
cross-context leak.** Key it:

```cpp
struct FPerContextData { /* ... */ };
TMap<FGameFeatureStateChangeContext, FPerContextData> ContextData;
```

Recipe: MG-11.

### One responsibility per action

Good: add components; add abilities; add input binding; add input mapping
context; add widgets; add cue path.

Bad: "set up shooter mode".

A focused action has a testable rollback and can be reused in an action set.

### The mandatory ownership ledger

Write this table **before** implementing any action:

| Added resource | Stored ownership | Removal |
|---|---|---|
| extension callback | request handle | release the handle |
| component | component request | remove the owned component |
| ability, effect, attribute set | granted handles | revoke the handles |
| input bind | bind handles per pawn | remove those exact binds |
| input mapping context | player + context | remove from the same subsystem |
| widget extension | extension handle | unregister |
| layout | widget or layout handle | deactivate and remove |
| global delegate | delegate handle | unbind |

**If the middle column is blank, reject the action.** Every teardown failure in
the measured reference is a blank middle column that shipped. Recipes: MG-01
through MG-05.

---

## 7. Deactivation is not optional

"Modular" is not proven by successful activation. The round trip is the test:

```text
inactive baseline
→ activate       → verify additions exactly once
→ deactivate     → verify exact baseline
→ reactivate     → verify no duplicates and no stale state
```

Run it with: actors that existed before activation; actors spawned after it; an
actor destroyed before the feature deactivates; two worlds in one process; client
and server roles; a partial load failure; and a plugin required by two
experiences at once.

### Removal must be idempotent

Resources come off by two independent paths: the explicit reset at deactivation,
and reactively when the actor dies first and the manager reports it. Both must be
safe to run, in either order, and must operate on "is there a record?" rather than
assuming one. Recipe: MG-08.

### Reference-count shared plugin activation

If two experiences need one plugin, count activations. One owner deactivating
must not unload a plugin the other still requires. **Check that the count is not
editor-only** — a reference count compiled out of shipping builds is a reference
count that protects development and nothing else. Recipe: MG-16.

### Diff requirements on experience change

```text
old - new         = deactivate and unload
new - old         = load and activate
intersection      = keep active
```

Do not unload everything and reload it immediately. If this diff is not
implemented, define experience changes as map-travel-only and say so in writing —
that is a legitimate scope decision, and leaving it undefined is not.

---

## 8. Failure handling

A production loader must not assert its way through configuration failure.
Represent failure as a state:

```text
Loaded
Failed(reason, failing asset / plugin / action)
```

Handle: an invalid asset ID; a missing plugin URL; a cancelled load; plugin
activation failure; action validation failure; timeout or partial completion; and
a deactivation pauser that never completes.

The loading screen consumes loader state and reason. **A permanent loading screen
is not error handling** — it is the absence of it, rendered.

---

## 9. Validation checklist

### Experience

- [ ] Asset ID registered and resolves.
- [ ] Default pawn data valid, or explicitly no pawn.
- [ ] Plugin names resolve to URLs.
- [ ] Action sets non-null and duplicate-free.
- [ ] Reusable behaviour in action sets; only the mode delta inline.
- [ ] Client and server bundles cover every soft reference.

### Action

- [ ] Target actor class valid; addition list non-empty.
- [ ] Existing and future actors both handled.
- [ ] Semantic readiness event used where the generic one is too early.
- [ ] Every request, delegate, grant, widget and input handle retained.
- [ ] Deactivation reverses activation exactly.
- [ ] Repeated activate/deactivate is idempotent.
- [ ] Per-context state cannot leak into another world.
- [ ] Index or key passed to a deferred callback matches the entry it names.

### Init states

- [ ] Every prerequisite is explicit.
- [ ] Every participating feature can reach every state.
- [ ] No feature waits on a signal produced only by a path it disabled.
- [ ] Authority and local-control branches tested.
- [ ] Late replication re-enters the same check.

---

## 10. Review questions

Before approving a modular feature:

1. Which definition selects it?
2. Which plugin owns its code and content?
3. Which action applies each effect?
4. Which readiness state makes that effect safe?
5. Which handle proves ownership?
6. What is the exact inverse operation?
7. What is loaded on client, on server, in the editor?
8. Can another feature share the same plugin or resource?
9. What happens on partial failure?
10. Does activate → deactivate → activate return to the same observable state?

**If questions 4 to 6 have no precise answer, the feature is dynamically attached
but not modular.** That distinction is the entire subject of this skill: attaching
is easy and demonstrable, detaching is neither, and only one of them gets
demonstrated.

---

## Provenance

The findings behind the failure modes come from a line-by-line source audit of
the feature-action layer of Epic's Lyra Starter Game on Unreal Engine 5.6, read
rather than run. The engine-side component manager and feature subsystem are not
part of that project, so every statement about them is inferred from call sites
in the audited code and is marked as such rather than presented as measured.

That audit found the architecture sound and its teardown half incomplete in five
separate actions — which is why this skill treats the ownership ledger and the
round-trip test as mandatory rather than advisory. Several of the gaps are
recorded by the original authors in their own comments, which is the strongest
confirmation a source audit can produce.

Source addresses stay in the research archive; what ships is the detection
recipe. Each entry carries a stable identifier (`MG-01`, `MG-02`, …) that
resolves back to the audited location there.

## Evidence boundary

One project, one engine version, one workspace. Binary assets were not read, so
which actions the shipped features actually configure is unknown and is recorded
as open rather than guessed. Re-run the recipes against your own tree before
trusting any specific claim.
