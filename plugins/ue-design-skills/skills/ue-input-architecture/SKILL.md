---
name: ue-input-architecture
description: >-
  Design or review Enhanced Input architecture in Unreal Engine: physical
  mapping contexts, input actions, semantic gameplay tags, input config data,
  native versus ability input paths, per-frame buffering on the ability system
  component, player-mappable settings, device switching, and runtime injection
  and removal of input by feature plugins. Use when adding controls, rebinding,
  gamepad or touch support, ability input, mode-specific input, or debugging
  actions that bind correctly and never fire.
---

# UE input architecture

The invariant:

> Physical controls, semantic commands and gameplay implementations are three
> separate layers joined by validated data.

```text
key / gamepad / touch
→ input mapping context
→ input action
→ input config: input action → input tag
→ native handler OR ability system component
→ ability set: input tag → ability
```

Measured patterns from a reference product: [patterns](references/patterns.md).
Detection recipes for silent input failures: [failure modes](references/failure-modes.md).

**The characteristic failure of this architecture is a button that does nothing
and logs nothing.** Read the failure modes before adopting it — most of them are
variations on that one observable.

Related skills: `ue-gameplay-tag-governance`, `ue-gas-architecture`,
`ue-modular-gameplay`, `ue-ui-architecture`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Keep the three layers independent

### Physical — the mapping context

Owns key, button and axis to input action; modifiers and triggers; priority
relative to other contexts; player-mappable metadata.

Changing a keyboard layout or a gamepad binding should stop here.

### Semantic — the input config

An immutable asset owning pairs:

```text
IA_Move        → InputTag.Move
IA_WeaponFire  → InputTag.Weapon.Fire
IA_Dash        → InputTag.Ability.Dash
```

Gameplay depends on tags, not on asset paths or physical keys.

### Capability — handlers and ability sets

Native tags bind to explicit handlers. Ability tags travel to the ability system
component as payload. Granted ability specs carry the matching semantic tag.

Changing an ability implementation should not require touching a mapping context.

---

## 2. Split native and ability actions

Make the distinction explicit in the config, with two separate lists.

**Native** — deterministic controller and pawn functions: move, look, crouch,
autorun. Each costs one explicit binding line, and the tag is a **lookup key at
bind time only**. The handler receives an input value; the tag does not exist at
runtime.

**Ability** — bound through one pressed/released pair with the row's tag passed
as a payload argument. One pair of functions serves any number of abilities, and
the count of new abilities you can add without writing code is unbounded.

### Classification test

Native when the action controls continuous motion, must execute immediately and
deterministically, and needs no ability lifecycle.

Ability when the action activates a grantable capability, can be blocked or
cancelled by tags, has cost or cooldown or prediction, or changes with equipment
or mode.

### Watch what the ability path fixes at bind time

If ability binding is hardcoded to two trigger events, then hold, tap and
double-tap variants must be expressed through triggers and modifiers in the
mapping context rather than through trigger-event selection. That is a
reasonable constraint — but it is a constraint, and it is invisible until
someone needs a third event.

---

## 3. Join semantic tags at grant time

When an ability set grants an ability, add the configured input tag to the
spec's dynamic source tags. Lookup then becomes:

```text
pressed input tag
→ scan activatable specs
→ exact tag match
→ buffer the spec handle
```

Do not store an input action pointer on the ability. That couples a capability to
one content asset and blocks per-mode and per-device remapping.

### The match is exact, not hierarchical

A spec tagged `InputTag.Weapon` is **not** matched by a press of
`InputTag.Weapon.Fire`. The tag hierarchy organises the vocabulary and filters
the editor picker; it does not participate in lookup. Assuming otherwise
produces a binding that is correct in every visible respect and never fires.
Recipe: IN-01.

### Validate the join

The input config and the ability set are independent assets. Their tag equality
is a foreign key with no database behind it, so validation is the only compiler
it will ever have:

- every input-driven ability has a non-empty tag;
- every intended ability tag is reachable from at least one active config;
- every config ability tag has a granted consumer in the intended composition;
- duplicates are intentional;
- category constraints hold on both sides.

