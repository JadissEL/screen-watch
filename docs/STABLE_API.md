# Stable API (0.2)

Starting with **v0.2.0**, the MCP tool names in `screen_watch.mcp.tools_catalog.TOOL_NAMES` are treated as a **compatibility surface**.

## Guarantees

- Tool **names** will not be removed or renamed without a major version bump.
- Existing parameters keep their meaning; new optional parameters may be added.
- New tools may be added in minor releases (additive); removals require a major bump.
- Resources `screen://privacy`, `screen://status`, `screen://tools`, `screen://recordings` stay available when the MCP SDK supports resources.
- Observation-only: no control-injection tools will be added under these names.

## Non-guarantees

- Exact JPEG bytes / `content_hash` algorithm may change (still a stable string for `since_hash` within a process).
- `change_score` scale is mean-abs grayscale thumb diff (0..255); thresholds remain user-configurable.
- Native capture backends may still fall back to `mss`.

See [MCP.md](MCP.md) for the full tool list.
