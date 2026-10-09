# Failure modes: evidence discipline

Ten ways an audit produces a confident wrong answer.

Every entry below happened during the work that produced this skill bundle. Not
"could happen" — happened, was caught, and cost real time. That is the only
provenance this document has and the only one it needs: a method document written
from imagination describes a method nobody has used.

The shared property is uncomfortable: **each of these produces output that looks
like evidence.** A count, a file list, a quoted line, a green check. The failure
is never a missing answer; it is a well-formed answer to a question you did not
ask.

Identifiers (`ED-01` and up) are stable.

---

## Searching

### ED-01 - An empty result read as absence

**Mechanism.** A search returns nothing, and "nothing" is recorded as "this does
not exist in the codebase".

**Why it is silent.** Zero hits is a definite-looking answer. It has no error
state, no partial result, and nothing that suggests the pattern rather than the
tree was at fault.

**Why the obvious check misses it.** The obvious check *is* the search. Verifying
it requires a second, differently-shaped search — which feels redundant precisely
when it is most needed, because the first one was so clear.

**Symptom.** A claim of the form "there is no X here" that turns out to be "my
pattern did not match X". In this project it happened three times: a structure
assertion missed because the namespace prefix was omitted; a subsystem file
missed because the path was guessed rather than found; and — the one that would
have shipped — a leaked-path audit whose pattern used doubled backslashes and
returned exactly one hit, which was nearly reported as "only one leak" when the
real count was nineteen across two donors.

**Detect.** Before recording an absence, widen deliberately:

```bash
rg -n "Scalability::FQualityLevels" .          # first attempt: 0 hits
rg -n "FQualityLevels" .                       # widened: 5 hits
rg -c "PatternPart" . ; rg -c "OtherPart" .    # both halves separately
```

Then check what your tool excludes by default — ignore files, binary files,
hidden directories — and whether the path you searched is the path that exists.

**Guardrail.** **An empty result proves the pattern, not the absence.** Record
absences only after a widened search, a path check, and a statement of what the
search could not see.

---

### ED-02 - Build output counted as source

**Mechanism.** An unrestricted search matches compiled artefacts — debug symbols,
binaries, intermediate files — and their hits are counted alongside source.

**Why it is silent.** The matches are real. The count is arithmetically correct.
Nothing marks a hit as coming from a file that is generated rather than written.

**Why the obvious check misses it.** The result list is usually long enough that
nobody reads every line, and the summary count is what gets quoted. The tool even
labels binary matches — in a line most people skip.

**Symptom.** A field described as "appearing four times" when it appears once. In
this project exactly that: three of four hits were debug symbol files, and the
source truth was a single declaration — which is a much stronger finding, since a
field declared once and never read is a cleaner defect than one used four times.

**Detect.** Restrict to source globs, always, and check the difference:

```bash
rg -c "Symbol" .                                        # everything
rg -c "Symbol" --glob "*.cpp" --glob "*.h" .            # source only
```

If the two numbers differ, the first one was never a fact about your code.

**Guardrail.** Default to source globs. When a count matters, state which file
types it covers.

---

### ED-03 - A count taken over the wrong root

**Mechanism.** A census runs over the primary content directory in a project whose
plugins mount their own roots, and reports a total.

**Why it is silent.** The number is real and internally consistent. Nothing in
the result indicates which roots were not visited.

**Why the obvious check misses it.** The primary root is the obvious root, and it
is where nearly all hand-authored content lives in a small project. The error only
appears at a scale where checking is expensive.

**Symptom.** Budgets, dependency graphs and audits that are individually correct
and collectively wrong. In this project the primary root held 2 838 assets while
the full set of 105 mount roots held 17 256 — a factor of six. Separately, a
native-symbol count restricted to the main source directory undercounted by
eighteen for the same reason.

**Detect.** Enumerate roots before counting within them:

```python
roots = ar.get_sub_paths("/", False)   # returns all mount roots
```

```bash
rg -c "PATTERN" Source/                       # one root
rg -c "PATTERN" Source/ Plugins/              # all of them
```

**Guardrail.** A count states its scope in the same sentence as its value. "3 876
project-owned assets across 105 mount roots" is a fact; "3 876 assets" is a number
waiting to be misused.

---

## Reasoning

### ED-04 - Measured and inferred mixed in one sentence

**Mechanism.** A sentence contains something read in source and something
concluded from it, with no marker separating them.

**Why it is silent.** The sentence is true. Both halves are defensible. The reader
inherits the conclusion with the same confidence as the observation, which is one
level of confidence too many.

**Why the obvious check misses it.** Review checks whether claims are correct, not
whether their epistemic status is labelled. A correct inference passes.

**Symptom.** An inference propagating into other documents as a measurement,
where it can no longer be traced back and questioned. Most false conclusions in
this project's audit originated at exactly this seam.

**Detect.** This one is answered by format, not by search. Require a marker per
claim — measured, derived, open — and treat an unmarked claim as unreviewed.
Then check the derived ones for the strongest available failure: what would have
to be true for this inference to be wrong, and did anyone check?

**Guardrail.** Three categories, never mixed within a sentence. An open question
stays written as open rather than closed with a plausible guess — a plausible
guess is indistinguishable from a finding six months later.

---

### ED-05 - A subagent's headline accepted without re-reading

**Mechanism.** Delegated investigation returns a confident summary. The summary is
used directly.

**Why it is silent.** Reports are fluent, structured and usually mostly right.
Errors arrive in the same register as correct findings.

**Why the obvious check misses it.** Reading the report *is* the check, and the
report is internally coherent. Detecting the error requires re-reading the source
the report was derived from — that is, redoing the delegated work at the points
that matter.

