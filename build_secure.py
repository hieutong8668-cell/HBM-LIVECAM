"""Build a source-stripped distribution using compiled bytecode."""

import os
import py_compile
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "secure_build")
EXCLUDE_DIRS = {".git", "__pycache__", "venv", "env", "FM-OFS-V2.2.2", "support-cache", "secure_build", "models"}
EXCLUDE_EXT = {".whl", ".part", ".zip"}

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
    rel = os.path.relpath(dirpath, ROOT)
    target_dir = OUT if rel == "." else os.path.join(OUT, rel)
    os.makedirs(target_dir, exist_ok=True)

    for name in filenames:
        if os.path.splitext(name)[1].lower() in EXCLUDE_EXT:
            continue
        src = os.path.join(dirpath, name)
        if name.endswith(".py"):
            try:
                py_compile.compile(src, cfile=os.path.join(target_dir, name + "c"), doraise=True)
            except Exception as exc:
                print(f"SKIP {src}: {exc}")
        else:
            shutil.copy2(src, os.path.join(target_dir, name))

print("Secure build created at:", OUT)
