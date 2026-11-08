# Build the app folder dist\MASSAB with:
#     .venv\Scripts\python -m pip install pyinstaller==6.22.3
#     .venv\Scripts\python -m PyInstaller --noconfirm MASSAB.spec
#
# One folder, not one file: a single exe unpacks itself on every launch.
# bin\ and models\ aren't bundled. The app looks for them in its own folder,
# and its Install AI button puts them there.
import importlib.util

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# RapidOCR puts its own folder on sys.path and imports these by name from a
# config file, so PyInstaller can't find them unless it's told where they are.
rapidocr_dir = importlib.util.find_spec("rapidocr_onnxruntime").submodule_search_locations[0]

a = Analysis(
    ["gui.py"],
    pathex=[rapidocr_dir],
    datas=[("prompts", "prompts"), ("data", "data"), ("fonts", "fonts"), *collect_data_files("rapidocr_onnxruntime")],
    binaries=collect_dynamic_libs("onnxruntime"),
    hiddenimports=["mss", "mss.windows", "ch_ppocr_v3_det", "ch_ppocr_v3_rec", "ch_ppocr_v2_cls"],
    excludes=["tkinter", "matplotlib", "pytest", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="MASSAB",
    console=False,
    # Keep everything next to the exe, so prompts\ and data\ are where the app
    # looks for them and easy to edit.
    contents_directory=".",
)
coll = COLLECT(exe, a.binaries, a.datas, name="MASSAB")
