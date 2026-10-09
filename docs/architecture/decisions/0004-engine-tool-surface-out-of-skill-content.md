---
status: accepted
date: 2026-09-05
deciders: project owner
consulted: live measurement of the first-party agent-tool layer in UE 5.8
informed: future contributors
---

# The engine's own tool surface stays out of skill content

## Context and Problem Statement

The engine now ships an agent-tool layer of its own: an MCP server, a registry of
toolsets, and skill assets discovered from the project. The obvious move is to write
recipes against it — name the toolset, name the tool, and the reader runs it.

Two measurements taken against a live editor say why that is a trap.

**The surface is larger and differently shaped than its own manifest suggests.** The
aggregator plugin lists 21 dependencies. The running server reported **53 registered
toolsets** from 22 plugins, one aggregated dependency contributing none at all and two
non-aggregated plugins contributing two. Any number written into a recipe is a number
about one project's plugin set, not about the engine.

**The number of visible tools is a project setting, not a property of the engine.** With
tool search on — the default — `tools/list` returns exactly three meta-tools and every
real tool is reached indirectly. With it off, every toolset tool registers natively. A
recipe that says "call tool X" is correct or nonsense depending on one checkbox.

Both layers are marked Experimental by their author, with an explicit notice that APIs
and data formats may change at any time. That is the vendor telling us the surface is
not a stable address.

## Decision Drivers

- **This bundle's subject is what fails silently.** A recipe naming a tool that no longer
  exists does not error: the tool is absent, nothing is found, and "nothing found" reads
  as "no problem here" — the exact confusion the bundle exists to prevent.
- **ADR-0002 already forbids naming one harness.** An engine build is the same category
  of dependency, and the argument for P13 is the argument here.
- **The first party asks for the same thing.** Its published skill-authoring norm lists
  *Durable* and *Agnostic* among six properties; this rule is those two, enforced.
- **A promise that lives in prose rots.** P13 was made checkable the hour it was decided.

## Considered Options

1. **Write recipes against the native tools.** Cheapest to read, dates fastest.
2. **Name tools but mark them version-bound.** A warning next to a command is read as a
   command; and the failure is silent, so the warning arrives too late.
3. **Keep the tool surface out of skill content, and enforce it.**

## Decision Outcome

Chosen: **option 3**, as gate rule **P17**.

Nothing under `skills/` may name a toolset, a meta-tool, an endpoint host:port, or the
Experimental class names of the engine's skill-asset API. Detect recipes may say *what*
to look for; they may not say *which first-party tool to look with*. Everything outside
`skills/` — the catalog, adapters, the gate, the research archive — is unaffected, and
that is where any tool-specific knowledge belongs.

### Consequences

- Good: a recipe written today still means something on the next engine build, or fails
  loudly by being unrunnable rather than quietly by finding nothing.
- Good: the bundle's neutrality claim now covers both axes it can drift on — the harness
  that runs the agent, and the engine that hosts the tools.
- Bad: recipes stay one step further from executable. The reader translates "find fields
  with no writer" into whatever their build offers. This is the accepted price.
- Bad: the rule cannot distinguish a tool name from an ordinary word that ends in the
  same token. Checked against the whole bundle before landing: zero matches, so the cost
  today is zero and any future collision is visible at the moment it is introduced.
- Neutral: knowledge about the native layer is not lost, only relocated. It lives in the
  research archive, where it can name builds, ports and classes freely.

## Confirmation

Checked at the time of writing, and required for every later change:

- `python _gate/gate.py .` reports zero violations. *(passing, 17 rules)*
- `python _gate/test_gate.py` reports every rule reddening on its own poisoned fixture,
  with a clean baseline and full surface coverage. *(passing, 17/17)*
- The P17 fixture names a toolset, a meta-tool and a `host:port` in one line, and the
  rule fires on it. *(verified)*
- The token list produces no match anywhere under `skills/` today. *(verified before the
  rule landed; a match would be a new violation, not a false positive to be excused)*

## Deferred

- **Whether the bundle ever ships an engine-side adapter** that maps a recipe to whatever
  tools the current build offers. That is the natural home for the knowledge this rule
  keeps out, and it should be written when a build is worth targeting — not before.
- **Whether skill assets inside the engine become a second delivery channel.** Measured as
  workable: an asset created in a live session appeared in the project's skill list with
  no editor restart. Also measured as fragile: an asset created with an empty description
  is created successfully and then never listed, with no error on either call. A channel
  whose failure mode is silent deletion needs a gate of its own before it carries anything.
