# Decisions and trade-offs

The deliberate choices NarrateX rests on: what was chosen, what was given up
for it and why. Each entry is the decision as the product makes it today.
The detail behind each one, with the tests that hold it, lives in
[ARCHITECTURE.md](ARCHITECTURE.md), the constraints in
[ARCHITECTURE_CONSTRAINTS.md](ARCHITECTURE_CONSTRAINTS.md) and the bookshelf
specification ([BOOKSHELF.md](BOOKSHELF.md)); [TECH_DEBT.md](TECH_DEBT.md)
holds what was weighed and deliberately left alone.

## The product as a whole

### Everything runs on the reader's machine

The voice, the parsing, the shelf and the audio cache all run on the computer
NarrateX is installed on, for the one person whose books they are.

- **Rather than:** cloud voices, an account or a subscription.
- **Gains:** nothing read leaves the device; once the voice model is in
  place, reading needs no connection; there is no per-word cost and no cap.
- **Costs:** the on-device voices are less natural than the large cloud
  services. The site says so rather than claiming otherwise.

### Kokoro and nothing else

Speech comes from one engine, Kokoro, using its built-in voices.

- **Rather than:** voice cloning with Coqui XTTS; a system voice as a
  fallback.
- **Gains:** far less dependency creep; packaging is more predictable; one
  engine to test and to tune the text for.
- **Costs:** no custom voices; when Kokoro cannot run there is nothing to
  fall back to.

### English voices only, all of them offered

The picker offers Kokoro's whole English inventory, British and American.
British voices are listed first.

- **Rather than:** a curated handful; regions Kokoro does not ship.
- **Gains:** the reader chooses from everything the engine can say.
- **Costs:** no Australian, New Zealand, Canadian or Indian English; no other
  language either. Kokoro ships none.

### What NarrateX deliberately is not

It reads books the reader can already open. It is not a phone app, a library
manager, a DRM remover or a scanner: a PDF whose pages are pictures is
reported as holding no text rather than recognised character by character.

- **Rather than:** an all-in-one reading suite.
- **Gains:** a small surface held to a high bar.
- **Costs:** those jobs need other tools.

### The bookshelf was specified before it was built

The bookshelf was written down as requirements, every open question ruled,
before its code. Later changes arrive as numbered amendments carrying the
measurement that forced them.

- **Rather than:** building first and describing afterwards.
- **Gains:** a ruling made once stays made; each amendment says what the real
  library showed that the document had not foreseen.
- **Costs:** the specification is work of its own to keep true.

## Privacy and the network

### The ways out, all named

NarrateX itself makes two kinds of request: the voice model download and the
update check. The voice library also asks its host whether the model files it
has cached are still current whenever it loads them, falling back to the cache
without a connection. The donate button hands its address to the desktop's
browser and stops there; a second launch talks to the first over a local
channel, not the network.

- **Rather than:** network use spread wherever it was convenient.
- **Gains:** "nothing you read leaves the device" can be checked by reading a
  handful of places; none of the requests carries anything about the reader.
- **Costs:** NarrateX never learns what the browser did next; the voice
  library's own check is left at its default rather than switched off.

### The voice model is fetched once, before the window opens

On first run the Kokoro weights and every voice the picker offers are
downloaded behind a progress dialog. The voice list is the repository's own,
handed in by the entrypoint, so no voice is left for Kokoro to fetch mid-read.
A failed download ends startup with a message.

- **Rather than:** opening a window that cannot narrate and failing at the
  first Play.
- **Gains:** a window that opens is one that can speak.
- **Costs:** the first run needs a connection and a wait.

### Update checks: daily, quiet unless there is news

A check runs shortly after launch and then once a day. It asks GitHub for the
latest published release only, so a draft, a prerelease or a bare tag can
never prompt. An automatic check says nothing when it fails or finds nothing
new; the About dialog's check always answers. A version that cannot be read
is never treated as newer; a skipped version is never offered again.

- **Rather than:** no check at all; one that reports every outcome.
- **Gains:** updates are found without nagging; a malformed tag never tells
  anyone their copy is stale.
- **Costs:** one unprompted request a day.

### No book is ever looked up online

Every title, author, cover and genre on the shelf comes from the file, its
Calibre sidecar or its filename.

