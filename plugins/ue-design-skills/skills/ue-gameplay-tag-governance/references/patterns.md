# Patterns: tag vocabulary in a measured reference product

A worked example of the governance rules from `SKILL.md`, against one specific
reference project read as source. It exists so the failure modes in
[failure-modes.md](failure-modes.md) can be read as *shapes that occur together*
rather than as a checklist of independent risks.

The project audited below is a careful, well-organised codebase. That is the
point. Every finding here survived review by competent engineers, because none of
them has a runtime signature.

Markers: **[measured]** — read in source or config; **[derived]** — conclusion
from measured facts; **[open]** — not answerable without the editor or a
networked build.

---

## 1. Six declaration sources, and only one of them is easy to find

The project declares tags from five distinct sources simultaneously
**[measured]**:

| Source | Count | Visible to a naive text search |
|---|---:|---|
| Project config, `+`-prefixed | 99 | yes |
| Plugin configs, no `+`, different section | 113 across 4 files | **no** |
| Native macros, central registry file | 35 | by symbol |
| Native macros, elsewhere in the tree | 59 across 30 files | by symbol |
| DataTable rows in binary assets | **[open]** | **no** |

Two numbers in that table are the lesson.

**212 versus 99.** A pattern anchored on the project-config form finds 99 tags and
reports them confidently. The real config vocabulary is 212 across five files
**[measured]**. The pattern is not subtly wrong; it misses the majority. Recipe:
TG-05.

**94 across 31 files, 35 central.** Native definitions split three ways — 24 plain
macros, 35 with comments, 35 file-local statics **[measured]**. The file whose
name promises to be the registry holds roughly a third of them. Restricting the
search to the primary source directory instead of including plugins undercounts by
18 **[measured]** — the same failure as the config case, one directory level up.
Recipe: TG-17.

**[derived]** There is no single artefact in this project that answers "what tags
exist". Any audit, rename or deletion built on one is incomplete by construction,
and will produce a number that looks authoritative.

---

## 2. Validation coverage: fourteen of sixty-four, one of them broken

Editable tag properties: 64. Properties carrying a `Categories` constraint: 14
**[measured]** — under sixteen per cent.

That ratio is a list of places where a typo cannot be caught. But the sharper
finding is inside the fourteen: one constraint named a namespace that appears
nowhere else in the project, while the tags it was meant to offer live under a
differently-named root **[measured]**.

**[derived]** The filter does not narrow the picker, it empties it. And it does so
in one of the few places where tag input was validated at all — so the single most
protective mechanism in the file was the one that was misconfigured.

The general form is worth stating: **a constraint is only a guardrail if something
proves it resolves.** An empty dropdown is indistinguishable from a namespace
nobody has populated yet, so the editor cannot tell you, and neither can the
compiler. Recipes: TG-03, TG-04.

---

## 3. A misspelling that works because every side repeats it

The token `Primarly` — for `Primarily` — appears at six sites across four files
**[measured]**: two project tag declarations, two platform-specific config files,
and a native tag macro plus its use in a widget class.

**[derived]** It functions precisely because every side misspells it identically.
Fixing any one site breaks the join, with no error at either end and a diff that
every reviewer would approve.

This is the cleanest available demonstration of the invariant at the top of the
skill: **when a string literal is the join, correctness means "all sides agree",
not "the string is right".** Recipe: TG-02.

The project's exposure to this class is total in a specific way: **zero
`GameplayTagRedirects` are declared**, confirmed with two independent search
patterns **[measured]**. Every rename in this project is therefore destructive,
including the corrective rename that fixing `Primarly` would require. Recipe:
TG-18.

---

## 4. Replication settings that carry an unstated limit

| Setting | Value **[measured]** | What it means in tags |
|---|---|---|
| Fast replication | enabled | Tags travel as registry indices; client and server registries must match exactly |
| Bits for container size | 6 | A hard cap of 63 entries per replicated tag container |

