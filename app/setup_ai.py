"""Download the local AI runtime and model that riddle mode uses.

Usage:
    python setup_ai.py              # llama-server and the default model
    python setup_ai.py --model 2b   # the smaller fallback model instead

Everything goes in bin/ and models/ next to this script. Each download is
checked against a pinned SHA-256, files that are already there are skipped, and
a stopped download picks up where it left off. The GUI's Install AI button
runs the same code.
"""
import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.request
import zipfile

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LLAMA_DIR = os.path.join(APP_DIR, "bin", "llama")
LLAMA_SERVER = os.path.join(LLAMA_DIR, "llama-server.exe")
BUILD_MARKER = os.path.join(LLAMA_DIR, "build.txt")
# Files that must all be there for the AI to run on the GPU. Losing any one of
# them (an antivirus, a sync tool, a git stash) leaves a server that won't start.
RUNTIME_FILES = ("llama-server.exe", "llama-server-impl.dll", "llama.dll", "ggml.dll", "ggml-base.dll",
                 "ggml-cuda.dll", "cudart64_13.dll", "cublas64_13.dll", "cublasLt64_13.dll")
MODELS_DIR = os.path.join(APP_DIR, "models")

BUILD = "b12119"
RELEASE = f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}"
RUNTIME = [
    (f"llama-{BUILD}-bin-win-cuda-13.4-x64.zip",
     "a9f71dbc45ddcbd4b2e233ff4c40738876c574783b77cb846c33bf653c05188f"),
    ("cudart-llama-bin-win-cuda-13.4-x64.zip",
     "738f8c251ac22b70c3ae6f83a10cf222725df0395246a2cf58f32bdb85fbe668"),
]
# name -> (Hugging Face repo, pinned revision, file, SHA-256)
MODELS = {
    "4b": ("unsloth/Qwen3.5-4B-GGUF", "e87f176479d0855a907a41277aca2f8ee7a09523",
           "Qwen3.5-4B-UD-Q4_K_XL.gguf", "b252c5610a42ca82d20fe2a12813e9d069eed89292907e26c783eeb0bc961bc7"),
    "2b": ("unsloth/Qwen3.5-2B-GGUF", "f6d5376be1edb4d416d56da11e5397a961aca8ae",
           "Qwen3.5-2B-Q4_K_M.gguf", "aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223"),
}
DEFAULT_MODEL = "4b"
CHUNK = 1 << 20


def model_path(name=DEFAULT_MODEL):
    return os.path.join(MODELS_DIR, MODELS[name][2])


def runtime_installed():
    try:
        with open(BUILD_MARKER) as f:
            if f.read().strip() != BUILD:
                return False
    except OSError:
        return False
    return all(os.path.exists(os.path.join(LLAMA_DIR, name)) for name in RUNTIME_FILES)


def ai_installed(name=DEFAULT_MODEL):
    return runtime_installed() and os.path.exists(model_path(name))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def print_progress(name, done, total):
    if total:
        print(f"{name}: {done * 100 // total}% of {total / 1e9:.2f} GB", flush=True)


def download(url, path, expected, progress=print_progress):
    """Fetch url to path through a .part file, so a stopped download can't pass for a
    finished one, and the next try carries on from it. progress(name, done, total)
    is called about every 1%."""
    name = os.path.basename(path)
    if os.path.exists(path) and sha256(path) == expected:
        print(f"have {name}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part, digest = path + ".part", hashlib.sha256()
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if have:
        with open(part, "rb") as f:
            while block := f.read(CHUNK):
                digest.update(block)
    request = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
        if e.code != 416:   # 416: the .part is already the whole file
            raise
        response = None
    if response is not None:
        with response:
            if have and response.status != 206:     # the server ignored the range: start over
                have, digest = 0, hashlib.sha256()
            total = have + int(response.headers.get("Content-Length", 0))
            done, shown = have, -1
            with open(part, "ab" if have else "wb") as out:
                while block := response.read(CHUNK):
                    out.write(block)
                    digest.update(block)
                    done += len(block)
                    percent = done * 100 // total if total else 0
                    if percent != shown:
                        shown = percent
                        progress(name, done, total)
    if digest.hexdigest() != expected:
        os.remove(part)
        raise SystemExit(f"{name} failed its SHA-256 check and was deleted. Try again.")
    os.replace(part, path)


def install_runtime(progress=print_progress):
    if runtime_installed():
        print(f"have llama-server {BUILD}")
        return
    for name, expected in RUNTIME:
        archive = os.path.join(LLAMA_DIR, name)
        download(f"{RELEASE}/{name}", archive, expected, progress)
        with zipfile.ZipFile(archive) as z:
            z.extractall(LLAMA_DIR)
        os.remove(archive)
    if not os.path.exists(LLAMA_SERVER):
        raise SystemExit("llama-server.exe wasn't in the download")
    with open(BUILD_MARKER, "w") as f:
        f.write(BUILD)


def install_model(name, progress=print_progress):
    repo, revision, file, expected = MODELS[name]
    download(f"https://huggingface.co/{repo}/resolve/{revision}/{file}", model_path(name), expected, progress)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL, help="which model to download")
    args = ap.parse_args()
    install_runtime()
    install_model(args.model)
    print("ready")


if __name__ == "__main__":
    main()
