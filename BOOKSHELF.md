# NarrateX Bookshelf: software requirements specification

Status: **BASELINED 1.0, 2026-09-19.** Every question in appendix B is ruled and the
genre vocabulary in appendix D is closed. Changes from here arrive as numbered amendments
carrying a reason, never as silent edits. Amendments A1 to A3 are recorded in appendix E;
each came from building against the real library rather than from rereading the
document.

## 1. Introduction

### 1.1 Purpose

NarrateX today opens exactly one book, chosen through a file dialog, remembered as a
single `last_book_path` in `preferences.json`. A reader holding a library of a few
thousand books cannot see what they own, cannot tell what they have already listened
to and cannot find a book without remembering where on disk it sits.

The Bookshelf is the launch surface that answers those three questions. It presents the
books already on disk as artwork, lets the reader narrow them by subject, then hands the
chosen one to the reading system that already exists.

### 1.2 Intended audience

The implementer of the feature; also the owner ruling on the open questions in appendix B.

### 1.3 Scope

In scope:

- A reader-chosen folder tree, scanned for the book formats NarrateX already opens
- A grid view of cover artwork and a list view of the same books
- Cover artwork, title and author read out of the files and their Calibre sidecars
- Subject tags read from the same sources, normalised onto a curated catalogue
- A filter over that catalogue, plus a text search
- Reading progress shown per book, read from the state NarrateX already keeps
- Opening a book from the shelf into the existing reader

Out of scope, explicitly:

- **Audio files.** MP3, M4B and any other recorded audio. NarrateX synthesises speech
  from a structured document; a recording has no document model, no headings, no index
  to exclude and no alignment, so none of the reading system applies to it.
- **A managed library directory.** Books are read where they sit. NarrateX never copies,
  moves, renames or deletes a book file. This extends the existing rule that removing a
  book forgets what NarrateX derived and never touches disk.
- **External metadata lookup.** No call to Open Library, Google Books or any other
  service. The README states that nothing read leaves the device and that there is no
  network call in the reading path; a metadata fetch would break both claims.
- **Editing book files.** No writing of tags, covers or metadata back into a book, its
  `.opf` or any sidecar.
- **DRM.** Unchanged from the existing product position.
- **Series, ratings, reading lists, notes, loans, collections.**
- **Import.** There is no import step; there is a folder and a rescan.

### 1.4 Definitions

| Term | Meaning, fixed for this document |
|---|---|
| Shelf | The whole feature: the scanned collection plus the two views over it |
| Shelf root | A folder the reader nominates; the scan walks it recursively |
| Entry | One row of the shelf index: one book file on disk |
| Work | One book as a reader thinks of it; one or more entries of differing format |
| Tile | A work drawn in the grid view: cover, title, author, progress |
| Shelf key | The cheap identity of an entry: absolute path, byte size, modified time |
| Book id | The existing narration identity: SHA-256 over the book's normalised text |
| Sidecar | A file beside a book that describes it: Calibre's `metadata.opf`, `cover.jpg` |
| Subject | A raw tag string as found in a file or sidecar, before normalisation |
| Genre | A name in the curated catalogue that subjects are mapped onto |
| Rescan | Re-walking a shelf root and reconciling the index with what is on disk |

`shall` is binding. `will` describes the environment. `should` never appears in a
requirement body.

### 1.5 References

