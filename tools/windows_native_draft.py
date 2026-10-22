#!/usr/bin/env python3
"""Create a single-video draft for the reviewed local Windows Jianying build.

The editor imports the new directory when it next starts. This command never
changes an existing draft or writes the editor's home index.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any


APP_VERSION = "11.5.3.14501"
EDITOR_SHA256 = "e5e4020bd5b37eb19968473e19d7246ca5efe80064a039136341a27b1fd5d8b7"
TEMPLATE_SHA256 = "f3b9036da3a0bce68145657bb3fa9b0147e0fe39f7082e43590fb91b63f99d94"
INDEX_RELATIVE = Path("JianyingPro/User Data/Projects/com.lveditor.draft/root_meta_info.json")


def require(value: Any, message: str) -> None:
    if not value:
        raise ValueError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def installed_editor() -> tuple[str, Path]:
    import winreg

    uninstall_keys = (
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, location in uninstall_keys:
        try:
            parent = winreg.OpenKey(hive, location)
        except OSError:
            continue
        with parent:
            for index in range(winreg.QueryInfoKey(parent)[0]):
                try:
                    child = winreg.OpenKey(parent, winreg.EnumKey(parent, index))
                    with child:
                        name = winreg.QueryValueEx(child, "DisplayName")[0]
                        if name != "剪映专业版":
                            continue
                        version = winreg.QueryValueEx(child, "DisplayVersion")[0]
                        uninstall = winreg.QueryValueEx(child, "UninstallString")[0]
                except OSError:
                    continue
                match = re.match(r'^"([^\"]+\.exe)"', uninstall)
                require(match is not None, "Cannot determine Jianying install directory")
                return str(version), Path(match.group(1)).parent
    raise ValueError("Windows Jianying Pro installation was not found")


def draft_roots() -> list[Path]:
    local_appdata = os.environ.get("LOCALAPPDATA")
    require(local_appdata, "LOCALAPPDATA is unavailable")
    index = Path(local_appdata) / INDEX_RELATIVE
    require(index.is_file(), "Jianying home index is missing; initialize it in the editor")
    data = json.loads(index.read_text(encoding="utf-8-sig"))
    require(isinstance(data.get("all_draft_store"), list), "Invalid Jianying home index")
    roots: dict[str, Path] = {}
    for row in data["all_draft_store"]:
        if not isinstance(row, dict) or not row.get("draft_root_path"):
            continue
        root = Path(row["draft_root_path"]).resolve(strict=True)
        require(root.is_dir(), "Jianying draft root is not a directory")
        roots[os.path.normcase(str(root))] = root
    require(roots, "No local draft root is registered; create one draft in Jianying first")
    return list(roots.values())


def dependency() -> Any:
    try:
        import pyJianYingDraft as draft
    except ImportError as error:
        raise ValueError("Install requirements-windows-native.txt in this Python environment") from error
    template = Path(draft.__file__).parent / "assets/draft_content_template.json"
    require(template.is_file() and digest(template) == TEMPLATE_SHA256,
            "pyJianYingDraft template differs from the reviewed source revision")
    return draft


def editor_running() -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq JianyingPro.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace",
    )
    require(result.returncode == 0, "Could not check whether Jianying is running")
    return '"JianyingPro.exe"' in result.stdout


def preflight() -> tuple[Path, list[Path], Any]:
    require(platform.system() == "Windows", "This native draft path requires Windows")
    require(sys.version_info >= (3, 9), "Python 3.9 or later is required")
    version, app_root = installed_editor()
    require(version == APP_VERSION, f"Unreviewed Jianying version: {version}; expected {APP_VERSION}")
    editor = app_root / APP_VERSION / "videoeditor.dll"
    require(editor.is_file() and digest(editor) == EDITOR_SHA256,
            "Installed Jianying editor differs from the reviewed 11.5.3 build")
    return app_root, draft_roots(), dependency()


def create(video: Path, name: str | None, root: Path | None) -> dict[str, Any]:
    app_root, roots, draft = preflight()
    require(not editor_running(), "Save your work and fully quit Jianying before creating a draft")
    if root is None:
        require(len(roots) == 1, "Multiple draft roots are registered; pass --draft-root")
        root = roots[0]
    else:
        root = root.resolve(strict=True)
        require(os.path.normcase(str(root)) in {os.path.normcase(str(p)) for p in roots},
                "--draft-root is not registered in Jianying")
    video = video.resolve(strict=True)
    require(video.is_file() and not video.is_symlink(), "Video must be a regular local file")
    require(video.suffix.lower() == ".mp4", "The reviewed single-video path currently accepts MP4")
    fps = 30  # Only the 30 fps single-video shape has been reviewed here.
    if name is None:
        from datetime import datetime
        from uuid import uuid4
        name = "headless-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
    require(name not in {"", ".", ".."} and name == name.strip()
            and not re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            and not name.endswith((".", " ")), "Unsafe draft name")
    require(not (root / name).exists(), "A draft with this name already exists")

    media = draft.VideoMaterial(str(video))
    require(media.material_type == "video" and media.duration > 0
            and media.width > 0 and media.height > 0, "The MP4 has no usable video track")
    script = draft.DraftFolder(str(root)).create_draft(name, media.width, media.height, fps)
    script.append_track(draft.TrackSpec(draft.TrackType.video, "main_video"))
    script.add_segment(draft.VideoSegment(media, draft.trange(0, media.duration)), "main_video")
    script.save()

    destination = root / name / "draft_content.json"
    content = json.loads(destination.read_text(encoding="utf-8"))
    require(len(content.get("tracks", [])) == 1
            and len(content["tracks"][0].get("segments", [])) == 1
            and len(content.get("materials", {}).get("videos", [])) == 1,
            "Generated single-video draft is structurally invalid")
    require(Path(content["materials"]["videos"][0]["path"]).resolve() == video,
            "Generated draft references a different video")
    return {"status": "created-awaiting-native-validation", "draft": str(root / name),
            "video": str(video), "duration_us": media.duration,
            "canvas": [media.width, media.height], "fps": fps,
            "app_version": APP_VERSION, "app_root": str(app_root),
            "next": "Start Jianying, open this draft, play it, save, quit, and reopen."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("doctor")
    build = actions.add_parser("create")
    build.add_argument("--video", type=Path, required=True, help="Absolute path to a local MP4")
    build.add_argument("--name", help="New draft name; omit for an automatic unique name")
    build.add_argument("--draft-root", type=Path, help="Registered Jianying draft directory")
    args = parser.parse_args()
    try:
        if args.action == "doctor":
            app_root, roots, _ = preflight()
            result = {"status": "preflight-ok", "app_version": APP_VERSION,
                      "app_root": str(app_root), "draft_roots": [str(p) for p in roots],
                      "editor_running": editor_running()}
        else:
            result = create(args.video, args.name, args.draft_root)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit("Windows draft creation failed: " + str(error)) from error


if __name__ == "__main__":
    main()
