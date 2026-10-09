---
status: accepted
date: 2026-09-03
deciders: project owner
consulted: licence text review (CC BY-ND 4.0 legal code, Apache-2.0, PolyForm family)
informed: future contributors, studios adopting the bundle
---

# Split licensing: CC BY-ND 4.0 for prose, Apache-2.0 for code

## Context and Problem Statement

Handoff question 2 has been open since 2026-09-01. ADR-0002 deliberately *removed*
`license` from the shipped metadata rather than filling in the planned value, on the
grounds that a licence asserted before it is chosen is a claim with no author. That left
the bundle shippable but not releasable.

The owner's requirements, stated directly:

> Free use by studios · my name credited, including in game credits · no forking my work
> into someone else's product without permission, commercial ones especially · no claim
> over the games and code built with the tool.

Translated into licensing terms: a grant on **use** including commercial (R1); attribution
triggered by **use** (R2); a restriction on **Share Adapted Material** (R3); an explicit
**output** carve-out (R4).

R1 and R3 are compatible: they govern different acts. Using a work and republishing a
modified version of it are separate permissions, and granting the first while withholding
the second is an ordinary construction.

**R2 as stated is not achievable through any licence.** Attribution obligations attach to
distribution. A studio that reads the skills, applies them and ships a game has
distributed nothing, so no licence term can reach that act. This was measured against the
candidate texts rather than assumed, and the owner withdrew the requirement once the
mechanism was clear, replacing it with a request in the README.

## Decision Drivers

- **The bundle is prose, not software.** ~19 000 lines of hand-written norms and recipes.
  Licences written for code do not carry the obligations prose needs.
- **Phase 1 puts C++ in this repository.** A restriction that is tolerable on a document
  is expensive on code a studio compiles into its editor. Licences cannot be changed
  retroactively for those who already took the work.
- **Adoption is the point.** A restriction that sends every studio's legal department into
  review defeats R1 more effectively than a permissive licence defeats R3.
- **The bundle's own doctrine constrains the licence.** It instructs the reader to verify
  every recipe against their own tree. Forbidding publication of the correction would make
  the delivery contradict its content.

## Considered Options

1. **MIT or Apache-2.0 throughout.** Fails R3 explicitly: both permit commercial forks.
2. **CC BY 4.0 throughout.** Real attribution on redistribution, but derivatives allowed.
3. **CC BY-NC.** Blocks commercial *use*, which is R1's audience. The owner's objection is
   to commercial forks, not commercial users; NC is aimed at the wrong act.
4. **PolyForm Internal Use.** Fits R1 and R3 closely, but is little known; an unfamiliar
   licence more often produces a refusal than a question.
5. **A bespoke four-clause licence.** Delivers R1–R4 including credits, at the cost of
   mandatory legal review at every adopting studio — the cost falls precisely on R1.
6. **Split: CC BY-ND 4.0 for prose, Apache-2.0 for code and metadata.**

## Decision Outcome

Chosen: **option 6**, with seven explicit additional permissions.

Copyright holder: **MagentaDolphin**, a pseudonym under which the owner publishes.
Section 3(a)(1)(A)(i) of the licence provides for attribution by pseudonym, so this is a
supported form rather than a compromise, and substituting a legal name later refines the
same holder rather than changing licence. Publisher: **MagentaDolphin**, recorded in
`catalog.json`. Collective pseudonyms were rejected for the copyright line: naming a
holder that stands for several people asserts joint ownership, and every later act — a
relicence, a translation grant, an enforcement — would then require their agreement.

| Surface | Licence |
|---|---|
| `plugins/ue-design-skills/` prose: `SKILL.md`, `references/`, `README.md` | CC BY-ND 4.0 |
| `catalog.json`, `.claude-plugin/plugin.json` | Apache-2.0 |
| `_gate/` | Apache-2.0 |
| Shell commands inside `Detect` fields | Apache-2.0 |
| Editor plugin, MCP server, installer (phases 1–3) | Apache-2.0 |

Additional permissions in `plugins/ue-design-skills/LICENSE`, each widening the grant:
metadata, gate and Detect commands are Apache-2.0; format adapters may be published;
translations may be published under stated conditions; private adaptation is restated as
already permitted; contributions via fork-and-pull are permitted.

**Attribution in game credits is a request in the README, not a licence condition.** It is
written as a request so that nobody mistakes it for an obligation they have breached.

### Consequences

- Good: R1, R3 and R4 hold. Commercial use is free; republishing modified prose is not;
  nothing is claimed over what users build.
- Good: the carve-outs keep ADR-0002 intact. A second harness adapter is explicitly
  permitted, so the neutrality commitment is not quietly revoked by the licence.
- Good: the code path stays permissive before any code exists, so phase 1 does not force
  a retroactive change.
- Bad: two licences in one repository require explanation. Mitigated by stating the
  boundary in three places — both `LICENSE` files and both READMEs.
- Bad: CC BY-ND is not an OSI-approved open-source licence. Some organisations restrict
  non-OSI content by policy. This is the accepted price of R3.
- Bad: R2 as originally stated is not delivered. Recorded here so that the gap is visible
  rather than assumed closed.
- Neutral: the licence is irrevocable. Anyone who takes the work under these terms keeps
  them. True of any licence, more expensive to get wrong with a restrictive one.

## Confirmation

Checked at the time of writing, and required for every later change:

- `claude plugin validate . --strict` passes at the marketplace root and the bundle root.
  *(passing; `publisher` and `license` were rejected inside marketplace `metadata` and
  moved to `catalog.json`, which is the source of truth per ADR-0002)*
- `python _gate/gate.py .` reports zero violations with both LICENSE files in place.
  *(passing)*
- `python _gate/test_gate.py` reports every rule reddening on its own fixture, plus every
  file in `SCAN_ROOT_FILES` reaching the line-level rules. *(passing, 16 rules, 2 root
  files)*
- The donor name inside the LICENSE `PROVENANCE` banner passes; the same name one line
  outside it fires P03. *(verified in both directions)*
- Licence texts are the canonical ones, fetched from `apache.org` and
  `creativecommons.org` rather than transcribed.

### A gate defect found by this work

`LICENSE` was declared in the gate's `SCAN_ROOT_FILES` from the start, and the line-level
rules filtered it out one line later because they matched on file extension and `LICENSE`
has none. A `LICENSE` carrying an absolute path, a source citation, the donor name,
Cyrillic and a wikilink passed the gate green — verified by poisoning it before the fix.

This is the gate's own P08 shape: a check whose condition could not become true, on the
one file a lawyer reads. The fix treats declared root files as text whatever their suffix,
and the self-test now asserts surface coverage separately from rule coverage — proving not
just that each rule *can* fire, but that each file the gate *claims* to scan actually
reaches the rules. Reverting the fix reddens the suite, which was checked.

## Deferred

- **Whether the repository is public.** Handoff question 1, still open. The licence choice
  does not decide it.
- **A legal review of the UE EULA question.** The bundle ships no third-party source, no
  file addresses and no verbatim excerpts, and the gate enforces the first two. That
  lowers the risk and is not a legal determination. If the release is public, this needs
  someone qualified.
- **Whether to register the pseudonym to a legal name.** Not required to publish; a
  refinement of the same holder when it happens.
