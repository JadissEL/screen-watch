# Security

screen-watch is **observation-only** and **local-only**.

## Guarantees (design)

- No mouse/keyboard injection APIs in the dependency surface for core features.
- MCP transport is **stdio** to the agent host you configure — frames do not leave the machine unless *that agent* sends them elsewhere.
- Recording and blur default **off**.
- Capture calls are serialized with a short min-interval gate to limit accidental stampede.

## Trust boundary

Any MCP client attached to this server can request screen frames. Treat Cursor / Claude Code / etc. as trusted for the duration of the session.

## Reporting

If you find a control-injection or exfil path in this repo, open a private issue with Jadiss or email the maintainer listed on the GitHub profile.
