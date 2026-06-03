# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs
from PyInstaller.utils.hooks import collect_all

datas = [('/Users/oliver/Development/NarrateX/LICENSE', '.'), ('/Users/oliver/Development/NarrateX/LGPL3-LICENSE', '.'), ('/Users/oliver/Development/NarrateX/narratex.png', '.'), ('/Users/oliver/Development/NarrateX/narratex_16.png', '.'), ('/Users/oliver/Development/NarrateX/narratex_24.png', '.'), ('/Users/oliver/Development/NarrateX/narratex_32.png', '.'), ('/Users/oliver/Development/NarrateX/narratex_48.png', '.'), ('/Users/oliver/Development/NarrateX/narratex_64.png', '.'), ('/Users/oliver/Development/NarrateX/narratex_128.png', '.'), ('/Users/oliver/Development/NarrateX/narratex_256.png', '.'), ('/Users/oliver/Development/NarrateX/narratex_512.png', '.')]
binaries = []
hiddenimports = ['misaki', 'torch', 'torch.distributed.rpc', 'soundfile', 'voice_reader.application.services.narration_service', 'voice_reader.application.services.bookmark_service', 'voice_reader.application.services.idea_map_service', 'voice_reader.application.services.idea_indexing_manager', 'voice_reader.application.services.structural_bookmark_service', 'voice_reader.application.services.voice_profile_service', 'voice_reader.domain.services.chunking_service', 'voice_reader.infrastructure.tts.tts_engine_factory', 'voice_reader.infrastructure.books.cover_extractor', 'voice_reader.infrastructure.audio.audio_streamer', 'voice_reader.infrastructure.books.converter', 'voice_reader.infrastructure.books.parser', 'voice_reader.infrastructure.books.repository', 'voice_reader.infrastructure.cache.filesystem_cache', 'voice_reader.infrastructure.bookmarks.json_bookmark_repository', 'voice_reader.infrastructure.ideas.json_idea_index_repository', 'voice_reader.infrastructure.preferences.json_preferences_repository', 'voice_reader.infrastructure.tts.voice_profile_repository', 'voice_reader.ui.main_window', 'voice_reader.ui.ui_controller']
datas += collect_data_files('misaki')
datas += collect_data_files('language_tags')
datas += collect_data_files('torch')
binaries += collect_dynamic_libs('torch')
binaries += collect_dynamic_libs('soundfile')
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
tmp_ret = collect_all('scipy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('numpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('soundfile')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['/Users/oliver/Development/NarrateX/app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tensorboard', 'torch.utils.tensorboard', 'torch.distributed._sharding_spec', 'torch.distributed._sharded_tensor', 'torch.distributed._shard.checkpoint'],
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
    codesign_identity='Developer ID Application: Oliver Ernster (W7K465GKFJ)',
    entitlements_file='/var/folders/54/hjq7jf8d2d10ghbqfg02hp6h0000gn/T/tmpxjg7ah68.entitlements',
    icon=['/var/folders/54/hjq7jf8d2d10ghbqfg02hp6h0000gn/T/tmpo3tgt4lr/narratex.icns'],
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
app = BUNDLE(
    coll,
    name='NarrateX.app',
    icon='/var/folders/54/hjq7jf8d2d10ghbqfg02hp6h0000gn/T/tmpo3tgt4lr/narratex.icns',
    bundle_identifier='uk.codecrafter.NarrateX',
)