---

## 4. Buffer ability input, process once per frame

Forwarding a tag must not activate immediately. Record held handles, pressed this
frame, released this frame; process from the controller's post-input step in
three passes — held with the while-active policy, then pressed with the
on-triggered policy, then activate everything in one batch, then releases.

This removes event-order dependence and makes simultaneous input resolvable.
See `ue-gas-architecture` for the activation policies and the global block tag.

**Accept the consequence:** the ability path is one input-processing step behind
the native path within the same frame. For most games that is invisible. It is
still a real difference between the two paths, and it belongs in the
classification decision rather than being discovered later.

---

## 5. Initialize input at a named readiness boundary

Binding depends on several independently arriving pieces: a local controller, the
input subsystem, the pawn data and its config, the project's input component
subclass, and any contexts added by features.

Do not treat `BeginPlay` as ready. Use init states and emit a semantic event —
"bind inputs now" — once the dependencies hold.

Feature actions must respond to **both** the generic extension-added event and
the semantic ready event, because either can arrive first. Set the readiness flag
*before* broadcasting, or a handler that checks it during the broadcast will see
false.

### Base initialization checklist

- [ ] the component is the expected input subclass, checked with a diagnostic
      that names the fix;
- [ ] clearing existing mappings is deliberate and its consequences are handled;
- [ ] default contexts added to the local player subsystem;
- [ ] settings registration separated from runtime activation (§6);
- [ ] native actions bound explicitly;
- [ ] ability actions bound **and their handles retained** (§7);
- [ ] the ready event is sent exactly once per initialization;
- [ ] late feature handlers can bind safely.

### Clearing all mappings is a broadcast dependency

If initialization clears every mapping on the subsystem, it also removes contexts
added by already-active features. Recovery then depends on those features hearing
the ready event and re-adding their contexts — which makes correctness a property
of event ordering rather than of stored state. It works; it is fragile; and it
must be a documented decision rather than a side effect. Recipe: IN-08.

---

## 6. Separate "register with settings" from "activate now"

These are two different operations:

```text
RegisterInputMappingContext(IMC)    // discoverable and rebindable
AddMappingContext(IMC, priority)    // actually active
```

A context may be active but not remappable, or registered but not currently
active. All four combinations are meaningful.

**One flag must not gate both.** If it does, unchecking "expose this for
rebinding" also silently removes the input — a designer changes a settings
checkbox and the character stops responding, with nothing in the log. Recipe:
IN-06.

---

## 7. Modular input needs ownership receipts

### Adding a mapping context

Data: context, priority, register-with-settings flag. Retain per activation
context: the extension and delegate handles, the exact players touched, and the
exact contexts and priorities activated.

### Adding ability bindings

Data: a list of input configs. Retain per pawn: **every returned bind handle**,
which config produced it, and the readiness subscription.

### Symmetric removal

```text
remove the exact bind handles this config created
remove the exact contexts this action added
unregister from settings only if this action registered them
release extension and delegate handles
```

**Never implement removal by clearing all bindings or all mappings on the pawn.**
That destroys other features' ownership, and it will look like it works.

The measured reference composes this well and tears it down badly: bind handles
are declared as locals and discarded, so the removal function *cannot* be
implemented without changing the component that binds. Copy the composition;
write the teardown yourself. Recipes: IN-03, IN-04.

---

## 8. Device switching belongs above gameplay semantics

Gameplay should not branch on keyboard versus gamepad for the same command. The
UI layer owns the active input type, glyphs, controller brand and style,
change notifications, and disconnected-device handling.

Gameplay may still use **distinct actions and tags** where the semantics genuinely
differ — mouse delta and analog stick look need different modifiers and
sensitivity, so:

```text
InputTag.Look.Mouse
InputTag.Look.Stick
```

That is semantic distinction, not device sniffing. The test is whether the two
paths do different arithmetic; if they do, they are different commands.

