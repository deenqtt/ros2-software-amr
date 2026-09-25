# Architecture decision records

One file per decision, named `NNNN-short-title.md`, numbered sequentially. A decision stays in this folder once written — if it is later reversed, add a new record that supersedes it rather than editing the old one.

## Format

```markdown
# NNNN — Title

**Date:** YYYY-MM-DD
**Status:** proposed | accepted | superseded by NNNN

## Context
What forced a decision. Cite code, measurements, or constraints.

## Decision
What was chosen.

## Consequences
What this makes easy, what it makes hard, what it rules out.

## Alternatives considered
What else was evaluated, and why it lost.
```

## Records

*(none yet)*

Decisions identified as needing a record, from [`../WEB_UI_REDESIGN_AUDIT.md`](../WEB_UI_REDESIGN_AUDIT.md):

- `0001-stay-on-vue-vite.md` — frontend framework: keep Vue 3 + Vite rather than migrating to React or Next.js
- `0002-multi-robot-topology.md` — one rosbridge per robot vs. one bridge with namespaced topics
- `0003-station-identity-model.md` — stations keyed by stable id rather than display name