**[derived]** The first row makes plugin-asymmetric tag loading a correctness
problem rather than a cosmetic one, and PIE cannot reproduce it: one process, one
registry. The second row is a gameplay limit expressed as a bit count, sitting in
a settings file, with nothing connecting it to the containers that will grow.

**[open]** Whether client and server registries actually match under asymmetric
feature-plugin loading is unanswerable without a dedicated-server build, and is
left open. Recipes: TG-10, TG-11.

---

## 5. Counters: the tag is validated, the amount is not

A tag-to-count container in the project validates its tag argument at both the add
and the remove site, with a warning on failure. Neither site validates the
*amount*: a guard of the form "if the amount is positive" returns silently
otherwise, and the accumulator has no clamp **[measured]**. An unresolved TODO
next to the remove path asks exactly what should happen when more is removed than
exists **[measured]**.

**[derived]** This asymmetry is the entire finding, and it is invisible for a
structural reason: seeing the tag validation satisfies the reviewer's question
"are the inputs checked here?". One checked parameter reads as a checked function.

Worth noting for balance: the same container implements all three replication
callbacks correctly, keeping its array and lookup map consistent **[measured]** —
which is exactly the discipline that a different structure in the same project
fails to apply. Recipes: TG-12, TG-13.

---

## 6. A stub with a second layer under it

One widget base class exposes an editable tag container for "hide when these tags
are present". Both consumer sites hardcode the check result to a constant, with
the real expression parked in a comment **[measured]**. That alone is an ordinary
stub: the property is authored, read nowhere, and does nothing.

The second layer is what makes it worth including here. A setter in the same class
overwrites the designer-authored visibility values during construction
**[measured]**.

**[derived]** So the obvious one-line fix — implement the hardcoded check —
produces *wrong* behaviour rather than correct behaviour, because it would select
between two values that no longer hold what the designer authored. The fix then
gets blamed and reverted, burying the original defect under a failed attempt.

**A stub can be deeper than its TODO admits.** Before implementing one, trace its
inputs. Recipes: TG-14, TG-15.

---

## 7. Documentation coverage

68 of 99 project-config tags carry an empty comment field — sixty-nine per cent
undocumented **[measured]**.

**[derived]** This is why vocabularies only grow. A tag nobody can explain is a tag
nobody can safely delete, so the safe action is always to add another one. Over a
project's life that produces duplicate tags for one concept, which is the
condition that makes hierarchical matching dangerous (TG-08) and renames necessary
(TG-18) — both of which this project is unprotected against.

One tag's own comment in the project admits that the tag sits in the wrong
namespace and needs to move **[measured]**. With zero redirects declared, that move
cannot be made without breaking every asset that references it. The comment is an
accurate description of a debt that the configuration makes unpayable.

---

## 8. What the reference got right

1. **A central registry file exists** and is well organised — the problem is its
   share, not its quality **[measured]**.
2. **Replication callbacks on the tag-stack container are complete**, keeping the
   replicated array and the lookup map consistent in all three **[measured]**.
3. **Tag validation with explicit warnings** at the stack add/remove sites — the
   discipline is present, it is simply applied to one parameter of two
   **[measured]**.
4. **Constraints exist at all.** Fourteen constrained properties is a low ratio,
   and it is fourteen more than most projects have.

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6, read as source and
config in a single workspace. Source addresses stay in the research archive that
produced this skill; each `TG-` identifier resolves back to the audited location
there. Numbers without an author are worth less than no numbers, so: this is where
these came from, and they can be produced on request.

One correction is recorded here rather than hidden: an earlier form of this
material stated that 59 native definitions were spread over "40+ files". The
re-measurement performed while writing this file gave **94 definitions across 31
files**, and that is the number above. The original figure was never verified; the
recipe in TG-17 is what produced the corrected one.

## Evidence boundary

Every claim above refers to one project on one engine version. These are examples
and failure evidence, not guarantees about other engine versions or other samples.
The counts are properties of that project on that day and are quoted only to show
the shape of the contrast a recipe produces — re-run the recipes against your own
tree rather than importing the numbers.
