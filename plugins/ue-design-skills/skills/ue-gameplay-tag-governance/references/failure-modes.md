# Failure modes: gameplay tag governance

Eighteen ways a tag-driven system stops working without reporting anything.

The common shape of every entry below: **the system does not fail, it declines to
act.** Tag defects do not produce crashes, log errors or failed builds. A missing
join and a correctly-evaluated "no" are the same observable. Design the gates
accordingly — the only reliable detection is a test that asserts the *positive*
behaviour, or a recipe that compares two counts.

Recipes use `rg` and are written to be run from a project root. Most of them are
deliberately a **pair** of searches: the class of defect here is "the thing is
present, and the thing that would give it meaning is absent", and a single search
can only ever show you the first half.

---

## Vocabulary and declaration

### TG-01 - Typo in a string-declared tag

**Mechanism.** A tag declared in ini, or authored into an asset by hand, is
misspelled. No compiler, linker or loader rejects it, because a tag is a string
until the moment something tries to match it.

**Why it is silent.** The lookup succeeds in the sense that matters to the engine:
it returns "no match", which is a legal answer that the calling system is required
to handle gracefully. A misspelled tag is indistinguishable from a condition that
is legitimately not met right now.

**Why the obvious check misses it.** Review reads the tag and it looks right —
misspellings survive review precisely because they are near-misses. Compile,
cook and startup all pass. The only artefact that would reveal it is a runtime
comparison that nobody logs, because logging every failed tag match would drown
the log.

**Symptom.** The feature does nothing. No log line, no error. Usually reported by
a designer, weeks later, as "this never worked" — by which time the change that
introduced it is far outside any bisect window.

**Detect.** Resolve the declared vocabulary against the referenced one:

```bash
# every tag string declared in config
rg -o -N 'Tag="([^"]+)"' -r '$1' Config/ Plugins/*/Config/ | sort -u > /tmp/declared
# every tag string mentioned in source
rg -o -N '"([A-Z][A-Za-z]+(\.[A-Za-z][A-Za-z0-9]*)+)"' -r '$1' Source/ | sort -u > /tmp/used
comm -13 /tmp/declared /tmp/used     # referenced but never declared
```

The third command is the finding: a tag string that code compares against and
that no source declares.

**Guardrail.** Native tag macros for anything C++ reads, so a typo becomes a link
error. `Categories` constraints on every editable tag property so authoring uses a
dropdown rather than a keyboard.

---

### TG-02 - Symmetric typo

**Mechanism.** The same misspelling exists at both ends of a join. The feature
works. A later cleanup corrects one side.

**Why it is silent.** It is not merely silent — it is *correct*. Both sides agree,
the join resolves, the feature ships and works for years. Nothing is wrong until
someone makes it right.

**Why the obvious check misses it.** Every check that exists passes, because the
system is working. The defect has no runtime signature at all; it is latent in the
spelling, and it converts into a failure only through a well-intentioned edit
whose diff looks obviously correct — which is why it also survives review of the
fix.

**Symptom.** A previously working feature breaks, and the commit that broke it is
a one-word spelling correction that every reviewer approves.

**Detect.** Before correcting any tag spelling, count the sites:

```bash
T='Primarly'         # the suspected misspelling
rg -n --no-heading "$T" Config/ Source/ Plugins/ | tee /tmp/sites | wc -l
```

On the measured reference this returned six sites across four files: two project
tag declarations, two platform-specific config files, and a native tag macro plus
its use in one widget class. Correcting any one of them would have broken the
join with no error at either end.

**Guardrail.** Treat a discovered typo as a coordinated multi-site rename plus a
redirect, never as a local edit. The rule generalises: **when a string literal is
the join, correctness means "all sides agree", not "the string is right".**

---

### TG-03 - `Categories` filter pointing at a namespace that does not exist

**Mechanism.** The `Categories` metadata string is not validated against the tag
tree. A stale or mistyped namespace yields an empty candidate set.

**Why it is silent.** An empty dropdown is a legitimate state — it is what a
correctly-configured filter shows before anyone has created tags under that
namespace. The editor has no way to distinguish "this filter is wrong" from "this
namespace is empty today".

