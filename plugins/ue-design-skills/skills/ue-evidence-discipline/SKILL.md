---
name: ue-evidence-discipline
description: >-
  How to produce and check claims about an Unreal Engine codebase so they can be
  trusted later: separating measured from derived from open, why an empty search
  result proves nothing, verifying a headline claim yourself before repeating
  it, treating a delegated report as raw material, and writing detection recipes
  that have been run. Use when auditing a codebase, reviewing someone else's
  audit, adopting a reference project, or writing any document that will be
  quoted back at you.
---

# Evidence discipline for codebase work

The invariant this whole bundle rests on:

> A claim without a source you can point at is not a result. A skill that is
> confident and wrong is worse than a missing one.

Every other skill here is normative — it tells you how to design something. This
one is methodological: it tells you how to know whether what you just wrote is
true. Read it once before using the others, and again before writing an audit
someone else will act on.

Ten ways this discipline fails in practice, each with a detection recipe:
[failure modes](references/failure-modes.md). They are all mistakes made during
the work that produced this bundle, which is the only reason they are specific
enough to be useful.

---

## 1. Three kinds of statement, never mixed in one sentence

| Marker | Meaning | Test |
|---|---|---|
| **measured** | read in the source, config or a live object | someone else can open the same place and see it |
| **derived** | a conclusion from measured facts plus engine semantics | the facts are cited and the inference is stated |
| **open** | not answerable with the tools used | says what would answer it |

**Do not mix two of these in one sentence.** The overwhelming majority of false
conclusions in codebase work are born exactly there: a measured fact and an
inference joined by a comma, where the reader inherits the confidence of the
first half for the second.

Concretely, this is wrong:

> The pool is only configured for one tier, so the other tiers are broken.

and this is right:

> The pool is configured for one tier **[measured]**. The other tiers therefore
> inherit engine values **[derived]** — whether that is wrong for this product is
> **[open]** until someone measures the target hardware.

The second version is longer and it is the only one you can act on.

### Corollary: an absence has a marker too

"There is no lag compensation in this project" is a measured claim **only** if
you say which searches you ran. Otherwise it is derived from your search
strategy, which brings us to the next rule.

---

## 2. An empty search result proves the pattern, not the codebase

This is the single most expensive mistake available in this work, because it
produces confident negative claims that survive review.

A search returns nothing when the code is absent — and also when the pattern was
wrong, when the path was wrong, when the file type was excluded, when ignore
rules filtered the directory, or when the identifier lives in a binary asset.
The tool reports the same empty result for all six.

**Before writing "this does not exist":**

1. widen the pattern and confirm it can match something you know is there;
2. check the path and include plugins, not only the primary source directory;
3. check file-type filters in both directions — too narrow hides code, too wide
   counts compiled debug symbols as source;
4. for anything that could live in a binary asset, state that the search cannot
   see it.

Two real corrections from the audit behind this bundle, both caught by re-running:

- a search for one declaration form found 99 entries; the correct pattern found
  **212 across five files**, because plugin configuration uses a syntax that
  differs by one character;
- a search for a suspected dead field returned four hits; three were compiled
  debug symbol files and the source truth was **one**.

Both would have shipped as facts.

---

## 3. Verify a headline claim yourself before repeating it

Any statement that will lead a section, appear in a summary, or be quoted gets
re-read at its source **by the person publishing it** — not accepted from a
teammate, a tool, or an earlier version of the same document.

This is not distrust. It is that a claim changes shape as it travels: a specific
finding about one function becomes a general statement about a subsystem in one
retelling, and nobody notices because each step was small.

Three corrections that came from exactly this re-reading, during the work behind
this bundle:

- "a field that is never read" was actually **written once in a constructor and
  never read** — the precise version names a real defect class; the loose version
  hides it;
- "the data graph has no compiler" was wrong: structural validation existed, in
  quantity. The true statement was narrower — **semantic cross-family validation
  is absent** — and the narrow version is the one that tells you what to build;
- a count of definitions "spread over 40+ files" was **31 files**, and the
  original number had never been measured.

