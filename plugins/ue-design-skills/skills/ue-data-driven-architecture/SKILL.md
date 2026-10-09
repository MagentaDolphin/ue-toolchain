---
name: ue-data-driven-architecture
description: >-
  Design or review data-driven architecture in Unreal Engine: definition layers,
  data asset versus zero-node Blueprint class defaults versus instanced
  fragments and actions, primary asset identifiers, soft and hard and class
  references, asset bundles, modular composition, validation, and the boundary
  between code and data. Use when adding game modes, pawn archetypes, ability
  packages, item and equipment definitions, playlists or feature plugins, or
  when a manager is growing per-variant branching.
---

# UE data-driven architecture

Data-driven does **not** mean "put fields in a data asset". It means:

> Code owns lifecycle, algorithms, replication and invariants. Data selects and
> composes implementations at explicit architectural layers.

Measured patterns from a reference product: [patterns](references/patterns.md).
Detection recipes for silent data-graph failures:
[failure modes](references/failure-modes.md).

**The characteristic failure of a data graph is that it compiles.** A wrong
reference, an unregistered identifier, a missing bundle and a copy-pasted
prototype are all valid data. Validation is the only compiler this layer will
ever have, and building it is part of the architecture rather than a follow-up
task.

Related skills: `ue-modular-gameplay`, `ue-gas-architecture`,
`ue-input-architecture`, `ue-ui-architecture`, `ue-cosmetics-and-teams`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Start with layers, not asset classes

Before creating an asset, name the level of composition it owns. A robust
product usually needs several narrow definitions, not one omniscient
configuration:

```text
catalog / playlist
├─ where and how to launch (map, session, display metadata)
└─ gameplay definition
   ├─ feature plugins to enable
   ├─ reusable action sets
   ├─ mode-specific delta
   └─ pawn archetype
      ├─ pawn class
      ├─ capability packages
      ├─ input semantics
      ├─ policy matrix
      └─ camera
```

Items form a separate pipeline:

```text
pickup presentation
└─ item definition
   ├─ inline fragments (display, stats, equippable, reticle)
   └─ equipment definition
      ├─ runtime instance class
      ├─ capability packages
      └─ actors and components to spawn
```

### The layer test

For every field ask:

1. Does it describe **launch and catalog UI**, or **runtime gameplay**?
2. Is it common to several modes, or a mode-specific delta?
3. Does it define an archetype, a capability, or presentation?
4. Who consumes it, and at which lifecycle phase?

If one asset answers all four, split it.

---

## 2. Pick the container by lifecycle

The storage type is an architectural decision, not a preference.

| Need | Use | Why |
|---|---|---|
| Standalone immutable record referenced as an object | data asset | object identity, editable in Details |
| Asset-manager discovery, bundles, async loading | primary data asset | stable identifier, bundle rules |
| A class default, a class reference, inheritance, or a runtime instance of that class | zero-node Blueprint subclass | class identity plus editable defaults |
| Polymorphic optional facet embedded in a definition | instanced object, edit-inline | composition without asset explosion |
| Polymorphic load/activate/deactivate operation | instanced action object | behaviour in code, targets in data |
| Dense homogeneous tabular records | data table | rows, import and export, bulk editing |

### A Blueprint with zero nodes is a data container

This is the most consequential and least visible fact in this skill. An entire
definition layer can live in Blueprint classes that contain no graph at all,
with values on their class defaults.

**An inventory that searches only for data-asset instances will not see any of
it.** Count both, or your census of the data layer is wrong by however much that
layer holds. Recipe: DD-01.

### When not to use a Blueprint class default

Do not use one merely because the editor offers it. Prefer a data asset when
consumers need an object rather than a class, when no runtime instance of the
subclass is created, when inherited defaults add nothing, and when asset-manager
identity matters more than a class reference.

---

## 3. Pick reference semantics explicitly

Every reference chooses loading and ownership behaviour.

| Reference | Use when | Failure mode |
|---|---|---|
| primary asset identifier | the target must be addressed before it is loaded | type or name not registered; resolves to nothing |
| soft object or class pointer | async load, optional content, role-specific content | not loaded when dereferenced; omitted from the build |
| hard pointer | the target is required whenever the owner is loaded | dependency graph grows transitively |
| class reference | data selects an implementation class or its defaults | construction and lifecycle become class-coupled |
| instanced object | the owner exclusively owns a small polymorphic facet | duplication; cannot be shared independently |

Write the decision into the property metadata and the validation, not only into
a design document.

