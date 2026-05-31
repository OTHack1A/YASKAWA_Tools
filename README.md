# YASKAWA Tools

A desktop application for generating structured documentation from **YASKAWA YRC1000** robot controller backups, and for reporting **YASKAWA GA500** inverter configurations.

---

## Overview

YASKAWA Tools reads the backup files exported from a YRC1000 controller (`.DAT`, `.PRM`, `.JBI`, `.CND`, and related files) and produces ready-to-print PDF documentation covering every aspect of the robot cell: identification data, parameters, jobs, user frames, tool files, I/O names, network configuration, interference areas, and more.

A dedicated module handles **DriveWizard Industrial** project files (`.YDWIProj`), parsing GA500 inverter parameters and generating a formatted PDF report for each drive in the project.

---

## Features

- **Full robot documentation** — generates a single comprehensive PDF from a YRC1000 backup folder, merging all sections automatically (cover page, table of contents, panel log, jobs, parameters, user frames, tool files, attachments).
- **Individual section reports** — each documentation module (targhetta, panel, jobs, parameters, points, user frames, tool files, variable names, I/O names, network config, interference cubes, form-cutting conditions, IF panel, log data) can be run independently.
- **GA500 inverter report** — parses `.YDWIProj` files from DriveWizard Industrial and produces a parameter report with descriptions for all 600+ GA500 parameters.
- **INFORM flowchart** — generates a graphical flowchart (PDF + draw.io XML) of the execution flow of any JBI job.
- **Interactive IF Panel viewer** — visualises the 15 IF panel pages with colours and I/O assignments.
- **Multilingual interface** — English (default), Italian, and Japanese. The language can be switched at runtime from the top bar.
- **Rotating log** — all user actions, generated files, warnings, and errors are written to a rotating log file (`YASKAWAToolsLog.log`, max 10 MB). The log is also visible in a collapsible panel inside the application.
- **Password protection** — access is guarded by an Argon2id-hashed password with a persistent lockout (3 failed attempts → 5-minute block) and a constant-time verification floor to prevent timing attacks.

---

## Requirements

- Windows 10 / 11 (64-bit)
- Python 3.10 or later (only needed if running from source)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Running from source

```bash
python main.py
```

---

## Building the executable

The project uses [PyInstaller](https://pyinstaller.org). Build with:

```bash
pyinstaller main.spec
```

The output is placed in `dist/YaskawaTools.exe` — a single self-contained executable, no installation required.

---

## Project structure

```
yaskawa-tools/
├── main.py              Entry point
├── main.spec            PyInstaller build spec
├── auth.py              Argon2id authentication + lockout
├── logger.py            Rotating log (10 MB cap)
├── secure_paths.py      %APPDATA% path helpers
├── tooltips.py          UI tooltips registry
├── translations.py      Multilingual strings (IT / EN / JA)
│
├── docs/                PDF generation modules (one per section)
├── gui/                 PySide6 GUI components
├── tests/               Unit / integration tests
├── assets/              Logo, icon, profile image
├── references/          YRC1000 parameter reference and GA500 parameter list
└── dist/                Pre-built executable (YaskawaTools.exe)
```

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

## License

MIT — see [LICENSE](LICENSE).