- **Rather than:** filling gaps from an online book catalogue.
- **Gains:** the shelf keeps the promise that nothing read leaves the device.
- **Costs:** a book that says little about itself shows little.

## Books and their structure

### One model answers what a book is

Every format is read into one document model of sections and blocks. The
reading pane, the narrator, the chapter list, the Sections bookmarks and the
ideas index all take their answer from it, including where the body begins.
A structural test fails any narration built without a model.

- **Rather than:** each feature scanning the raw text for itself, which let
  the narrator and the pane disagree about where a book starts.
- **Gains:** what is shown and what is read are one decision; a fix to the
  model reaches every feature at once.
- **Costs:** the model must be right for every format, so each format has a
  reader of its own to maintain.

### The text is never rewritten; the model points into it

Each block records a span into the book's canonical text rather than holding
a copy. A paragraph that cannot be located in that text is dropped, never
guessed at.

- **Rather than:** a model carrying its own altered text.
- **Gains:** bookmarks, the resume position, click-to-seek, highlighting and
  the audio cache all share one coordinate system that nothing can shift.
- **Costs:** a block that cannot be placed is lost from the structure; its
  loss counts against the confidence check below.

### Structure only when it is trusted

The structured model is kept only when it accounts for nearly all of the text
and finds real body content. Otherwise the book is read as one plain,
unstructured document through the same code path.

- **Rather than:** the far lower bar used while the model only drove the
  display. Once it decided what is spoken, a model covering part of a book
  would have read only that part aloud without a sign of the rest.
- **Gains:** a failed extraction costs structure, never text. The real books
  measured sit well clear of the line.
- **Costs:** a book just under the line loses its chapters entirely.

### Shown and spoken are one policy

Each kind of block says once whether it is displayed and whether it is
spoken. Page numbers, running heads and contents entries are neither; code
and the back-of-book index are shown but never read aloud.

- **Rather than:** the pane and the narrator each deciding.
- **Gains:** a folio the reader never sees is never read; the hardback's
  index, eleven thousand characters of names and page numbers, is no longer
  narrated.
- **Costs:** none recorded.

### A PDF's layout is evidence

A PDF is read with its fonts, weights and positions, not as flat text.
Headings are found by size, folios by their margin, running heads by
repeating across pages. The running heads and margin folios are then removed
from the text itself.

- **Rather than:** flattened text with guesses laid over it.
- **Gains:** furniture can be neither indexed, narrated nor displayed; the
  text and the structure describe the same book.
- **Costs:** a book's identity is a hash of its text, so a change to what is
  stripped gives a PDF a new identity and its resume position and ideas map
  start again.

### Headings a book never marked up, found in order of trust

A book's own heading tags come first. Where it has none, the chapter names
in its navigation table are found in the text. Where that is missing too, a
line naming a numbered division ("Chapter 12", "PART I") or one of the few
English never numbers ("Prologue") counts. Each applies only where the one
above found nothing.

- **Rather than:** one rule for every book; treating a wholly emphasised line
  as a heading, which measured as little better than a coin toss and dragged
  the keyword rule's precision down with it.
- **Gains:** Kindle conversions that state no headings gain a chapter spine;
  every EPUB that states its own is untouched.
- **Costs:** a book whose chapters carry only prose names and no navigation
  table is left without chapters rather than half recognised.

### Running headers and indented bodies are recognised, not read

A line repeated at the top of a Kindle book's documents is furniture when it
is the book's own title or when it leads most of the documents. A quotation
tag covering more of a book than plain paragraphs do is indentation, so the
book is read as prose.

- **Rather than:** a fixed proportion to tune; reading a repeated line as
  furniture on repetition alone, which measured over a set of real books
  would also have taken a chapter opening and chapter numbers.
- **Gains:** one book stopped hearing its title on every page; another
  stopped rendering entirely in italic. Both rules are comparisons, so there
  is nothing to tune.
- **Costs:** a book that genuinely quotes more than it narrates would be read
  as prose; none has been seen.

### A contents list at the back is not the front

A contents list counts as front matter only where most of the book follows
it.

- **Rather than:** taking the last contents entry anywhere in the book, which
  started one book past its own end.
- **Gains:** a book that keeps its contents at the back still has a body.
- **Costs:** none recorded.

