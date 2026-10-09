# Adoption patterns: a worked classification

This is the C1-C5 classification from `SKILL.md` applied end to end against one
real reference project, plus the tax analysis and vocabulary hygiene that follow
from it.

Individual silent failures are not repeated here. They live in
[failure modes](failure-modes.md), one entry each, with a detection recipe you
can run against your own tree. This file is about *how the categories behave* and
what each one costs, so that when you meet a new element you can place it.

---

## 1. What each category feels like from the inside

The categories are not severity levels. They are answers to a different question:
**what does the author of the reference believe about this element?**

| | Author's belief | Your evidence | Your move |
|---|---|---|---|
| **C1 Defect** | "this works" | it demonstrably does not | fix the line, keep the design |
| **C2 Showcase stub** | "this is not finished" | reads as finished | implement or delete the field |
| **C3 Scope narrowing** | "a sample does not need this" | nothing is wrong at all | budget it or accept the risk in writing |
| **C4 Architecture tax** | "this is worth it for us" | correct, working, expensive | adopt by need, not completeness |
| **C5 Foreign legacy** | nobody believes anything | a name from another product | rename on entry |

The dangerous boundary is C2 against C3, because from the outside they look
identical: a mechanism that produces a neutral result forever. The distinction is
whether the author intended to come back. It changes nothing about your cost, and
everything about how you talk to your team: a C2 is a hole in the reference, a C3
is a hole in your understanding of what you bought.

---

## 2. C1 - Defects

A defect in a reference project is the cheapest category and the least
interesting. Fix the line, keep the surrounding design, and do not let it
discredit the pattern that contains it.

Three shapes recur often enough to be worth naming:

**The filter that filters nothing.** A field constrains designer input to a
namespace, and the namespace does not exist in this project. The picker comes up
empty, which reads as "no matching entries yet" rather than "this constraint is
misconfigured". Where such filters are rare in a codebase, each one is load-bearing
and worth checking individually.

**The symmetric typo.** A misspelled identifier used as a string join across
config, code and platform overrides works perfectly, because every side misspells
it identically. It is only discovered by someone fixing the spelling in one place.
The lesson is not "check spelling"; it is that when a string literal is the join,
correctness means *all sides agree*, and the way to get that is one declaration
site referenced everywhere else.

**The loop over an empty container.** A local collection is declared next to a
TODO, never populated, and then iterated. The loop reads as a mechanism. It is a
placeholder for one.

None of these survives a careful read of the consumer. They survive a read of the
declaration, which is why they get copied.

---

## 3. C2 - Showcase stubs

The defining property is precise, and worth memorizing:

> The declaration exists. The consumer exists. The **writer** does not - or the
> consumer is a literal.

Neither a compiler warning nor an "unused symbol" search finds these, because the
symbol is used. Reading the code convinces you it is wired up. This is why the
highest-yield check in the whole skill is searching for assignment rather than
mention.

Sub-shapes, each with an entry in the failure-mode index:

- a tunable compared against a timestamp that is never assigned (RA-06);
- an ordering field stored, copied through the entire API surface, and never
  compared (RA-07);
- an editable tag container whose consumer is a hardcoded `false` (RA-08);
- a parameter threaded through several call layers, whose only call site passes a
  literal, waiting for a subsystem that was never written (RA-09);
- a field dropped silently in both directions of a conversion helper (RA-10);
- a replicated structure with no callers at all (RA-11).

### The trap inside the trap

A stub can be deeper than its TODO admits. In one measured case, implementing the
obvious missing condition would still not restore the intended behaviour, because
a second method on the same class overwrites the designer-authored values on its
first call. The TODO points at one line; the repair is two.

Treat a TODO as evidence that the author knew about *something*, not as a
specification of what is missing. Read the whole class before pricing the fix.

### What to do

Either implement it before exposing it, or delete the field. There is no third
option that is honest. An editable property whose consumer is a literal constant
is a trap for designers, who will tune it for days and then report that the build
is broken.

---

## 4. C3 - Deliberate sample-scope narrowings

Nothing here is broken. The reference is internally consistent with every one of
these. They become expensive only when the sample becomes the base of a product.

This is the category that costs a subsystem rather than a line, and the one that
adoption discussions habitually skip, because there is nothing to point at.

### The largest one: no lag compensation

When a reference project has no server-side rewind - no historical position
storage, no custom saved-move pipeline - everything downstream follows
mechanically:

- the server does not trace, because tracing is gated on being locally
  controlled, and the server controls nobody;
- the client's target data is consumed as authoritative, because there is nothing
  to compare it against;
- damage falloff is computed from the client's own reported trace origin;
- surface-material multipliers are taken from the client's reported hit.

Read as a defect list, this is four bugs. Read correctly, it is one design
decision with four consequences. "The reference forgot to validate hits" is the
wrong diagnosis, and it leads to four local patches that do not add up to server
authority.

**Adoption decision:** choose a hit-registration model *before* borrowing a weapon
stack. Server-authoritative with rewind, client-claim with plausibility checks, or
full trust. A sample usually implements the third. Each has a different cost and a
different cheat surface, and the choice dictates how abilities, tracing and damage
are structured - which is why it cannot be retrofitted cheaply.

### Configuration that ships disabled

A subsystem can be present, implemented, documented by its own console variables,
and switched off in shipped configuration with an essentially empty routing table.
The implementation being there tells you nothing about whether it was ever
exercised. Copying that configuration copies untested settings, and the settings
are the part that needs production-scale traffic to tune.

### Machinery made unreachable by a mode switch

A load-mode enum set to "load everything upfront" can short-circuit every branch
that would install a delay-load subsystem's delegates. The inherited machinery is
functional; the sample bypasses it. The diagnostic tools built for that subsystem
then report zeros forever, which reads as "nothing to report" rather than "this
code never runs".

