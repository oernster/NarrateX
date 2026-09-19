"""The genres a book can be filed under: mains with styles, plus the aliases.

**Two levels rather than one flat list.** Space Opera is a kind of science
fiction; Police Procedural is a kind of crime writing. A flat list puts each
beside its own parent as though they were peers, so a reader asking for
everything science-fictional cannot have it.

**Curated to this library, not taken whole from anywhere.** The vocabulary was
measured on 2026-09-19 over 2784 Kindle files holding 1025 distinct subject
strings. A raw subject list is not a filter anybody can use: the same shelf is
stated six ways (`Horror`, `Horror - General`, `Fiction - Horror`,
`Horror fiction`, `Horror tales`, `Horror & Ghost Stories`), `General` appears
1389 times and says nothing; one file is filed under a release group's
signature. The alias table below is what turns that into a catalogue.

**Rulings, Oliver, 2026-09-19.** Each overrides what the raw counts alone would
have chosen, so each is written down rather than remembered:

- **Crime is the main; Mystery is a style beneath it.** The library says
  `Mystery` 614 times against `Crime` 97, so the counts pointed the other way.
  Crime is the name a reader here reaches for. Mystery keeps every alias it had.
- **Criticism is a main of its own**, not a style under Literary. 252 files
  reach it and nearly all of it is writing ABOUT an author rather than by them,
  so a reader choosing something to listen to tonight should not be handed a
  critical study filed as Literary.
- **Thriller absorbs Suspense.** `Suspense` at 607 and `Thrillers` at 364 fold
  into one main.
- **Psychological stays under Horror.** The fold most likely to want revisiting
  once the shelf can be looked at; revisiting it costs one line of ALIASES.
- **A style with no files is offered anyway** where the genre plainly exists and
  the library's tags simply do not say it. Absence from the tags is a fact about
  the tags, not about the shelf.

Measured coverage of this catalogue: 1483 of the 1533 files stating any subject
reach at least one genre, which is 96.7%.
"""

from __future__ import annotations

# Each main with the styles beneath it. Order is the order a reader is offered.
CATALOGUE: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Science Fiction",
        (
            "Space Opera",
            "Hard Science Fiction",
            "Dystopian",
            "Time Travel",
            "Post-Apocalyptic",
            "Military Science Fiction",
            "First Contact",
        ),
    ),
    (
        "Fantasy",
        ("Epic Fantasy", "Urban Fantasy", "Sword and Sorcery", "Magical Realism"),
    ),
    (
        "Horror",
        ("Ghost Stories", "Supernatural", "Occult", "Psychological Horror", "Vampires"),
    ),
    (
        "Crime",
        (
            "Mystery",
            "Detective",
            "Police Procedural",
            "Private Investigators",
            "Women Sleuths",
            "Serial Killers",
            "Cosy Mystery",
        ),
    ),
    (
        "Thriller",
        (
            "Espionage",
            "Legal Thriller",
            "Medical Thriller",
            "Techno-thriller",
            "Political Thriller",
            "Conspiracy",
        ),
    ),
    ("Adventure", ()),
    ("Historical", ()),
    ("Romance", ()),
    ("Literary", ("Classics", "Satire", "Short Stories")),
    ("Criticism", ()),
    ("Poetry", ()),
    ("Children and Young Adult", ()),
    ("Popular Science", ()),
    ("History", ()),
    ("Biography", ()),
    ("True Crime", ()),
    ("Humour", ()),
    ("Western", ()),
    ("War", ()),
)