**Why the obvious check misses it.** The property has a constraint, which is the
thing reviewers check for, and it is spelled plausibly. Confirming it requires
opening the property in the editor and looking at the dropdown — a five-second
check that nothing prompts anyone to perform, because the code reads as complete.

**Symptom.** Designers see an empty dropdown, conclude the tags are not ready yet,
and leave the field blank. The feature is then wired to an unset tag, which is the
same failure as TG-01 arriving by a different route.

**Detect.** Extract every filter string and confirm each resolves:

```bash
rg -o -N 'Categories\s*=\s*"([^"]+)"' -r '$1' Source/ | sort -u > /tmp/filters
while read -r ns; do
  n=$(rg -c "Tag=\"$ns" Config/ Plugins/*/Config/ 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')
  [ "$n" = "0" ] && echo "EMPTY FILTER: $ns"
done < /tmp/filters
```

On the measured reference one filter named a namespace that appeared nowhere else
in the project, while the real tags lived under a differently-named root. That
filter was one of only fourteen constrained properties in the entire codebase —
one of the few places tag input was validated at all, and it was misconfigured.

**Guardrail.** Open every constrained property once and confirm the dropdown is
non-empty. Re-check after any namespace rename: `Categories` is a string, and no
rename tool touches it.

---

### TG-04 - Unconstrained tag property

**Mechanism.** A tag field without `Categories` offers the entire project
vocabulary — thousands of entries, of which a handful are legal here.

**Why it is silent.** Any tag the designer picks is a valid tag. It serialises, it
loads, it compares. The system that reads it simply never matches, which is the
TG-01 observable again.

**Why the obvious check misses it.** There is nothing to see. The absence of one
optional metadata specifier does not appear in a diff as a change, does not warn,
and does not look like an omission in review — most properties do not have it
either, so it reads as normal.

**Symptom.** Wrong-namespace tags assigned in assets; the system ignores them
silently. The designer's mental model — "I set the tag, so it is wired" — is
reasonable and wrong.

**Detect.** Report the coverage ratio, which is the only number that matters:

```bash
total=$(rg -c "FGameplayTag(Container)?\s+\w+;" Source/ | awk -F: '{s+=$2} END {print s+0}')
constrained=$(rg -c "meta\s*=\s*\([^)]*Categories" Source/ | awk -F: '{s+=$2} END {print s+0}')
echo "constrained $constrained of $total"
```

On the measured reference this was fourteen of sixty-four — under sixteen per cent
— and one of the fourteen was broken per TG-03. A low ratio is not itself a bug;
it is a list of places where a typo cannot be caught.

**Guardrail.** `meta=(Categories=...)` on every editable tag property and `UPARAM`
on every Blueprint-exposed tag argument. Track the ratio as a number that only
goes up.

---

### TG-05 - A grep pattern that misses a declaration source

**Mechanism.** Plugin tag config uses `GameplayTagList=` without the leading `+`
and under a different section header than project config. A pattern anchored on
`+` never sees it.

**Why it is silent.** The audit succeeds. It produces a number, the number is
plausible, and nothing indicates it is partial. A confident wrong answer is
produced by a working tool.

**Why the obvious check misses it.** The obvious check *is* the grep, and greps
do not report what they could not have matched. This is the general hazard of
proving absence by search: **an empty or small result proves the pattern, not the
codebase.**

**Symptom.** An audit reports a small tag vocabulary and concludes the project is
safer than it is. Renames and migrations are then planned against an inventory
that is missing most of its entries.

**Detect.** Count with two patterns and require them to agree:

```bash
rg -c '^\+GameplayTagList=' Config/                          # project form
rg -c 'GameplayTagList=\(Tag=' Config/ Plugins/*/Config/     # both forms
```

On the measured reference the first pattern found 99 tags in one file; the second
found 212 across five files, four of which were plugin configs. The difference is
not an edge case — it is the majority of the vocabulary.

**Guardrail.** Reconcile every count against a documented per-namespace source
list. Never conclude "absent" from one pattern; widen it, then widen the path.

---

### TG-06 - Tag declared in a source no static search can see

**Mechanism.** DataTable-sourced tags live in binary assets. Runtime registration
leaves no declaration text at all.

**Why it is silent.** These tags work perfectly. They resolve, match and replicate
like any other. They are invisible only to *tooling*, and tooling is not what
exercises them.

