# Windows single-video Jianying draft (experimental)

This optional command creates a new editable draft from one local MP4. It has
been checked against an installed Jianying Pro 11.5.3.14501 with a pinned
`videoeditor.dll` identity. The editor indexed a generated draft. After it
opened the draft, Jianying wrote a two-second duration, generated a cover,
and saved an encrypted draft file. Playback, cold reopening, and native export
have not yet been verified. Do not use the output as a finished project until
those checks succeed.

The command uses [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft)
at an exact source revision. Its Apache-2.0 notice is retained in
[third-party notices](../THIRD_PARTY_NOTICES.md). The source video remains in
its original location; keep it there while the draft uses it.

## Install the optional dependency

Run from the repository root in PowerShell:

```powershell
python -m venv work\windows-native-venv
work\windows-native-venv\Scripts\python.exe -m pip install -r requirements-windows-native.txt
work\windows-native-venv\Scripts\python.exe tools\windows_native_draft.py doctor
```

The `doctor` command requires exactly the reviewed application version and
editor-library SHA-256, and checks the pinned package template. A different
application build stops instead of silently using an unreviewed format.

## Create a draft

Save and fully quit Jianying, then run:

```powershell
work\windows-native-venv\Scripts\python.exe tools\windows_native_draft.py create --video "D:\Videos\my-video.mp4"
```

The result contains the new draft path. Start Jianying to have it index the new
directory, then open the draft, play it, save, fully quit and reopen it. The
command only creates a new folder; it does not alter an existing draft or edit
the homepage index. To set a name, pass `--name`. The draft uses a 30 fps
timeline; the original video's frames are referenced without transcoding.

This first version creates one full-length video segment on one track. It does
not cut footage, add text or music, edit an existing draft, or export MP4.
Those functions need separate Windows validation. For a standalone MP4 without
an editable Jianying draft, use [Windows FFmpeg export](windows-ffmpeg.md).