### Kindle books go through Calibre, kept apart from NarrateX

Kindle formats are converted to EPUB by Calibre, when it is installed. Every
call goes through one function that strips NarrateX's own Qt settings from
the child's environment and asks Windows for no console window.

- **Rather than:** a Kindle reader of NarrateX's own; letting the child
  inherit the parent's environment, which made Calibre load NarrateX's Qt
  plugins and crash from a packaged build.
- **Gains:** Kindle books open from the installed application; no black
  window flashes past.
- **Costs:** Calibre is an optional extra the reader installs; each
  conversion takes seconds.

### A book with no text says so

A book that opens cleanly but holds no text is refused with a message
saying its pages are probably pictures.

- **Rather than:** an empty reader and silence; recognising characters in
  the pictures.
- **Gains:** the reader knows why nothing is there.
- **Costs:** scanned books are not read.

### Opening a book happens in another process

Parsing, structure, chapters and the cover are worked out in a separate
process; the window waits on the answer without working. The formatting of
the pane is then applied in one batch with drawing suspended.

- **Rather than:** a worker thread, which still froze the window because the
  parse is pure Python holding the interpreter lock; formatting the visible
  pane block by block, which took many seconds on the largest book.
- **Gains:** the largest book measured loads in a few seconds with the window
  live throughout; formatting the pane became near instant.
- **Costs:** a second composition root for the child process; the cost of
  starting an interpreter on every open.

## Narration

### Next and Previous step by chapters

Next and Previous Chapter move between a book's major divisions, ranked from
the heading levels that book actually uses, with front matter excluded
before ranking. Every section stays listed in the Sections dialog. The
status line names the chapter and how far through it the reader is.

- **Rather than:** stopping at every sub-heading; a fixed heading level,
  when a chapter is level 3 in one book and level 2 in another; a count of
  text fragments.
- **Gains:** on the largest book measured the stops fell from over a thousand
  to the chapters a reader would name; the status answers a question a
  listener has.
- **Costs:** a sub-heading is reached through Sections rather than by
  pressing Next.

### Shouted words are read as words

Only an initialism the author marked with stops, such as U.K., is spelled
out. A run of capitals is left for the voice engine, which already tells an
initialism from a word.

- **Rather than:** spelling out any short run of capitals, which in one novel
  fired hundreds of times, only a small fraction of them real initialisms.
- **Gains:** a scream in capitals is read as a scream.
- **Costs:** an undotted initialism the engine reads badly is read badly.

### Separator lines are not spoken

A line of nothing but dashes, underscores or asterisks is never synthesised.

- **Rather than:** passing it to the voice, which produces silence a listener
  hears as a stall.
- **Gains:** scene breaks no longer sound like a fault.
- **Costs:** none recorded.

### Seeking lands on a chunk

Clicking in the text restarts narration from the nearest chunk boundary.

- **Rather than:** seeking inside the audio by time.
- **Gains:** the highlight, the resume position and the audio all agree on
  where the reader is.
- **Costs:** a click cannot land mid-sentence inside a chunk.

### A place is kept only once listening has begun

The resume position is saved on pause, stop and exit, though only once at
least one chunk has actually played. A click to seek saves it at once; a
narration failure saves it before reporting the error.

- **Rather than:** saving whenever a book is opened.
- **Gains:** opening a book to look at it does not move the place; a failure
  never sends the reader back to the start.
- **Costs:** none recorded.

### No voice is chosen for the reader

The voice picker starts empty. When a book loads, an amber ring flashes until
the picker is touched; Play without a voice asks for one. Synthesis of the
opening chunks starts as soon as a voice is chosen.

- **Rather than:** a default voice picked silently.
- **Gains:** the voice heard is one the reader chose; the first Play after
  choosing is near instant.
- **Costs:** one choice to make before the first Play.

### Synthesis runs ahead; it stops when told

Synthesis works a bounded number of chunks ahead of playback. A worker
handing over a chunk waits in short slices, checking for a stop between
them; the pre-synthesis at voice selection answers to its own cancel signal.

- **Rather than:** synthesising each chunk as it is needed; a blocking hand
  over that could wait for ever on a queue nobody was reading; sharing the
  stop signal, which left pre-synthesis abandoning its first chunk on every
  book.