**Why the obvious check misses it.** Every text-based inventory is structurally
incapable of seeing them. Widening the grep does not help, because there is no
text to find — the failure is in the choice of instrument, not its configuration.

**Symptom.** Tags exist at runtime that no inventory, document or search reports.
A rename sweep misses them; a "delete unused tags" pass deletes something that is
in use.

**Detect.** Ask the runtime, not the filesystem:

```bash
rg -n "GameplayTagTableList|AddNativeGameplayTag|AddTagTableRow" Config/ Source/
```

Any hit means your static inventory is incomplete by construction. Close the gap
by dumping the tag registry from a running build and diffing it against the static
inventory; the difference is exactly the set this entry describes.

**Guardrail.** Document every namespace's declaration source in one place. Forbid
runtime registration outside module startup, so at least the timing is knowable.

---

## Matching semantics

### TG-07 - Exact/hierarchical mismatch inside one feature

**Mechanism.** One code path uses hierarchical matching and another uses exact
comparison, on the same data, sometimes in the same class.

**Why it is silent.** Both calls are correct in isolation and both are correct for
the tags used during development — typically leaf tags, where hierarchical and
exact matching give identical answers. The two forms only diverge for a tag that
has descendants, which is a case that arrives later.

**Why the obvious check misses it.** Reading either call site shows a defensible
choice. The defect exists only in the relationship between two call sites that may
be hundreds of lines apart, and no tool reports "these two comparisons on the same
field disagree about semantics".

**Symptom.** The rule works for the tags used in testing and fails for others —
the failure distribution that is hardest to reproduce, because the reporter's
repro steps look identical to the ones that pass.

**Detect.** List both forms per file and look for files that contain both:

```bash
rg -l "MatchesTag\(" Source/ > /tmp/hier
rg -l "MatchesTagExact\(|HasTagExact\(" Source/ > /tmp/exact
comm -12 <(sort /tmp/hier) <(sort /tmp/exact)
```

Files in the intersection are candidates. On the measured reference one mapping
class used hierarchical matching in two methods and exact matching in a third, all
against the same tag container.

**Guardrail.** State matching intent explicitly at each call site — prefer the
`...Exact` form even where `==` would do. Review the read and write paths of a
rule together, never separately.

---

### TG-08 - Unintended enrolment via a new child tag

**Mechanism.** A system matches on a parent tag. Adding a child anywhere in the
project enrols that child in the system automatically.

**Why it is silent.** The enrolment is the feature working as designed. Nothing
malfunctions; a new tag simply acquires behaviour its author did not know about,
and that behaviour is usually plausible.

**Why the obvious check misses it.** The person adding the tag is looking at the
tag list, not at every hierarchical match in the codebase. The person who wrote
the match is not present. There is no declaration anywhere that says "this parent
is load-bearing", so the coupling exists only in the reader's memory.

**Symptom.** A newly added, unrelated tag activates behaviour nobody wired, in a
subsystem nobody touched, in the same release as dozens of other changes.

**Detect.** Enumerate the parents that carry behaviour, then their descendants:

```bash
rg -o -N 'MatchesTag\(([A-Za-z_:]+)\)' -r '$1' Source/ | sort -u   # load-bearing parents
# for each parent P, list current descendants:
rg -o -N 'Tag="(P\.[^"]+)"' -r '$1' Config/ Plugins/*/Config/
```

Read the descendant list and confirm every entry belongs in that subsystem. Do
this at the moment you add a hierarchical match, and record the result next to
the parent declaration.

**Guardrail.** Document each parent's contract at its declaration and treat parent
tags used in hierarchical matches as public API. Reserve a leaf-only convention
for tags that are identities.

---

### TG-09 - Partial string lookup in gameplay code

**Mechanism.** A helper resolves a tag from a substring, returning the first match
in registry order.

**Why it is silent.** It returns a real, valid tag. Everything downstream works
normally with it. The answer is only wrong in the sense that it is not the answer
you would have chosen, and there is no way to notice that from the outside.

**Why the obvious check misses it.** The function has a plausible name and a
`bool` parameter that defaults to the safe behaviour. Reviewing the helper shows a
correct implementation of what it says it does. The hazard is in the *export* —
it crosses a module boundary with a permissive mode available — and export
surfaces are reviewed for compilation, not for misuse potential.