Per-player sensitivity, dead zones and inversion belong in input modifiers that
read settings — not in handler code. Note that a modifier which resolves a setting
by property **name** through reflection will break silently on a rename, with no
compiler help. Recipe: IN-10.

---

## 9. Context priority and consumption

A handler can be perfectly bound and never fire because an earlier context
consumes the key.

Before adding a mapping: list every active context in priority order; find all
mappings for the physical key; inspect triggers, modifiers and consume-input
behaviour; establish whether the contexts can be active simultaneously; and
confirm no raw key path bypasses the system.

Priority is meaningful only between concurrently active contexts. Document why a
feature needs to outrank the baseline.

### Avoid raw key fallback

Raw key handling bypasses rebinding, device parity, triggers and modifiers,
context priority, and input profiles. Use it only for editor and debug controls,
with a stated reason.

---

## 10. The config-file boundary

With Enhanced Input, the project input config file should contain the
player-input and input-component classes, user-settings class registration, debug
bindings, UI input defaults, and legacy axis properties only where the engine
still requires them.

Gameplay mappings live in mapping context assets; semantic mappings live in input
config assets. **Legacy axis configuration that sits beside Enhanced Input is
actively misleading** — it looks like the place sensitivity is set, and it is not.
Recipe: IN-09.

---

## 11. Test matrix

### Composition

Baseline pawn data and config; a mode action set adding a second config;
equipment granting and removing matching abilities; a feature activating both
before and after pawn readiness; two features adding distinct configs at once.

### Lifecycle

```text
spawn → bind → activate feature → press / hold / release
→ deactivate feature → verify no response
→ reactivate → verify exactly one response
```

### Devices

Keyboard and mouse; gamepad; touch; hot-swap while UI is open; a saved and
reloaded remap; two local players with separate profiles.

### Network and abilities

Owning-client predicted activation; server rejection with failure feedback; input
held across a possession or avatar change; the block tag clearing buffered state;
an ability removed while its input is held.

---

## 12. Review checklist

- [ ] Physical key knowledge stops at the mapping context.
- [ ] Gameplay uses semantic tags, not asset references.
- [ ] Native versus ability classification is intentional.
- [ ] Ability input is buffered, not activated inside the event callback.
- [ ] Config and ability-set tags are validated as a join, in both directions.
- [ ] Tag matching semantics are known to be exact, and the data suits that.
- [ ] Binding waits for a named readiness state, not for begin play.
- [ ] Base and feature bindings both retain handles.
- [ ] Runtime activation and settings registration are independent.
- [ ] Deactivation removes only what this owner added.
- [ ] Priority and consumption conflicts have been audited for shared keys.
- [ ] Device icons and method switching stay in the UI layer.
- [ ] Activate, deactivate, reactivate produces no duplicate callbacks.

---

## 13. When this architecture is too much

For a single-mode project with one device family, no dynamic abilities and no
rebinding, direct bindings are honest and this indirection is overhead.

Introduce semantic tags when at least one becomes true: abilities are granted
dynamically; several pawn archetypes reuse controls; features add input at
runtime; rebinding and device parity matter; gameplay must be independent of
content asset paths.

The architecture is paid for by **modularity of content** and **many archetypes
with different action sets**. Without either, the cost is real and the benefit is
not: to answer "what does the left mouse button do?" a reader must traverse
mapping context, action, config, tag, pawn data, ability set and spec tags —
seven assets instead of one call stack.

---

## Provenance

The findings behind the failure modes come from a line-by-line source audit of
the input layer of Epic's Lyra Starter Game on Unreal Engine 5.6 — about 870
lines across seven file pairs, plus its integration points in the hero component
and two feature actions — read as source rather than run.

Source addresses stay in the research archive that produced this skill; what
ships is the detection recipe. Each entry carries a stable identifier (`IN-06`
and up) that resolves back to the audited location.

## Evidence boundary

One project, one engine version, one workspace. Mapping contexts and input
actions are binary assets and were not read, so every claim about which keys map
to which actions is out of scope rather than concluded. Re-run the recipes
against your own tree before acting on any specific claim.
