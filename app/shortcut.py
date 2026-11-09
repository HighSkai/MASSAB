"""Makes MASSAB.lnk in the project folder: double-click it to start MASSAB.

A .bat file can't have its own icon, so a shortcut does that job instead,
with the M from the window as its icon. Run it again if you move the folder.

    .venv\\Scripts\\python app\\shortcut.py
"""
import os
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(APP_DIR)
LINK = os.path.join(ROOT, "MASSAB.lnk")


def make_shortcut():
    pythonw = os.path.join(ROOT, ".venv", "Scripts", "pythonw.exe")
    if not os.path.exists(pythonw):
        raise SystemExit(f"{pythonw} not found. Make the .venv first (see README).")
    # Values go in through the environment, so no path needs quoting for PowerShell.
    env = dict(os.environ, LINK=LINK, TARGET=pythonw, ARGS=f'"{os.path.join(APP_DIR, "gui.py")}"',
               WORKDIR=ROOT, ICON=os.path.join(APP_DIR, "massab.ico"))
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LINK); "
              "$s.TargetPath = $env:TARGET; $s.Arguments = $env:ARGS; $s.WorkingDirectory = $env:WORKDIR; "
              "$s.IconLocation = \"$env:ICON,0\"; $s.Description = 'MASSAB'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env, check=True)
    print(f"made {LINK}")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    make_shortcut()