**Symptom.** The resolved tag changes when an unrelated tag is added elsewhere in
the project. Non-deterministic behaviour, no error, and a repro that depends on
the contents of the tag registry rather than on anything in the feature.

**Detect.** Find partial-match helpers and check who calls them with matching
enabled:

```bash
rg -n "PartialMatch|bMatchPartialString|FindTagByString" Source/
rg -n "FindTagByString\([^)]*true" Source/       # callers opting into partial
```

On the measured reference the helper was exported from the game module with the
permissive parameter defaulting to off, and its only current callers were cheat
commands passing it on — safe today, one production caller away from
non-deterministic.

**Guardrail.** Confine partial matching to cheat and console paths. Do not export
such a helper across a module boundary at all; if you must, do not give it a
permissive mode.

---

## Replication

### TG-10 - Divergent tag registries under fast replication

**Mechanism.** Fast replication sends tags by registry index. Client and server
must hold identical registries for an index to mean the same thing on both ends.

**Why it is silent.** Indices are always valid. A mismatched index does not fail
to deserialise — it resolves to a different, perfectly real tag. The receiving
side then acts correctly on the wrong fact.

**Why the obvious check misses it.** PIE shares one process and therefore one
registry, so the divergence cannot exist in the environment where testing happens.
Any check performed in the editor is performed on a configuration where the bug is
impossible by construction.

**Symptom.** Wrong tags received, or replication failures, only in networked
builds with asymmetric plugin loading — and the symptom is a wrong behaviour, not
an error.

**Detect.** Find every conditional path into tag registration:

```bash
rg -n "FastReplication" Config/
rg -n -B4 "AddNativeGameplayTag|RegisterGameplayTag" Source/ \
  | rg "IsRunningDedicatedServer|WITH_EDITOR|#if|IsClient|bIsServer"
```

Any conditional wrapping tag registration is a divergence risk. Confirm by
dumping the registry from a client build and a dedicated-server build and diffing
them; that diff is the only authoritative answer.

**Guardrail.** Register vocabulary unconditionally on both sides. Gate the
*content* a tag refers to, never the vocabulary itself.

---

### TG-11 - Replicated container size cap

**Mechanism.** A setting fixes the number of bits used for a replicated tag
container's element count, which caps how many tags fit in one container.

**Why it is silent.** Under the cap, everything is correct. Over it, the excess
entries are simply not transmitted — a truncation, not an error. The receiving
side sees a valid container with fewer tags.

**Why the obvious check misses it.** The cap lives in a settings file as a bit
count, not as a tag count, so its practical meaning requires a mental exponent.
Nothing connects it to the container that will eventually exceed it, and the
container that exceeds it does so only under gameplay conditions that accumulate
tags.

**Symptom.** Tags beyond the cap are lost in transit with no compile-time or
runtime signal. Debugging starts at the gameplay logic, which is correct.

**Detect.** Read the cap, convert it, and compare against your worst case:

```bash
rg -n "NumBitsForContainerSize|FastReplication" Config/
```

On the measured reference the value was 6 bits — a hard limit of 63 entries per
replicated container. Then find containers that grow without bound:

```bash
rg -n "AddTag\(|AppendTags\(" Source/ | rg -i "replicat|net"
```

**Guardrail.** Know the cap as a tag count, not a bit count, and write it next to
any container that grows dynamically. Assert the size where it grows.

---

## Counters

### TG-12 - Tag counter swallowing zero or negative deltas

**Mechanism.** A stack-modifying function guards on `if (Amount > 0)` with no
`else`, so a zero or negative amount returns silently.

**Why it is silent.** Returning without acting is a legal response to a degenerate
input, and the caller has no return value to check. The write is lost with the
same observable as a write that was never attempted.

**Why the obvious check misses it.** The function *does* validate — there is a
warning path for an invalid tag right beside the silent path for an invalid
amount. Seeing the tag validation satisfies the reviewer's question "is this
input checked?", and the asymmetry between the two checks is invisible unless you
compare them deliberately.

**Symptom.** A lost write reported as "the ability did nothing". Because the tag
was valid, the tag-level warning never fires, so the log is clean.

**Detect.** Compare validation coverage between the two parameters:

