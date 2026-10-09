---
status: accepted
date: 2026-09-01
deciders: project owner
consulted: Lyra/VibeUE post-mortem
informed: future contributors
---

# Discovery over PID file

## Context and Problem Statement

VibeUE, the current third-party MCP server for Unreal Engine, couples its operation to a
**PID file** written by the editor plugin to disk. The MCP server reads this file on
startup to find which editor instance to talk to.

This coupling produces concrete pain:

1. **Cold start requires existing marker.** If no PID file is on disk, the MCP server
   either fails to start or hangs on a 60-second timeout waiting for it.
2. **Zombie state after editor close.** When the editor is closed, the PID file remains.
   The MCP server's `tools/list` answers instantly but any `tools/call` hangs for 60s,
   because the file references a process that no longer exists.
3. **Two-editor ambiguity.** Two editors writing to the same PID file → one wins
   randomly. The other editor is invisible to MCP until the winning one closes.
4. **Restart coupling.** Restarting the editor requires restarting the MCP server, or
   the server keeps holding a stale connection.

The user described this as "wildly annoying" (`дико бесит`). It is also an architectural
mistake: **a process's metadata file is a cache, not the source of truth.** When the
process dies, the cache becomes a lie.

How should `ue-toolchain` locate a running editor instance?

## Decision Drivers

- **No file-based state on disk for liveness.** Liveness is a property of a running
  process, observable through the network.
- **Multiple editor instances must coexist.** A developer working on two UE projects
  side-by-side is normal.
- **MCP server must be useful without the editor running.** Filesystem reads, project
  analysis, and pre-generated documentation do not require a live editor.
- **Tools available to the agent must reflect reality.** If the editor is down, its
  tools must not appear in `tools/list`. Stale `tools/call` timeouts are unacceptable.
- **Recovery is automatic.** When the editor restarts, the MCP server reconnects
  without manual intervention.

## Considered Options

1. **PID file (VibeUE approach).** File on disk, written by plugin, read by MCP server.
2. **UDP broadcast discovery.** Plugin announces itself; MCP server listens.
3. **TCP port scan + handshake.** Try known ports, see who responds.
4. **OS-level IPC (named pipes / Unix domain sockets).** One socket per editor instance,
   filesystem-based.

## Decision Outcome

Chosen option: **"UDP broadcast discovery"**, with TCP for the actual data channel,
and **graceful degradation** so the MCP server stays useful without an editor.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ MCP server (always running, independent of UE)              │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ filesystem   │  │ project      │  │ editor tools     │  │
│  │ tools        │  │ analysis     │  │ (registered iff  │  │
│  │ (always)     │  │ tools        │  │  editor found)   │  │
│  │              │  │ (always)     │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         ▲                 ▲                  ▲              │
└─────────┼─────────────────┼──────────────────┼──────────────┘
          │                 │                  │
        disk             disk            TCP (if editor)
```

### Discovery protocol (UE plugin side)

On `StartupModule`, the plugin:

1. Picks a free TCP port (system-assigned or requested via config).
2. Starts a UDP broadcaster on `127.0.0.1:8088`. Every 2 seconds it emits a small
   payload: `{ magic: "UEToolchain", pid, project_path, engine_version, tcp_port }`.
3. Starts a JSON-RPC server on the chosen TCP port.

The broadcaster runs **only on loopback** (127.0.0.1), so there is no network exposure.

### Discovery protocol (MCP server side)

On startup, the MCP server:

1. Registers filesystem tools and analysis tools unconditionally.
2. Sends a UDP broadcast "who's UEToolchain here?" on `127.0.0.1:8088`.
3. Waits up to 500ms for responses.
4. For each response, validates `magic == "UEToolchain"`, then attempts a TCP
   handshake to the announced port.
5. On successful handshake, registers editor tools in the live tool registry.
6. If no response within timeout → runs in **editor-less mode**. Only filesystem and
   analysis tools are visible to the agent.

A heartbeat loop runs every 5 seconds. If the chosen instance misses 3 consecutive
heartbeats (15 seconds), the MCP server marks the connection dead and:

- Removes editor tools from `tools/list`.
- Optionally retries discovery to find a fresh instance.

### Multi-instance behavior

When two editors announce themselves, the MCP server sees both. Selection rules
(applied in order):

1. `--project=<path>` CLI flag → match by `project_path`.
2. `--engine=<version>` CLI flag → match by `engine_version`.
3. Config file `~/.config/ue-toolchain/config.toml` → preferred project.
4. Otherwise → first response received wins; the other is logged but not used.

### Graceful degradation

Tools are decorated with `requires_editor: bool`:

```python
@mcp.tool(requires_editor=False)
def read_cpp_file(path: str) -> str:
    """Read a C++ source file. Works without UE running."""
    ...

