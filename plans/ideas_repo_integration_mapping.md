# NarrateX Ideas (🧠) — Integration mapping to current repo (Phase 7)

This maps the Ideas/indexing feature family onto the actual NarrateX repository architecture with a conservative integration plan.

Primary repo anchors:

- Entry wiring: [`main()`](app.py:180)
- UI boundary: [`MainWindow`](voice_reader/ui/main_window.py:45) + [`UiController`](voice_reader/ui/ui_controller.py:45)
- Playback engine: [`NarrationService`](voice_reader/application/services/narration_service.py:51)
- Existing navigation indexing (chapters): [`ChapterIndexService`](voice_reader/application/services/chapter_index_service.py:24)
- Existing stable “chunk mapping without playback”: [`NavigationChunkService`](voice_reader/application/services/navigation_chunk_service.py:19)
- Manual bookmarks:
  - UI wiring: [`open_bookmarks_dialog()`](voice_reader/ui/_ui_controller_bookmarks.py:8)
  - persistence: [`JSONBookmarkRepository`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:62)

---

## 1) Repo-specific architectural mapping

### Where Ideas should live by layer

UI layer (`voice_reader/ui`):

- Add a new toolbar button in [`MainWindow.__init__()`](voice_reader/ui/main_window.py:57):
  - 🧠 Ideas (tooltip `Map the book`)
  - future 🔎 search button (disabled until index exists; not implementing search)
- Add controller helper module `voice_reader/ui/_ui_controller_ideas.py` (mirrors bookmark/chapter helpers).
- Add an `IdeasDialog` similar to [`BookmarksDialog`](voice_reader/ui/bookmarks_dialog.py:45).

Application layer (`voice_reader/application/services`):

- Add `IdeaMapService` orchestrator:
  - checks cached index availability
  - kicks off background indexing
  - loads parsed IdeaMap for UI
- Add `IdeaIndexingManager` (process-based) for job submission/cancellation/progress.

Domain layer (`voice_reader/domain`):

- Add entities/value objects for idea nodes/anchors (dataclasses, similar style to [`Book`](voice_reader/domain/entities/book.py:8)).
- Add protocol interface `IdeaIndexRepository` (mirrors `BookmarkRepository`).
- Add pure services for scoring/deduping (kept independent of IO).

Infrastructure layer (`voice_reader/infrastructure`):

- Add JSON repository implementation `JSONIdeaIndexRepository` located near bookmarks:
  - writes `bookmarks/<book_id>.ideas.json`
  - uses atomic write pattern from [`JSONBookmarkRepository._write_doc()`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:117)

---

## 2) Existing modules that should remain untouched (if possible)

- Playback engine core loop in [`NarrationService._run()`](voice_reader/application/services/narration_service.py:146) and audio streamer modules.
- Manual bookmarks UI and persistence:
  - [`BookmarksDialog`](voice_reader/ui/bookmarks_dialog.py:45)
  - [`open_bookmarks_dialog()`](voice_reader/ui/_ui_controller_bookmarks.py:8)
  - [`JSONBookmarkRepository`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:62)

Rationale: these are core to the “do one thing well” proposition; ideas must remain modular and non-invasive.

---

## 3) Where the new code should live

Proposed new modules (conservative, consistent naming):

- UI:
  - `voice_reader/ui/_ui_controller_ideas.py`
  - `voice_reader/ui/ideas_dialog.py`

- Application:
  - `voice_reader/application/services/idea_map_service.py`
  - `voice_reader/application/services/idea_indexing_manager.py`

- Domain:
  - `voice_reader/domain/entities/idea_node.py`
  - `voice_reader/domain/entities/idea_anchor.py`
  - `voice_reader/domain/interfaces/idea_index_repository.py`
  - `voice_reader/domain/services/idea_indexer.py` (pure-ish; may use spaCy but called from worker)

- Infrastructure:
  - `voice_reader/infrastructure/ideas/json_idea_index_repository.py`
  - `voice_reader/infrastructure/ideas/index_worker.py` (process entrypoint)

---

## 4) Refactors needed first?

Recommend **no large refactors**.

One small preparatory extraction may be valuable:

- Introduce a UI-level “secondary status message” mechanism (or a simple arbitration rule) so indexing status does not clash with playback updates performed in [`apply_state()`](voice_reader/ui/_ui_controller_state.py:19).

However, this can be done incrementally in the same phase that introduces 🧠.

---

## 5) Minimal-risk integration plan

1. UI-only: add 🧠 button + disabled 🔎 button (no indexing yet).
2. Add `IdeaIndexRepository` + JSON persistence + “index exists” check.
3. Add process-based indexing manager and worker plumbing (with fake algorithm initially).
4. Wire controller action to:
   - permission prompt
   - start indexing
   - progress reporting
5. Add Ideas dialog that loads and displays persisted index.
6. Replace fake indexer with v1 local algorithm (bounded text processing).

---

## 6) Open questions caused by the current code structure

1. `book_id` stability: it’s derived from `(title + normalized[:2000])` in [`LocalBookRepository.load()`](voice_reader/infrastructure/books/repository.py:20). If the same file’s title/stem changes, the id changes.
   - Mitigation: we also persist `text_fingerprint_sha256` and can treat that as canonical for invalidation.
2. Progress UI arbitration: existing status/progress is narration-owned via [`apply_state()`](voice_reader/ui/_ui_controller_state.py:19).
   - Need a clear rule so indexing doesn’t confuse playback.
3. Packaging: spaCy model availability is assumed for Kokoro packaging (see PyInstaller collects in [`buildexe.py`](buildexe.py:192)), but Ideas should still have a graceful fallback.