**Symptom.** In this project: an exploration agent reported three sites carrying
absolute workstation paths; the real count was nineteen. Separately, a claim that
the game-phase system lived in a feature plugin, when it lives in the main module.

**Detect.** For each headline claim in a report, open the cited location and read
it. If the report cites no location, the claim is unverifiable and is dropped
rather than softened.

**Guardrail.** Delegated output is **raw material**, not a result. Every headline
claim is re-read at the source before it reaches a document or a conclusion.

---

### ED-06 - A number carried forward without re-measurement

**Mechanism.** A count measured once is quoted in later documents. The tree
changes, or the original measurement was scoped differently, and the number
persists.

**Why it is silent.** Numbers do not expire visibly. A stale count looks exactly
like a fresh one, and having a number at all suppresses the impulse to take one.

**Why the obvious check misses it.** Review checks whether the document is
coherent, and it is. The original measurement was correct when taken.

**Symptom.** In this project, an audit stated "59 native definitions across 40+
files". Re-measured during depersonalization: **94 definitions across 31 files**,
with the discrepancy caused by ED-03 in the original. The correction was recorded
alongside the original rather than replacing it, because which of the two readings
was direct is itself information.

**Detect.** Re-run the measurement when quoting it in a new context, and diff:

```bash
rg -c "PATTERN" Source/ Plugins/ | awk -F: '{s+=$2} END {print s}'
```

**Guardrail.** A quoted number carries the command that produced it, so the next
reader can re-run it in one paste. Corrections are recorded as corrections — an
archive that silently self-heals loses the trail of which reading was direct.

---

## Recording

### ED-07 - A finding that never left the conversation

**Mechanism.** Something real is discovered, discussed, and not written down.

**Why it is silent.** At the moment of discovery it feels known. The cost arrives
later, when the context holding it is gone.

**Why the obvious check misses it.** There is nothing to check. The absence of a
note is not visible from anywhere except the future.

**Symptom.** The same investigation performed twice. A conclusion remembered
without its evidence, which then cannot be defended or corrected.

**Detect.** At the end of a session, diff what was concluded against what was
written. Anything in the first list and not the second is already lost — writing
it down later is a reconstruction, not a record.

**Guardrail.** **Found and not written down is lost.** Write the observation
immediately, with its address, before continuing. A conversation is not a store.

---

### ED-08 - A check whose condition cannot become true

**Mechanism.** A validator tests for a literal that could never appear — a path
from a different workspace, a name from a previous project, a case the current
tree cannot produce.

**Why it is silent.** The check runs, passes, and reports success. Green is the
outcome it was built to produce, and it produces it forever.

**Why the obvious check misses it.** The validator exists, is invoked, and is
listed in the process documentation. Everything about it says "this is checked".
Nobody re-reads a passing check.

**Symptom.** In this project: a skill validator searched for one hardcoded
absolute path from a *different* project, and only inside one file type. It ran
green for months while nineteen leaked paths from two donors sat in the tree.
That validator became this bundle's worked example — our own code, not the
reference's.

**Detect.** For every check, produce the input that makes it fail. If you cannot
construct one, the check does not exist:

```bash
python validate.py            # green
# now poison a fixture with the exact thing the rule forbids
python validate.py            # must be red
```

**Guardrail.** **A rule with no fixture that reddens it is not a rule.** Keep one
poisoned fixture per rule, plus a clean baseline, and assert the rule count so a
rule cannot be dropped silently.

---

### ED-09 - A namespace collision that collapses two sets

**Mechanism.** Two independent collections use the same identifier prefix. A tool
that merges them by key silently overwrites, and reports success on the survivors.

**Why it is silent.** Every remaining entry resolves. The tool's output is a
consistent, complete-looking mapping — of a smaller set than it was given.

**Why the obvious check misses it.** The check verifies that everything present
resolves, which is true. Nothing verifies that everything given is still present.
The count is the only tell, and only if someone compares it against the source.

**Symptom.** In this project, two skills adopted the same two-letter prefix. Nine
entries vanished from the resolver, which reported "173 shipped, 173 mapped, 0
unresolved" — a perfectly green run against a set that had lost nine members. It
was caught only because the total failed to grow after adding nine entries.

**Detect.** Count both sides independently and compare:

```bash
rg -c "^### [A-Z]{2,4}-" skills/*/references/*.md | awk -F: '{s+=$2} END {print s}'
# compare against what the merging tool reports
```

Then check prefix uniqueness directly, and make it a rule rather than a habit.

**Guardrail.** Any tool that merges by key asserts that its output cardinality
equals its input cardinality. A resolver that cannot lose entries is worth more
than one that reports zero failures.

---

### ED-10 - A recipe published without being run

**Mechanism.** A detection recipe is written from understanding of the defect
rather than from executing it against a real tree.

**Why it is silent.** The recipe is plausible, well-formed, and would work if the
world were slightly simpler. It is published in a document whose whole purpose is
to be trusted.

**Why the obvious check misses it.** Reading the recipe confirms it expresses the
right idea. Only running it reveals that the pattern matches something it should
not, or misses something it should catch.

**Symptom.** In this project, three recipes were wrong on first draft and each was
wrong in a way that produced a **false negative** — the worst direction. A search
for a field's writer matched the declaration's own initializer and reported "there
is a writer" in exactly the case the recipe exists to catch. A character class
intended to find comparisons matched the arrow operator and reported assignments
as comparisons. A search for a namespace matched nothing because real names carry
a prefix — and zero hits would have read as "this problem is absent here".

**Detect.** Run every recipe against a tree where you already know the answer, and
check both directions: does it find the known instance, and does it stay quiet
where there is none?

**Guardrail.** **A recipe that has not been run is a hypothesis.** Publish the
corrected form, and where the first draft failed in an instructive way, publish
that too — the trap is often more useful than the recipe.
