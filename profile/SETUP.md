# GitHub profile setup and cleanup review

## Prepared profile fields

Name: Vishak S

Bio: Backend Engineer | Python, Django, FastAPI, PostgreSQL | Payments, APIs & async systems | Bengaluru, India

Location: Bengaluru, India

Website: https://www.linkedin.com/in/s-vishak/

## Activate the profile README

Create a public repository named `Vyshak1736` under your personal account and copy `profile/README.md` from this repository into its root as `README.md`. This filename and repository name are required for GitHub's profile README feature. The available connection cannot create repositories or edit profile fields.

Pin the portfolio and Voice CRM Assistant. Once Webhook Ledger is moved to its own repository, pin that repository as your primary backend project.

## Cleanup findings

| Repository | Evidence | Proposed action |
| --- | --- | --- |
| portfolio | Public; its README previously contained only a title | Keep; professional introduction and backend project added |
| Voice-CRM-Assistant | Public; documented Django/React prototype | Keep; clearly label mock transcription; verify setup and add tests before calling it production-ready |
| CoffieWebsite | Public; repetitive README and tracked Python caches | Generated Python cache files can be removed safely; archive if this learning project is no longer useful |
| vishak-s | Private; three files; portfolio.html has the exact same blob SHA as portfolio | Archive candidate; confirm no unique history or deployment before deletion |
| chap-project / CHAP-EZY-Helpers | Both main branches point to a08c61702eb10f874c963cae1d12fe3ec6469e69 | Keep private; compare other branches, CI, deployments, and collaborators before archiving one |
| EZY-Helpers/demo-repository | Company-owned repository shown in screenshot | Leave unchanged; ownership and active use need verification |

Repository deletion is permanent enough to require an explicit list of targets. No repositories have been deleted. `db.sqlite3` in CoffieWebsite may contain data and has not been removed. Removing files from a current branch does not purge historical Git commits.

This review covers accessible repository metadata, file trees, and READMEs. It is not a full source-code, security, or deployment audit. The existing portfolio.html has not been rewritten or visually audited.
