"""API keys for web search, kept in Windows Credential Manager.

A key never goes in settings.json, which is a plain file next to the app.
Credential Manager keeps it under this Windows account, and it shows up there
as "MASSAB/tavily" or "MASSAB/brave" if you want to look at it or remove it.
A key in an environment variable (TAVILY_API_KEY, BRAVE_API_KEY) is used
instead of a saved one.
"""
import ctypes
import os
import sys
from ctypes import wintypes

TARGET = "MASSAB/{}"
ENVIRONMENT = {"tavily": "TAVILY_API_KEY", "brave": "BRAVE_API_KEY"}
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
MAX_KEY_LENGTH = 512


class CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]


_api = None


def advapi():
    """Credential Manager's functions, or None off Windows."""
    global _api
    if _api is None and sys.platform == "win32":
        api = ctypes.WinDLL("advapi32", use_last_error=True)
        api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
        api.CredReadW.restype = wintypes.BOOL
        api.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None
        _api = api
    return _api


def load(provider):
    """The key to use for a search provider, or "" if there's none."""
    from_environment = os.environ.get(ENVIRONMENT.get(provider, ""), "").strip()
    return from_environment or saved(provider)


def from_environment(provider):
    return bool(os.environ.get(ENVIRONMENT.get(provider, ""), "").strip())


def saved(provider):
    api = advapi()
    if api is None:
        return ""
    pointer = ctypes.POINTER(CREDENTIAL)()
    if not api.CredReadW(TARGET.format(provider), CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        return ""
    try:
        cred = pointer.contents
        return ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize).decode("utf-8", "replace").strip()
    finally:
        api.CredFree(pointer)


def save(provider, key):
    """Keep a key for next time. Raises OSError if Windows won't."""
    key = key.strip()
    if not key or len(key) > MAX_KEY_LENGTH or any(c.isspace() for c in key):
        raise ValueError("That doesn't look like an API key")
    api = advapi()
    if api is None:
        raise OSError("Saving keys needs Windows. Set the key in an environment variable instead.")
    blob = key.encode("utf-8")
    buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = CREDENTIAL(Type=CRED_TYPE_GENERIC, TargetName=TARGET.format(provider), CredentialBlobSize=len(blob),
                      CredentialBlob=ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
                      Persist=CRED_PERSIST_LOCAL_MACHINE, UserName="MASSAB")
    if not api.CredWriteW(ctypes.byref(cred), 0):
        raise OSError(ctypes.get_last_error(), "Windows wouldn't save the key")


def forget(provider):
    api = advapi()
    if api is not None:
        api.CredDeleteW(TARGET.format(provider), CRED_TYPE_GENERIC, 0)
