# Ravens: Optional Bifröst Three-Tier Memory Adapter

**Date:** 2026-11-19  
**Status:** proposed integration plan, NOT deployed  
**Architecture authority:** [Bifröst canonical three-tier memory specification](https://github.com/hrabanazviking/bifrost-viewer/blob/docs/second-brain-incremental-multimodal-gateway-2026-11-19/docs/roadmaps/SECOND_BRAIN_THREE_TIER_MEMORY_ARCHITECTURE_2026-11-19.md) and [additive modernization plan](https://github.com/hrabanazviking/bifrost-viewer/blob/docs/second-brain-incremental-multimodal-gateway-2026-11-19/docs/roadmaps/SECOND_BRAIN_ADDITIVE_INCREMENTAL_MULTIMODAL_GATEWAY_2026-11-19.md).

## Owner's memory requirement

The Second Brain has **three mutually distinct retention/mutability tiers**:
- **Long-term**: stable and **immutable once committed**. Any correction is a NEW independently archived record with a supersession link. No reinforcement, decay, expiry, consolidation or ordinary write to archived facts.
- **Medium-term**: mutable **current focus domains**, projects, folder categories and importance/association priorities; may link to immutable sources by stable canonical IDs without copying or modifying them.
- **Short-term**: rapidly changing, short-lived working memory for one session/task, automatically expires and purges without being kept or backed up by default. Promoting anything to a longer tier requires an explicit authorized action.

**Uniform whole-brain read-only client access** remains the default for authorized Janitor/SillyTavern characters, with no per-character collection or folder permission tuning. Session buffers are isolated only to prevent dialogue mixups. The Ravens may enhance ranking/association, but can never become an alternate authority over the archived corpus.

## Fit with existing Ravens functionality

Muninn (`muninn/`) already implements Hebbian links, activation logs, memory-strength updates, decay and consolidation in an independent SQLite store. Huginn (`huginn/`) already implements retrieval over local lexical or optional Qdrant-based stores. The separate `hrabanazviking/bifrost` composite bridge already has a documented integration with both.

Bifröst Viewer, however, already owns a primary PostgreSQL+pgvector corpus and its own hybrid retrieval. The optional Raven adapter should **NOT copy the full Second Brain** into new SQLite or Qdrant stores. It should prefer stable Bifröst source IDs, reference-only associations and minimal derived state where a lightweight auxiliary store is justified. Use the existing Bifröst composite bridge where appropriate rather than invent a competing integration.

## Thin optional integration contract

- [ ] **Reference mapping**: establish stable, versioned mapping from canonical Bifröst source/document/visual-lore IDs to Raven memory IDs. Avoid assuming identical integer namespaces; ensure reuse through reload/restore and safe migration.
- [ ] **Medium-term association service**: let trusted Bifröst orchestrator record co-activation among current focus domains and selected evidence IDs via Muninn in its own auxiliary store. Decay/consolidation must touch ONLY auxiliary links and activity; archive content/versions are never changed, deleted, or rewritten.
- [ ] **Read-only recall**: return related source IDs, activation/focus scores, confidence, tier and provenance to Bifröst's Memory Composer. Bifröst/Skry fetch current source evidence through its existing read API. Raven associations do not automatically assert factual relations.
- [ ] **Short-term isolation**: ordinary chat/session scratch state lives in volatile Bifröst-owned short-term memory. Do not persist full temporary dialogue to Muninn/Huginn by default. No implicit `remember`, `activate`, `retrieve(touch=True)`, `decay`, or logging as a side effect of the externally exposed read-only gateway.
- [ ] **Explicit lifecycle**: external client read requests never write to Raven store; separate authorized internal maintenance jobs may update medium associations. Store only safe minimal metadata, no raw personal chat content or secret keys.
- [ ] **Folder and multimodal support**: folder/project category IDs and image/audio/video source IDs may be association endpoints. Multiple copies with one content hash have multiple source-location links but one reusable content embedding/caption. Moving an unchanged file does not generate new Raven memory or model inference.
- [ ] **Optional fallback**: disable the Raven integration cleanly without reducing original Bifröst knowledge accessibility. Keep all Raven public API signatures/standalone behavior backward compatible.

## Three-tier acceptance tests

1. With an immutable Bifröst record, 10,000 Muninn activations or decay calls alter **no bytes** in canonical long-term records; only an allowed auxiliary association state changes.
2. A medium focus folder's importance can rise and fall; the same canonical source remains unchanged and discoverable outside the focus.
3. A short-term dialogue expires and leaves no transcript in either Raven store; no content-bearing persistent logs.
4. A read-only character gateway query returns only source evidence/provenance, and all persistent write attempts are denied.
5. Two characters use uniform long-term/medium access while their session-local short-term contexts remain isolated without per-character source permissions.
6. Moving/copying a file updates current folder provenance and link references without reinserting duplicate content-derived knowledge.
7. A correction appends a new long-term version; the original stays immutable and the Raven reference resolves currentness with provenance.
8. Disconnect Raven auxiliary store or disable module: Bifröst's long-term search and existing interfaces still work. No forced data migration.

## Implementation order

Review the existing `docs/INTEGRATION.md` contract and source first, test against Bifröst Viewer (not just the **different** `hrabanazviking/bifrost` composite bridge), add a minimally privileged opt-in adapter, test volatile/medium/long-term boundaries, and benchmark relevance/overhead before enabling. Private state and credentials remain off GitHub.

This document updates integration requirements only. It does not claim that the adapter or the Bifröst three-tier architecture has shipped.
