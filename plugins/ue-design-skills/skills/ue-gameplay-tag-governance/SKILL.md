---
name: ue-gameplay-tag-governance
description: >-
  Govern GameplayTags in Unreal Engine as a typed vocabulary rather than loose
  strings: choosing declaration source (native macro, project ini, plugin ini,
  DataTable, platform ini, runtime), namespace design, constraining tag inputs
  with meta=(Categories=...), exact vs hierarchical matching, redirects and
  renaming, replication of tag sets, tag-driven counters, and auditing an
  existing tag inventory. Use when adding a tag namespace, wiring systems
  through tags, reviewing tag usage, or debugging a tag-driven feature that
  silently does nothing.
---

# UE gameplay tag governance

The invariant:

> A GameplayTag is a foreign key with no database behind it. Every tag join must
> be validated on both sides by something other than the compiler.

Measured patterns from a reference product: [patterns](references/patterns.md).
Eighteen detection recipes for silent tag failures:
[failure modes](references/failure-modes.md).

Read the failure modes before adopting or reviewing a tag-driven design. Each
entry names the mechanism, why it stays silent, why the obvious check misses it,
and a command you can run against your own tree.

Related skills: `ue-gameplay-messaging`, `ue-gas-architecture`,
`ue-modular-gameplay`, `ue-input-architecture`, `ue-architecture-guardrails`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Why tags need governance at all

A tag replaces a compile-time reference with a runtime string comparison. That is
the whole point — and the whole cost. Once a system is joined by a tag:

- the compiler no longer sees the dependency;
- "find all references" no longer finds it;
- a typo is not an error, it is an empty result;
- deleting the producer does not break the consumer's build.

The characteristic failure is therefore never a crash. It is **nothing happens**,
reported weeks later by a designer, in a build nobody can bisect.

Governance means deliberately re-adding the checks the compiler stopped doing.

---

## 2. Decide the declaration source before the first tag

Unreal accepts tags from at least six independent sources. They do not behave
the same and they are not equally visible to search.

| Source | Form | Compile-time symbol | Found by grep pattern |
|---|---|---|---|
| Native, registered | `UE_DEFINE_GAMEPLAY_TAG_COMMENT` + `_EXTERN` in a header | yes | symbol name |
| Native, file-local | `UE_DEFINE_GAMEPLAY_TAG_STATIC` | file-local only | symbol name |
| Project config | `+GameplayTagList=(Tag="...")` in the project tag ini | no | `+GameplayTagList=` |
| Plugin config | `GameplayTagList=(Tag="...")` — **no leading `+`**, different section | no | `GameplayTagList=(Tag=` |
| DataTable | binary asset referenced by `+GameplayTagTableList` | no | not text-searchable |
| Runtime | `AddNativeGameplayTag` during module startup | no | call site only |

### Rules

1. **Default to native, registered tags** for anything C++ reads or writes. They
   give Ctrl+Click, rename support, and a link error instead of a silent miss.
2. **Use ini only for namespaces owned by data**, where designers add entries
   without engineers — cosmetic variants, surface types, platform traits.
3. **Never split one namespace across sources.** A namespace half in C++ and half
   in ini has no single place to read its vocabulary.
4. **Record the source of every namespace** in one document. This is the only
   defence against source #6, which no static inventory can see.
5. **Never trust a single grep pattern** when auditing. Plugin ini syntax differs
   from project ini syntax by exactly one character, and a pattern anchored on
   `+` returns a confident, wrong zero. Recipe: TG-05.

---

## 3. Design the namespace as a tree that means something

Hierarchy is not decoration. `MatchesTag` and partial matching turn parentage into
executable logic: a system asking "is this an action?" will answer yes for every
descendant, forever, including ones added next year by someone who never read that
call site.

### Rules

1. **A parent tag is a promise.** Adding a child enrols it in every hierarchical
   check that already matches the parent. Only create a child if that enrolment
   is intended.
2. **Do not encode two dimensions in one path.** `Weapon.Rifle.Silenced` conflates
   class and modifier; the modifier cannot then be queried independently. Use two
   tags.
3. **Depth is coupling.** Every additional level is another place a hierarchical
   query can accidentally match.
4. **Reserve a leaf-only convention** for tags used as identities (channels, cue
   names, state nodes). If a tag is an identity, nothing should ever be its child.
5. **Document each parent's contract** where the parent is declared — what a
   descendant is required to satisfy.

### Naming

Pick one scheme and enforce it in review:

```text
<Domain>.<Category>.<Specific>

Ability.Type.Action.Reload
InitState.DataAvailable
Event.Combat.Elimination
Platform.Trait.Input.PrimaryController
```

Do not abbreviate inconsistently. Do not mix singular and plural at the same
level. These are unenforceable by tooling and therefore purely a review duty.