- **Gains:** fewer gaps between chunks; stop really stops; a test fails any
  test that leaves a narration worker alive.
- **Costs:** more ceremony around every thread.

### Synthesised audio lasts one session

The audio cache is cleared at every launch unless a development setting says
otherwise. Its key carries a version that changes whenever what is spoken
changes.

- **Rather than:** keeping synthesised audio between launches.
- **Gains:** the cache never outgrows one session's listening; audio made
  under old rules is never played.
- **Costs:** the opening of a book is synthesised again after a relaunch.

## The bookshelf

### Books are read where they sit

The shelf reads the folders the reader names and never copies, moves,
renames, edits or deletes a book file, nor writes anything inside those
folders. Its index and thumbnails live in NarrateX's own storage.

- **Rather than:** a managed library directory; sidecar files beside the
  books.
- **Gains:** the reader's collection is never at risk from NarrateX.
- **Costs:** what NarrateX knows about a book lives only in NarrateX.

### No process is started to read the shelf

A scan and the covers it draws never start a process. Kindle titles, authors
and covers are read straight from the file's own header; a test fails if any
process is started for any format.

- **Rather than:** a Calibre conversion per book, which over the reference
  library of a few thousand files measured close to an hour.
- **Gains:** the direct read covered the same library in seconds and
  recovered most of its covers.
- **Costs:** a reader of the Kindle container to maintain; a format without
  that container reaches a cover only through a sidecar image.

### What a book says about itself, in order

Title and author come from a Calibre sidecar first, then the file's own
header, then the filename. Covers come from an image beside the book, then
the file itself. The sidecar is never asked about the cover.

- **Rather than:** trusting the sidecar's cover field, which none of the
  sidecars measured filled in while hundreds of books had an image beside
  them.
- **Gains:** each source is asked the question it actually answers.
- **Costs:** none recorded.

### A filename is read by the library around it

Where a filename puts a person and a title either side of a dash with
nothing to say which is which, the side that has more books behind it across
the library is taken as the author.

- **Rather than:** one fixed filename convention.
- **Gains:** author-first filenames sort under the author.
- **Costs:** an author whose every file is written that way cannot be learned,
  because there is nothing to learn from.

### Two identities for a book

The shelf knows a file by its path, size and modified time. Narration knows
a book by a hash of its text. The two are joined when a book is first
opened, since only a full parse can produce the second.

- **Rather than:** parsing every book during a scan.
- **Gains:** a scan stays cheap; a book's progress follows the narration's
  own record rather than a copy.
- **Costs:** a moved or renamed file is a new entry to the shelf.

### One work, its cheapest format

A book held in several formats appears once and opens in the format that
costs least to read: EPUB, PDF and the text formats before any Kindle format.

- **Rather than:** a tile per file.
- **Gains:** a library holding both .mobi and .azw3 copies shows each book
  once; opening avoids a conversion wherever it can.
- **Costs:** the format opened is not chosen by the reader.

### A scan reconciles; an unreachable drive removes nothing

A rescan re-reads only a file whose size or modified time changed. A folder
on a drive that is not connected keeps its books on the shelf and is named
to the reader.

- **Rather than:** rebuilding the index on every scan.
- **Gains:** a rescan of an unchanged library was measured at a fraction of a
  second, re-reading nothing; unplugging a drive costs nothing.
- **Costs:** a folder that is genuinely gone keeps its books on the shelf.

### The reader's own word survives everything

Genres the reader states are kept in a table of their own, apart from what
the scan derives. They outrank what the file says. The index lives with the
bookmarks, outside the cache that is cleared at launch.

- **Rather than:** one table, rebuilt by a scan.
- **Gains:** rebuilding what was scanned can never take the reader's work
  with it.
- **Costs:** two directories with two rules to keep apart.

### A settled genre catalogue

Genres are a fixed catalogue of main genres with styles under them, ported
in shape from Stellody. The subjects files state are mapped onto it; strings
that say nothing are dropped and unmatched ones reported. A work may carry
several genres. Books that state none get a choice of their own in the
filter.

- **Rather than:** offering whatever strings the files contain, which in the
  reference library were often authors, characters and places.
- **Gains:** a filter means the same thing every time.
- **Costs:** the alias table needs keeping up.

