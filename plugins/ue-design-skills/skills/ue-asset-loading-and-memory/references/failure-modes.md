# Failure modes: asset loading and CPU memory

Ten ways a project loads more than it meant to, keeps it forever, and reports
nothing.

The shared property here is different from the other skills in this bundle, and
it is worth stating because it changes what the recipes look like: **memory
defects are not events.** There is no moment at which something goes wrong. An
asset is loaded because a reference exists; it stays because a reference still
exists. Both are correct behaviour at every instant, and the failure is a
property of an aggregate that no single frame contains.

That has two consequences for detection. First, **counting is the primary
instrument** — call sites, unload paths, packages in a closure. Second, a count of
**zero** is often the finding: no release API, no unload call, no bundle tag.
Several recipes below are therefore searches you expect to come back empty, and
the empty result is the evidence rather than the absence of it.

Recipes use `rg` from a project source root, and were executed against the
audited project while this file was written.

---

## References

### AL-01 - A reference type chosen by convenience, costing three orders of magnitude

**Mechanism.** A definition holds hard references to the things it selects — a
class, a data asset, a package of capabilities — because hard references are
simpler and always resolve. Loading the definition therefore loads its entire
transitive closure.

**Why it is silent.** Everything works, immediately and correctly. Hard
references never fail, never arrive late and never need a fallback. The cost is
paid once, at load, in a place nobody attributes to this asset.

**Why the obvious check misses it.** Reviewing the definition shows a handful of
properties — five or six references, all necessary. The cost is not the direct
count but the closure, and the closure lives in assets this file never mentions.
Nothing at the declaration hints at its size.

**Symptom.** A boot or transition hitch attributed to "the level" or "shaders".
In the audited reference the same architectural family ranged from **two**
packages when addressing by identifier to **over a thousand** when holding a hard
chain — a difference produced entirely by reference type.

**Detect.** Direct counts are not the measurement; build the closure. From
source you can only find the candidates:

```bash
rg -n "TObjectPtr<|TSubclassOf<" --glob "*.h" . | rg -i "definition|data|archetype"
rg -n "TSoftObjectPtr<|TSoftClassPtr<" --glob "*.h" . | rg -i "definition|data"
```

Then, from the editor or a registry dump, compute the transitive hard closure per
definition and rank by size. **Compare each against its architectural layer**: a
catalog entry with a large closure is the finding; an archetype with one may be
correct and budgeted.

**Guardrail.** Write the intended reference type into the property metadata and
validate it. Re-measure the closure of every archetype-level definition when it
changes; a closure without a recorded baseline cannot be reviewed.

---

### AL-02 - A bundle name that no property uses

**Mechanism.** A bundle tier is declared as a constant and requested at load time
alongside the role bundles. No property in the codebase is annotated with it.

**Why it is silent.** Requesting a bundle that matches nothing is not an error.
The load succeeds, the other bundles arrive, and the tier appears to be part of
the loading strategy.

**Why the obvious check misses it.** The constant is declared, referenced at the
request site, and named meaningfully. "Is this bundle used?" answers yes at two
places. The absent half is the **annotation**, and nothing connects a request to
the properties it is meant to gather.

**Symptom.** No runtime symptom at all. The cost is a false model: the team
believes there is an equipped-content tier, plans around it, and the loading
strategy has one fewer dimension than it appears to.

**Detect.** Compare declared bundle names against annotated ones:

```bash
rg -n "AssetBundles=\"[^\"]*\"" --glob "*.h" . -o | sed 's/.*AssetBundles=//' | sort -u
rg -n "BundlesToLoad.Add|LoadStateClient|LoadStateServer|FName\(TEXT\(\"" --glob "*.cpp" . \
  | rg -i "bundle"
```

Any name in the second list and not the first is requested and unpopulated. In
the audited project one such tier is requested on every load regardless of net
mode, and appears in no annotation in the entire source tree.

**Guardrail.** Assert at startup that every requested bundle name matches at
least one annotated property, or remove the tier. A bundle nobody fills is a
plan, not a mechanism.

---

## Startup

### AL-03 - Progress scaffolding where every layer is independently broken

**Mechanism.** A startup framework reports per-job progress. Three things must
work: the job must hand back a load handle, a throttle must permit an update, and
a receiver must render it.

**Why it is silent.** A progress bar that does not move looks like a fast load or
a coarse-grained one. There is no error state for "progress was never reported",
and the framework's logs still print per-job timings, so it looks instrumented.

**Why the obvious check misses it.** Each layer is individually plausible. The
macro compiles and runs the job. The throttle has a sensible-looking comparison.
The receiver is a real function with a real name. Only reading all three together
shows that the handle is never assigned, the comparison can never be true, and
the receiver's body is a comment.

**Symptom.** No visible progress during startup, so the slowest job is unknown.
The team optimizes what it guesses rather than what it measured.

**Detect.** Check the three layers separately, and expect each to look fine:

```bash
# 1. does anything assign the out-parameter handle?
rg -n -B4 -A8 "TSharedPtr<FStreamableHandle>& \w+" --glob "*.h" --glob "*.cpp" .
# 2. is the throttle comparison the right way round?
rg -n -B2 -A6 "LastUpdate|LastReport" --glob "*.h" --glob "*.cpp" .
# 3. does the receiver have a body?
rg -n -A4 "UpdateInitial\w*Percent|::UpdateProgress" --glob "*.cpp" .
```

In the audited project the throttle reads `LastUpdate - Now > interval`, where
the elapsed value is monotonically increasing and the stored value starts at
zero — so the difference is never positive and the branch is unreachable.

**Guardrail.** Test that progress fires at all before trusting it. A callback
that has never been observed to run is indistinguishable from one that cannot.

---

### AL-04 - Global data with soft references and no bundle tags

**Mechanism.** A globally-loaded data asset holds soft class pointers to effects
or classes used across the game. The asset is loaded at startup; its soft targets
are not, because nothing tags them into a bundle.

**Why it is silent.** The pointers resolve on demand and everything works. The
first resolution is a synchronous load, and it lands in whatever frame first
needs it — commonly the first damage event, which is already a busy frame.

**Why the obvious check misses it.** The asset is loaded at startup, which
answers "is the global data preloaded?" with yes. Whether its *contents* are
preloaded is a different question, decided by annotations that are absent — and
absent annotations look exactly like properties that do not need them.

**Symptom.** A hitch at first damage, first dynamic tag, or first use of any
global class. Reproduces once per session, which makes it easy to dismiss.

**Detect.** Find globally-loaded data assets and check their soft properties for
tags:

```bash
rg -n -A20 "class \w*GameData" --glob "*.h" . | rg "TSoftClassPtr|TSoftObjectPtr|AssetBundles"
```

Soft properties with no bundle annotation on a startup-loaded asset is the
finding. Then find where they first resolve:

```bash
rg -n "GetSubclass\(|GetAsset\(" --glob "*.cpp" . | rg -i "gamedata"
```

**Guardrail.** Tag them and load them with the mode. A soft reference on a global
asset without a bundle is a deferred synchronous load with an unpredictable
trigger.

---

## Retention

### AL-05 - A keep-in-memory pool with no way out

**Mechanism.** A convenience loader resolves a soft pointer, and adds the result
to a reflected set so it stays alive. The keep-in-memory parameter **defaults to
true**. No removal API exists.

**Why it is silent.** It is a cache doing its job. Every call is faster than the
last, nothing is ever missing, and the set has no size at which it complains.

**Why the obvious check misses it.** The parameter is visible in the signature
and reads as a considered choice — which it is, at the declaration. At every call
site it is invisible, because it is defaulted. Reviewing a call shows a load; the
retention is in the default argument of a function in another file.

**Symptom.** Residency that only grows across a session, unaffected by mode
changes, map travel or anything else. Because the growth is monotonic and
attributable to nothing, it is usually first noticed as "we are over budget"
rather than as a leak.

**Detect.** Count additions against removals, and read the default:

```bash
rg -n "LoadedAssets|KeptAssets|RetainedAssets" --glob "*.h" --glob "*.cpp" .
rg -n "bKeepInMemory" --glob "*.h" . | head
```

In the audited project the set is added to at one site, read at two — both inside
a dump command — and **never removed from anywhere**, with the flag defaulting to
true and no call site in the project passing false.

**Guardrail.** Default to false, or make the flag explicit at every call site.
Ship a paired release API and a console command that prints the set's size. A
cache without an eviction policy is a leak with a nicer name.

---

### AL-06 - Strong keys pin graphs; raw keys lose them

**Mechanism.** Two opposite errors in the same area. A map keyed by a **strong
object pointer** keeps its key alive, so one missed unregister pins an actor and
everything it owns. A map holding object pointers inside a **non-reflected**
struct is invisible to garbage collection, so the values can be collected while
still referenced.

**Why it is silent.** The first has no symptom until memory is measured — the
actor is dead in gameplay terms and alive in memory. The second has no symptom
until collection happens to run at the wrong moment, which is rare and
non-deterministic.

**Why the obvious check misses it.** Both look like ordinary containers. The
difference between a reflected and a non-reflected struct is one macro, and the
difference between a strong and a weak key is one wrapper type. Neither reads as
a memory decision at the declaration site.

**Symptom.** Actors that never disappear from a memory report, or — from the
other error — a crash on a pointer that was valid a moment ago. Both are usually
investigated far from the container.

**Detect.** Audit direction as well as presence:

```bash
# strong keys
rg -n "TMap<TObjectPtr<\w+>|TMap<A\w+\*" --glob "*.h" .
# object pointers outside the reflection system
rg -n -B6 "TArray<U\w+\*>|U\w+\* \w+;" --glob "*.h" . | rg -v "UPROPERTY"
```