---

## 4. Constrain every tag input

An unconstrained `FGameplayTag` UPROPERTY offers the designer the entire project
vocabulary — thousands of entries, of which a handful are legal. This is the
single highest-leverage guardrail available, and it is one line:

```cpp
UPROPERTY(EditAnywhere, meta = (Categories = "Ability.Type.Action"))
FGameplayTag ActionTag;

UPROPERTY(EditAnywhere, meta = (Categories = "Event.Combat"))
FGameplayTagContainer ObservedChannels;
```

### Rules

1. **Every editable tag property gets `Categories`.** No exceptions for "it's
   obvious" — obvious is exactly what a typo defeats.
2. **`UPARAM(meta=(Categories=...))`** for `BlueprintCallable` tag arguments.
3. **Verify the constraint actually resolves.** `Categories` pointing at a
   non-existent namespace produces an *empty* dropdown, not an error. It looks
   like a working constraint and is worse than none, because it silently blocks
   the designer while passing review. Recipe: TG-03.
4. **Re-verify `Categories` after any namespace rename.** It is a string; the
   rename tool does not touch it.
5. **Measure coverage**: count tag properties versus properties carrying
   `Categories`. Anything below full coverage is a list of known holes, and
   should be tracked as such. Recipe: TG-04.

### Verification procedure for a constraint

Open the property in the editor. If the dropdown is empty, the namespace does not
exist. This takes five seconds and is the only check that exists.

---

## 5. Choose exact versus hierarchical matching per call site

Three different operations look alike and mean different things:

| Call | Semantics |
|---|---|
| `A == B` | exact identity |
| `A.MatchesTagExact(B)` | exact identity, explicit |
| `A.MatchesTag(B)` | A is B **or a descendant of** B |
| `Container.HasTag(B)` | any element matches B or descends from it |
| `Container.HasTagExact(B)` | any element is exactly B |

### Rules

1. **State the intent at every call site.** Prefer the explicit `...Exact` form
   even when `==` would do, so the next reader does not have to infer.
2. **Never mix the two forms across one feature's read and write paths.** If a
   rule is stored hierarchically and queried exactly (or the reverse), the feature
   works for the tags that were tested and fails for the rest — the worst possible
   failure distribution. Recipe: TG-07.
3. **Hierarchical matching is a public API.** Once a system matches on a parent,
   the parent's whole subtree is part of that system's contract.
4. **Default to exact** for identities; use hierarchical only where "any kind of
   X" is genuinely the rule.

---

## 6. Renaming: redirects are not optional

A tag lives in binary assets, ini files, DataTables, and blueprint graphs. A
rename without a redirect silently zeroes every one of those references.

```ini
[/Script/GameplayTags.GameplayTagsSettings]
+GameplayTagRedirects=(OldTagName="Ability.Type.Action.Fire",NewTagName="Ability.Type.Action.WeaponFire")
```

### Rules

1. **Add the redirect in the same commit as the rename.** Not after; a build
   between the two loses data permanently in any asset that gets resaved.
2. **Never delete a redirect** until every asset in every branch has been resaved
   and verified. Redirects are cheap; lost designer work is not.
3. **A project with zero redirects and a non-trivial tag history has already lost
   references** — or has never renamed a tag, which is itself worth confirming.
   Recipe: TG-18.
4. **Typos are renames.** Fixing a misspelled tag requires a redirect exactly like
   any other rename.

### The symmetric-typo trap

A misspelled tag that is misspelled *identically* in every location works
perfectly. It will keep working until one person fixes one of the spellings —
at which point the join breaks with no error at either end. Treat a discovered
typo as a coordinated multi-file change with a redirect, never as a local fix.
Recipe: TG-02.

---

## 7. Replication of tag vocabulary

Tags replicate as indices, not strings, when fast replication is enabled. That
requires **client and server to have byte-identical tag registries**.

### Rules

1. **Any source of tags that can differ between builds breaks fast replication.**
   That includes plugin-supplied tags when the plugin loads on one side only, and
   any runtime tag registration.
2. **Register tags before networking starts**, unconditionally on both sides.
3. **Watch the replicated container size cap.** It limits how many tags fit in one
   replicated container; exceeding it is a runtime failure, not a compile error.
   Recipe: TG-11.
4. **Do not gate tag registration on `IsRunningDedicatedServer()` or platform.**
   Gate the *content* those tags refer to, never the vocabulary.

---

## 8. Tag-driven counters and state

Tag-to-count containers (stacks) are a common pattern for ammo, charges,
resources. They are arithmetic wearing a tag as a label, and inherit arithmetic's
problems.

### Rules

1. **Validate the amount, not only the tag.** A zero or negative delta that
   silently returns is a lost write that reports as "the ability did nothing".
   Recipe: TG-12.
