from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


repo_root = Path(SPECPATH).parents[1]
datas = []
binaries = []
hiddenimports = collect_submodules("commands")

for package in ("django", "ninja", "nodriver", "openpyxl", "python_calamine"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports

analysis = Analysis(
    [str(repo_root / "apps/api/desktop_runtime.py")],
    pathex=[str(repo_root / "apps/api"), str(repo_root / "apps/cli")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="knocklet-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="knocklet-runtime",
)