### Filing many books at once

The reader can file one book under a genre. Ctrl or Shift gathers several;
the whole gathering is then filed at once. The dialog opens on the genres
every gathered book already shares, since ticking replaces rather than adds.

- **Rather than:** one book at a time, which over a large library is not a
  task anyone completes.
- **Gains:** a library's filing can be done in a sitting.
- **Costs:** a click has to say what it means: a plain click opens, a
  modified click gathers.

### The shelf fills while the scan runs

A running scan hands the shelf a new batch only when both a number of
entries and a slice of time have passed since the last.

- **Rather than:** a count alone, which floods a cached walk; a clock alone,
  which leaves a walk over a sleeping drive motionless; an empty shelf until
  the end.
- **Gains:** books appear as they are found.
- **Costs:** a pacing rule to maintain.

### One scan at a time

A second scan while one runs is refused rather than queued.

- **Rather than:** a queue.
- **Gains:** two walks can never race to save the same index.
- **Costs:** a press during a scan does nothing but say so.

### Covers drawn, never built as widgets

The grid and the list are one view over one model in two modes, drawn by a
delegate. No tile is a live widget. Covers are read off the painting thread
and the decoded pictures held in a bounded cache.

- **Rather than:** a widget per tile; a second view for the list.
- **Gains:** a library of hundreds of works draws with no tile widgets at
  all; switching between grid and list loses and reorders nothing.
- **Costs:** every visual detail of a tile is drawing code.

### A thumbnail is made when a tile needs it

Reduced covers are made the first time a tile is drawn rather than during a
scan. They are kept lossless in the cache directory.

- **Rather than:** a cover pass during the scan, measured at many times the
  cost of the scan itself, for a library of which a reader sees a screenful.
- **Gains:** the shelf appears sooner; covers already cached redraw almost
  at once.
- **Costs:** the cache is far larger than a lossy one would be.

### The shelf sits beside the open control, inside the window

The shelf and the reader are two pages of the main window; the open control
stays. While narration holds a book the shelf refuses to open another, as
the open control always has; it says to pause or stop first.

- **Rather than:** a separate shelf window; replacing the open control,
  which would strand a book outside every shelf folder.
- **Gains:** opening a book changes the page, not the window; the shelf
  cannot undo background work in exchange for silence.
- **Costs:** none recorded.

### One click opens a book

A single click on a tile opens it; double-click is not connected.

- **Rather than:** double-click, which with both connected opened the same
  book twice.
- **Gains:** one gesture, one book.
- **Costs:** none recorded.

## The interface

### Pictures are artwork, never emoji

Every picture control shows shipped artwork, built through one factory that
gives each button the same box, the same ring and a tooltip naming what it
does. A structural test keeps emoji out of the source.

- **Rather than:** emoji, which rendered differently on every platform (the
  flags came out as boxed letters on Windows) and sat off centre.
- **Gains:** the buttons match by construction.
- **Costs:** every new control needs artwork drawn for it.

### One ring language

An enabled control rings green on hover and keyboard focus; a disabled one
rings red until it is enabled again; amber asks for attention. The colours
are named once and the shelf's drawing reads the same constants.

- **Rather than:** the mixed purple, white and amber scheme it replaced.
- **Gains:** the state of any control can be read at a glance, dialogs and
  the setup program included.
- **Costs:** every new control has to join the scheme.

### Red when a press would do nothing

The chapter buttons ring red whenever pressing them would do nothing, such
as after Stop or with no voice chosen. One function answers where a press
would go, for the jump and for the button alike.

- **Rather than:** enabled buttons that quietly did nothing.
- **Gains:** a control that looks usable is usable.
- **Costs:** the state has to be refreshed on every narration change.

### Nothing is focused on launch

An invisible stop takes the first focus and drops out of the ring, so the
window opens with no ring showing; the first Tab lands on a real control.

- **Rather than:** Qt's default of focusing the first control.
- **Gains:** a neutral window before the reader has touched anything.
- **Costs:** none recorded.

### One keyboard ring

Tab and Right step forward, Shift+Tab and Left step back, the ring wraps and
follows the visual order. Enter presses the focused button; Down opens a
closed dropdown and Space or Tab commits from an open one. The arrows move
the volume in fixed steps.

