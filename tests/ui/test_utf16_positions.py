"""Tests for Python index to Qt position translation."""

from __future__ import annotations

from voice_reader.ui._utf16_positions import Utf16PositionMap

EMOJI = "\U0001f449"  # a non-BMP character, two UTF-16 code units


class TestPlainText:
    def test_text_without_wide_characters_is_an_identity(self) -> None:
        mapping = Utf16PositionMap.for_text("plain ascii text")

        assert mapping.is_identity is True

    def test_identity_text_translates_unchanged(self) -> None:
        mapping = Utf16PositionMap.for_text("plain ascii text")

        for index in range(len("plain ascii text") + 1):
            assert mapping.to_qt(index) == index
            assert mapping.to_index(index) == index

    def test_accented_characters_are_still_single_unit(self) -> None:
        # Latin-1 and most scripts sit inside the BMP.
        mapping = Utf16PositionMap.for_text("café naïve Ωμέγα")

        assert mapping.is_identity is True


class TestWideCharacters:
    def test_a_wide_character_is_detected(self) -> None:
        mapping = Utf16PositionMap.for_text(f"a{EMOJI}b")

        assert mapping.is_identity is False

    def test_positions_before_a_wide_character_are_unchanged(self) -> None:
        mapping = Utf16PositionMap.for_text(f"ab{EMOJI}cd")

        assert mapping.to_qt(0) == 0
        assert mapping.to_qt(1) == 1
        assert mapping.to_qt(2) == 2

    def test_positions_after_a_wide_character_shift_by_one(self) -> None:
        mapping = Utf16PositionMap.for_text(f"ab{EMOJI}cd")

        assert mapping.to_qt(3) == 4
        assert mapping.to_qt(4) == 5

    def test_each_wide_character_adds_another_unit(self) -> None:
        mapping = Utf16PositionMap.for_text(f"a{EMOJI}b{EMOJI}c")

        assert mapping.to_qt(0) == 0
        assert mapping.to_qt(2) == 3
        assert mapping.to_qt(4) == 6

    def test_translation_round_trips(self) -> None:
        text = f"start {EMOJI} middle {EMOJI} end"
        mapping = Utf16PositionMap.for_text(text)

        for index in range(len(text) + 1):
            assert mapping.to_index(mapping.to_qt(index)) == index

    def test_the_end_of_the_text_accounts_for_every_wide_character(self) -> None:
        text = f"a{EMOJI}b{EMOJI}"
        mapping = Utf16PositionMap.for_text(text)

        assert mapping.to_qt(len(text)) == len(text) + 2


class TestAgainstQt:
    def test_it_matches_what_qt_actually_reports(self, qapp) -> None:
        # The claim this module exists for, checked against Qt itself rather
        # than against my own arithmetic.
        from PySide6.QtGui import QTextDocument

        text = f"alpha {EMOJI} beta {EMOJI} gamma"
        document = QTextDocument()
        document.setPlainText(text)
        mapping = Utf16PositionMap.for_text(text)

        # characterCount() is the UTF-16 length plus one for the final block.
        assert document.characterCount() - 1 == mapping.to_qt(len(text))

    def test_a_cursor_lands_on_the_expected_text(self, qapp) -> None:
        from PySide6.QtGui import QTextCursor, QTextDocument

        text = f"alpha {EMOJI} beta"
        document = QTextDocument()
        document.setPlainText(text)
        mapping = Utf16PositionMap.for_text(text)

        start = text.index("beta")
        cursor = QTextCursor(document)
        cursor.setPosition(mapping.to_qt(start))
        cursor.setPosition(
            mapping.to_qt(start + len("beta")),
            QTextCursor.MoveMode.KeepAnchor,
        )

        assert cursor.selectedText() == "beta"

    def test_without_translation_the_cursor_would_be_wrong(self, qapp) -> None:
        # Demonstrates the bug the translation fixes.
        from PySide6.QtGui import QTextCursor, QTextDocument

        text = f"alpha {EMOJI} beta"
        document = QTextDocument()
        document.setPlainText(text)

        start = text.index("beta")
        cursor = QTextCursor(document)
        cursor.setPosition(start)
        cursor.setPosition(start + len("beta"), QTextCursor.MoveMode.KeepAnchor)

        assert cursor.selectedText() != "beta"
