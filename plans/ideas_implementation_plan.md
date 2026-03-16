# NarrateX Ideas (🧠) — Phased implementation plan (Phase 8)

Constraints honored:

- Playback stability first (do not risk [`NarrationService`](voice_reader/application/services/narration_service.py:51))
- Deliver in small vertical slices
- No search feature yet; only prepare the dependency hook and disabled-state UX
- No library-management features

---

## Phase 0 — Add UI affordances (🧠 + disabled 🔎) with no backend

**Goal**: introduce visible, testable UI entry points without affecting playback.

**Changes**

- Add 🧠 button (tooltip `Map the book`) to [`MainWindow`](voice_reader/ui/main_window.py:57)
- Add 🔎 button (disabled) to the same toolbar row
- Add new signals on `MainWindow`:
  - `ideas_clicked`
  - `search_clicked` (wired but no behaviour besides tooltip)
- Wire signals in [`UiController._connect_signals()`](voice_reader/ui/ui_controller.py:141)
- Add handler stub `UiController.open_ideas_dialog()` that shows a calm message for now

**Validation**

- Manual bookmarks still work unchanged ([`BookmarksDialog`](voice_reader/ui/bookmarks_dialog.py:45))
- Playback unaffected
- UI smoke test: window contains buttons

**Rollback risk**: low (UI-only)

---

## Phase 1 — Ideas persistence + index status detection (load-only)

**Goal**: enable “already indexed → open immediately” behaviour (even if dialog is basic).

**Changes**

- Add `IdeaIndexRepository` protocol
- Add `JSONIdeaIndexRepository` that reads/writes `bookmarks/<book_id>.ideas.json` using atomic replace pattern from [`JSONBookmarkRepository._write_doc()`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:117)
- Add minimal `IdeaMapService.has_index(book_id)` and `load_index(book_id)`
- Wire into app composition in [`main()`](app.py:180) (pass service into controller)

**Validation**

- Unit tests for repo tolerant reads + atomic writes (mirror existing bookmark repo tests)
- Clicking 🧠 with no index shows permission stub (next phase)
- Clicking 🧠 with a fixture index opens a simple dialog listing nodes

**Rollback risk**: low (new modules + wiring)

---

## Phase 2 — Ideas dialog (read-only) + navigation actions

**Goal**: allow browsing and jumping to idea anchors once index exists.

**Changes**

- Add [`IdeasDialog`](voice_reader/ui/ideas_dialog.py:1) patterned after [`BookmarksDialog`](voice_reader/ui/bookmarks_dialog.py:45)
- Add controller helper `voice_reader/ui/_ui_controller_ideas.py`:
  - open dialog
  - list nodes
  - go-to selected node via `NarrationService.prepare(... start_playback_index=...)` similar to bookmark go-to in [`open_bookmarks_dialog()`](voice_reader/ui/_ui_controller_bookmarks.py:8)

**Validation**

- UI test: opening dialog is non-blocking modal
- Integration test: go-to triggers `prepare` with node anchor `chunk_index`

**Rollback risk**: low-medium (touches controller wiring)

---

## Phase 3 — Background indexing manager (process-based) with fake indexer

**Goal**: implement safe plumbing for asynchronous indexing with progress, without committing to NLP complexity.

**Changes**

- Add `IdeaIndexingManager` that spawns worker process and streams progress events
- Add worker entrypoint module (minimal)
- Add indexing state machine + job handle
- UI permission prompt on first click when no index
- Progress reporting:
  - Inline status updates (and optionally, only use progress bar when playback idle)
  - Implement a simple arbitration flag so narration updates in [`apply_state()`](voice_reader/ui/_ui_controller_state.py:19) remain primary

**Validation**

- Unit tests: manager emits progress and completion
- Manual test: playback can run while indexing (no UI freeze)

**Rollback risk**: medium (adds multiprocessing plumbing)

---

## Phase 4 — Real v1 local indexing algorithm

**Goal**: replace fake indexer with the v1 pipeline described in [`plans/ideas_indexing_algorithm.md`](plans/ideas_indexing_algorithm.md:1).

**Changes**

- Implement sectioning + Top Concepts pipeline with strict budgets
- Use `pysbd` for sentence segmentation (already in [`requirements.txt`](requirements.txt:115))
- Use spaCy when available; fallback heuristics when not
- Use `NavigationChunkService` mapping pattern to produce `chunk_index` anchors

**Validation**

- Deterministic unit tests on a short fixture text
- Golden-file style tests for schema validity

**Rollback risk**: medium (CPU cost risk; mitigated by process isolation and caps)

---

## Phase 5 — Caching, invalidation, and resilience polish

**Goal**: ensure restart-safe and “no reindex on reload” is correct.

**Changes**

- Implement fingerprinting checks (`text_fingerprint_sha256`)
- Add schema/version invalidation logic
- Handle book switch mid-index:
  - cancel running job by default
- Handle app exit mid-index:
  - request cancel; terminate if needed

**Validation**

- Tests for invalidation rules
- Manual scenario tests: switch books mid-index; restart app

**Rollback risk**: low-medium

---

## Phase 6 — 🔎 disabled-state signalling hook (no search)

**Goal**: show dependency UX without implementing search.

**Changes**

- Show 🔎 disabled until `IdeaMapService.has_index(book_id)` is true
- Add orange border style consistent with existing amber “locked” cue in [`apply_main_window_theme()`](voice_reader/ui/window_helpers.py:15)
- Tooltip for disabled state: `Search requires an idea map. Click 🧠 to map the book.`

**Validation**

- UI state toggles when index appears

**Rollback risk**: low