- **Rather than:** Qt's defaults, where arrows changed a closed dropdown
  silently and wandered focus by geometry.
- **Gains:** the whole window works without a mouse.
- **Costs:** every new control needs its place in the ring.

### A pane is never a stop and never wears a ring

Panels and frames never take focus. A text view is a Tab stop only while it
overflows, a click never focuses it and no stylesheet rings it. A dialog
opens on its first control. Guards walk every window and scan every
stylesheet, each proved by planting the old fault.

- **Rather than:** a green outline round a whole page.
- **Gains:** a ring always means a control that can be acted on.
- **Costs:** none recorded.

### Long help reads itself; the book does not

The Guide and the licence texts scroll themselves gently and pause at any
scroll, click or key. The reading pane never does: it keeps the narration's
pace.

- **Rather than:** static pages; a scrolling book that fights the
  highlight.
- **Gains:** long text can be read hands free.
- **Costs:** none recorded.

### Muted is the volume at zero

The speaker button drops the volume to zero and brings back the last
audible level on a second press.

- **Rather than:** a mute flag beside the volume.
- **Gains:** one number answers whether NarrateX is audible.
- **Costs:** none recorded.

### Tooltips show while another program has focus

Every top-level window is marked to show tooltips when inactive, by one
filter installed by both the application and the setup program.

- **Rather than:** Qt's default of tooltips over the active window only.
- **Gains:** hovering a button always says what it does.
- **Costs:** none recorded.

### Removing a book forgets it and never touches the file

Remove current book deletes NarrateX's bookmarks, resume position, ideas map
and cached audio for that book, after a confirmation that names the book and
defaults to Cancel. The file stays on disk.

- **Rather than:** deleting the file; leaving no way to forget.
- **Gains:** a fresh start on one book costs nothing on disk.
- **Costs:** none recorded.

### A press never ends in a traceback

Transport controls catch anything unexpected at the slot, log it and say so
in the status line.

- **Rather than:** an error escaping to the console from a button.
- **Gains:** a click can never crash the window.
- **Costs:** a fault shows as a status message; the log holds the detail.

### One copy runs

A second launch asks the running copy to raise its window, then exits.

- **Rather than:** several copies narrating at once.
- **Gains:** one narrator, one set of files being written.
- **Costs:** none recorded.

## Building and installing

### PyInstaller, a folder rather than one file

The application is built with PyInstaller as a folder holding the
executable and its libraries. The Windows setup program is a separate single
file carrying the application as a payload.

- **Rather than:** a single-file application that unpacks itself on every
  launch.
- **Gains:** a fast, predictable build and start.
- **Costs:** the installed application is a folder of many files.

### Hidden imports come from the wiring table

The packagers derive the modules PyInstaller cannot see from the same table
the application wires itself from. The generated spec files are not kept in
the repository.

- **Rather than:** hand-copied import lists in each packager, which drifted
  and shipped a build that died at startup; committed spec files carrying one
  machine's paths.
- **Gains:** a new module cannot be forgotten by one platform's build.
- **Costs:** the packagers import the application's own wiring.

### A supported Python, checked first

Running from source checks the interpreter before anything else and exits
with a message outside Python 3.10 to 3.12. A packaged build skips the check.

- **Rather than:** a bare import error on an interpreter Kokoro publishes no
  wheels for.
- **Gains:** the cause and the fix are in the first line the developer sees.
- **Costs:** the macOS build environment runs on 3.13, so there it builds the
  disk image but cannot run the source.

### Installed for one user

On Windows the setup program installs into the user's own folders and
registry. Uninstalling removes the user's data too unless the setup program
was told to keep it; the confirmation names the bookmarks and the shelf when
they will go and says the data is kept when it will stay.

- **Rather than:** a machine-wide install; leaving data behind by default.
- **Gains:** no administrator prompt; a default uninstall leaves nothing.
- **Costs:** each account installs separately; a default uninstall takes the
  bookmarks and shelf genres with it.

### A setup program of its own

Install, repair and removal are one bespoke program wearing the
application's look. Unpacking and repair report progress weighted by bytes.
A payload entry that would land outside the install folder is refused. A
locked file is waited on briefly; a lock that outlasts the wait names the
process holding it.

