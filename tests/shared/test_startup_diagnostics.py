"""Tests for startup diagnostics helpers."""

from __future__ import annotations

import pytest

from voice_reader.shared.startup_diagnostics import (
    enforce_supported_python,
    unsupported_python_message,
)


class TestUnsupportedPythonMessage:
    def test_a_supported_interpreter_yields_no_message(self) -> None:
        assert unsupported_python_message((3, 11, 9)) is None

    def test_the_lower_bound_is_inclusive(self) -> None:
        assert unsupported_python_message((3, 10, 0)) is None

    def test_the_upper_bound_is_exclusive(self) -> None:
        # 3.13 is exactly the interpreter that cannot resolve requirements.txt.
        assert unsupported_python_message((3, 13, 0)) is not None

    def test_an_older_interpreter_is_rejected(self) -> None:
        assert unsupported_python_message((3, 9, 18)) is not None

    def test_the_message_names_the_interpreter_it_found(self) -> None:
        message = unsupported_python_message((3, 13, 11))

        assert message is not None
        assert "3.13" in message

    def test_the_message_states_the_supported_range(self) -> None:
        message = unsupported_python_message((3, 13, 0))

        assert message is not None
        assert "3.10" in message

    def test_the_message_gives_a_command_to_fix_it(self) -> None:
        message = unsupported_python_message((3, 13, 0))

        assert message is not None
        assert "venv" in message

    def test_the_message_explains_why(self) -> None:
        message = unsupported_python_message((3, 13, 0))

        assert message is not None
        assert "kokoro" in message


class TestEnforceSupportedPython:
    def test_a_supported_interpreter_passes_silently(self) -> None:
        written: list[str] = []

        enforce_supported_python((3, 11, 9), write=written.append)

        assert written == []

    def test_an_unsupported_interpreter_stops_the_program(self) -> None:
        written: list[str] = []

        with pytest.raises(SystemExit) as exit_info:
            enforce_supported_python((3, 13, 0), write=written.append)

        assert exit_info.value.code == 1

    def test_the_reason_is_reported_before_exiting(self) -> None:
        written: list[str] = []

        with pytest.raises(SystemExit):
            enforce_supported_python((3, 13, 0), write=written.append)

        assert len(written) == 1
        assert "3.13" in written[0]