2. **Guard the accumulator.** Unchecked `int32` addition on a stack count is an
   overflow waiting for an idle-game or a modifier loop. Recipe: TG-13.
3. **Decide the contract for removing more than exists**, then implement it —
   clamp to zero, fail loudly, or allow negative. Silence is not a contract.
4. **Keep the map and the array in sync in every replication callback** if the
   container maintains both a replicated array and a lookup map. Every
   `PreReplicatedRemove` / `PostReplicatedAdd` / `PostReplicatedChange` must
   update the map, or clients read stale counts.

---

## 9. String-to-tag lookup is a debug tool

Resolving a tag from a runtime string — especially with partial/substring
matching — returns the first registry match in registry order. That order is not
stable against adding unrelated tags.

### Rules

1. **Confine partial matching to cheat/console/debug paths.**
2. **Do not export a partial-match helper with a permissive default** across a
   module boundary. The first production caller who passes `true` gets a
   non-deterministic tag and no warning. Recipe: TG-09.
3. **Exact lookup with explicit failure handling** is the only form allowed in
   gameplay code.

---

## 10. Auditing an existing tag inventory

Run this before trusting any tag-driven system you did not write. Each step maps
to a recipe in the failure modes.

```text
1. Count declarations per source (all six). Reconcile against the documented
   list. Count with two patterns, not one.                          TG-05, TG-06
2. Count editable tag properties; count those with Categories.
   Report the ratio.                                                      TG-04
3. Resolve every Categories string against the actual namespace list.
   Empty dropdown = broken constraint.                                    TG-03
4. List every parent tag used in a hierarchical match; enumerate its
   current descendants and confirm each one belongs.                      TG-08
5. Search for tags declared but never read, and read but never declared.   TG-16
6. Count redirects. Zero redirects plus renamed tags in history =
   data loss.                                                             TG-18
7. Diff the tag registry between a client build and a server build.        TG-10
```

Steps 1 and 3 find most real defects. Step 4 finds the ones that will appear
later, when someone adds a child.

---

## 11. Review checklist

- [ ] Namespace has one documented declaration source.
- [ ] Tags read by C++ are native, not ini-only strings.
- [ ] Every editable tag property/parameter carries `Categories`.
- [ ] Every `Categories` string resolves to a namespace that exists.
- [ ] Exact vs hierarchical matching is explicit and consistent per feature.
- [ ] Parent tags used in hierarchical matches have a documented contract.
- [ ] Renames ship with redirects in the same commit.
- [ ] Tag registration is unconditional and identical on client and server.
- [ ] Tag counters validate amount and guard overflow.
- [ ] Partial string lookup exists only in debug paths.
- [ ] A tag-driven feature has a test that fails when the tag is wrong.

---

## 12. Tests

The purpose of these tests is to convert "nothing happened" into a red build.

### Vocabulary

- every tag referenced in C++ resolves at startup;
- every tag in ini is referenced somewhere, or is explicitly marked data-owned;
- registry contents identical between client and server targets.

### Matching

- exact query does not match a descendant;
- hierarchical query matches every current descendant;
- adding a new child does not change any exact query's result.

### Constraints

- each `Categories` string yields a non-empty candidate set;
- a property rejects a tag outside its category.

### Counters

- add zero, add negative, remove more than present, remove from empty;
- replication callbacks leave map and array consistent;
- large accumulations do not overflow.

### Migration

- renaming a tag with a redirect preserves asset references;
- loading an asset saved with the old name resolves to the new tag.

---

## 13. When not to use a tag

Use a stronger construct when:

- the set of values is closed and owned by code → **enum**;
- the value selects an implementation → **class reference or DataAsset**;
- the join must be checked at compile time → **interface or typed pointer**;
- exactly one consumer exists and it is in the same module → **direct call**.

A tag earns its cost when the vocabulary is open, the consumers are unknown to the
producer, and the join genuinely crosses a module or data boundary. Used anywhere
else, it converts a compile error into a silent runtime no-op — which is the only
thing it reliably does.

---

## Provenance

The findings behind the failure modes come from a line-by-line source audit of
Epic's Lyra Starter Game on Unreal Engine 5.6, read rather than run. Source
addresses stay in the research archive that produced this skill; what ships is the
detection recipe, because an address in someone else's tree is not something you
can act on and a recipe is.

Each entry carries a stable identifier (`TG-01`, `TG-02`, …) that resolves back to
the audited location in that archive. If you need the original address to settle a
dispute, it exists and can be produced.

## Evidence boundary

The measured material refers to one specific reference project on one engine
version in one workspace. It is evidence of failure modes, not a guarantee about
other engine versions or other samples. Re-run the recipes against your own tree
before trusting any specific claim — including the counts, which are properties of
that project on that day and are quoted only to show the shape of the contrast a
recipe produces.
