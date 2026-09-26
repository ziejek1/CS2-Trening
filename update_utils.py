import json
import os
import re
import subprocess
import tempfile
import urllib.request


REPOSITORY = "ziejek1/CS2-Trening"
RELEASES_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
INSTALLER_ASSET_NAME = "CS2Trening-Setup.exe"


def parse_version(value):
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(value or ""))
    if not match:
        return (0, 0, 0)
    return tuple(int(part or 0) for part in match.groups())


def fetch_latest_release(current_version):
    request = urllib.request.Request(
        RELEASES_API_URL,
        headers={"User-Agent": "CS2-Trening-Updater"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        release = json.loads(response.read().decode("utf-8"))

    latest_version = parse_version(release.get("tag_name"))
    if latest_version <= parse_version(current_version):
        return None

    asset = next(
        (
            item for item in release.get("assets", [])
            if item.get("name") == INSTALLER_ASSET_NAME
        ),
        None
    )
    return {
        "version": release.get("tag_name", ""),
        "url": asset.get("browser_download_url", "") if asset else "",
        "notes": release.get("body", ""),
        "installer_ready": bool(asset and asset.get("browser_download_url")),
    }


def download_installer(download_url):
    installer_path = os.path.join(tempfile.gettempdir(), INSTALLER_ASSET_NAME)
    request = urllib.request.Request(
        download_url,
        headers={"User-Agent": "CS2-Trening-Updater"}
    )
    with urllib.request.urlopen(request, timeout=60) as response, open(installer_path, "wb") as output:
        output.write(response.read())
    return installer_path


def launch_installer(installer_path):
    launcher_path = os.path.join(tempfile.gettempdir(), "CS2Trening-update.cmd")
    installer_path = os.path.abspath(installer_path)
    with open(launcher_path, "w", encoding="utf-8") as launcher:
        launcher.write(
            "@echo off\n"
            "timeout /t 3 /nobreak >nul\n"
            f'start "" /wait "{installer_path}"\n'
            'del "%~f0"\n'
        )
    subprocess.Popen(
        ["cmd.exe", "/c", launcher_path],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
