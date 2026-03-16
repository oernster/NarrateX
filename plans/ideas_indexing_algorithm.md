# NarrateX Ideas (🧠) — Local indexing algorithm design (Phase 4)

Design goal: generate a **useful, navigable Idea Map** for the *currently loaded book* using local, deterministic NLP where practical.

The v1 UX preference (approved): **conservative hybrid** → headings/chapters provide the primary hierarchy, plus a small **Top Concepts** section.

Repo context:

- Normalized text is produced by [`normalize_text()`](voice_reader/infrastructure/books/parser.py:11) and passed to UI via [`UiController.select_book()`](voice_reader/ui/ui_controller.py:208).
- Chapters are already detected deterministically via [`ChapterIndexService.build_index()`](voice_reader/application/services/chapter_index_service.py:39).
- Chunk mapping logic exists via [`NavigationChunkService.build_chunks()`](voice_reader/application/services/navigation_chunk_service.py:24).

---

## 1) Recommended v1 indexing algorithm (summary)

**Two-layer output**:

1. **Section tree** (high precision): derive sections from chapter/heading detection (and fallback heuristics when headings are absent).
2. **Concept layer** (controlled recall): extract candidate concepts (noun phrases, entities) per section; score + dedupe; emit:
   - a **Top Concepts** list (global, small)
   - per-section concepts (small)

Anchors for all nodes are **hybrid**: `char_offset` + `chunk_index` + optional `sentence_id` (null in v1 unless we add sentence tracking later).

---

## 2) Pipeline stages (in order)

### Stage 0 — Inputs, fingerprinting, and guardrails

Inputs:

- `book_id`, `title`
- `normalized_text` (string)
- optionally `language` (default `en` in config)

Pre-compute:

- `text_fingerprint_sha256 = sha256(normalized_text)`
- `text_length`

Guardrails:

- Hard cap on processed text length for concept extraction (e.g. first N chars, or sample per section) to keep runtime bounded for very large books.
- Maintain strict time/CPU etiquette: indexing must be cancelable and should yield progress frequently.

### Stage 1 — Sectioning (headings-first)

Primary approach:

- Reuse chapter heading detection logic from [`ChapterIndexService`](voice_reader/application/services/chapter_index_service.py:24).
- Produce section boundaries as `(start_char, end_char)` plus a `label`.

Fallback (when no “Chapter …” matches):

- Treat double newlines as paragraph separators and build coarse sections by:
  - detecting all-caps lines, or
  - detecting short lines surrounded by blank lines (heading-like), or
  - falling back to fixed-size windows (e.g. every 5–10k chars)

Output:

- A root node: `Book`
- Child section nodes: `Chapter/Heading`

### Stage 2 — Sentence segmentation (lightweight)

Goal: create sentence boundaries primarily to:

- locate a concept’s “first mention” precisely
- capture a small `snippet` for UI

Preferred v1 method:

- Use `pysbd` (already in [`requirements.txt`](requirements.txt:115)) for fast sentence boundary detection.

Alternative (if already loaded for other reasons):

- spaCy sentencizer only (no parser/NER required) to reduce overhead.

Output:

- For each section: a list of sentences with `(start_char, end_char, text)`

Note: `sentence_id` remains `null` in persisted output unless we introduce a stable sentence-id strategy (see deferrals).

### Stage 3 — Candidate concept extraction (deterministic, local)

Extract concepts *per section*, with two extraction paths:

**Path A (preferred when available): spaCy noun chunks + NER**

- Load `en_core_web_sm` when present.
- Extract:
  - noun chunks (lemmatized head + modifiers)
  - named entities (PERSON/ORG/GPE/etc.)

**Path B (fallback): regex + heuristics**

- Extract capitalized multiword phrases and high-frequency nouns using simple tokenization.

Normalization rules (both paths):

- lowercase for comparison (preserve original-cased display label separately)
- strip punctuation
- collapse whitespace
- drop stopwords-only phrases
- limit phrase length (e.g. 1–5 tokens)

### Stage 4 — Concept scoring and filtering (keep it useful)

The main purpose is to avoid noise.

Scoring signals (simple and explainable):

- `tf`: term frequency within section
- `df`: section frequency across book sections (concepts appearing across multiple sections are often useful)
- `position_bonus`: earlier appearance in a section → slightly higher
- `spread_bonus`: appears in multiple sections → higher global importance

Example score (conceptual):