Note that in all three the correction made the claim *more* useful, not less. A
weaker true statement beats a stronger false one, and usually points at the fix.

---

## 4. A delegated report is raw material

Output from a subagent, a script, or a search tool is an input to your judgement,
not a result. Re-verify every headline claim by reading the source directly
before it reaches a document or a conclusion.

The same rule with a sharper edge: **a report that agrees with what you expected
deserves more scrutiny, not less.** During the work behind this bundle a delegated
search reported three instances of a defect; direct measurement found nineteen.
The report was not wrong in kind, only in scale, which is the hardest error to
notice because nothing about it looks incorrect.

---

## 5. A recipe you have not run is a hypothesis

Every detection recipe in this bundle was executed against a real codebase before
being written down. That is not thoroughness for its own sake — it is the only
way to find the recipes that are confidently wrong.

Two examples from this bundle, both caught by running them:

- a search for "is this field ever assigned" matched the **declaration**
  `double LastFireTime = 0.0;`, so it reported a writer where none exists — a
  false negative, in the exact case the recipe was written to catch;
- a search for "is this ordering value ever compared" matched the arrow operator
  in `Entry->Priority`, so two assignments were counted as comparisons.

Both recipes looked correct. Both would have told the reader "no problem here" at
precisely the moment there was one.

**A detector that fails silently in the case it exists for is worse than no
detector**, because it converts an open question into a wrong answer. Run the
recipe against a codebase where you already know the answer, both when the answer
is yes and when it is no.

---

## 6. A check that has never failed may not be a check

Write the failing case for every gate you add, and confirm it fails.

The worked example is from this bundle's own tooling. A validator ran green for
months. It checked exactly one condition: that skill documents did not contain an
absolute path from **a different workspace than the one it ran in** — a literal
that could never appear. The check existed, the consumer existed, the report said
zero errors, and nineteen real leaks were present.

That is category C2 from `ue-reference-project-adoption` — a mechanism whose
consumer exists and whose condition can never become true — found in our own
code rather than in someone else's. It is the reason the delivery gate for this
bundle ships with one poisoned fixture per rule and refuses to pass if any rule
has never reddened.

Apply the same rule to content-validation commandlets, asserts, editor
validation and CI steps: **break something on purpose and confirm the pipeline
notices.** A gate whose failure path has never executed is a log line with
ambitions.

---

## 7. Write findings down where they survive

A finding that exists only in a conversation is lost. Context ends; files do not.

- write the observation at the moment it is made, not at the end of the session;
- put the citation next to the claim, not in a separate index;
- record open questions **as open**, rather than closing them with a plausible
  guess;
- when a later measurement contradicts an earlier note, add the correction and
  keep both — the fact that the number changed is itself information about how
  it was obtained.

That last point matters more than it looks. Two of the corrections in §3 were
only findable because the original number had been written down precisely enough
to be checked.

---

## 8. Publication checklist

Before an audit, a review or a skill leaves your hands:

- [ ] every headline claim re-read at its source by you;
- [ ] measured, derived and open marked, and never mixed in one sentence;
- [ ] every negative claim states the searches that produced it;
- [ ] every recipe executed against a real codebase, in both directions;
- [ ] every gate has a failing case that has been observed to fail;
- [ ] open questions listed as open;
- [ ] counts re-measured rather than carried over from an earlier draft;
- [ ] corrections recorded rather than silently applied.

---

## 9. What this does not give you

None of the above makes a claim true. It makes a false claim **findable** — by a
reader, by a later measurement, by the person who inherits the document. That is
the whole ambition, and it is worth stating plainly because the alternative
belief is dangerous: a document full of markers and citations can still be
wrong, and a green gate means the form is right, not the content.

The one thing that reliably catches the rest is the habit in §3: read it yourself
before you say it.

---

## Provenance

Every rule here was written after violating it. The examples are real, they come
from the audit that produced this bundle, and they are included specifically
because rules stated without the failure that motivated them do not survive
contact with a deadline.

## Evidence boundary

This skill contains no claims about any codebase. Its examples describe mistakes
made during one research project and the corrections that followed; they are
offered as illustrations of a class, not as findings about the project they came
from.
