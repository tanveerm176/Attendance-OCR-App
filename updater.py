import os
import sys
import requests
from pathlib import Path

GITHUB_API_URL = "https://api.github.com/repos/tanveerm176/Attendance-OCR-App/releases/latest"
VERSION_FILE = Path(__file__).parent/ "VERSION"

def get_local_version() -> str:
    return VERSION_FILE.read_text().strip()


def get_latest_release() -> tuple[str, str]:
    """
    Returns (tag, download_url) of the latest Github release asset.
    Raises requests.RequestException on network failure
    """
    response = requests.get(GITHUB_API_URL, timeout=5)
    response.raise_for_status()
    data = response.json()

    tag = data["tag_name"].lstrip("v") # "v1.2.0" → "1.2.0"

    # Find the .exe asset
    assets = data.get("assets", [])
    exe_asset = next((a for a in assets if a["name"].endswith(".exe")), None)

    if not exe_asset:
        raise ValueError("No .exe asset found in latest release")
 
    return tag, exe_asset["browser_download_url"]


def is_newer(latest: str, current: str) -> bool:
    """ Compare semantic version strings - '1.2.0'> '1.0.0'. """
    return tuple(int(x) for x in latest.split(".")) > \
            tuple(int(x) for x in current.split("."))


def download_and_replace(download_url: str):
    """
    Downloads the new .exe, replaces the current executable, relaunches.
    Only runs when the app is a PyInstaller bundle to avoid downloading 
    in development (sys.frozen = True)
    """
    current_exe = Path(sys.executable)
    tmp_path = current_exe.with_suffix(".tmp.exe")

    print("Downloading update...")
    response = requests.get(download_url, stream=True, timeout=60)
    response.raise_for_status()

    # Write response to tmp executable 
    with open(tmp_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    # On Windows, rename rather than overwrite the running exe
    backup = current_exe.with_suffix("old.exe")
    current_exe.rename(backup)
    tmp_path.rename(current_exe)

    print("Update complete. Relaunching...")
    os.execv(str(current_exe), sys.argv) # relaunch with same args


def check_for_update():
    """
    Enrty point called from main.py at startup.
    Silently no-ops if network is unavailable or app is not a frozen bundle.
    """
    try:
        local = get_local_version()
        latest, download_url = get_latest_release()

        if not is_newer(latest, local):
            return # already up to date, proceed silently

        print(f"\nUpdate available: v{local} -> v{latest}")
        choice = input("Install now? (Y/N): ").strip().lower()

        if choice != "y":
            print("Skipping update. Continuing with current version.\n")
            return

        if not getattr(sys, "frozen", False):
            # Running as a .py script during development - skip the replace step
            print("(Running in dev mode - skipping exe replacement)\n")
            return

        download_and_replace(download_url)

    except Exception as e:
        # Prevent app from crashing over update failure
        print(f"Update check failed ({e}). Continuing...\n")
    