# A raw subject reaches a name when its folded form matches the name itself or
# one of these. Folding removes case, punctuation and spacing entirely, so
# "Horror - General" arrives here as "horrorgeneral".
ALIASES: dict[str, tuple[str, ...]] = {
    "Science Fiction": (
        "sciencefiction",
        "sf",
        "scifi",
        "sciencefictionfantasy",
        "sciencefictionandfantasy",
        "americansciencefictionandfantasy",
        "sciencefictiongeneral",
        "fictionsciencefiction",
        "sciencefictionadventure",
        "sciencefictionshortstories",
        "lifeonotherplanets",
        "interplanetaryvoyages",
        "robots",
        "geneticengineering",
    ),
    "Space Opera": ("spaceopera", "sciencefictionspaceopera"),
    "Hard Science Fiction": (
        "hightech",
        "sciencefictionhightech",
        "hardsciencefiction",
        "technological",
    ),
    "Dystopian": ("dystopia", "dystopian"),
    "Time Travel": ("timetravel",),
    "Post-Apocalyptic": ("postapocalyptic", "apocalyptic"),
    "Military Science Fiction": ("militarysciencefiction",),
    "First Contact": ("firstcontact",),
    "Fantasy": (
        "fantasyfiction",
        "fantasygeneral",
        "fictionfantasy",
        "fantasyseries",
        "fantasticfiction",
        "magic",
        "wizards",
        "midkemiaimaginaryplace",
    ),
    "Epic Fantasy": ("epic", "fantasyepic", "epicfantasy"),
    "Urban Fantasy": ("urbanfantasy",),
    "Sword and Sorcery": ("swordandsorcery",),
    "Magical Realism": ("magicalrealism",),
    "Horror": (
        "horrorgeneral",
        "fictionhorror",
        "horrortales",
        "horrorfiction",
        "horrorstories",
        "americanhorrorfiction",
        "horrorghoststories",
        "goodandevil",
    ),
    "Ghost Stories": ("ghoststories",),
    "Occult": ("occult",),
    "Psychological Horror": (
        "psychological",
        "psychologicalfiction",
        "fictionpsychologicalsuspense",
    ),
    "Crime": ("murder",),
    "Mystery": (
        "mysteryfiction",
        "fictionmystery",
        "americanmystery",
        "mysterydetective",
        "mysteryanddetectivestories",
        "mysteryandsuspensefiction",
        "detectiveandmysterystories",
    ),
    "Detective": ("detectivegeneral",),
    "Police Procedural": (
        "policeprocedural",
        "detectivepoliceprocedural",
        "police",
        "africanamericanpolice",
        "policepsychologists",
    ),
    "Private Investigators": ("privateinvestigators", "privateinvestigator"),
    "Women Sleuths": ("womensleuths",),
    "Serial Killers": ("serialmurders", "serialkillers"),
    "Cosy Mystery": ("cozymystery", "cosymystery"),
    "Thriller": (
        "thrillers",
        "suspense",
        "suspensefiction",
        "intrigue",
        "action",
        "actionadventure",
    ),
    "Espionage": ("fictionespionage", "espionage", "terrorism"),
    "Legal Thriller": ("legalthriller", "legal"),
    "Medical Thriller": ("medicalthriller", "medical"),
    "Techno-thriller": ("technothriller",),
    "Political Thriller": ("political", "politicalthriller"),
    "Conspiracy": ("conspiracy",),
    "Adventure": ("adventurestories", "adventurefiction"),
    "Historical": ("historicalgeneral", "historicalfiction", "fictionhistorical"),
    "Literary": (
        "literaryfiction",
        "literature",
        "modernfiction",
        "contemporaryfictionpostc1945",
    ),
    "Classics": ("literatureclassics", "classic"),
    "Short Stories": ("shortstories", "shortstoriessingleauthor"),
    "Criticism": ("literarycriticism", "criticism", "criticismandinterpretation"),
    "Children and Young Adult": (
        "juvenilefiction",
        "juvenilenonfiction",
        "childrensbooks",
        "childrenyoungadultgr79",
        "youngadult",
    ),
    "Popular Science": ("science", "popularscience"),
    "Biography": ("biographyautobiography", "autobiography", "memoir"),
    "True Crime": ("truecrime",),
    "Humour": ("humorousfiction", "humor", "humour"),
    "Western": ("westerns",),
    "War": ("military", "warfiction", "warandmilitary"),
}

# Subjects that say nothing about what a book is. Dropped in silence, because
# reporting 1389 sightings of "General" as unmatched teaches nobody anything.
SAYS_NOTHING: frozenset[str] = frozenset(
    {
        "fiction",
        "fictiongeneral",
        "general",
        "american",
        "modern",
        "contemporary",
        "nonclassifiable",
        "nonfiction",
        "largetypebooks",
        "unknown",
        "books",
        "ebook",
        "english",
        "genrefiction",
        "fictionandliterature",
        "popularculture",
        "miscellaneous",
    }
)

# Subjects naming how a book came to exist rather than what it is. Also
# dropped; kept apart from SAYS_NOTHING so the reason stays legible.
NOT_A_GENRE: frozenset[str] = frozenset(
    {
        "mediatiein",
        "mediatieingeneral",
        "movie",
        "movietiein",
        "tvtieins",
        "audiobook",
        "omnibus",
        "boxedset",
        "anthology",
        "collection",
    }
)

MAINS: tuple[str, ...] = tuple(main for main, _styles in CATALOGUE)

STYLE_PARENT: dict[str, str] = {
    style: main for main, styles in CATALOGUE for style in styles
}

NAMES: frozenset[str] = frozenset(MAINS) | frozenset(STYLE_PARENT)