- `voice_reader/application/services/narration/cache_key.py`: book id derivation
- `voice_reader/infrastructure/books/cover_extractor.py`: existing cover strategy
- `voice_reader/infrastructure/books/converter.py`: Kindle conversion via Calibre
- `voice_reader/ui/_ui_controller_book_removal.py`: the never-touch-disk rule
- Stellody `stellody/domain/genres.py`: the curated two-level catalogue with aliases
- Stellody `stellody/domain/text.py`: normalisation and comparison keys
- Stellody `stellody/infrastructure/store.py` and `artwork.py`: catalogue and art cache
- ISO/IEC/IEEE 29148:2018; EARS (Mavin et al., RE'09)

## 2. Overall description

### 2.1 Product perspective

An addition to an existing PySide6 application built on
`UI -> Application -> Domain <- Infrastructure`, enforced by structural tests. The
shelf introduces no new layer. It introduces one new domain concept (the catalogue of
works), one new application service (scanning and querying it), new infrastructure
(metadata and cover readers, the index store, the thumbnail cache) and a new UI surface.

### 2.2 User classes

One class: the reader, who owns the machine and the files. There is no second role, no
administrator and no sharing.

### 2.3 Operating environment

Windows, macOS and Linux desktop, as the existing product. The reference library for
every measurement in this document is `H:\Books` on the owner's Windows machine.

**Measured on 2026-09-19**, by walking that tree:

| Measurement | Value |
|---|---|
| Book files NarrateX can open | 2818 |
| `.azw3` | 1423 |
| `.mobi` | 1354 |
| `.pdf` | 23 |
| `.epub` | 11 |
| Directories holding at least one book | 1328 |
| Maximum depth below the root | 3 |
| Directories holding exactly one book | 1312 |
| Book files with a sibling `metadata.opf` | 652 |
| Book files with a sibling cover image | 541 |
| `.opf` files carrying at least one `dc:subject` | 381 of 652 |

Two directories dominate the rest: `H:\Books\uncatalogued` holds 718 `.mobi` files and
`H:\Books\FIXED\uncatalogued` holds 716 `.azw3` files with the same stems, so roughly
717 works are present twice in two formats with no sidecar metadata at all.

Further measurements that decide the design:

| Measurement | Value |
|---|---|
| One Calibre `ebook-convert` of a 275 KB `.mobi` | 2.3 seconds |
| Cover read directly from a `.mobi` EXTH header | about 1.3 ms per file |
| Cover read directly from an `.azw3` EXTH header | about 7 ms per file |
| Author read directly from EXTH, 120-file sample | 120 of 120 |

A scan that spawns Calibre once per book costs roughly 54 minutes over this library.

**The whole-library direct read, measured on 2026-09-19.** Every `.mobi`, `.azw3` and
`.azw` file in the reference library was opened and its header read, extracting the
cover, the author and the subjects in one pass:

| Measurement | Value |
|---|---|
| Kindle-format files read | 2784 |
| Wall-clock for the whole pass | 5.0 seconds |
| Covers recovered, `.mobi` | 1121 of 1354 |
| Covers recovered, `.azw3` | 1170 of 1423 |
| Covers recovered, `.azw` | 5 of 7 |
| Covers recovered, all Kindle formats | 2296 of 2784 |
| Books stating at least one subject | 1533 of 2784 |
| Distinct subject strings after splitting | 1025 |
| Thumbnail encode at 320x480, per cover | 3.3 ms |
| Thumbnail encode projected over 2296 covers | 8 seconds |
| Thumbnail store projected over 2296 covers | 68 MB at quality 82 |

So the whole cold scan of the reference library, extraction plus thumbnails, costs
roughly 15 seconds rather than 54 minutes. The Calibre conversion path is the entire
cost and removing it from the scan removes the problem.

### 2.4 Constraints

- **C-1** The shelf makes no network call, ever.
- **C-2** The shelf writes nothing inside a shelf root. Index and thumbnails live in the
  application's own storage.
- **C-3** No process is spawned during a scan. Calibre may be used only on the path that
  opens a book for reading, where it is already used today.
- **C-4** The existing layering, the 400-line module limit and the coverage gate apply
  unchanged.
- **C-5** The narration book id requires a full parse, so the shelf cannot compute it
  during a scan.

### 2.5 Assumptions and dependencies

| # | Assumption | Owner | Confirm by |
|---|---|---|---|
| A-1 | The reference library is representative of the reader's collection | Oliver | before baseline |
| A-2 | No shelf root sits on a network share or a removable drive that may vanish mid-scan | Oliver | before baseline |
| A-3 | The curated genre catalogue may be ported in shape from Stellody without being ported in vocabulary | Oliver | before baseline |

## 3. Requirements

Priorities are MoSCoW. Acceptance criteria are stated as `Given / When / Then`.

### 3.0 Prioritisation, stated honestly

Counted over the requirements below: 59 Must, 7 Should, 1 Could. That proportion would
normally mean no prioritisation has happened, so it is worth saying why it stands here.

The shelf is one mechanism rather than a bundle of features. A shelf that cannot scan;
that cannot identify a book; that cannot draw a cover; that cannot open what the reader
picks: none of those is a smaller shelf, because none of them is a shelf. Most of the
Musts are load-bearing parts of that one mechanism. A large share of them are failure
paths, which are the requirements most often dropped and least often safe to drop.

The Won't-this-time list is section 1.3's out-of-scope list, which is where the real
prioritising was done: audio files, a managed library, external metadata, series, ratings
and reading lists are all things a bookshelf could plausibly have and this one will not.

**The smallest shippable shelf**, if the work has to be cut: the 59 Musts, less the list
view (FR-BS-051) and less reader-stated genres (FR-BS-046, FR-BS-046a, FR-BS-046b). That
is a grid over several roots with covers, a filter over what the files already state and
the existing reader behind it. Everything else in the Musts is either the mechanism or a
failure path.

### 3.1 Shelf roots and scanning

**FR-BS-001 Nominate a shelf root** (Must)
The shelf shall allow the reader to nominate a folder as a shelf root.
*Acceptance:* Given no shelf root is set, when the reader chooses `H:\Books`, then the
shelf records that path and begins a scan of it.

**FR-BS-001a Several shelf roots** (Must)
The shelf shall hold any number of shelf roots and shall present the works found under
all of them as one collection.
*Ruled by Oliver, 2026-09-19 (OQ-2).*
*Acceptance:* Given `H:\Books` and a second folder elsewhere, when both are nominated,
then one shelf shows the works of both and a rescan covers both.

**FR-BS-001b Remove a shelf root** (Must)
When the reader removes a shelf root, the shelf shall drop the entries found under it
and shall retain anything the reader stated about a work that is still reachable under
another root.
*Acceptance:* Given two roots, when one is removed, then the works found only under it are gone; a work still reachable under the other keeps every genre the reader stated.
**FR-BS-001c A root inside another root** (Should)
If a nominated root lies inside an existing root, then the shelf shall say so and shall
not record it twice.
*Rationale:* the reference library holds `H:\Books\FIXED\uncatalogued` below `H:\Books`,
so this is not a hypothetical.
*Acceptance:* Given `H:\Books` is a root, when `H:\Books\FIXED` is nominated, then the shelf says it lies inside an existing root and does not record it.
**FR-BS-002 Recursive walk** (Must)
When a scan runs, the scanner shall walk each shelf root recursively and record every
file whose extension is one NarrateX opens.
*Acceptance:* Given the reference library as the only root, when a scan completes, then
the index holds 2818 entries.

**FR-BS-002a Every format the reader can already open** (Must)
The scanner shall recognise exactly the extensions the existing open control offers:
`.epub`, `.pdf`, `.txt`, `.md`, `.markdown`, `.mobi`, `.azw`, `.azw3`, `.prc`, `.kfx`.
*Rationale:* a book that can be opened through the file dialog but cannot appear on the
shelf would make the shelf a partial view of the library, which is worse than no shelf.
*Acceptance:* Given one file of each of the ten extensions in a root, when a scan
completes, then the index holds ten entries.
*Verified by:* a test over a fixture folder holding one file per extension.

**FR-BS-002b The format list has one home** (Must)
The shelf and the open control shall read the recognised extensions from one declaration.
*Rationale:* two lists drift; the file dialog's filter and the scanner's filter are the
same knowledge.
*Verified by:* a structural test asserting that no second literal list of book extensions
exists in the source.

**FR-BS-003 Scan off the interface thread** (Must)
While a scan is running, the shelf shall remain operable, with the shelf drawable and
every control answering.
*Acceptance:* Given a scan of the reference library is running, when the reader switches
between grid and list view, then the view changes without waiting for the scan.

**FR-BS-004 Scan progress** (Should)
While a scan is running, the shelf shall state the number of works found so far and that
a scan is in progress.
*Acceptance:* Given a scan of the reference library, when it is part way through, then the shelf states how many works have been found and that a scan is running.
**FR-BS-005 Rescan on demand** (Must)
When the reader asks for a rescan, the scanner shall reconcile the index with the shelf
root: entries whose file is gone are removed; files not in the index are added; an entry
whose size or modified time changed is re-read.
*Acceptance:* Given an index of the reference library, when one file is deleted, another is added and a rescan runs, then the index loses the first and gains the second.
**FR-BS-006 Unreadable folder is reported, not fatal** (Must)
If a folder below the shelf root cannot be read, then the scanner shall record that
folder as unreadable, continue the scan and report the count at the end.
*Rationale:* an absence is an answer; a permission failure is a fault, so the two are
worded differently.
*Acceptance:* Given a folder whose permissions deny reading, when a scan runs, then the scan completes and reports one unreadable folder.
**FR-BS-007 Missing shelf root** (Must)
If a recorded shelf root no longer exists when the shelf opens, then the shelf shall
show the last index it holds, state that the root is unreachable and name it.
*Rationale:* an external drive that is not plugged in must not empty the shelf.
*Acceptance:* Given a root on a drive that is not connected, when the shelf opens, then the works last indexed are shown and the root is named as unreachable.
**FR-BS-008 No writes inside a shelf root** (Must)
The shelf shall not create, modify, move or delete any file inside a shelf root.
*Acceptance:* Given a scan of a read-only copy of the reference library, when the scan
completes, then no file below the root has a changed modified time and no file was added.

### 3.2 Identity and works

**FR-BS-009 Upgrade from a version with no shelf** (Must)
When the application starts for the first time after the shelf is added, the shelf shall
hold no root and the existing last-book behaviour shall be unchanged.
*Ruled by Oliver, 2026-09-19 (OQ-1).*
*Rationale:* a folder guessed from `last_book_path` would scan whatever happens to sit
beside one book, which on the reference library would be 718 files the reader did not ask
for.
*Acceptance:* Given `preferences.json` holding a `last_book_path` and no shelf root, when
the application starts, then that book loads as it does today and the shelf states that no
folder has been chosen.

**FR-BS-010 Shelf key** (Must)
The scanner shall identify an entry by its absolute path, its byte size and its modified
time; it shall not parse a book to identify it.
*Rationale:* C-5. The narration book id costs a full parse; 2818 parses cannot happen at
scan time.
*Acceptance:* Given a scan of the reference library, when it completes, then no book has been parsed and no book id has been computed.
*Verified by:* a test counting calls into the parser during a scan.
**FR-BS-011 Lazy book id** (Must)
When a book is opened from the shelf, the shelf shall record the resulting book id
against that entry.
*Acceptance:* Given an entry never opened, when its tile is drawn, then no progress is
shown; given the same entry after it has been opened once, when its tile is drawn, then
its progress is read from the existing bookmark store under its book id.

**FR-BS-011a The book's length arrives with its identity** (Must)
*Added by amendment A3.*
When a book is opened from the shelf, the shelf shall record the book's length in
characters alongside its book id.
*Rationale:* the resume position NarrateX already keeps is a character offset; an offset
without a length is not a fraction, so a tile could say "reading" with no way to say how
far. The length costs the full parse that opening the book has already paid for,
so recording it then costs nothing and recording it at scan time is impossible (C-5).
*Acceptance:* Given a work opened once, when its resume position is halfway through its
length, then the tile reads as reading at 50%.
*Verified by:* tests/application/shelf/test_library.py

**FR-BS-012 Grouping entries into works** (Must)
The shelf shall group entries that share a normalised title and author into one work.
*Acceptance:* Given `uncatalogued\2001_ A Space Odyssey - Arthur C. Clarke.mobi` and
`FIXED\uncatalogued\2001_ A Space Odyssey - Arthur C. Clarke.azw3`, when the shelf is
drawn, then one tile appears, not two.

**FR-BS-013 Format preference within a work** (Must)
When a work holds more than one entry, the shelf shall open the entry whose format costs
least to read, in the order EPUB, PDF, plain text, then Kindle formats.
*Rationale:* measured; a Kindle format costs a 2.3 second Calibre conversion that EPUB
does not.
*Acceptance:* Given a work holding both a `.mobi` and an `.epub`, when it is opened, then the `.epub` is the file loaded.
**FR-BS-014 Near-duplicate works are not merged silently** (Could)
Where two works differ only after normalisation, the shelf shall show both and mark them
as possible duplicates.
*Rationale:* the reference library holds `2010 Odyssey Two - Arthur C Clarke` beside
`2010_ Odyssey Two - Arthur C. Clarke`. Merging on a guess loses a book; showing both
with a mark loses nothing. See OQ-4.
*Acceptance:* Given `2010 Odyssey Two - Arthur C Clarke` beside `2010_ Odyssey Two - Arthur C. Clarke`, when the shelf is drawn, then two tiles appear, each marked as a possible duplicate of the other.

### 3.3 Metadata

**FR-BS-020 Metadata precedence** (Must)
The reader of an entry shall take its title, author and subjects from the first source
that states them, in the order: sibling `metadata.opf`, the file's own embedded metadata,
then the filename.
*Acceptance:* Given a Calibre folder holding `metadata.opf` stating a title, when the
entry is read, then the tile shows that title rather than the filename.

**FR-BS-021 Filename fallback** (Must)
Where neither a sidecar nor embedded metadata states a title, the reader shall derive the
title and author from the filename pattern `<title> - <author>`.
*Acceptance:* Given `A Wanted Man - Child, Lee.azw3` with no other source, when the entry
is read, then the title is `A Wanted Man` and the author is `Lee Child`.

**FR-BS-021a The three conventions a filename may use** (Must)
*Added by amendment A1.*
The reader shall recognise three further shapes: a filename stating the author first in
sort form; a filename separating co-authors with the same punctuation a sort name uses;
a filename stating an issue date where an author would go.
*Rationale:* measured over the reference library, 2738 stems hold a separator. 296 state
the author first (`Cussler, Clive - Dirk Pitt 17 - Atlantis Found`), 28 state one author
in sort form (`Anansi Boys - Gaiman_ Neil`), 16 separate co-authors with the same
punctuation (`Juggler of Worlds - Larry Niven_ Edward M. Lerner`) and 18 state an issue
date (`New Scientist - 19 April 2014`). Reading every stem as `<title> - <author>` put
296 people's names in the title of a tile.
*Acceptance:* Given `King, Stephen - From a Buick 8`, when it is read, then the title is
`From a Buick 8` and the author is `Stephen King`; given
`Ambler Warning, The - Ludlum, Robert`, the title is `The Ambler Warning`, because the
word after the comma is an article.
*Verified by:* tests/domain/shelf/test_text_conventions.py

**FR-BS-021b An author stated first with nothing to signal it** (Must)
*Added by amendment A2.*
Where a filename states the author first with no punctuation to mark it, the shelf shall
decide which half is the person by how many books in the library stand behind each name.
*Rationale:* measured, 216 of 2819 files do this (`Kurt Vonnegut - Bluebeard`). No rule
reading one filename alone can tell that half from a title. The library can: `Neil
Gaiman` stands behind 58 books while `A Study in Emerald` stands behind 2.
*Acceptance:* Given a library where `Neil Gaiman` is the author of three books, when
`Neil Gaiman - A Study in Emerald` is read, then the title is `A Study in Emerald` and
the author is `Neil Gaiman`; given `The Mediterranean Caper - Clive Cussler`, the halves
are left as they are, because Clive Cussler outweighs the Caper.
*Verified by:* tests/domain/shelf/test_corpus.py

**FR-BS-022 Unparsable filename** (Must)
If the filename does not match the pattern, then the reader shall use the whole stem as
the title and shall state the author as unknown.
*Acceptance:* Given `book1.azw3` stating nothing about itself, when it is read, then the title is `book1` and the author reads as unknown.
**FR-BS-023 No metadata is written back** (Must)
The shelf shall hold every correction it makes in its own index and shall not write to
the book file or its sidecars.
*Acceptance:* Given a work whose genre the reader has stated, when a rescan runs, then the book file and its `.opf` hash the same as before.

### 3.4 Cover artwork

**FR-BS-030 Cover precedence** (Must)
The cover reader shall take an entry's artwork from the first source that yields an
image, in the order: sibling cover image, the cover named by a sibling `metadata.opf`,
the image embedded in the file, then none.
*Rationale:* this extends the existing precedence in `cover_extractor.py`, which already
prefers a Calibre sidecar.
*Acceptance:* Given a book carrying both a sibling `cover.jpg` and an embedded cover, when its tile is drawn, then the sidecar image is the one shown.
**FR-BS-031 No conversion during a scan** (Must)
The cover reader shall not spawn a process while scanning.
*Acceptance:* Given a scan of the reference library, when the scan completes, then no
`ebook-convert` process was started.
*Rationale:* measured at 2.3 seconds per book, roughly 54 minutes over the library.

**FR-BS-032 Kindle covers are read directly** (Must)
The cover reader shall read a Kindle format's cover from the file's own record structure.
*Acceptance:* Given a 60-file sample from either uncatalogued folder, when covers are
read, then at least 45 yield an image and the whole sample completes within 5 seconds.
*Rationale:* measured at 47 of 60 for each format, in 0.41 seconds and 0.04 seconds.

#### Format capability, measured

| Format | Metadata source | Cover source | Measured cost per file |
|---|---|---|---|
| `.epub` | sidecar `.opf`, then the OPF inside the file | sidecar image, then the embedded cover | 14 ms over 11 files |
| `.pdf` | sidecar `.opf`, then the document information dictionary | sidecar image, then the first page rastered | 55 ms over 10 files |
| `.mobi`, `.azw`, `.azw3` | sidecar `.opf`, then the EXTH header | sidecar image, then the EXTH cover record | 1.3 ms to 7 ms over 2784 files |
| `.prc` | expected identical to `.mobi` | expected identical to `.mobi` | UNTESTED, see OQ-9 |
| `.kfx` | sidecar `.opf` only | sidecar image only | UNTESTED, see OQ-9 |
| `.txt`, `.md`, `.markdown` | filename only | none, ever | filesystem only |

`.prc` and `.kfx` carry no measurement because the reference library holds none of
either. `.prc` is the same container family as `.mobi`, so the same reader is expected to
serve it; that is a hypothesis, not a measurement. `.kfx` is a different container
entirely and the header reader will not serve it, so it falls to a sidecar or to the
placeholder. Both are recorded in OQ-9 with the probe that would settle them.

**FR-BS-033 A work with no cover still appears** (Must)
If no source yields an image, then the tile shall show a placeholder bearing the title
and author; the work shall remain selectable.
*Acceptance:* Given a `.txt` file, when its tile is drawn, then a placeholder bearing the title and author is shown; the tile can still be activated.
**FR-BS-034 Thumbnails are cached** (Must)
The shelf shall cache a downscaled thumbnail per work and shall redraw from that cache
rather than re-reading the book file.
*Acceptance:* Given a work already scanned, when the shelf is reopened, then its tile is drawn without the book file being opened.
*Verified by:* a test counting file opens while drawing.
**FR-BS-035 The thumbnail cache is derived** (Must)
When the thumbnail cache is deleted, the shelf shall rebuild it on the next scan without
loss of any reader-stated information.
*Acceptance:* Given a scanned library with genres the reader has stated, when the thumbnail cache is deleted and a rescan runs, then every thumbnail returns and every stated genre survives.
**FR-BS-036 The shelf fills as the scan runs** (Should)
While a scan is running, the shelf shall show each work as it is found rather than
waiting for the scan to finish.
*Rationale:* the reader asked whether the shelf could paginate to avoid a long wait. The
measured cold scan is about 15 seconds, so there is no long wait to page around; a shelf
that fills in front of the reader answers the same need without splitting the collection
into pages it must then be navigated between.
*Acceptance:* Given a scan in progress, when 100 works have been found, then those 100 are drawable before the scan ends.
**FR-BS-037 The grid holds only what it draws** (Must)
The grid shall build tiles only for the rows within or near the visible area, however
many works the shelf holds.
*Acceptance:* Given 3000 works, when the shelf opens, then the number of live tile
widgets is bounded by a constant and does not grow with the collection.
*Rationale:* the cost that scales badly is now drawing, not reading.

**FR-BS-038 An expensive cover is deferred** (Must)
Where a cover cannot be obtained by reading the file's own header or a sidecar, the cover
reader shall defer that work until the tile is about to be drawn.
*Acceptance:* Given a root of PDFs, when a scan completes, then no page has been rastered
for a work that has never been on screen.
*Rationale:* measured, a PDF first page costs 55 ms against 1.3 ms for a Kindle header;
any future fallback through Calibre would cost 2.3 seconds.

### 3.5 Genres and filtering

**FR-BS-040 Curated catalogue** (Must)
The shelf shall hold a curated catalogue of genres of two levels, onto which each raw
subject is mapped through a table of aliases.
*Rationale:* measured over 652 `.opf` files, the raw vocabulary states `Horror`,
`Horror - General`, `Fiction - Horror`, `Horror fiction`, `Horror tales` and
`Horror & Ghost Stories` as six names for one shelf. `General` appears 273 times and says
nothing. One sample file states `Azizex666`, which is a release-group signature. A raw
tag list is not a filter a reader can use.
*Acceptance:* Given the raw subjects `Horror - General`, `Horror tales` and `Fiction - Horror`, when they are read, then all three reach Horror.
**FR-BS-041 Unmatched subjects are reported** (Must)
Where a subject matches no entry in the catalogue and no alias, the shelf shall report it
as unmatched rather than discard it.
*Rationale:* ported from Stellody, where the unmatched report is how the catalogue grows.
*Acceptance:* Given the raw subject `Azizex666`, when it is read, then it reaches no genre; it appears in the unmatched report.
**FR-BS-042 Filter by genre** (Must)
When the reader ticks one or more genres and asks to show them, the shelf shall show
every work carrying at least one ticked genre.
*Acceptance:* Given works tagged Horror and works tagged Fantasy, when Horror alone is
ticked, then only the Horror works are shown.

**FR-BS-043 A main genre includes its styles** (Must)
When a main genre is ticked, the shelf shall include works carrying any style beneath it.
*Acceptance:* Given a work whose only genre is Space Opera beneath Science Fiction, when
Science Fiction is ticked, then that work is shown.

**FR-BS-044 Works stating no genre** (Must)
The filter shall offer a choice that shows works carrying no genre at all.
*Rationale:* measured, only 1533 of 2784 Kindle files state any subject at all. Without this choice a large part of the library is
unreachable through the filter.
*Acceptance:* Given a work stating no subject, when the no-genre choice is ticked, then that work is shown.
**FR-BS-045 Clearing the filter** (Must)
When the reader clears the filter, the shelf shall show every work.
*Acceptance:* Given a filter showing 50 works of 1400, when the filter is cleared, then all 1400 are shown.
**FR-BS-046 Reader-stated genre** (Must)
The shelf shall allow the reader to state a genre for a work; that statement shall
outrank anything read from the file.
*Ruled by Oliver, 2026-09-19 (OQ-5): in the first release.*
*Rationale:* measured, 1251 of 2784 Kindle files state no subject at all, so without this
nearly half the library is reachable only by search.
*Acceptance:* Given a work stating no genre, when the reader files it under Horror, then
it appears when Horror is ticked; it still does after a rescan.

**FR-BS-046a Stating a genre for several works at once** (Should)
The shelf shall allow the reader to select several works and state one genre for all of
them.
*Rationale:* filing 1251 works one at a time is not a task anyone completes.
*Acceptance:* Given ten works selected together, when the reader files them under Horror, then all ten carry Horror.
**FR-BS-046b A reader statement is never overwritten** (Must)
When a rescan re-reads a work whose genre the reader has stated, the shelf shall keep the
reader's statement.
*Acceptance:* Given a work whose file states Horror that the reader has filed under Fantasy, when a rescan runs, then it still reads as Fantasy.
**FR-BS-048 Entity-escaped subjects** (Must)
The subject reader shall decode character entity references before a subject is split or
matched.
*Rationale:* measured, `Mystery &amp; Detective` appears 70 times in the reference
library and splitting it without decoding yields the genre `Mystery &amp`, which matches
nothing and reads as a defect on screen.
*Acceptance:* Given the raw subject `Mystery &amp; Detective`, when it is read, then the work reaches Mystery and Detective; no genre named `Mystery &amp` exists anywhere.
**FR-BS-049 Subjects are split before matching** (Must)
The subject reader shall split a raw subject on the separators the sources actually use,
being the semicolon, the comma, the solidus and the ampersand; it shall match each piece
independently.
*Acceptance:* Given `Fiction - Science Fiction; Horror`, when it is read, then the work
carries both Science Fiction and Horror.

**FR-BS-047a A work carries every genre it reaches** (Must)
A work shall carry every genre its subjects reach, rather than one.
*Ruled by Oliver, 2026-09-19 (OQ-12).*
*Rationale:* the sources state several and a book genuinely sits in two places; measured,
a single file commonly states both Horror and Thriller.
*Acceptance:* Given a work whose subjects reach Horror and Thriller, when either is
ticked, then that work is shown.

**FR-BS-047 Text search** (Must)
When the reader types into the search field, the shelf shall show works whose title or
author contains that text, case-insensitively, combined with any active genre filter.
*Acceptance:* Given 1400 works, when `clarke` is typed, then only works whose title or author holds that text are shown.

### 3.6 Views

**FR-BS-050a The shelf is a view of the main window** (Must)
The shelf shall be a view within the existing main window rather than a separate window
or a startup screen.
*Ruled by Oliver, 2026-09-19 (OQ-6).*
*Rationale:* Stellody's model; the reader switches between the shelf and the book being
read without a window changing beneath them.
*Acceptance:* Given the reader is looking at the shelf, when a work is opened, then the same window shows the reader; no second window appears.
**FR-BS-050 Grid view** (Must)
The shelf shall offer a grid of tiles showing cover, title and author.
*Acceptance:* Given a scanned library, when the grid is drawn, then each work appears exactly once carrying its cover, title and author.
**FR-BS-051 List view** (Must)
The shelf shall offer a list showing, per row, a small cover, the title, the author, the
genres and the reading progress.
*Acceptance:* Given the same library, when the list is drawn, then each row carries a small cover, the title, the author, the genres and the progress.
**FR-BS-052 The view choice persists** (Should)
When the shelf is reopened, it shall open in the view last used.
*Acceptance:* Given the list was the view last used, when the application restarts, then the shelf opens in the list view.
**FR-BS-053 Sort order** (Must)
The shelf shall order works by author then title.
*Acceptance:* Given works by Clarke and by Koontz, when the shelf is drawn, then Clarke's works precede Koontz's; within each author the titles ascend.
**FR-BS-053a Other orderings** (Should)
The shelf shall offer ordering by title alone and by most recently read.
*Acceptance:* Given ordering by most recently read, when it is chosen, then the work opened most recently is first.
**FR-BS-054 Progress on a tile** (Must)
Where a work has been opened before, the tile shall show a state of unread, reading or
finished, together with a bar showing how far through it the reader is.
*Ruled by Oliver, 2026-09-19 (OQ-8).*
*Acceptance:* Given a work whose resume position is halfway, when its tile is drawn, then
the state reads as reading and the bar is half filled.

**FR-BS-055 Open a work** (Must)
When the reader activates a tile or a row, the shelf shall load that work's preferred
entry into the reader exactly as the existing file dialog does today.
*Acceptance:* Given a tile, when it is activated, then the same book loads as choosing that file through the open control would.
**FR-BS-056 A missing file** (Must)
If the file behind a work no longer exists when the reader activates it, then the shelf
shall say so, name the path and offer a rescan.
*Acceptance:* Given a work whose file has been deleted since the scan, when it is activated, then the shelf names the path and offers a rescan.
**FR-BS-056a The shelf control sits beside the open control** (Must)
The main window shall carry a control that shows the shelf, placed beside the existing
open-a-book control, which shall remain.
*Ruled by Oliver, 2026-09-19 (OQ-3).*
*Rationale:* a book outside every shelf root must still be openable.
*Depends on:* `assets/bookshelf.png`, supplied by Oliver on 2026-09-19. Verified as
1254x1254 RGBA with a transparent background, matching `assets/select-book.png` exactly in
size and mode.
*Acceptance:* Given the main window, when it is drawn, then a shelf control carrying `assets/bookshelf.png` sits beside the open control; the open control still opens a file.
**FR-BS-057 Empty shelf** (Must)
While no shelf root is set, the shelf shall state that no folder has been chosen and
shall offer the control that chooses one.
*Acceptance:* Given no shelf root, when the shelf is shown, then it states that no folder has been chosen and offers the control that chooses one.
**FR-BS-058 A root holding no books** (Must)
If a scan finds no book file, then the shelf shall state that the folder holds nothing it
can read and shall name the formats it looks for.
*Acceptance:* Given a folder holding only images, when a scan completes, then the shelf states that the folder holds nothing it can read and names the extensions it looks for.
**FR-BS-059 Keyboard reachability** (Must)
The shelf shall join the existing focus ring, with the grid traversable by cursor key and
a work activated by Enter or Space; no pane shall take a focus ring.
*Rationale:* the existing keyboard rules apply unchanged; see the `keeb` and
`noborderfocus` models.
*Acceptance:* Given the shelf has the focus, when Tab and the cursor keys are pressed, then the ring moves between works in visual order; no container paints a ring.
**FR-BS-060 Forget a work** (Must)
When the reader asks to forget a work, the shelf shall delete what NarrateX derived about
it and shall leave the tile in place, marked unread.
*Rationale:* the existing removal control forgets derived state and never touches disk.
On a shelf the file is still there, so the tile must stay.
*Acceptance:* Given a work carrying bookmarks and cached audio, when the reader forgets it, then its tile remains and reads unread; the file on disk is untouched.

### 3.7 Non-functional requirements

Measured on the reference machine in section 2.3, against the reference library.

**NFR-BS-001 First paint** (Must)
When the shelf opens against a warm index of 3000 works, it shall draw its first screen
of tiles within 1.0 second at the 95th percentile.
*Verified by:* a timed test over a generated index of 3000 entries.

**NFR-BS-002 Cold scan** (Must)
When a scan runs over the reference library of 2818 files, it shall complete within 60
seconds.
*Rationale:* measured, 5.0 seconds to read every Kindle header plus 8 seconds projected
to encode 2296 thumbnails, so about 15 seconds; 60 seconds carries a fourfold margin for
the walk, the sidecars and the writes.
*Verified by:* a timed scan over the reference library, reported in the scan summary.

**NFR-BS-003 Filter latency** (Must)
When a filter or a search term is applied to 3000 works, the shelf shall redraw within
200 milliseconds at the 95th percentile.
*Verified by:* a timed test applying a filter to a generated index of 3000 works.
**NFR-BS-004 Thumbnail cache ceiling** (Should)
The thumbnail cache shall hold no more than 30 MB per 1000 works.
*Rationale:* measured, a 320x480 thumbnail at quality 82 averages 29 KB, so the reference
library's 2296 covers project to 68 MB. The ceiling is set from that measurement rather
than from a preference; a smaller tile lowers it.
*Verified by:* measuring the cache directory after a scan of the reference library.
**NFR-BS-005 No network** (Must)
The shelf shall make no outbound network connection.
*Verified by:* a structural test forbidding network imports in the shelf packages, in the
shape of the existing domain-purity tests.

**NFR-BS-006 Interrupted scan** (Must)
If a scan is interrupted by the application closing, then the index shall remain readable
and the next scan shall complete the work.
*Acceptance:* Given a scan stopped halfway by the application closing, when it starts again, then the index opens and a rescan completes the remainder.
**NFR-BS-007 Layering** (Must)
The shelf's domain shall hold no I/O, no framework import and no clock read, enforced by
the existing structural tests.
*Verified by:* the existing structural tests, extended to cover the shelf packages.
**NFR-BS-008 Coverage** (Must)
The shelf's domain and application layers shall be covered by the existing 100% gate.
*Verified by:* the existing coverage gate, with the shelf packages inside its scope.

### 3.8 Data requirements

**DATA-BS-001** The shelf index is a cache derived wholly from disk. Deleting it loses
nothing that cannot be rebuilt by a rescan.
*Verified by:* a test that deletes the index, rescans and compares the rebuilt index with
the original, ignoring reader-stated fields.

**DATA-BS-002** Reader-stated information (a corrected genre, a corrected title) is NOT
derived and shall survive a rescan and an index rebuild. It is keyed by shelf key and by
book id where one is known.
*Verified by:* FR-BS-046b's rescan test, extended to an index rebuild.

**DATA-BS-003** The index and the thumbnail cache live in the application's own storage,
never inside a shelf root.
*Verified by:* FR-BS-008's read-only-root test, which also proves nothing was written.

**DATA-BS-004** Reading progress is not duplicated. The shelf reads it from the existing
bookmark store, keyed by book id.
*Verified by:* a structural test asserting the shelf holds no progress field of its own.

## 4. Other requirements

Internationalisation, legal and regulatory: unchanged from the existing product. No risk
register is proposed; this is a personal desktop utility with no safety, financial or
regulatory exposure, so FMEA would be disproportionate.

## Appendix A: the silence check

Answered above: first run with no data (FR-BS-057), the largest plausible input
(NFR-BS-002), a partial or interrupted operation (NFR-BS-006), no permission
(FR-BS-006), the disk being unavailable (FR-BS-007), a file vanishing between scan and
open (FR-BS-056).

Not yet answered, therefore in appendix B: upgrade from a version with no shelf
(OQ-1), a second shelf root (OQ-2), concurrent access (not applicable; single instance).

## Appendix B: open questions

**All open questions were ruled on 2026-09-19. The register is closed and this document is
baselined at version 1.0.** Later changes arrive as numbered amendments with a reason,
never as silent edits. Questions are kept with their ruling and never renumbered.

| # | Question | Ruling, Oliver, 2026-09-19 | Where it lives |
|---|---|---|---|
| OQ-1 | On upgrade, does `last_book_path` seed a shelf root? | No. The reader chooses a root; the last book still auto-loads as today | FR-BS-009 |
| OQ-2 | One shelf root or several? | Several | FR-BS-001a to FR-BS-001c |
| OQ-3 | Does the shelf replace the open-a-file control or sit beside it? | Beside it; the open control stays | FR-BS-056a |
| OQ-4 | Near-duplicates: mark both or merge on a looser key? | Mark both | FR-BS-014 |
| OQ-5 | Reader-stated genres in the first release or later? | First release | FR-BS-046 |
| OQ-6 | A view in the main window or a separate screen? | A view in the main window | FR-BS-050a |
| OQ-7 | The genre catalogue's vocabulary | Drafted and measured | Appendix D |
| OQ-8 | How does progress read on a tile? | A state plus a bar | FR-BS-054 |
| OQ-9 | `.prc` and `.kfx`, which the library holds none of | Recognised and scanned; `.prc` expected to behave as `.mobi`, `.kfx` expected to reach a cover only through a sidecar. Both remain UNMEASURED until a file of each exists | FR-BS-002a, format matrix |
| OQ-10 | Artwork for the shelf control | Supplied as `assets/bookshelf.png` | FR-BS-056a |
| OQ-11 | The five vocabulary rulings | Crime the main with Mystery beneath it; Criticism a main of its own; the rest as drafted | Appendix D |
| OQ-12 | Several genres per work or exactly one? | Several | FR-BS-047a |

**The one thing still labelled as unmeasured is OQ-9.** `.prc` and `.kfx` are specified
and will be scanned; what their readers actually yield is a hypothesis until a file of
each is dropped into a root. That is stated in the format matrix rather than hidden in a
priority.

## Appendix C: traceability

Every requirement above names either an acceptance criterion or a verification method.
The test names are written when the tests are, against these identifiers. Identifiers are
never reused and never renumbered.

## Appendix D: the drafted genre vocabulary

Drafted on 2026-09-19 at Oliver's request (OQ-7) and **measured against the reference
library the same day**. Every count below is a count of Kindle-format FILES, not of
works, because roughly 717 works are present twice; the shape of the distribution is
what the counts are for, not their absolute size.

**How it was measured.** The draft catalogue plus its alias table was run over all 2784
`.mobi`, `.azw3` and `.azw` files. Of those, 1533 state at least one subject and 1483
reach at least one genre, so **96.7% of the books that say anything about themselves are
filed**. The remaining 3.2% and the books that say nothing are why FR-BS-046 exists.

### The catalogue

Ruled by Oliver on 2026-09-19. Mains in bold, styles beneath. The number is the files
that reached that name, measured after the ruling was applied.

| Main | Files | Styles, with files |
|---|---|---|
| **Horror** | 665 | Psychological Horror 220, Ghost Stories 220, Supernatural 45, Occult 20, Vampires 6 |
| **Thriller** | 639 | Espionage 178, Political Thriller 26, Conspiracy 2, Legal Thriller 0, Medical Thriller 0, Techno-thriller 0 |
| **Science Fiction** | 562 | Hard Science Fiction 96, Space Opera 64, Time Travel 14, Dystopian 0, Post-Apocalyptic 0, Military Science Fiction 0, First Contact 0 |
| **Crime** | 464 | Mystery 438, Detective 256, Police Procedural 80, Private Investigators 30, Women Sleuths 28, Serial Killers 24, Cosy Mystery 0 |
| **Literary** | 354 | Short Stories 122, Classics 28, Satire 20 |
| **Fantasy** | 352 | Epic Fantasy 122, Urban Fantasy 0, Sword and Sorcery 0, Magical Realism 0 |
| **Adventure** | 272 | none |
| **Criticism** | 252 | none |
| **Children and Young Adult** | 102 | none |
| **Historical** | 78 | none |
| **Poetry** | 68 | none |
| **Romance** | 50 | none |
| **Popular Science** | 34 | none |
| **History** | 32 | none |
| **Humour** | 20 | none |
| **War** | 18 | none |
| **Biography** | 8 | none |
| **True Crime** | 0 | none |
| **Western** | 0 | none |

Nineteen mains. A style showing zero is offered anyway where the genre plainly exists in
the world and the library's tags simply do not say it. That is the rule Stellody settled
on for Punk and Country: absence from the tags is a fact about the tags, not about the
shelf.

### The vocabulary rulings, closed

Ruled by Oliver on 2026-09-19, recorded here because a ruling that is not written down
gets re-argued.

1. **Crime is the main; Mystery is a style beneath it.** The library says `Mystery` 614
   times and `Crime` 97, so the raw counts pointed the other way; the ruling overrides
   them, since Crime is the name a reader here reaches for. Mystery keeps every alias it
   had, so nothing is lost from the fold.
2. **Criticism is a main of its own**, not a style under Literary. 252 files reach it and
   almost all of it is writing ABOUT an author rather than by them, so a reader choosing
   something to listen to tonight should not have a critical study handed to them under
   Literary.
3. **Thriller absorbs Suspense.** `Suspense` at 607 and `Thrillers` at 364 fold into one
   main.
4. **Psychological stays under Horror.** Noted as the fold most likely to want revisiting
   once the shelf can be looked at; revisiting it costs one line of the alias table.
5. **The zero-count mains stay.** True Crime, Western and the empty styles are offered on
   the Punk principle.

Coverage after the ruling is unchanged: 1483 of the 1533 files stating a subject reach a
genre, which is 96.7%.

### What is deliberately not a genre

- **Says nothing, so it is dropped rather than reported:** `Fiction` (1696),
  `General` (1389), `American` (365), `Non-Classifiable` (63), `Contemporary` (49),
  `Modern` (34), `Large type books` (39).
- **A provenance or a form, not a genre:** `Media Tie-In` (101 plus 79 as
  `Media Tie-In - General`), `Movie` (73), `TV Tie-Ins` (47 plus 26). These say how a
  book came to exist, not what it is.

### What the unmatched report will show on day one

Measured, the largest unmatched strings are author names, character names and places,
which is the correct outcome rather than a gap to be closed:

| Unmatched string | Files | What it actually is |
|---|---|---|
| `King` / `king` / `stephen` / `Stephen - Prose` | 270 combined | An author, split by the punctuation in the raw tag |
| `Azizex666` | 98 | A release-group signature inside the file's metadata |
| `Maine` | 74 | A place |
| `Koontz` / `Dean R. (Dean Ray) - Prose` | 124 combined | An author |
| `Jack (Fictitious character)` | 50 | A character |
| `Roland (Fictitious character : King)` | 48 | A character |
| `Reacher`, `Cross`, `Alex (Fictitious character)`, `Seldon` | 133 combined | Characters |
| `New York (N.Y.)`, `Washington (D.C.)`, `California`, `United States` | 114 combined | Places |

This is the evidence for FR-BS-041: an unmatched string is reported rather than
discarded, so the alias table can grow where the string is a genre and stay still where
it is a person.

## Appendix E: amendments

Numbered changes made after the 1.0 baseline. Each names what forced it.

**A1, 2026-09-19: three filename conventions, not one.** FR-BS-021 assumed every stem
reads `<title> - <author>`. Building the domain layer and driving it over the reference
library showed three further shapes, together covering 358 files. FR-BS-021a added.

**A2, 2026-09-19: the author stated first with no punctuation to mark it.** 216 files put
a person's name where a title goes, with nothing in the filename to say so. This cannot be
settled by one filename, so the rule reads the whole library and weighs how many books
stand behind each name. FR-BS-021b added. It is worth stating as a limit: an author whose
every file is written this way cannot be learned, because there is nothing to learn from.

**Measured after both amendments**, driving the domain headlessly over `H:\Books`: 2819
files fold to 863 works in under a second, 84% carry a cover and 51% reach a genre.

**A3, 2026-09-20: a length recorded with the book id.** FR-BS-054 asks a tile for a bar
as well as a state; a bar needs a fraction. NarrateX stores a character offset, not a
fraction, so the length has to come from somewhere; the only moment it is free is the
parse that opening the book already performs. FR-BS-011a added.

**Measured after the application layer, driving it headlessly over `H:\Books`:**

| Measurement | Value | Against |
|---|---|---|
| Cold scan of 2819 files | 23.2 seconds | NFR-BS-002, 60 seconds |
| Rescan of the same tree | 0.2 seconds, 2819 kept, nothing re-read | FR-BS-005 |
| Works after folding | 793 | FR-BS-012 |
| Works drawn as the scan ran | 2819 entries reported | FR-BS-036 |
| Three queries over 793 works | 111 ms in total | NFR-BS-003, 200 ms each |

**One thing worth watching rather than fixing yet.** Each query re-folds the whole index
into works, so a query costs about 37 ms at 793 works and would cost roughly four times
that at 3000. That still meets NFR-BS-003 with headroom to spare, so nothing is done
about it now; the fix, if the measurement ever says otherwise, is to hold the folded
works in the service and drop them when the index is saved.

**A4, 2026-09-20: the figures re-measured through the committed infrastructure.** Every
number above it was taken with throwaway probe infrastructure, before the four ports had
real implementations. Driving `bootstrap.build_shelf` over `H:\Books` gives the table
below. The library was measured unchanged first (2819 book files, none modified since
2026-09-19), so nothing here is the disk moving.

| Measurement | Committed wiring | Recorded in A3 | Against |
|---|---|---|---|
| Book files found | 2819 | 2819 | FR-BS-002 |
| Cold scan | 1.1 s to 6.0 s, see below | 23.2 s | NFR-BS-002, 60 s |
| Rescan | 0.2 s, 2819 kept, nothing re-read | same | FR-BS-005 |
| Works after folding | 791 | 793 | FR-BS-012 |
| Works carrying a cover | 646 | 640 | FR-BS-034 |
| Works reaching a genre | 390 | 390 | FR-BS-039 |
| Three queries | 166 ms in total, 75 ms the slowest | 111 ms | NFR-BS-003, 200 ms each |

**The cold-scan figure is dominated by the operating system's file cache, not by the
scan.** The first run of a session measured 6.0 s and an immediate repeat into a fresh
index measured 1.1 s, against 23.2 s recorded on a machine that had not touched the drive.
The honest reading is that the requirement holds by a wide margin on every reading taken
and that a single cold-scan number is not a stable thing to quote.

**Where the two-work difference lives, measured rather than assumed.** Folding the same
2819 entries with the metadata ignored gives 863 works, which is exactly the figure A2
recorded for the domain alone, so the fold is unchanged. 396 entries take their title and
229 take their author from a sidecar or an embedded header; that is what carries 863 down
to 791. The difference against A3's 793 is therefore in the metadata reader; the
probe reader that produced 793 was a scratch file and is gone, so which two files read
differently cannot be recovered. The committed reader also finds six more covers. Both
runs of the committed wiring agreed exactly, so the result is deterministic.
