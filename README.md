# YASKAWA Tools

A desktop application for generating structured documentation from **YASKAWA YRC1000** robot controller backups, and for reporting **YASKAWA GA500** inverter configurations.

[![Build](https://github.com/OTHack1A/YASKAWA_Tools/actions/workflows/build.yml/badge.svg)](https://github.com/OTHack1A/YASKAWA_Tools/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-orange.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue.svg)](#requirements)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)

---

## Overview

YASKAWA Tools reads the backup files exported from a YRC1000 controller (`.DAT`, `.PRM`, `.JBI`, `.CND`, and related files) and produces ready-to-print PDF documentation covering every aspect of the robot cell: identification data, parameters, jobs, user frames, tool files, I/O names, network configuration, interference areas, and more.

A dedicated module handles **DriveWizard Industrial** project files (`.YDWIProj`), parsing GA500 inverter parameters and generating a formatted PDF report for each drive in the project.

<img width="1004" height="736" alt="YASKAWA Tools — main window" src="https://github.com/user-attachments/assets/7255520b-ebcb-44b8-ba7a-0f5f8b18799f" />

---

## Features

- **Full robot documentation** — generates a single comprehensive PDF from a YRC1000 backup folder, merging all sections automatically (cover page, table of contents, panel log, jobs, parameters, user frames, tool files, attachments).
- **Individual section reports** — each documentation module (targhetta, panel, jobs, parameters, points, user frames, tool files, variable names, I/O names, network config, interference cubes, form-cutting conditions, IF panel, log data) can be run independently.
- **Instruction documentation in the JOBs PDF** *(new in v1.2.0)* — when the backup folder contains the name files produced through the tool's own Template → Names workflow (`IONAME.DAT`, `EXIONAME.DAT`, `VARNAME.DAT`), every INFORM line that references a named I/O signal or variable is automatically annotated with that name, rendered as an inline comment (e.g. `WAIT IN#(3)=ON  'IN#(3): Fotocellula 1`).
- **GA500 inverter report** — parses `.YDWIProj` files from DriveWizard Industrial and produces a parameter report with descriptions for all 600+ GA500 parameters.
- **INFORM flowchart** — generates a graphical flowchart (PDF + draw.io XML) of the execution flow of any JBI job.
- **Interactive IF Panel viewer** — visualises the 15 IF panel pages with colours and I/O assignments.
- **Points-only editor** — edits the position variables (`P`) of `VAR.DAT` in a single table (number-prefix search, all slots listed so free slots can become new points) and exports them back, rewriting only the changed point lines while preserving the rest of the file byte-for-byte.
- **Editable creator name** — the name that appears in the header of every generated PDF can be customised directly from the **top bar**: click the *PDF name* field, type the desired name, and press Enter or click elsewhere to confirm. The value is persisted to `%APPDATA%\YaskawaTools\config.json` and used automatically by all PDF modules on next generation.
- **Multilingual interface** — seven languages: English (default), Italian, French, German, Spanish, Ukrainian, and Japanese. The language can be switched at runtime from the top bar.
- **Rotating log** — all user actions, generated files, warnings, and errors are written to a rotating log file (`YASKAWAToolsLog.log`, max 10 MB). The log is also visible in a collapsible panel inside the application.
- **Password protection** — access is guarded by an Argon2id-hashed password (hardened cost: 128 MiB memory, time 4, parallelism 4) with a persistent lockout (3 failed attempts → 5-minute block) and a constant-time verification floor to prevent timing attacks. The lockout state file is HMAC-integrity-protected and fails closed if tampered with, so an in-progress lockout cannot be cleared by editing it.

---

## Requirements

- Windows 10 / 11 (64-bit)
- Python 3.10 or later (only needed if running from source)

Install Python dependencies into a **clean virtual environment** (dependencies are
pinned to exact versions in `requirements.txt` so a build never silently pulls a
newer or compromised release):

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on *nix)
pip install -r requirements.txt
```

---

## Running from source

```bash
python main.py
```

---

## Building the executable

The project uses [PyInstaller](https://pyinstaller.org). Build from the same clean
virtual environment (add `-r requirements-dev.txt` for the build/test tooling):

```bash
pip install -r requirements-dev.txt
pyinstaller main.spec
```

The output is a single self-contained executable in `dist/YaskawaTools.exe` — no
installation required. Use `--distpath <dir>` to redirect the output folder.

**Reproducible / supply-chain-hardened build (recommended for releases):** generate
a hash-locked file and enforce it (see the header of `requirements.txt`), then
**code-sign** the result so the binary is tamper-evident and trusted by the OS:

```powershell
# Windows (Authenticode + RFC-3161 timestamp):
.\scripts\sign_windows.ps1 -Thumbprint <cert-thumbprint>
```

```bash
# macOS (codesign + optional notarization):
IDENTITY="Developer ID Application: <Name> (<TEAMID>)" ./scripts/sign_macos.sh dist/YaskawaTools.app
```

Signing material (`*.pfx` / `*.p12`, identities, passwords) must **never** be
committed — it is excluded by `.gitignore`.

---

## Project structure

```
yaskawa-tools/
├── main.py              Entry point
├── main.spec            PyInstaller build spec (Windows)
├── main_macos.spec      PyInstaller build spec (macOS)
├── main_linux.spec      PyInstaller build spec (Linux)
├── auth.py              Argon2id authentication + lockout
├── config.py            Persistent user settings (creator name) — JSON in %APPDATA%
├── logger.py            Rotating log (10 MB cap)
├── secure_paths.py      %APPDATA% path helpers
├── tooltips.py          UI tooltips registry
├── translations.py      Multilingual strings (IT / EN / FR / DE / ES / UA / JA)
│
├── docs/                PDF generation modules (one per section); the YRC1000 /
│                        GA500 parameter reference is embedded in docs/help_data.py
├── gui/                 PySide6 GUI components
├── assets/              Logo, icon, profile image
├── scripts/             Release helpers (code-signing for Windows / macOS)
└── tests/               Unit tests
```

> Build output (`dist/`), private controller dumps (`R1/`, `references/`) and
> signing material are intentionally **not** tracked — see `.gitignore`.
> Binaries are distributed via [Releases](../../releases).

---

## Digest control

The binaries are published under [Releases](../../releases). Verify the file you
downloaded matches the SHA-256 published for that release before running it.

**SHA-256 for the latest release (v1.2.0 — update these on every release):**

```
YaskawaTools.exe (Windows) --> sha256:pending — see the v1.2.0 release page
YaskawaTools     (Linux)   --> sha256:pending — see the v1.2.0 release page
YaskawaTools.dmg (macOS)   --> sha256:pending — see the v1.2.0 release page
```

How to compute the digest of a downloaded file:

```powershell
# Windows (PowerShell)
Get-FileHash .\YaskawaTools.exe -Algorithm SHA256
```

```bash
# Linux
sha256sum YaskawaTools
# macOS
shasum -a 256 YaskawaTools.dmg
```

---

## Code signing policy

Windows binaries published under [Releases](../../releases) are code-signed.

Free code signing provided by [SignPath.io](https://signpath.io), certificate by
[SignPath Foundation](https://signpath.org).

**Team roles** (single-maintainer project):

| Role | Member |
|---|---|
| Committers | [0THack1A](https://github.com/OTHack1A) |
| Reviewers | [0THack1A](https://github.com/OTHack1A) |
| Approvers | [0THack1A](https://github.com/OTHack1A) |

All releases are built from this repository by the public
[GitHub Actions workflow](.github/workflows/build.yml) and require manual
approval by an Approver before signing.

**Privacy statement:** this program will not transfer any information to other
networked systems unless specifically requested by the user. The only network
feature is the optional *attachment translation* function, which — only when
the user explicitly runs it — sends the text extracted from the selected PDF
attachment to the Google Translate service ([deep-translator](https://pypi.org/project/deep-translator/));
a warning is written to the in-app log before any data leaves the machine.
Everything else (parsing, PDF generation, logging) is performed locally.

---

## Supported file formats (input)

| File | Content |
|---|---|
| `SYSTEM.SYS` | Robot identification and system configuration |
| `PANELBOX.LOG` | Operator panel event log |
| `ALL.PRM` / `*.PRM` | Controller parameters |
| `*.JBI` | INFORM job programs |
| `IONAME.DAT`, `VARNAME.DAT`, `EXIONAME.DAT` | I/O and variable name tables |
| `USRGRPIN.DAT`, `USRGRPOT.DAT` | User group I/O |
| `VAR.DAT` | Variable backup |
| `LOGDATA.DAT` | Controller data log |
| `CUBEINTF.CND` | Cubic interference areas (up to 64) |
| `FORMCUT.CND` | Form-cutting conditions |
| `IFPANEL.DAT` | IF panel configuration (15 panels) |
| `IPNETCFG.DAT`, `IPNETEX.DAT` | Network configuration |
| `*.YDWIProj` | DriveWizard Industrial project (GA500 inverters) |

---

## Usage & access

See the [**User Guide**](USER_GUIDE.md) for download, login, and step-by-step usage.

> 🔑 **Access requires a password.** It is not published here — request it by
> e-mail at **[OThack1A@proton.me](mailto:OThack1A@proton.me)**. Please do not
> open public issues for password requests.

---

## License

MIT — see [LICENSE](LICENSE).
