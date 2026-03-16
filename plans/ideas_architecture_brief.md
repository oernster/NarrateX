# NarrateX Ideas (🧠) — Architectural brief (Phases 1–2)

This brief extends NarrateX with a second navigation system: **Ideas** (🧠) that generates idea-based navigational anchors for the **currently loaded book**.

Key repo anchors:

- Playback orchestration: [`NarrationService`](voice_reader/application/services/narration_service.py:51)
- Manual bookmarks dialog wiring: [`open_bookmarks_dialog()`](voice_reader/ui/_ui_controller_bookmarks.py:8)
- Existing manual bookmark persistence: [`JSONBookmarkRepository`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:62)
- UI toolbar buttons live in: [`MainWindow`](voice_reader/ui/main_window.py:45)

---

## Phase 1 — Architectural framing and design constraints

### 1) Concise architectural summary

Add a **modular, background indexer** that produces a persisted **Idea Map** for the *current* book. The Idea Map is:

- **Local**: runs fully on the user’s machine.
- **Non-blocking**: runs off the UI thread and must not interfere with playback correctness.
- **Cached**: persisted per book and reloaded on subsequent openings without re-indexing.
- **Subordinate**: indexing is secondary to playback; failures must not destabilize narration.

Implementation principle: keep the Ideas system out of the playback core. The playback engine (threading, queues, audio streamer) stays owned by [`NarrationService`](voice_reader/application/services/narration_service.py:51). Ideas indexing runs as an independent subsystem that consumes **book text snapshots** and produces **navigation anchors**.

### 2) Main subsystem boundaries

**Unchanged / protected**

- Playback engine: [`NarrationService`](voice_reader/application/services/narration_service.py:51) + audio streamer(s)
- Manual bookmark system: UI + application service + repository (keep meaning and UI distinct)

**New**

- Ideas UI surface:
  - 🧠 toolbar button (tooltip: Map the book)
  - Permission dialog (first use per book)
  - Progress UI (0–100% while indexing)
  - Ideas dialog/modal (idea-based navigation list/tree)
- Ideas application service (orchestrator) to:
  - load cached idea index if present
  - request indexing (with permission gate)
  - monitor progress
  - expose “open dialog now” behaviour after completion
- Ideas indexing runtime (background): scheduler + worker(s)
- Ideas persistence: per-book `*.ideas.json` stored next to bookmarks

### 3) Proposed data ownership boundaries

- **Playback state** (current chunk, highlight, queues, TTS caching) remains owned by [`NarrationService`](voice_reader/application/services/narration_service.py:51).
- **Manual bookmarks** remain owned by `BookmarkService` + [`JSONBookmarkRepository`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:62) and are not merged with Ideas.
- **Idea Map** is owned by a new `IdeaIndexRepository` (JSON file per book) and a new `IdeaMapService` (app-layer orchestrator).
- **UI** owns presentation state only (dialogs open/closed, currently selected idea node).

Persisted Ideas location (approved): store alongside bookmarks, e.g. `bookmarks/<book_id>.ideas.json`, where `book_id` comes from [`LocalBookRepository.load()`](voice_reader/infrastructure/books/repository.py:20).

### 4) Major risks

1. **Playback regression via CPU contention**
   - Indexing may compete with TTS synthesis and audio playback.
2. **UI responsiveness**
   - Large books + indexing must not block the Qt thread.
3. **Cache invalidation correctness**
   - Must avoid re-indexing unchanged books; must detect when an index is stale.
4. **Noise / low-signal output**
   - If the idea map is too noisy, users will ignore it.
5. **Packaging fragility**
   - spaCy model availability (notably `en_core_web_sm`) must be treated as optional dependency for Ideas, even if Kokoro already pulls it in (see [`TTSEngineFactory`](voice_reader/application/services/tts_engine_factory.py:23)).

### 5) Recommended implementation sequence (minimize risk to playback)

1. Add UI affordance and wiring only (🧠 button + stub flow) without indexing.
2. Add persistence + “already indexed” detection (load-only path).
3. Add background job framework + progress reporting (no heavy NLP yet; fake progress in tests).
4. Add v1 deterministic indexing algorithm behind the interface.
5. Add Ideas dialog presentation bound to loaded index.
6. Add guardrails (throttling, cancellation, book-switch handling, failure recovery).

---

## Phase 2 — Feature decomposition into modules and responsibilities

### 1) Subsystem list