### Asset bundles belong beside the soft reference

```cpp
UPROPERTY(EditAnywhere, meta=(AssetBundles="Client"))
TSoftClassPtr<UUserWidget> WidgetClass;

UPROPERTY(EditAnywhere, meta=(AssetBundles="Client,Server"))
TSoftClassPtr<UGameplayAbility> AbilityType;
```

The definition then declares both **composition** and the **load and cook
boundary** in one place. Do not maintain a separate, undocumented table of which
assets belong to which role.

Two failure modes follow directly, and both are silent:

- a soft reference with **no** bundle annotation is not pulled into the build by
  its owner, so it resolves to null in a packaged game and works in the editor;
- a bare accessor on a soft reference assumes the bundle worked, and returns null
  without complaint when it did not.

Recipes: DD-03, DD-04.

### Cross-plugin dependency gate

For every reference crossing a feature-plugin boundary: is the target plugin
active before this asset resolves? Does the owning bundle pull it into the
build? Can the source deactivate while the target is still referenced? Is the
dependency one-way, or did you just create a cycle?

---

## 4. Code consumer, data selection

A healthy definition has a narrow code consumer. The consumer owns when loading
happens, authority and client rules, replication, initialization order, apply and
rollback, validation and error handling.

Data owns which class or asset or tag is selected, numeric and presentation
parameters, variant composition, and role flags where the consumer supports them.

### The switch test

If adding a new mode, weapon or pawn requires another branch in a manager, a
definition, action or fragment boundary is probably missing.

### But do not move an invariant into data

These stay in code, always:

- "only the authority grants capabilities";
- "the archetype must exist before this readiness state";
- replication rules;
- teardown order;
- "one grant revokes only its own handles".

**The variant is data; the safety rule is code.** A rule that can be edited by
opening an asset is a rule that will be edited by someone who does not know it is
a rule.

---

## 5. Compose reuse; do not hide it in inheritance

Prefer flat composition:

```text
experience = shared input + standard components + standard HUD + mode delta
```

over an inheritance chain:

```text
base → shooter → team → deathmatch
```

Composition makes dependencies visible, reusable and diffable. Inheritance
accumulates defaults silently and creates ordering questions nobody asked.

If your definition type supports Blueprint subclassing, consider **rejecting it
in validation** and pointing the author at composition instead. A reference
product does exactly this, with an error message naming the alternative
— a validator that teaches rather than only refuses. Recipe: DD-05.

### The symmetry gate for actions

Before approving any action that adds something at runtime, fill this table:

| Resource added | Handle retained | Exact rollback |
|---|---|---|
| extension handler | request handle | release handle |
| component | component request or instance | remove only the owned component |
| capability grant | granted handles | revoke only those handles |
| input binding | bind handles | remove each binding |
| mapping context | player plus context | remove from the same player |
| widget or layout | extension or layout handle | unregister or remove |

**A blank middle column means the action cannot be rolled back.** Do not
advertise runtime-deactivatable modularity until the table is complete and
tested. See `ue-modular-gameplay` for the failure modes this prevents.

---

## 6. Use fragments for optional facets

Avoid one definition carrying every possible field for every possible item.
Use polymorphic inline fragments and let consumers query by class:

```cpp
UCLASS(DefaultToInstanced, EditInlineNew, Abstract)
class UItemFragment : public UObject {};

UPROPERTY(EditDefaultsOnly, Instanced)
TArray<TObjectPtr<UItemFragment>> Fragments;
```

The definition stays open to new facets without changing its base class,
irrelevant fields do not appear on unrelated items, and designers compose facets
in the editor.

Fragment rules: one responsibility each; state whether duplicates are legal;
validate required combinations; never depend on array order unless the order is
named and documented; fragments select and configure behaviour, they do not own
lifecycle.

---

## 7. Put cross-cutting policy in a policy definition

When many capabilities repeat the same relationships, do not copy the same
containers into all of them. Use a matrix selected by the archetype, so the same
capabilities can run under different policies.

Good candidates: capability relationships, presentation parameter bags,
sensitivity curves, class-to-widget mappings, quality thresholds.

Bad candidates: authority decisions, anti-cheat rules, irreversible lifecycle
transitions, and the validation logic itself.

---

## 8. Validation is part of the architecture

A data graph creates failure classes that code-only systems do not have. Every
definition family needs validation, and it needs to run somewhere other than the
editor.

### Universal checks