```bash
rg -n -A6 "void .*Stack(Count|Tag)?\(|AddStack|RemoveStack" Source/ \
  | rg "if\s*\(.*Amount|ensure|UE_LOG"
rg -n "//\s*@?TODO" Source/ | rg -i "stack|amount|negative|zero"
```

On the measured reference the invalid-tag path carried warnings at both the add
and remove sites while the invalid-amount path returned silently at both, and an
unresolved TODO next to the remove path asked exactly the question this entry
describes.

**Guardrail.** Validate the amount as strictly as the tag. Define and implement
the contract for removing more than exists — clamp, fail loudly, or allow
negative. Silence is not a contract.

---

### TG-13 - Unguarded accumulation on a stack count

**Mechanism.** Unchecked `int32` addition on a tag count, with no upper bound.

**Why it is silent.** Every individual addition is correct. The wrap requires an
accumulation that no test performs, and after it wraps the value is still a valid
integer that every subsequent comparison evaluates without complaint.

**Why the obvious check misses it.** Overflow guards are absent from most
arithmetic in most codebases, so their absence here does not stand out. The
addition is one line in a function whose logic is otherwise about tags, and the
reviewer's attention is on the tag semantics.

**Symptom.** A count wraps to negative under a modifier loop or a long session.
Every `>= required` check then fails, so the ability with the most resources
behaves as if it had none.

**Detect.** Find unbounded accumulation on stack counts:

```bash
rg -n -B2 -A2 "StackCount\s*\+=|Count\s*\+=\s*\w+" Source/ \
  | rg -v "Clamp|Min\(|check\(|ensure"
```

Any addition with no clamp in the surrounding lines is the finding.

**Guardrail.** Clamp against a documented maximum on every add, and state the
maximum where the container is declared.

---

## Stubs and documentation

### TG-14 - Tag-shaped property with no reader

**Mechanism.** A tag container is exposed for authoring while the code that would
consume it is stubbed or deferred.

**Why it is silent.** An unread property is not an error at any level of the
stack. It serialises, it appears in the editor, and it survives every cook. The
authored value simply goes nowhere.

**Why the obvious check misses it.** The property exists, is documented by its
name, and appears in the class next to properties that do work. "Is this
implemented?" is answered by the presence of the field. The absent half is the
*reader*, and no default tooling asks who reads a property.

**Symptom.** Designers configure the field; nothing happens. The feature appears
implemented in the editor and in review, so the investigation starts from "the
data must be wrong".

**Detect.** For each editable tag property, search for a reader:

```bash
P='HiddenByTags'                       # substitute your property
rg -n "\b$P\b" Source/                 # declaration plus any uses
rg -n "\b$P\b" Source/ | rg -v "UPROPERTY|^\s*FGameplayTag"   # actual reads
```

A declaration with no read is a stub. On the measured reference one widget base
class exposed such a container while both of its consumer sites hardcoded the
result of the check to a constant, with the real expression parked in a comment.

**Guardrail.** Do not ship an editable property whose consumer does not exist. If
it must exist for serialisation reasons, mark it non-editable or log when it is
non-empty.

---

### TG-15 - Restoring a stubbed tag check without restoring its inputs

**Mechanism.** The stub from TG-14 coexists with other damage: the values the
restored check would select between are themselves overwritten at runtime.

**Why it is silent.** Both halves are individually invisible. The stub is silent
per TG-14; the overwrite is a normal-looking assignment in an initialisation path.
Neither produces a symptom while the feature is switched off.

**Why the obvious check misses it.** The obvious check is reading the stub, which
tells you exactly what to implement. It does not tell you that the inputs to the
thing you are about to implement have been clobbered somewhere else, because that
assignment lives in a different method with a different purpose.

**Symptom.** The obvious one-line fix produces wrong behaviour instead of correct
behaviour, and the fix gets blamed and reverted — burying the original defect
under a failed attempt.

**Detect.** Before re-enabling any stub, verify every input it reads is still
authored where it appears to be authored:

```bash
V='ShownVisibility'                   # a field the stub would select between
rg -n "\b$V\b\s*=" Source/            # who writes it, and when
```

On the measured reference the designer-authored visibility fields were overwritten
by a setter called during construction, so implementing the tag check alone would
have selected between two values that no longer held the authored data.