1. Playback engine (existing)
2. Manual bookmark system (existing)
3. Idea map generation / indexing (new)
4. Persisted metadata storage (new repository)
5. Idea map UI / modal presentation (new dialogs)
6. Progress reporting (new signals/callbacks)
7. Future search enablement hooks (interface boundary only; no search feature now)

### 2) Responsibilities of each subsystem

#### Playback engine (existing)

- Owns real-time narration correctness, state updates, and highlight positions via [`NarrationService.current_position()`](voice_reader/application/services/narration_service.py:202).
- Must remain ignorant of Ideas implementation details.

#### Manual bookmark system (existing)

- Manual anchors only; UI and persistence remain as-is.
- Keep the existing manual bookmark icon semantics (do not re-skin, do not repurpose).

#### Idea map generation / indexing (new)

- Input: snapshot of the current book’s normalized text + lightweight metadata.
- Output: Idea Map consisting of:
  - nodes (concepts / headings / themes)
  - anchors (jump targets)
  - optional relationships (edges) for later search/graph features
- Must be restart-safe and cacheable.

#### Persisted metadata storage (new)

- Read/write per-book `*.ideas.json` adjacent to existing bookmark files.
- Provide:
  - `get_status(book_id)` / `load_index(book_id)`
  - `save_index_atomic(book_id, index_doc)`
  - temp/partial handling during in-progress indexing

#### Idea map UI / modal presentation (new)

- Triggered by 🧠.
- Behaviours:
  - first click per unindexed book → permission prompt
  - during indexing → progress 0–100%
  - once indexed → open idea dialog immediately

#### Progress reporting (new)

- Indexer emits progress events that UI can display.
- Must be thread-safe (Qt main thread applies UI updates).

#### Future search enablement hooks (new boundary)

- Add a minimal “index available” capability flag so that the future 🔎 search can be disabled/enabled without entangling search logic.

### 3) Suggested interfaces between subsystems

Keep interfaces narrow and deterministic:

- `IdeaMapService` (application layer)
  - `has_index(book_id) -> bool`
  - `get_index_status(book_id) -> IndexStatus`
  - `request_index(book_id, text_snapshot, fingerprint, progress_cb) -> JobHandle`
  - `load_index(book_id) -> IdeaMap`

- `IdeaIndexer` (domain service or application service)
  - `build(text, *, progress_cb) -> IdeaMap`

- `IdeaIndexRepository` (domain interface + infrastructure implementation)
  - `load(book_id) -> IdeaIndexDoc | None`
  - `save_atomic(book_id, doc) -> None`
  - `load_status(book_id) -> IndexStatus`

- `IndexingScheduler` (runtime)
  - `submit(job) -> JobHandle`
  - `cancel(job_id) -> None`

Navigation boundary:

- Ideas and chapters share the *shape* of a navigation anchor `(chunk_index, char_offset)` as used by [`ChapterIndexService`](voice_reader/application/services/chapter_index_service.py:1) and manual bookmarks.
- They remain distinct concepts (different dialogs, different icons, different repositories).

### 4) Lifecycle: indexing from 🧠 click to persisted result

1. User clicks 🧠.
2. UI controller checks a cheap cached status: does `bookmarks/<book_id>.ideas.json` exist and validate?
3. If missing/stale → show permission prompt.
4. On approval:
   - create an indexing job with a text snapshot and a fingerprint
   - show progress UI (0–100%)
5. Background indexer runs pipeline stages, sending progress events.
6. On completion:
   - persist final `*.ideas.json` via atomic write
   - update status to completed
   - open Ideas dialog with the generated content

### 5) Lifecycle: reopening a previously indexed book

1. Book is loaded normally via [`UiController.select_book()`](voice_reader/ui/ui_controller.py:208).
2. Ideas subsystem performs a cheap status check for `*.ideas.json` for that `book_id`.
3. If present and valid:
   - clicking 🧠 opens Ideas dialog immediately
   - indexing is not triggered

### 6) Explicit notes on keeping playback isolated from indexing

- No direct calls from indexing into [`NarrationService`](voice_reader/application/services/narration_service.py:51) other than:
  - requesting a *read-only* book id
  - optionally requesting a *snapshot* of the current normalized text
- Indexing progress must not reuse the narration progress bar semantics.
- All indexing failures are contained:
  - errors are surfaced in the Ideas UI only
  - playback continues unaffected
- Indexing uses an execution model that can be throttled and cancelled.

---

## Phase 3+ note (context only)

Anchoring preference (approved): **hybrid** anchors with `char_offset` + `chunk_index`, with room for optional `sentence_id` later.

