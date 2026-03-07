from __future__ import annotations

from voice_reader.domain.services.reading_start_service import ReadingStartService


def test_detect_start_prefers_chapter_one() -> None:
    text = (
        "Title\n\n"
        "Copyright 2020\n\n"
        "Contents\n"
        "Chapter 1 .... 1\n"
        "Chapter 2 .... 9\n\n"
        "CHAPTER 1\n"
        "This is the beginning of the story."
    )
    svc = ReadingStartService()
    start = svc.detect_start(text)
    assert start.reason == "Detected Chapter 1"
    assert text[start.start_char :].lstrip().startswith("This is the beginning")


def test_detect_start_prefers_introduction() -> None:
    text = (
        "Title\n\n"
        "CONTENTS\n"
        "Introduction .... v\n"
        "Chapter 1 .... 1\n\n"
        "INTRODUCTION\n"
        "This is the introduction.\n\n"
        "CHAPTER 1\n"
        "Then chapter one."
    )
    svc = ReadingStartService()
    start = svc.detect_start(text)
    assert start.reason == "Detected Introduction"
    assert "INTRODUCTION" not in text[start.start_char :].splitlines()[0]
    assert text[start.start_char :].lstrip().startswith("This is the introduction")


def test_detect_start_skips_outline_to_first_prose() -> None:
    text = (
        "INTRODUCTION\n"
        "1\n"
        "Introduction\n"
        "1.1\n"
        "About me\n"
        "1.1.1\n"
        "Perspective\n"
        "I am a CTO-level technical leader focused on reducing risk.\n"
        "More prose follows.\n"
    )
    svc = ReadingStartService()
    start = svc.detect_start(text)
    assert "I am a CTO-level" in text[start.start_char :]


def test_detect_start_ignores_toc_chapter_one_line() -> None:
    text = (
        "Contents\n"
        "Chapter 1 .... 1\n"
        "Chapter 2 .... 9\n\n"
        "CHAPTER 1\n"
        "Real content."
    )
    svc = ReadingStartService()
    start = svc.detect_start(text)
    assert text[start.start_char :].lstrip().startswith("Real content")


def test_detect_start_uses_prologue_when_no_chapter_one() -> None:
    text = (
        "Some Title\n\n"
        "Contents\n"
        "Prologue .... i\n"
        "Chapter 1 .... 1\n\n"
        "PROLOGUE\n"
        "It begins."
    )
    svc = ReadingStartService()
    start = svc.detect_start(text)
    assert start.reason == "Detected Prologue"
    assert text[start.start_char :].lstrip().startswith("It begins")


def test_detect_start_skips_toc_when_present() -> None:
    text = (
        "Title\n\n"
        "TABLE OF CONTENTS\n"
        "1. First .... 1\n"
        "2. Second .... 5\n"
        "\n"
        "1.\n"
        "First\n"
        "Real content starts here."
    )
    svc = ReadingStartService()
    start = svc.detect_start(text)
    assert start.start_char > 0
    assert "contents" not in text[start.start_char :].lower()[:50]


def test_detect_start_defaults_to_beginning_when_no_markers() -> None:
    text = "Just a short text without headings."
    svc = ReadingStartService()
    start = svc.detect_start(text)
    assert start.start_char == 0
    assert start.reason == "Start at beginning"
