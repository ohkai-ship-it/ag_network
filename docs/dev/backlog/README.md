# Backlog (persistent)

This folder contains the **canonical product/engineering backlog** for `agnetwork`.

- The single source of truth list is: `BACKLOG_INDEX.md`
- Each work item has its own file in `items/`
- Create new items using `templates/BACKLOG_ITEM_TEMPLATE.md`

## Relationship to review docs

- `docs/dev/reviews/FINDINGS_BACKLOG.md` is a **triage queue** for findings coming out of code/CLI reviews.
- Only items that are accepted into planned work should become `BI-XXXX` backlog items here.

## Conventions

- Backlog items are named: `BI-0001-short-slug.md`
- Keep PRs small; split one backlog item into multiple PRs if needed.
