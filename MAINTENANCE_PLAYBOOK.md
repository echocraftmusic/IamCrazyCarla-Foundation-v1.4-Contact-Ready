# MAINTENANCE_PLAYBOOK.md — iamcrazycarla.com

**Updated:** 2026-10-22  
**Read with:** [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)  
**Confidence:** Entry paths below were observed directly in GitHub source. Deployment, runtime state, credentials, and connected Cloudflare resources were **not independently verified**.

## Known code entry points

- `index.html` — Performer homepage; dark theme
- `js/reviews.js` — Customer reviews integration; references https://reviews-api.iamcrazycarla.com/api/reviews and /admin/reviews.html
- `js/main.js` — Main frontend behavior

## Key regression and risk checks

Critical: moderation authorization, review approve/archive/delete, email notifications and submission protections. D1/Worker bindings are not confirmed by frontend alone; test authenticated admin flows before changes.

## Before each requested update

1. Read `PROJECT_CONTEXT.md`, this playbook, and the latest code/commit history.
2. Confirm domain `https://iamcrazycarla.com`, GitHub default branch and Cloudflare project. Do **not** assume the repository automatically publishes to the live website.
3. Identify exact existing implementation and safest edit path; do not reconstruct a current working site from old snippets.
4. List user-requested changes and any dependencies before editing; preserve all unrelated styles and functionality.
5. For edits involving Worker bindings, payments, authentication, content publication or client data, inspect the supporting implementation first and never guess configuration.
6. Test desktop and mobile layout; verify links and core actions; check browser console/network issues where possible.
7. Record changed files, deployment method and actual verification result. Do not call a Git commit a live deployment.
8. Update `PROJECT_CONTEXT.md` for decisions and this file when code layout or testing procedures materially change.

## Deployment handoff (fill from verified Cloudflare settings)

- GitHub repo: `echocraftmusic/IamCrazyCarla-Foundation-v1.4-Contact-Ready`
- Production URL: https://iamcrazycarla.com
- Deployment method: **UNVERIFIED**
- Cloudflare account/project: **UNVERIFIED**
- Production branch: **UNVERIFIED**
- Build/output directory: **UNVERIFIED**
- Worker routes/bindings: **UNVERIFIED (never record secret values)**
- Last independently verified production release: **UNVERIFIED**

## What to provide at the end of any future site task

- Changed files and summary
- Commit hash / PR if written to GitHub
- Build/test results and remaining unknowns
- Deployment status: not deployed / deployed but unverified / verified live
- Updated project documentation when substantive

## Activity log

- **2026-10-22** — Created code-entry-point and maintenance checklist from inspected repository files. Documentation-only; no live deployment performed.
