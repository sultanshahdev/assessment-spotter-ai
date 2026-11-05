## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Permanent engineering contract
For every task read this file, CONTEXT.md and relevant docs/decisions.md entries; inspect Git status, phase and scope. Query an existing graph before broad searching; verify graph freshness and inspect relevant source, callers, interfaces and tests before editing.
Authority: official assessment requirements > approved decisions > tested API contracts > verified source behavior > project context > suggestions. Flag contradictions; never simplify business rules silently.
Keep modules small, cohesive, typed and testable. Use explicit units and reliable errors. Prefer maintainable delivery over abstractions.
Django validates HTTP and orchestrates; keep routing, geometry, checkpoints, ETA, weather normalization, risk, exposure and recommendation separate from views.
React/TypeScript separates API, form, comparison, recommendation, map, checkpoint interaction, heatmap, slider and loading/errors. Never duplicate backend risk logic; avoid unnecessary global state.
Verify every meaningful change with relevant tests, static checks, builds or runtime checks; report exact commands and actual outcomes.
Use environment variables and safe .env.example placeholders. Never expose credentials, private environment values or authenticated URLs. Never commit .env.
Implement only approved scope; preserve functionality and avoid unrelated refactors. No commits or pushes without explicit authorization.
Update CONTEXT.md after meaningful changes and relevant docs for decisions, interfaces, algorithms, assumptions, limitations and milestones. AGENTS.md is behavioral policy, not a progress log.
Refresh an existing graph after meaningful code changes with graphify update .; verify completion and inspect changed relationships. Graph inference never proves functionality. Use incremental updates, preserve managed content, keep generated output ignored. Do not install globally, add MCP or graph services without authorization.
End significant tasks with task ID, summary, files changed, graph investigation, executed checks/results, architecture implications, context updates, unresolved issues and next bounded task.
P01 review is required before full application implementation. Preserve the official 16-working-hour constraint; approximately two calendar days were reported at task intake.
