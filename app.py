"""Application entrypoint."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from voice_reader.application.services.device_detection_service import (
    DeviceDetectionService,
)
from voice_reader.application.services.narration_service import NarrationService
from voice_reader.application.services.tts_engine_factory import TTSEngineFactory
from voice_reader.application.services.voice_profile_service import VoiceProfileService
from voice_reader.domain.services.chunking_service import ChunkingService
from voice_reader.infrastructure.audio.audio_streamer import SoundDeviceAudioStreamer
from voice_reader.infrastructure.books.converter import CalibreConverter
from voice_reader.infrastructure.books.parser import BookParser
from voice_reader.infrastructure.books.repository import LocalBookRepository
from voice_reader.infrastructure.cache.filesystem_cache import FilesystemCacheRepository
from voice_reader.infrastructure.tts.voice_profile_repository import (
    FilesystemVoiceProfileRepository,
)
from voice_reader.shared.config import Config
from voice_reader.shared.logging_utils import configure_logging
from voice_reader.ui.main_window import MainWindow
from voice_reader.ui.ui_controller import UiController


def main() -> int:
    configure_logging(logging.INFO)
    log = logging.getLogger("app")

    project_root = Path(__file__).resolve().parent
    config = Config.from_project_root(project_root)
    config.ensure_directories()

    device = DeviceDetectionService().detect()
    log.info("Detected device: %s", device)

    # Infrastructure
    converter = CalibreConverter(temp_books_dir=config.paths.temp_books_dir)
    parser = BookParser()
    book_repo = LocalBookRepository(converter=converter, parser=parser)
    cache_repo = FilesystemCacheRepository(cache_dir=config.paths.cache_dir)
    voice_repo = FilesystemVoiceProfileRepository(voices_dir=config.paths.voices_dir)
    voice_service = VoiceProfileService(repo=voice_repo)

    tts_engine = TTSEngineFactory(model_name=config.tts_model_name).create()
    audio_streamer = SoundDeviceAudioStreamer(target_buffer_seconds=15.0)

    narration_service = NarrationService(
        book_repo=book_repo,
        cache_repo=cache_repo,
        tts_engine=tts_engine,
        audio_streamer=audio_streamer,
        chunking_service=ChunkingService(),
        device=device,
        language=config.default_language,
    )

    # UI
    app = QApplication([])
    window = MainWindow()
    UiController(
        window=window,
        narration_service=narration_service,
        voice_service=voice_service,
        device=device,
        engine_name=tts_engine.engine_name,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
