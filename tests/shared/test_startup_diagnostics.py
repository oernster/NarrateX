"""Tests for startup diagnostics helpers."""

from __future__ import annotations

import pytest

from voice_reader.shared.startup_diagnostics import (
    enforce_supported_python,
    running_in_flatpak,
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

    def test_a_managed_runtime_skips_the_check(self) -> None:
        # The Flatpak runs on 3.13 with pre-built wheels, so the guard whose
        # premise is venv resolution must not fire there.
        written: list[str] = []

        enforce_supported_python(
            (3, 13, 0), write=written.append, in_managed_runtime=True
        )

        assert written == []


class TestRunningInFlatpak:
    def test_it_is_true_when_the_sandbox_marker_exists(self) -> None:
        assert running_in_flatpak(path_exists=lambda p: p == "/.flatpak-info")

    def test_it_is_false_without_the_marker(self) -> None:
        assert not running_in_flatpak(path_exists=lambda _p: False)
