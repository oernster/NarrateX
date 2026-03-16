# NarrateX Ideas (🧠) — UX flow and UI behaviour (Phase 6)

This designs the user-visible behaviour for **🧠 Ideas** on the top toolbar.

Approved choices:

- 🧠 lives on the main toolbar, tooltip: **Map the book**
- Manual bookmarks remain distinct and keep existing ribbon icon UX
- Indexing progress should be **inline** using the existing status label + progress bar

Repo context:

- Toolbar controls are built in [`MainWindow.__init__()`](voice_reader/ui/main_window.py:57)
- Status and progress widgets already exist: [`lbl_status`](voice_reader/ui/main_window.py:154), [`progress`](voice_reader/ui/main_window.py:160)
- Narration state already updates these via [`apply_state()`](voice_reader/ui/_ui_controller_state.py:19)

Implication: indexing UI must not “fight” with playback progress updates. The design below includes a clean separation so playback remains primary.

---

## 1) Full UX flow: first-time click on 🧠 (unindexed book)

Preconditions:

- A book is loaded (book_id available via [`NarrationService.loaded_book_id()`](voice_reader/application/services/narration_service.py:197)).

Flow:

1. User clicks 🧠.
2. If no book loaded:
   - Show a calm message: `Load a book to map ideas.`
3. If book loaded but no completed index exists:
   - Show a permission dialog:
     - Title: `Map the book`
     - Body:
       - `NarrateX can analyse this book locally and generate idea-based navigation.`
       - `Indexing runs in the background while playback continues.`
       - `This may use CPU and take a while for large books.`
     - Buttons:
       - Primary: `Index this book`
       - Secondary: `Not now`
4. On approval:
   - Start indexing job in background.
   - Inline progress presentation:
     - status label becomes: `Mapping ideas…` (plus stage, if available)
     - progress bar shows 0→100
     - progress label (if used) shows e.g. `Ideas: 42%`
5. On completion:
   - status label becomes: `Idea map ready`
   - progress bar returns to playback ownership immediately (see arbitration below)
   - Ideas dialog opens automatically.

---

## 2) Full UX flow: already-indexed books

1. User clicks 🧠.
2. If completed index exists and is valid:
   - Open Ideas dialog immediately.
   - No permission prompt, no progress.

If index exists but is stale/incompatible:

- Treat as unindexed and show permission prompt (with an added line: `This book changed since it was last mapped.`).

---

## 3) Indexing progress behaviour (inline)

### Progress ownership arbitration (critical)

Because playback already updates the same status/progress widgets via [`apply_state()`](voice_reader/ui/_ui_controller_state.py:19), we need a simple rule:

- Playback updates are always applied.
- Indexing updates are shown **only when they won’t confuse playback**.

Recommended behaviour:

- If playback is idle/paused/stopped:
  - reuse the main progress bar for indexing.
- If playback is active:
  - keep the main progress bar for playback,
  - show indexing progress only in `lbl_status` text (e.g. `Playing… (Ideas 42%)`), or via a small secondary indicator.

This avoids a jarring progress bar that switches meaning mid-play.

### Cancellation

- Add a `Cancel indexing` option inside the Ideas dialog (or a small inline cancel affordance next to 🧠 in a later pass).
- v1 minimal: allow cancellation only by re-clicking 🧠 during indexing → show a small prompt `Indexing in progress. Cancel?`.

---

## 4) Structure of the generated Ideas dialog

Follow the calm, simple pattern of [`BookmarksDialog`](voice_reader/ui/bookmarks_dialog.py:45): modal, scrollable list, clear buttons.

Dialog title: `Ideas`

Sections:

1. Header row:
   - `Ideas` title
   - small subtitle: book title
2. Main body (scrollable):
   - Tree-ish presentation (can be implemented as a list with indentation in v1)
   - Primary hierarchy: `Chapters/Headings` (🗺️ conceptually)
     - children: concepts for that section
   - Secondary group at top or bottom: `Top concepts`
3. Buttons:
   - `Go To` (navigates to selected node’s primary anchor)
   - `Close`
   - Optional: `Reindex` (behind confirmation)

Visual markers (data model supports richer ones later):

- Headings/groups: can later show 🗺️
- Related/network: can later show 🌐
- Manual bookmark references: show the existing ribbon icon when present (not required v1)

---

## 5) Hierarchy/groups in a scrollable UI

Conservative v1 presentation:

- A single list where items are prefixed by indentation:
  - `Chapter 1 …`
    - `Decision fatigue`
    - `Choice architecture`
- `Top concepts` group is a header with its own children.

This avoids building a complex tree widget early.

---

## 6) Wording for key dialogs/buttons/tooltips

🧠 tooltip:

- `Map the book`

Permission prompt:

- Title: `Map the book`
- Body:
  - `NarrateX can analyse this book locally and generate idea-based navigation.`
  - `Indexing runs in the background while playback continues.`
- Buttons: `Index this book` / `Not now`

Indexing status label examples:

- `Mapping ideas… 12%`
- `Mapping ideas… Extracting concepts (42%)`
- `Idea map ready`
- `Idea mapping failed` (plus `See details` in the Ideas dialog)

---

## 7) Future 🔎 disabled-state signalling (no search implemented now)

Design intent:

- 🔎 is conceptually dependent on indexing.

Behaviour:

- Before indexing exists for current book: show 🔎 disabled with an orange border.
- Once a completed index exists: remove orange border and enable the button.
- Clicking disabled 🔎 shows a tooltip: `Search requires an idea map. Click 🧠 to map the book.`

Implementation note:

- The orange-border affordance aligns with existing "locked" styling in [`apply_main_window_theme()`](voice_reader/ui/window_helpers.py:15) which already uses an amber border for locked states.