Both patterns appearing in one codebase is common and is worth stating plainly in
a review: they are not variants of one mistake, they are opposite mistakes, and a
fix for one does not address the other.

**Guardrail.** Prefer object keys with explicitly-owned values plus a periodic
prune. Every object pointer that must survive collection is reflected; every one
that must not is weak. There is no third category.

---

### AL-07 - No unload path anywhere

**Mechanism.** Content is loaded per mode through bundles. Nothing releases it —
no unload call, no bundle removal, no explicit collection request.

**Why it is silent.** For a session-based game with a process restart between
matches, it is correct and cheap. The absence only becomes a defect when modes
change within one process, which is a product decision made later.

**Why the obvious check misses it.** There is nothing to see. Reviewing the
loading code finds a complete, well-built loading path; the absence of a
symmetric release path is not a line anyone reads. The authors of the audited
project recorded it themselves, in comments, and shipped it.

**Symptom.** Memory that never returns to baseline across mode changes. The first
mode's content is resident for the whole session alongside the second's.

**Detect.** One command, and the expected answer is a row of zeros:

```bash
for p in UnloadPrimaryAsset bRemoveAllBundles CollectGarbage FlushAsyncLoading TrimMemory; do
  printf "%-24s %s\n" "$p" "$(rg -c "$p" --glob '*.cpp' --glob '*.h' . | wc -l)"
done
```

In the audited project every one of those is **zero**. That table is the finding,
and it takes ten seconds to produce in any project.

**Guardrail.** Either implement release, or write down that mode changes require
map travel. An undefined middle is what grows.

---

## Failure handling

### AL-08 - Cancellation bound to the completion callback

**Mechanism.** An asynchronous load binds a completion delegate, and binds the
**same** delegate to cancellation.

**Why it is silent.** Cancellation is rare — it needs a mode change or a world
teardown mid-load. When it does happen, the system reports success and proceeds,
and every downstream consumer of a missing asset fails silently in its own way.

**Why the obvious check misses it.** Both delegates are bound, which is more
than most code does. The lambda is short and reads as deliberate. Nothing
distinguishes "handle cancellation" from "handle cancellation *correctly*" at the
binding site.

**Symptom.** A mode reports loaded with partially loaded content. Downstream,
unloaded classes resolve to null and are skipped without logging, so the result
is a mode missing several features and no diagnostic anywhere.

**Detect.** Compare the two bindings:

```bash
rg -n -B6 -A6 "BindCancelDelegate" --glob "*.cpp" .
```

If the cancel lambda executes the completion delegate, that is this defect. In
the audited project it does, in three lines, immediately below the completion
binding.

**Guardrail.** Cancellation enters a distinct state — failed, or cancelled — that
the loading screen and the consumers can observe. Success is a claim; make it
provable.

---

### AL-09 - An asynchronous result that is never read

**Mechanism.** A plugin or asset load completes with a result parameter carrying
success or failure. The callback decrements a counter and ignores the parameter.

**Why it is silent.** The counter reaches zero either way, so the pipeline
completes. A failed load is indistinguishable from a successful one at every
point downstream.

**Why the obvious check misses it.** The callback has the right signature and is
bound correctly. An unused parameter in a delegate signature produces no warning,
because the signature is imposed by the API rather than chosen.

**Symptom.** A feature that silently does not activate, in a build where one of
its assets failed to load. The failure is attributed to the feature.

**Detect.** Find completion callbacks whose result parameter is unused:

```bash
rg -n -A8 "::On\w*LoadComplete\(const \w+::\w+& Result\)" --glob "*.cpp" . \
  | rg -c "Result"
```

A count of one — the signature only — is the finding.

**Guardrail.** Read the result, log the failure with the identifier that failed,
and enter a failed state. An ignored result is a decision to be surprised later.

---

## Measurement

### AL-10 - Measuring residency in the editor

**Mechanism.** The editor loads both client and server bundles, because it must
be able to run either role.

**Why it is silent.** The measurement completes and produces a number. The number
is real; it just describes a configuration that ships to nobody.

**Why the obvious check misses it.** It is intentional and correct — nothing to
find in the memory system. The inflating condition is a boolean expression in the
bundle-selection code, and nobody profiling memory reads the loading policy.

**Symptom.** Memory budgets built on editor numbers, wrong in a direction that
feels safe until a platform limit is real.

**Detect.** Read the bundle-selection condition before trusting any in-editor
number:

```bash
rg -n -B2 -A6 "bLoadClient|bLoadServer|LoadStateClient" --glob "*.cpp" . | rg "GIsEditor"
```

An editor branch that unions both sets means editor residency is directional
only. The audited project does this in two places, and one of them carries a
comment from its authors noting the resulting hitching.

**Guardrail.** Residency numbers require a packaged build of the target role. Use
the editor for relative structural comparison, and say so whenever an in-editor
number is quoted.
