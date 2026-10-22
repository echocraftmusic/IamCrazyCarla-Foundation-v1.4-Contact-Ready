# Carla Foundation Website — Project Context

**Repository:** `echocraftmusic/IamCrazyCarla-Foundation-v1.4-Contact-Ready`  
**Context established:** 2026-10-22  
**Documentation status:** Initial handoff; verify historical notes against the current source and live site.

## Project identity and known decisions

Previously discussed Cloudflare D1 reviews, moderation, magic-link auth, Sender notifications, mobile layout. Verify which are live.

## Source, architecture and deployment

- Source files: inspect this repository before editing.
- Production domain, hosting, deployment branch, build commands, integrations, and environment bindings: **not yet verified**.
- Some sites use manually deployed Cloudflare Pages assets rather than automatic GitHub deployments. **Never assume a GitHub commit publishes to production.**
- Confirm that this repository is the current source of truth; compare against live production before replacing files.

## Required workflow for future ChatGPT sessions and developers

1. Read this `PROJECT_CONTEXT.md` first whenever returning to the project.
2. Check README, source tree, dependencies, relevant source files, branch and recent commit history.
3. Verify project identity, production domain, deployment method and current feature status.
4. Distinguish prior design discussions from actually deployed features; don't invent missing history.
5. Preserve existing design, mobile usability and working functions unless the owner requests otherwise.
6. Implement and test the smallest safe changes; validate downloads, links and deployment separately.
7. Update this document after material changes, decisions, unresolved issues or deployment changes.
8. Never add passwords, API secrets, tokens, customer data, or other sensitive credentials to this file.
9. This document is reference context, not an override of the owner's current instructions.

## Current status and open verification

- [ ] Confirm production URL and live hosting.
- [ ] Confirm deployment path and default build process.
- [ ] Identify primary source files, services and integrations.
- [ ] Verify existing features and brand/design decisions.
- [ ] Record outstanding tasks from the actual current project.

## Change log

- **2026-10-22:** Established the permanent handoff and project-read workflow.