- **Rather than:** a generic installer.
- **Gains:** a bar that moves honestly; a repair that survives the moment
  after NarrateX closes.
- **Costs:** the setup program is NarrateX's own to maintain.

### Builds that check themselves

The macOS application and its disk image are both notarised and stapled,
since a ticket on the disk image alone leaves the copied-out application
without one. The build stops when the environment lacks anything the
requirements ask for. Linux ships a Flatpak, which bundles the audio library,
the phonemiser and the language model, beside a plain folder build.

- **Rather than:** stapling the disk image only; trusting PyInstaller, which
  only warns about a missing package and so let a stale environment build,
  sign and notarise an application that died at launch.
- **Gains:** a stale environment fails the build instead of the user's first
  launch.
- **Costs:** an Apple developer account; four requirements files, because
  the native audio dependencies differ by platform.

### GPL with an LGPL interface, plus a commercial licence

The application is GPL-3.0 and its reusable interface layer LGPL-3.0. A
commercial licence for the author's own code is offered separately. The
setup program's licence dialog says its text covers the setup program only.

- **Rather than:** one licence for everything.
- **Gains:** the interface can be reused under the terms Qt itself carries.
- **Costs:** two licence files to keep straight.

### A website without dates, honest about the voices

The site is published from its own directory, carries no dates and leads
with long-form structure rather than the number of voices. The home page
makes the case and points the way; the features have a page of their own. It
says the voices are less natural than the cloud services and what that buys.
Stylesheet links carry a hash of their content.

- **Rather than:** a version chip with a release date; leading with the
  number of voices, which invites the one comparison cloud services win.
- **Gains:** nothing on the site goes stale by the calendar; a browser never
  pairs a new page with an old stylesheet.
- **Costs:** the pages have to be stamped from the source before each build.

## Engineering

### Layers with few places where they meet

The code is split into domain, application, infrastructure and interface,
each depending only inward. Wiring happens only in a few named composition
roots, the book-loading child among them. Structural tests hold both rules.

- **Rather than:** convention alone.
- **Gains:** the rules about books and narration can be tested with no Qt,
  no audio device and no disk.
- **Costs:** more modules and more explicit wiring.

### Complete coverage where it can mean something

The suite fails below 100% coverage of the application package. The audio
devices, the voice engine, the bookmark and preference stores and the Qt
windows are among the named exclusions; the entry point is outside the
measured source altogether.

- **Rather than:** a figure over everything, met by standing in for the
  very hardware worth testing.
- **Gains:** the whole domain and application layers are fully covered.
- **Costs:** device and window code relies on targeted tests; two guards that
  cannot fire by construction stay uncovered and say why.

### Small modules, never nearly full

No module may exceed a fixed line cap, nor sit in the last few lines below
it: a file that reaches that band is cut well below the cap rather than
trimmed. Build scripts are exempt by name.

- **Rather than:** a cap alone, which let a file sit one line under it and
  fail on the next unrelated edit.
- **Gains:** modules split at real seams, once.
- **Costs:** many small files.

### Every value has one home

The version lives in one file that the package, the packagers and the site
all read. Every icon size is generated from one master. The recognised book
formats, the ring colours and the division words each have one declaration.

- **Rather than:** copies written where they are needed.
- **Gains:** a change is made once and cannot drift.
- **Costs:** static files have to be stamped or generated from the source.

### Three linters

Formatting is black's; flake8 and ruff both lint. Ruff keeps its default
rules only.

- **Rather than:** flake8 alone, which missed dead imports ruff found; turning
  on ruff's wider rule families in the same step.
- **Gains:** genuinely dead code is caught.
- **Costs:** three tools to keep clean from the repository root.

### A swallowed failure says what it degrades to

Every broad exception handler on the startup path and in the setup program
states its fallback and why it stays broad.

- **Rather than:** handlers that caught everything and explained nothing.
- **Gains:** a reader can tell a deliberate degrade from an accident.
- **Costs:** none recorded.

### Tests wait for answers, not for time

A test that starts a worker waits on the worker's own answer, with a
deadline that reports itself, rather than polling for a fixed time.

- **Rather than:** a fixed short poll, which failed most runs on a busy
  machine and blamed the wrong code.
- **Gains:** a slow machine makes a test slower, not red.
- **Costs:** none recorded.
