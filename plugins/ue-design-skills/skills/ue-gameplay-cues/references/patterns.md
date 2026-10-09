# Patterns: a cue subsystem read end to end

A worked reading of one real GameplayCue subsystem, audited as source. It is here
because the cue layer has a property that makes reading a class list useless:
**large parts of it can be present, correct, maintained, and unreachable**, and
nothing in the structure says which parts.

Individual failures are in [failure-modes.md](failure-modes.md), one entry each,
with a recipe. This file is about the shapes — what the subsystem is for, where
its cost lives, and which of its parts were actually running.

Markers: **[measured]** — read in source; **[derived]** — conclusion from measured
facts; **[open]** — not settled by source reading, and left open.

---

## 1. The trade the mechanism makes

A cue replaces an asset reference with a string-like tag, and a registry resolves
the tag by scanning content directories.

What you buy is real: gameplay assets carry no presentation payload, presentation
ships in a separate plugin, and the whole layer is absent on a dedicated server.

What you pay is one specific thing, and it is worth naming precisely:

> **You have exchanged a reference the toolchain checks for a join the toolchain
> does not check.**

A hard pointer that dangles is a cook error. A tag with no notify is silence.
Both halves of the join stay individually valid — the tag exists, the asset
exists — and no tool owns the relation between them. Everything in this file
follows from that one exchange.

This is why cues are an application of tag governance with a loading subsystem
attached, rather than a feature in their own right. Every rule about string joins
applies here first, and the loading subsystem is where the surprises live.

---

## 2. Where the complexity actually is

Reading the audited manager, the code divides into three very unequal parts:

| Part | Size | Status in the shipped configuration |
|---|---|---|
| Dispatch: tag arrives, notify is invoked | small | running |
| Discovery: scan directories, build the tag-to-asset index | moderate | running |
| Preload: async library load, preload set, always-loaded tags, reference tracking, GC and map-transition hooks | **most of the file** | **unreachable** |

The third row is the finding, and it is a shape rather than a bug.

A load-mode constant is set to "load everything upfront" **[measured]**. That
value short-circuits three separate switch sites **[measured]**, and the third of
them returns before the statements that bind the subsystem's delegates
**[measured]**.

The consequence **[derived]**: tag-loaded, post-garbage-collect and post-load-map
handlers are never bound; the preload set, the always-loaded set and the reference
tracker are never populated; and the project's own diagnostic command reports
zero, forever.

**That last detail is the trap.** A diagnostic reporting zero reads as "there is
nothing to preload". It actually means "this counter is dead". Anyone
investigating cue memory starts from a number that is not measuring anything, and
the natural next step — reading the preload implementation for a bug — is a day
spent in correct code. Recipe: GC-11.

The transferable rule is not about cues at all:

> Before debugging a subsystem, establish that its code runs. A diagnostic that
> reports zero is a claim about reachability until proven otherwise.

---

## 3. Knobs that are not knobs

In the same file, a namespace named after console variables contains three
declarations **[measured]**. Exactly one — a console *command* — is registered
with the engine. The other two, including the load mode from §2, are plain
statics **[measured]**.

Project-wide the ratio is one such namespace against eight real console-variable
registrations **[measured]**.

Two things make this worth an entry rather than a footnote:

1. **The naming is the entire defect.** The code is correct; it is a constant and
   behaves as one. What lies is the scope name, and nothing checks scope names.
2. **The obvious search fails.** Grepping for the literal `namespace Cvars` finds
   nothing, because real names are prefixed with the owning type. The first draft
   of the detection recipe for this returned zero hits and would have been read as
   "we do not have this problem". The corrected recipe searches for any namespace
   whose name *contains* the token. This is recorded in GC-12 with the trap
   spelled out, because the trap generalises further than the finding does.

---

## 4. Feature-plugin registration: the one thing done right

Cue path registration from a feature plugin has a timing constraint that is easy
to get wrong and invisible when you do: the manager builds its index during its
object library scan, so a path added after that scan is not indexed until
something triggers a rescan. In the editor, incidental rescans hide it. In a cold
packaged run, nothing does. Recipe: GC-14.

The audited project solves it with a pattern worth copying verbatim
**[measured]**:

> **The feature action is a pure data declaration; a lifecycle observer is the
> executor.**

The action object declares the directory list and validates it in the editor — and
has *no activation body at all* **[measured]**. A separate observer registered
with the feature policy listens for the earliest lifecycle phase and performs the
registration for every action of that type it finds. Paths are added with the
rescan flag off, and a single index rebuild follows **[measured]**.

The empty activation body is the part people delete when adopting this, because an
action with no `Activate` looks unfinished. It is not: it is the point.

### And the asymmetry that survived inside it

The same function pair is also the audit's best example of a near-miss
**[measured]**:

| Direction | Manager resolution | Refresh call |
|---|---|---|
| Registering | project's own manager subclass | present |
| Unregistering | engine base class | **absent** |

Both calls compile and both work, because the subclass inherits the method. They
are equivalent exactly as long as the subclass adds no bookkeeping **[derived]**.
And the refresh performed on the way in has no counterpart on the way out, so the
asset manager keeps describing directories that have been removed **[derived]**.

Recipes: GC-15, GC-16.

**What redeems it, and what to actually copy:** the removal path counts what it
removed and asserts the count against what was added **[measured]**. In an audit
whose dominant finding across the whole project was "add works, remove is
incomplete", this was the one place where teardown was both implemented and
asserted. Copy the assertion; fix the asymmetry it sits next to.

---

## 5. The network rule, and why it is first

Cues never run on a dedicated server, because the presentation layer does not
exist there.

Every consequence of that is a design constraint rather than a caution:

- a notify may not carry gameplay side effects — on a dedicated server that code
  never executes (GC-01);
- cue parameters are a lossy channel, and what a conversion helper drops is
  dropped silently on every client. The audited helpers drop a context tag
  container in **both** directions, each with its own unfinished-work comment
  **[measured]** (GC-17);
- delivery is unreliable by design: packet loss, relevancy changes and mid-effect
  joins all produce missed cues;
- cue assets belong in the client bundle only.

The acceptance test that covers all four at once is cheap and nobody runs it: **run
the feature on a dedicated server with every cue asset removed, and require
byte-identical gameplay results.**

---

## 6. What source reading could not settle

Two limits, stated because they bound the claims above:

1. **Blueprint call sites are invisible to text search.** The conversion helpers
   in §5 have zero C++ callers and are Blueprint-callable **[measured]**. That is
   recorded as **[open]** — an open question, not dead code. Deleting them on the
   strength of an empty `rg` result is GC-18, committed by the person who wrote
   the audit. (It was not.)
2. **Editor memory figures do not describe shipping.** The experience loader's
   bundle selection unions client and server bundles when running in the editor
   **[measured]**, so in-editor cue residency is overstated by whatever the server
   set contains. Editor measurements are good for direction of change and nothing
   else (GC-20).

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6, read as source
rather than run, in a single workspace. Source addresses stay in the research
archive that produced this skill; each `GC-` identifier resolves back to the
audited location there, so any specific claim above can be produced on request.

## Evidence boundary

One project, one engine version, one workspace. These are examples and failure
evidence, not guarantees about other engine versions or other samples. Several
claims are explicitly marked open and stay open. Re-run the recipes in
[failure-modes.md](failure-modes.md) against your own tree before acting on
anything here.