**Guardrail.** Treat "implement the stub" as a task that starts with tracing the
stub's inputs, not with writing the missing expression.

---

### TG-16 - Vocabulary without documentation

**Mechanism.** The per-tag comment field is optional and tag names are terse.

**Why it is silent.** An undocumented tag works exactly as well as a documented
one. The cost is paid by people, later, and never by the build.

**Why the obvious check misses it.** There is no check. Nothing measures
documentation coverage, and the field is empty by default, so an empty one looks
like every other one.

**Symptom.** Duplicate tags with different spellings for the same concept; tags
nobody dares delete because nobody knows what reads them. The vocabulary grows
monotonically because deletion is unsafe.

**Detect.** Measure the ratio:

```bash
total=$(rg -c 'GameplayTagList=\(Tag=' Config/ | awk -F: '{s+=$2} END {print s+0}')
empty=$(rg -c 'DevComment=""' Config/ | awk -F: '{s+=$2} END {print s+0}')
echo "undocumented $empty of $total"
```

On the measured reference this was 68 of 99 in the project config — sixty-nine per
cent undocumented, in a project otherwise notable for its care.

**Guardrail.** Require a comment in review for every declared tag, and run a
periodic declared-but-unread / read-but-undeclared diff so the vocabulary can
shrink as well as grow.

---

### TG-17 - Vocabulary with no central registry

**Mechanism.** File-local native tag macros scatter definitions across the module,
each valid, none discoverable from the others.

**Why it is silent.** Every definition works. Scattering costs nothing at runtime
and nothing at build time; it costs only the ability to answer a question.

**Why the obvious check misses it.** Looking at the central registry file shows a
well-organised list, and it is genuinely well organised — it is simply a minority
of the vocabulary. The check confirms what it can see, and what it cannot see does
not announce itself.

**Symptom.** No single place answers "what tags does this project have". Audits
and renames are incomplete by construction, and each incomplete audit produces a
number that looks authoritative.

**Detect.** Compare the central file against the whole tree, and include plugins:

```bash
rg -c "UE_DEFINE_GAMEPLAY_TAG" Source/ Plugins/ | awk -F: '{s+=$2} END {print "total", s}'
rg -l "UE_DEFINE_GAMEPLAY_TAG" Source/ Plugins/ | wc -l
rg -c "UE_DEFINE_GAMEPLAY_TAG" Source/*/GameplayTags.cpp 2>/dev/null
```

On the measured reference this gave 94 definitions across 31 files, of which 35
sat in the central registry — so roughly two thirds of the vocabulary lived
outside the file whose name promises to hold it. Note that restricting the search
to the main source directory undercounts by 18, which is TG-05 arriving again in a
different disguise.

**Guardrail.** A central registry header for shared tags; file-local macros only
for tags used in exactly one file and never authored in data. Measure the central
share and treat a falling ratio as drift.

---

## Migration

### TG-18 - Rename without a redirect

**Mechanism.** Tag references in assets and configs are strings resolved at load
time. A rename leaves them unresolvable.

**Why it is silent.** An unresolvable tag reference loads as an empty tag. The
asset opens, the editor shows a blank field, and the system reads "no tag set" —
which is a legal state that means "not configured yet".

**Why the obvious check misses it.** The rename itself is a code or config change
that compiles and passes review. The damage is in binary assets that nobody opens
during the change, and it becomes permanent only when one of them is resaved for
an unrelated reason — at which point the old string is gone from disk entirely.

**Symptom.** Assets silently lose the tag. If they are resaved before anyone
notices, the reference cannot be recovered from the asset; it has to be
reconstructed from memory or version control.

**Detect.** Count redirects against rename history:

```bash
rg -n "GameplayTagRedirects" Config/ Plugins/*/Config/    # declared redirects
git log --oneline -S 'GameplayTagList' -- Config/ | head  # config tag churn
```

On the measured reference the first command returned nothing at all, confirmed
with two independent patterns. Zero redirects means either that no tag has ever
been renamed, or that every rename was destructive — and the second command tells
you which.

**Guardrail.** Ship the redirect in the same commit as the rename. Never remove a
redirect until every branch has been resaved and verified. Redirects are cheap;
reconstructing a designer's work is not.
