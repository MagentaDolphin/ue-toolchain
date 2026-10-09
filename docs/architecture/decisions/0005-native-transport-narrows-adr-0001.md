---
status: accepted
date: 2026-09-06
deciders: project owner
consulted: ADR-0001; live measurement of the engine's own MCP server (UE 5.8)
informed: future contributors
amends: 0001-discovery-over-pid-file
---

# The engine ships the transport; ADR-0001 narrows to what it still decides

## Context and Problem Statement

ADR-0001 was written against one existing bridge, which tied a server to a PID file on
disk. It rejected that and specified a replacement: our own JSON-RPC server inside the
editor, our own UDP-broadcast discovery on a loopback port, our own heartbeat.

None of that was built. In the meantime the engine acquired an agent-tool layer of its
own: an MCP server, a toolset registry, and skill assets discovered from the project.
This was measured, not read about -- a live editor served a session over the documented
endpoint, negotiated a protocol version, and answered a tool listing.

So the question ADR-0001 answered is no longer open in the same form. Building a second
transport beside a first-party one is not a contest this project can win: it doubles the
surface, and the vendor's version moves with the engine.

What ADR-0001 got right is separate from what it specified. Its reasoning was about
**liveness** -- a file cannot say whether a process is alive, tools that require an editor
must disappear when the editor does, and the client must recover without a restart. That
reasoning survives a change of transport intact.

## Decision Drivers

- **Do not compete with the first party on transport.** The server, the session model and
  the protocol ship and are maintained with the engine.
- **A tool layer is still missing where it matters.** The registry that serves toolsets is
  editor-only by declaration; the transport module is not. The one thing measurement shows
  nobody covers is tools that run in a live game outside the editor.
- **The liveness contract from ADR-0001 is still the product.** Its value was never the
  broadcast; it was that file-based tools keep working and editor-based ones vanish
  honestly.
- **What we do not build, we do not have to keep working.**

## Decision Outcome

ADR-0001 is **narrowed, not withdrawn**. Its analysis stands; three of its mechanisms are
dropped, and one is replaced.

**Kept.**

- The process is the source of truth, never a file on disk.
- File and analysis tools work with no editor present.
- Editor-dependent tools appear in the tool list only while a connection is live, and
  disappear on their own when it is not.
- Recovery without restarting the client.

**Dropped.**

- Our own JSON-RPC server inside the editor. The engine has one.
- UDP-broadcast discovery on a loopback port. Superseded below.
- Our own heartbeat protocol. The session layer already has one.

**Replaced.** Discovery becomes a probe of the engine's documented endpoint rather than a
broadcast we invent: a configured host, port and URL path, with the endpoint's own answer
deciding liveness. Measured behaviour that makes this cheap: a request to the wrong path
returns a plain HTTP 404 with a routing error body, immediately and without hanging, and
path matching tolerates case and a trailing slash. A wrong guess is therefore a fast
negative, which is what a probe needs and what the PID file could not give.

**What remains ours to build**, and only this:

1. A server that runs without the engine, carrying file and analysis tools -- unchanged
   from ADR-0001, and the reason a component still exists at all.
2. Tools that run in a live game outside the editor, registered through the engine's
   public runtime interface. This is the one layer measurement shows is uncovered: the
   toolset registry and every toolset built on it are declared editor-only, while the
   transport module is not.

Explicitly **not** ours: the protocol, the server, the session model, the editor-side
toolsets, and the skill-asset registry.

## Consequences

- Good: phases 1 and 2 of the handoff shrink by an order of magnitude. There is no bridge
  plugin to write, no protocol to version, no discovery to debug.
- Good: the uncovered layer we take on -- runtime, outside the editor -- is the same
  territory as the one skill with no first-party equivalent. Scope and product need
  coincide rather than compete.
- Good: nothing in ADR-0001's liveness criteria is lost; they are restated below against
  the new transport.
- Bad: the project now depends on a plugin its author marks Experimental, with a stated
  warning that APIs and formats may change at any time. Accepted, and mitigated where it
  touches the delivery: ADR-0004 keeps that surface out of skill content entirely.
- Bad: two editors on one machine both default to the same port, and how the second
  behaves has not been measured. Under ADR-0001 this was our problem to solve; now it is a
  question to answer, and it is listed as open rather than assumed benign.
- Neutral: the rejected design is not deleted. ADR-0001 keeps its four arguments against
  the PID file, which is why the replacement is a probe with a fast negative and not
  another file.

## Confirmation

Required before this ADR is treated as implemented:

- Cold start with no editor running: file and analysis tools answer, editor tools are
  absent from the tool list, no call blocks.
- Editor running: editor tools become reachable after a probe, and the probe's negative
  path costs one fast HTTP response rather than a timeout. *(the negative path is already
  measured: HTTP 404 with a routing error body, no hang)*
- Editor closed mid-session: editor tools disappear without a client restart and no call
  hangs waiting for them.
- Editor restarted: tools return without restarting the client.
- A runtime tool registered through the engine's public interface answers in a packaged
  build with no editor present. **Not yet attempted** -- this is the load-bearing claim of
  the whole narrowing, and until it runs, item 2 above is derived, not measured.

## Deferred

- **Two editors, one default port.** Which instance binds, what the second reports, and
  whether the client can address a specific project. Unmeasured; do not guess it.
- **Whether an editor-side component is ever needed.** Nothing requires one today. If one
  appears, it should arrive as its own ADR with a reason, not as scope creep into this one.
- **Remote operation.** Deferred by ADR-0001 and still deferred. Nothing measured here
  changes that.
