"""Download the local AI runtime and model that riddle mode uses.

Usage:
    python setup_ai.py              # llama-server and the default model
    python setup_ai.py --model 2b   # the smaller fallback model instead

Everything goes in bin/ and models/ next to this script. Each download is
checked against a pinned SHA-256, and files that are already there are skipped.
"""
import argparse
import hashlib
import os
import sys
import urllib.request
import zipfile

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LLAMA_DIR = os.path.join(APP_DIR, "bin", "llama")
LLAMA_SERVER = os.path.join(LLAMA_DIR, "llama-server.exe")
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


def ai_installed(name=DEFAULT_MODEL):
    return os.path.exists(LLAMA_SERVER) and os.path.exists(model_path(name))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def download(url, path, expected):
    """Fetch url to path through a .part file, so a stopped download can't pass for a finished one."""
    if os.path.exists(path) and sha256(path) == expected:
        print(f"have {os.path.basename(path)}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part, digest, done, shown = path + ".part", hashlib.sha256(), 0, -1
    with urllib.request.urlopen(url) as response, open(part, "wb") as out:
        total = int(response.headers.get("Content-Length", 0))
        while block := response.read(CHUNK):
            out.write(block)
            digest.update(block)
            done += len(block)
            percent = done * 100 // total if total else 0
            if percent // 10 != shown:
                shown = percent // 10
                print(f"{os.path.basename(path)}: {percent}% of {total / 1e9:.2f} GB", flush=True)
    if digest.hexdigest() != expected:
        os.remove(part)
        raise SystemExit(f"{os.path.basename(path)} failed its SHA-256 check and was deleted")
    os.replace(part, path)


def install_runtime():
    marker = os.path.join(LLAMA_DIR, "build.txt")
    if os.path.exists(LLAMA_SERVER) and os.path.exists(marker):
        with open(marker) as f:
            if f.read().strip() == BUILD:
                print(f"have llama-server {BUILD}")
                return
    for name, expected in RUNTIME:
        archive = os.path.join(LLAMA_DIR, name)
        download(f"{RELEASE}/{name}", archive, expected)
        with zipfile.ZipFile(archive) as z:
            z.extractall(LLAMA_DIR)
        os.remove(archive)
    if not os.path.exists(LLAMA_SERVER):
        raise SystemExit("llama-server.exe wasn't in the download")
    with open(marker, "w") as f:
        f.write(BUILD)


def install_model(name):
    repo, revision, file, expected = MODELS[name]
    download(f"https://huggingface.co/{repo}/resolve/{revision}/{file}", model_path(name), expected)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL, help="which model to download")
    args = ap.parse_args()
    install_runtime()
    install_model(args.model)
    print("ready")


if __name__ == "__main__":
    main()
