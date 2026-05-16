# Periodic Review Plan

This document leaves the Level 3 learning path prepared as a supervised
future workflow. It is intentionally not automated in the live system.

## What exists now

- `user_context_memory`
  - supports live personalization with a short functional memory per scope
  - does not store identity or full transcripts
- `conversation_curation`
  - stores selected valuable turns for later human review
  - keeps review labels and candidate targets without promoting them automatically

## What Level 3 could do later

1. Review `conversation_curation` entries in periodic batches.
2. Mark entries as:
   - `util`
   - `neutral`
   - `revisar`
3. Optionally promote reviewed entries to:
   - anchor examples
   - prompt revisions
   - rule proposals
4. Validate changes before updating production assets.

## Why it is not automatic

- To avoid uncontrolled drift in prompts, anchors or rules.
- To keep human supervision over sensitive socioemotional support behavior.
- To prevent the system from learning directly from noisy or private data.

## Suggested future review cadence

- Weekly or biweekly review of new curated entries.
- Manual export of candidate records grouped by:
  - detected category
  - detected intent
  - generation source
  - review status

## Suggested future outputs

- curated anchor candidates for classical or semantic classifiers
- prompt improvement notes for `llm_gateway`
- rule candidates for routers or decision support
- exclusion notes for low quality or unsafe generations