Important qualification: this is a *configuration choice of the sample*, not an
engine defect. Diagnosing it as a broken engine feature sends you into engine
source for no reason. Check the mode before you check the mechanism.

### The rest, in one table

| Narrowing | What it costs a product |
|---|---|
| State transitions on a health or death component written without an authority check, on public virtual methods | Death becomes a state with no owner; every caller is an authority |
| Team or faction lookup that fails open on an invalid argument | Unknown membership resolves to "damage allowed" |
| No tag or asset redirects configured anywhere | Every rename is a breaking change with no migration path |
| A reliable server RPC declared without validation | Unvalidated input from the network; a Blueprint-authority marker does not constrain C++ callers |
| An init-state gate that admits simulated proxies with no controller | "Ready" means something different per net role |

Each row is a line item in your adoption budget, not a bug report against the
reference.

### The rule

> Every C3 narrowing you accept must be written down as an accepted risk with an
> owner, or scheduled. "We did not notice" is the only unacceptable outcome.

---

## 5. C4 - Architecture tax

Correct, working, and sized for the reference author's team, release cadence and
platform matrix. The question is never "is this good architecture". It is "does my
product have the problem this solves".

### Measured shape of one reference project

| Element | Measured | When it stops paying |
|---|---|---|
| Definition-to-instance stack: experience selects feature plugins, which contribute action sets, which grant abilities and data | 5 gameplay-feature plugins out of 81 plugins total | One game mode and no post-launch content: you buy distributed control flow and receive no modularity in return |
| C++ / Blueprint boundary | 493 Blueprints scanned, median 5 nodes each; 1256 `BlueprintCallable` entry points against 45 `BlueprintImplementableEvent` plus `BlueprintNativeEvent` override points | The 28:1 ratio means C++ exposes *calls*, not *extension points*. That assumes a permanently available C++ team. Without one, designers stall on their first non-trivial request |
| Plugin-mounted content roots | primary game root holds 2 838 assets; all 105 mount roots hold 17 256; project-owned content is 3 876 | Any census, budget or memory number computed over the primary root alone understates by roughly six times |

The second row is the one people copy without noticing they copied it. A C++ to
Blueprint ratio is a staffing decision wearing an architecture costume. Measure
both columns before adopting the boundary, and name the person who will add to the
second one.

The third row is a measurement discipline, not an architecture choice, and it
generalizes: in any plugin-based project, enumerate all mount roots. Tooling that
defaults to the primary game root will quietly report a fraction of reality.

### How to decide

State the question the modular stack answers *for you*:

- more than one team shipping into the same binary?
- content added after launch without a client patch?
- game modes swapped at runtime by data?
- platform-specific feature sets?

Zero yes answers means the whole stack is tax. One or two means adopt the layers
that answer them and stop there. Adopting for completeness is paying for an answer
to a question you do not have.

---

## 6. C5 - Foreign-product legacy

Three recurring shapes:

- global constants and type identifiers carrying another title's brand, usually
  because the subsystem was lifted from that title;
- a tag whose own descriptive comment admits it is in the wrong namespace and
  needs to move;
- a class comment copy-pasted from a different class, describing something the
  class is not.

Harmless as code. Corrosive as vocabulary. Within a year nobody remembers why a
primary asset type is named after another game's content, and part of the team
assumes it is an engine term. The comment case is worse than the constant case: a
wrong name is eventually questioned, a wrong explanation is believed.

Rename at import time. After the first sprint it becomes archaeology.

---

## 7. The counterexample worth copying

A register-and-unregister pair, in which the unregister path removes exactly the
paths that registration added and then asserts on the removal count:

```cpp
// on unregister
const int32 NumRemoved = Registry.RemovePathsAddedBy(Feature);
ensure(NumRemoved == PathsAddedBy(Feature).Num());
```

In an audit whose dominant finding was "add works, remove is incomplete", this was
the one place where teardown was both implemented and asserted. Copy the shape:
paired add/remove, plus an assertion that the counts match. The assertion is what
turns a silent leak into a test failure.

Note the asymmetry that remained even there: registration went through the
project's own manager subclass while unregistration reached for the engine base
class, and a refresh call made on the way in had no counterpart on the way out.
Even the good example is worth reading twice - copy the shape, fix the asymmetry.

---

## 8. What source reading cannot settle

Three limits are worth stating, because they bound every claim in this skill:

1. **Blueprint call sites are invisible to source search.** A function with zero
   C++ callers may be called from a Blueprint graph. Absence of C++ callers is not
   absence of callers; settling it requires opening the graphs.
2. **Data tables and data assets are binary.** How many entries a table
   contributes to a registry cannot be read from text. It requires the editor.
3. **An empty search result proves the pattern, not the absence.** Widen the
   pattern, check the path, and check what your search tool excludes by default
   before concluding that something does not exist.

The third has caught real errors in this material more than once. Treat it as a
standing rule rather than a caveat.

---

## Provenance

The classification and every measured number above come from a line-by-line audit
of Epic's Lyra Starter Game on Unreal Engine 5.6, read as source rather than run,
during a research project whose product was this skill set.

Source addresses stay in that archive. What ships is the recipe, because an
address in a tree you do not have is not actionable and a recipe is. Entry
identifiers (`RA-01` and up) in [failure modes](failure-modes.md) resolve back to
the audited locations, so any specific claim can be produced on request.

## Evidence boundary

One reference project, one engine version, one workspace. This is a worked example
of the classification, not a defect list to carry into other engine versions or
other samples. Re-run the tests from `SKILL.md` against your own reference before
trusting any specific claim here.