- `score = w1*tf_norm + w2*log(1+df) + w3*spread - w4*stopword_penalty`

Filtering rules:

- Drop concepts below a minimum score threshold.
- Drop concepts that are too generic (stopword lists + a curated “book noise” list like `chapter`, `figure`, `table`, `copyright`).
- Deduplicate by lemma/root form.
- Enforce budgets:
  - `Top Concepts`: max ~15–30
  - Per section: max ~5–12

### Stage 5 — Anchor selection (jump targets)

For each retained concept (and each section heading), choose:

- a **primary anchor**: typically the first sentence occurrence of the concept in that section
- optional additional anchors: a few high-signal mentions (cap small)

Anchor resolution:

- `char_offset`: exact start char of the matched span
- `chunk_index`: resolve from `char_offset` by building navigation chunks via [`NavigationChunkService.build_chunks()`](voice_reader/application/services/navigation_chunk_service.py:24) and mapping offsets similarly to [`ChapterIndexService.build_index()`](voice_reader/application/services/chapter_index_service.py:64)

This intentionally matches existing navigation semantics (manual bookmarks and chapters already use `chunk_index`).

### Stage 6 — Grouping & hierarchy assembly

Primary hierarchy:

- Root
  - Sections (chapters/headings)
    - Concepts within each section

Secondary global area:

- Root
  - Top Concepts (virtual group node)
    - Concepts (global)

Optional (v1 minimal) edges:

- Build weak `related` edges by co-occurrence within the same section/sentence window.
- Cap total edges aggressively (avoid graph explosion).

### Stage 7 — Persisted output

- Emit the document described in [`plans/ideas_data_model.md`](plans/ideas_data_model.md:1)
- Write atomically (same pattern as [`JSONBookmarkRepository._write_doc()`](voice_reader/infrastructure/bookmarks/json_bookmark_repository.py:117))

---

## 3) Computational cost expectations

Costs depend on chosen extraction path:

- Sectioning: O(n) over text with regex scanning; cheap.
- Sentence segmentation:
  - `pysbd`: typically fast; linear.
- Concept extraction:
  - spaCy `en_core_web_sm` over full book can be heavy.
  - v1 should **process per-section samples** or cap total processed characters to keep it “background-safe”.

Practical approach:

- Always run full sectioning.
- Run concept extraction on a bounded subset:
  - e.g. first M sentences per section, or up to X chars per section, or a global cap.

---

## 4) Likely failure modes

1. **No headings detected**
   - Fallback sectioning becomes coarse; concept grouping still works.
2. **spaCy model missing**
   - Must fall back to heuristic extraction (still produce something).
3. **Noisy OCR PDFs**
   - Sentence segmentation and concept extraction degrade; rely more on Top Concepts and conservative filters.
4. **Fiction content**
   - Concepts skew to characters/places; hierarchy may be less semantically “useful”.
5. **Concept spam**
   - Over-extraction leads to clutter; mitigated via strict budgets + stoplists + score thresholds.

---

## 5) How to keep output useful, not noisy

Primary levers (v1):

- Headings-first structure (user always sees a familiar spine)
- Strict per-section and global budgets
- Aggressive stoplists and generic-term filtering
- Prefer multiword noun phrases over single tokens
- Prefer concepts with multi-section spread for Top Concepts
- Include `snippet` to provide immediate context and reduce “mystery labels”

---

## 6) Fiction vs nonfiction adaptation (lightweight)

Heuristic classification (no heavy ML):

- Nonfiction hints: frequent headings, presence of `chapter`, many noun phrases, lower dialog ratio.
- Fiction hints: high dialog punctuation ratio, many PERSON entities, lower heading density.

Behaviour changes:

- Nonfiction: enable more noun-phrase concepts, allow small co-occurrence edges.
- Fiction: reduce emphasis on abstract noun phrases; prefer:
  - chapter/heading navigation
  - recurring named entities (characters/places) but cap strongly
  - optionally label Top Concepts as “Key names” instead of “Top concepts” (UX decision; can be deferred)

---

## 7) What can be deferred to later versions

- Stable `sentence_id` scheme (persisting sentence boundaries and ids)
- Rich relationship graphs (🌐) beyond minimal `related` edges
- Topic modeling / clustering beyond simple spread-based grouping
- Cross-book indexing (explicitly out of scope)
- Search (🔎) implementation; only the dependency hook should exist later

