# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\Oliver\\Development\\NarrateX\\LICENSE', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\LGPL3-LICENSE', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex.ico', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_16.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_32.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_48.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_64.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_128.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_256.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_512.png', '.')]
binaries = []
hiddenimports = ['misaki', 'torch', 'torch.distributed.rpc', 'voice_reader.application.services.narration_service', 'voice_reader.application.services.bookmark_service', 'voice_reader.application.services.idea_map_service', 'voice_reader.application.services.idea_indexing_manager', 'voice_reader.application.services.structural_bookmark_service', 'voice_reader.application.services.voice_profile_service', 'voice_reader.domain.services.chunking_service', 'voice_reader.infrastructure.tts.tts_engine_factory', 'voice_reader.infrastructure.books.cover_extractor', 'voice_reader.infrastructure.audio.audio_streamer', 'voice_reader.infrastructure.books.converter', 'voice_reader.infrastructure.books.parser', 'voice_reader.infrastructure.books.repository', 'voice_reader.infrastructure.cache.filesystem_cache', 'voice_reader.infrastructure.bookmarks.json_bookmark_repository', 'voice_reader.infrastructure.ideas.json_idea_index_repository', 'voice_reader.infrastructure.preferences.json_preferences_repository', 'voice_reader.infrastructure.tts.voice_profile_repository', 'voice_reader.ui.main_window', 'voice_reader.ui.ui_controller']
datas += collect_data_files('misaki')
datas += collect_data_files('language_tags')
datas += collect_data_files('torch')
binaries += collect_dynamic_libs('torch')
tmp_ret = collect_all('kokoro')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('phonemizer')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('espeakng_loader')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('spacy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('en_core_web_sm')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('transformers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('numpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('soundfile')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:\\Users\\Oliver\\Development\\NarrateX\\app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tensorboard', 'torch.utils.tensorboard', 'torch.distributed._sharding_spec', 'torch.distributed._sharded_tensor', 'torch.distributed._shard.checkpoint', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NarrateX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Oliver\\Development\\NarrateX\\narratex.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NarrateX',
)