- required references non-null;
- arrays with no effective entries rejected;
- class derives from the required base or implements the required interface;
- tags valid and constrained to the expected category;
- identifiers resolve;
- soft targets belong to available, cooked plugins;
- duplicate semantic keys detected;
- client-only assets not bundled for the server, and the reverse;
- every action has a complete rollback path;
- production definitions reference no prototype or test content.

### Cross-family checks

These are the ones that catch real defects, because they cross an ownership
boundary that no single reviewer owns:

```text
playlist identifier      → resolves to a registered gameplay definition
gameplay definition      → archetype has a class, or is explicitly empty
archetype capabilities   → input tags match a reachable input config
item equippable fragment → resolves to an equipment definition
equipment definition     → capability packages valid for its instance type
pickup presentation      → matches the item definition it claims to present
```

The last row is not theoretical. In the audited reference, two health pickups
reference the pistol item definition. It compiles, cooks, and ships. Recipe:
DD-07.

### Editor-only validation is feedback, not a boundary

If invalid data can reach a packaged build through an automated cook, the
validation must run there too. In the audited reference **eleven of twelve
validation entry points are compiled out of non-editor builds** — which is
normal, correct, and exactly why a commandlet or automation test has to exist
beside them. Recipe: DD-09.

---

## 9. Auditing an existing project

### A. Inventory both containers

1. Query the asset registry for instances deriving from the data-asset base.
2. Query the class registry for zero-node classes whose parent is a definition
   type.
3. Include every mount root — the primary content root alone is incomplete in a
   plugin-based project.
4. Exclude world-partition external actor packages from asset counts.

**Do not read binary asset files from disk.** Use the asset registry and live
editor APIs. This is a hard constraint, not a preference: a text search over
binary assets produces confident nonsense.

### B. Build the reference graph

For each definition record the owner layer, the consumer, the identifier, the
reference kinds, the bundle metadata, and the incoming and outgoing plugin
boundaries.

### C. Measure behaviour density

A definition class should have zero or very few graph nodes. A definition
carrying a large graph is secretly both data and manager.

### D. Trace one complete variant end to end

Do not stop at class declarations. Pick one real variant and follow it:

```text
playlist → definition → action sets → archetype
→ capability and input policy → item → equipment → grant
```

Record the actual configured values. Generic reflection frequently hides
inherited class-default fields and reports zero properties on a populated
object; read known fields by name from the schema instead of concluding the
object is empty. Recipe: DD-02.

---

## 10. Review checklist

- [ ] The definition's architectural layer has a name.
- [ ] It has exactly one consumer owner.
- [ ] Container type matches lifecycle.
- [ ] Reference kinds are intentional and written in metadata.
- [ ] Bundle metadata matches client and server use.
- [ ] Reuse is composition, not a chain of inherited defaults.
- [ ] Actions and fragments have focused responsibilities.
- [ ] Apply and rollback symmetry is proven, not assumed.
- [ ] Required links and semantic joins are validated.
- [ ] Cross-plugin references are acyclic and cooked.
- [ ] A real instance was traced end to end.
- [ ] Production data contains no prototype or copy-pasted references.

If more than two boxes are unknown, the architecture is not data-driven yet — it
is data-shaped.

---

## 11. When to stop

Introduce a definition layer when at least one is true: several modes reuse the
same composition; content ships after launch; variants are authored by people who
do not write code; a manager is accumulating per-variant branches.

Do not introduce one because the reference project has it. Every layer costs an
asset type, a validation surface, a loading path and a debugging hop. The
measured benefit of this architecture is that a mode becomes a list rather than a
subclass — if you have one mode, you are paying for an answer to a question you
do not have.

---

## Provenance

The measured material comes from an inspection of Epic's Lyra Starter Game on
Unreal Engine 5.6, performed through a live editor bridge rather than by reading
files: 84 native data assets across 21 runtime classes, 23 zero-node definition
classes, and 37 inline actions across ten definitions and five action sets. That
method matters — see DD-01, which exists because a purely text-based census of
this layer is structurally incapable of seeing most of it.

Source addresses and asset paths stay in the research archive that produced this
skill. Each entry carries a stable identifier (`DD-01`, `DD-03`, …) resolving
back to the audited location there.

## Evidence boundary

Values obtained through the editor describe one project at one moment. Graph
assets whose internals no safe reader exposed — environment queries, state trees,
blackboards — were listed but not read, and are marked as such rather than
summarised. Re-run the recipes against your own project; the counts here show the
shape of a contrast, not a target.