@mcp.tool(requires_editor=True)
def set_blueprint_node_property(blueprint: str, node_id: str, pin: str, value: str) -> str:
    """Modify a Blueprint node. Requires UE editor with UEToolchain plugin."""
    ...
```

The server filters `tools/list` to remove editor tools when no editor is connected.
This means **agents do not call tools that will fail.** Stale-tool-call hangs are
structurally impossible.

### Consequences

Good:

- **No stale state.** File is not the source of truth; the process is.
- **Cold start works.** Discovery finds a running editor even if MCP starts after it.
- **Multi-editor safe.** Two editors do not fight over a single file.
- **Editor-less mode is useful.** Reading code, analyzing structure, querying docs
  works without UE running. The server is not idle during the long shader-compile
  minutes.
- **Automatic recovery.** Heartbeat-driven reconnect; no manual restart.

Bad:

- **Loopback-only broadcast** is a deployment constraint: editor and MCP client must
  be on the same machine. Remote scenarios (editor on one host, agent on another) are
  not addressed by this decision. If such a need arises, it will be handled by a
  future ADR when there is a concrete request — not pre-empted now.
- **Discovery adds latency** to first tool call (≤500ms once at startup, then cached).
  Negligible compared to the 60s timeouts it replaces.
- **Two-editor scenario needs disambiguation** rules, which the user must configure
  or accept the default.

### Confirmation criteria

This decision is considered successfully implemented when:

- MCP server starts in <1s with no editor running and exposes filesystem tools only.
- MCP server starts in <1s with one editor running and exposes editor tools after
  discovery.
- Closing the editor: editor tools disappear from `tools/list` within 15s (3 missed
  heartbeats), no `tools/call` hangs.
- Restarting the editor: editor tools reappear within 5s (next discovery cycle),
  no MCP server restart needed.
- Two editors running: `--project=` flag selects the correct one; without the flag,
  the first response wins deterministically (logged).

## Pros and Cons of the Options

### PID file (VibeUE approach)

- Good: simple to implement.
- Bad: stale state after editor close; ambiguity with multiple editors; cold start
  coupling; the exact problem the user wants to avoid.

### UDP broadcast discovery

- Good: process-as-source-of-truth; multi-instance safe; no disk state; fast.
- Bad: 500ms latency on startup; loopback-only constraint.
- Notes: this is the chosen option.

### TCP port scan

- Bad: requires knowing ports in advance; no discovery of new instances.
- Notes: rejected; doesn't solve the multi-instance problem.

### OS-level named pipes / Unix sockets

- Good: filesystem-based, no network.
- Bad: cross-platform complexity (Windows pipes vs Unix sockets); still requires
  a directory to scan; doesn't naturally broadcast liveness.
- Notes: rejected; UDP is simpler and already cross-platform.

## References

- VibeUE behavior analysis (post-mortem of user's daily driver pain):
  LyraResearch project, skill `unreal-blueprint-editing`, observation about the 60s
  hang on `tools/call`.
- MADR template: <https://adr.github.io/madr/>
- LyraResearch `STRATEGY.md` line 113-122 documents the port-8088 conflict caused
  by the same PID-file-based discovery.
