# Nexus Knowledge Base

Local knowledge base backing the `nexus_info` MCP tool. Each file in
[`kb/`](kb/) is a small Markdown file with a frontmatter block:

```markdown
---
id: unique-id
title: Human-readable title
url: https://...
category: servicenow | portal | documentation | ...
keywords: comma, separated, search, terms
---
Free-text body shown as the summary.
```

To add a new entry (e.g. a new ServiceNow catalog item or portal link), add
another `kb/*.md` file following this format — no code changes needed. The
`nexus_info` tool (`nexus_mcp/tools/info.py`) reads every `*.md` file in this
directory at call time and keyword-matches them against the caller's query.

This folder must ship alongside `nexus_mcp/` in every deployment (pip
install, Docker). See the `Dockerfile`'s `COPY nexus/ ./nexus/` step.
