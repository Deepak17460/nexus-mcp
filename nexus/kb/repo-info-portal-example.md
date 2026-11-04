---
id: repo-info-portal-example
title: Example - Repository Info / Ownership Portal
url: https://example.com/nexus-repo-info/
category: portal
keywords: repo info, repository list, browse repositories, which repo, repo owner, find repository, approver, repo name
---
Placeholder for an org-specific page listing Nexus repositories along with
their owners/approvers and other metadata — something Nexus's own REST API
doesn't expose at all.

If your org has a page like this, check it **before** submitting an access
request — it's usually the fastest way to find the exact repository name
and its approver. Related: `nexus_get_repository_owner` and the
`NEXUS_REPO_INFO_URL` environment variable, which can point at this same
kind of portal (set it to enable that tool; see `README.md`).
