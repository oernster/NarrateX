# NarrateX Ideas (🧠) — Data model design (Phase 3)

This proposes the **persisted schema** and **in-memory model** for the Ideas feature, designed to:

- keep manual bookmarks separate (existing ribbon icon semantics remain unchanged)
- persist an idea index per book
- support jump-to-position navigation using existing anchor primitives
- allow richer semantic markers later (🗺️ 🌐) without forcing v1 UI complexity

Repo constraints and existing anchor precedent:

- Manual bookmark anchor fields: [`JSONBookmarkRepository._bookmark_to_dict()`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:135)
- Chapter anchor fields: [`ChapterIndexService.build_index()`](voice_reader/application/services/chapter_index_service.py:39)
- Stable `book_id` used for per-book persistence: [`LocalBookRepository.load()`](voice_reader/infrastructure/books/repository.py:20)

Approved anchoring direction: **hybrid** `char_offset` + `chunk_index`, with **optional** `sentence_id` now.

---

## 1) Proposed persisted schema (`bookmarks/<book_id>.ideas.json`)

### Top-level document

```json
{
  "schema_version": 1,
  "indexer": {
    "name": "narratex-ideas",
    "version": "1",
    "params": {
      "language": "en",
      "max_nodes": 150
    }
  },
  "book": {
    "book_id": "<16-hex>",
    "title": "<string>",
    "source_hint": "<optional path/name>",
    "text_fingerprint_sha256": "<sha256 of normalized_text>",
    "text_length": 123456
  },
  "status": {
    "state": "completed",
    "created_at": "2026-03-15T23:00:00Z",
    "completed_at": "2026-03-15T23:00:30Z",
    "error": null
  },
  "anchors": [
    {
      "anchor_id": "a1",
      "char_offset": 1024,
      "chunk_index": 12,
      "sentence_id": null,
      "snippet": "...short nearby text..."
    }
  ],
  "nodes": [
    {
      "node_id": "n1",
      "kind": "concept",
      "label": "Decision fatigue",
      "score": 0.83,
      "parent_id": null,
      "group_id": "g1",
      "primary_anchor_id": "a1",
      "anchor_ids": ["a1"],
      "tags": ["keyword"],
      "manual_bookmark_refs": []
    }
  ],
  "groups": [
    {
      "group_id": "g1",
      "label": "Self-control and choices",
      "kind": "cluster"
    }
  ],
  "edges": [
    {
      "src": "n1",
      "dst": "n2",
      "type": "related",
      "weight": 0.42
    }
  ]
}
```

### Field notes

- `schema_version`: allows safe future migrations.
- `indexer`: captures enough configuration to interpret results and decide invalidation.
- `book.text_fingerprint_sha256`: the primary “unchanged book” check (see invalidation rules below).
- `status.state`: one of `not_started | queued | indexing | completed | failed | cancelled`.
  - Persisting non-completed states is optional; if we do persist them, they must never block playback.

### Anchor schema

Anchors are **navigation targets**. They are intentionally similar in spirit to manual bookmarks and chapters, but belong to Ideas.

- `char_offset`: used for text highlighting and to resolve a nearby chunk if needed.
- `chunk_index`: used for immediate “Go To” semantics that align with existing navigation flows.
- `sentence_id` (optional): reserved for later sentence-aligned UX and more precise search results.
- `snippet`: tiny UI affordance; keeps the Ideas dialog readable.

### Node schema

Nodes are the “Ideas” the user navigates.

- `kind`: `concept | heading | theme | entity` (v1 may only emit `concept` + `heading`).
- `parent_id`: supports hierarchy (tree in modal).
- `group_id`: supports grouped presentation (🗺️ map/group structure).
- `manual_bookmark_refs` (optional): allows the Ideas dialog to *reference* user ribbon bookmarks when useful, without merging systems.
  - Values should be manual bookmark IDs from existing bookmark files, not copies.

### Edges schema

Edges are optional for v1, but included to avoid blocking future graph-aware search.

- `type`: `related | broader | narrower | cooccurs` (keep minimal).
- `weight`: 0–1.

---

## 2) Proposed in-memory model

Recommend plain dataclasses (mirrors current style across entities and services):

- `IdeaMapIndexDoc` (loaded from JSON)
- `IdeaAnchor`
- `IdeaNode`
- `IdeaGroup`
- `IdeaEdge`

Additionally, create an in-memory convenience view:

- `IdeaMap`
  - `nodes_by_id`
  - `children_by_parent_id`
  - `anchors_by_id`
  - `groups_by_id`

This keeps UI rendering fast and deterministic.

---

## 3) Anchoring recommendation: hybrid

### Recommendation

Use **hybrid** anchoring for v1:

- persist both `char_offset` and `chunk_index`
- include `sentence_id` now as optional/null

### Why hybrid fits this repo

- Existing navigation already operates in `chunk_index` terms (chapters and manual bookmarks jump via chunk index).
- Existing UI highlight and chapter tracking are `char_offset` driven (see [`apply_state()`](voice_reader/ui/_ui_controller_state.py:19)).
- Hybrid allows resilient behaviour if chunking changes slightly: fall back to `char_offset` to re-resolve a chunk, or to highlight nearby text.

---

## 4) Indexing status, versioning, invalidation rules

### Status

Persist `status.state`:

- `completed`: safe to open Ideas dialog immediately.
- `failed`: show calm error + offer to retry.
- `indexing/queued/cancelled`: mainly runtime state; may be persisted for crash recovery but should not be required in v1.

### Versioning

Invalidation triggers (in priority order):

1. `schema_version` differs → treat index as incompatible; require reindex.
2. `indexer.version` differs → either reindex or load-with-warning; recommend reindex for major version change only.
3. `book.text_fingerprint_sha256` differs from current computed fingerprint → require reindex.

### Avoid reindexing unchanged books

- Use `book_id` to locate the index file (`bookmarks/<book_id>.ideas.json`).
- Validate freshness via `text_fingerprint_sha256`.
  - For best UX, compute fingerprint lazily or in a low-priority background step (so opening the book stays snappy).

---

## 5) Persistence format / IO safety

Follow the reliability pattern in [`JSONBookmarkRepository._write_doc()`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:117):

- write to temp file
- atomic replace
- tolerant reads (treat invalid/missing as “no index”)

