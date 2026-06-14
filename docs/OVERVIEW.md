# YASKAWA Tools — Application Documentation

**Version:** v1.1.8 build 1
**Platform:** Windows 10 / 11 (64-bit) — also buildable for Linux and macOS
**Core dependencies:** Python 3.10+, PySide6, ReportLab, openpyxl, pypdf

<img width="1004" height="736" alt="image" src="https://github.com/user-attachments/assets/7255520b-ebcb-44b8-ba7a-0f5f8b18799f" />


---

## 1. Overview

**YASKAWA Tools** is a desktop application for inspecting, documenting, and reporting on **YASKAWA YRC1000** robot controllers. It reads the backup exported from a controller — a folder containing the controller's `.DAT`, `.PRM`, `.JBI`, `.CND`, and related files — analyses its contents, and produces clean, ready-to-print **PDF documentation** for every aspect of the robot cell.

The application is aimed at integrators, maintenance engineers, and commissioning staff who need a reliable paper (or PDF) trail of a robot installation: identification data, parameters, teach points, user frames, tool calibration, I/O naming, network configuration, interference zones, and more. Rather than navigating the teach pendant or cross-referencing raw backup files by hand, the user points the tool at a backup folder and obtains a structured, human-readable document in seconds.

A dedicated module extends the same philosophy to **YASKAWA GA500** inverters: it parses **DriveWizard Industrial** project files (`.YDWIProj`) and generates a parameter report — complete with descriptions for all 600+ GA500 parameters — for each drive contained in the project.

The interface is **password-protected** (Argon2id), supports a **light/dark theme**, and is fully **localised in seven languages** (Italian, English, French, German, Spanish, Ukrainian, and Japanese). The language and theme can be switched at runtime from the top bar.

---

## 2. Startup and authentication

On launch the application shows a login window before any functionality becomes available. Authentication is intentionally conservative because the tool can expose configuration details of an industrial cell:

- The password is verified against a stored **Argon2id** hash (hardened parameters: `m=131072` (128 MiB), `t=4`, `p=4`). The plaintext password is never stored.
- After a maximum of **3 failed attempts**, the application arms a **5-minute lockout**.
- The lockout state is **persisted** to `auth_state.json` under `%APPDATA%\YaskawaTools`. Because the counter lives on disk rather than in process memory, simply closing and reopening the application does **not** reset it — this prevents a trivial brute-force bypass.
- The lockout state file is **HMAC-integrity-protected** (keyed by an embedded pepper bound to the local machine name). A file that is present but carries a missing or invalid signature is treated as tampering and fails closed — the lockout remains active — rather than being silently reset. Deleting the file reverts to a first-run state, which is an inherent limit of any server-less design.
- Every verification call enforces a **constant-time floor of 500 ms**. This neutralises timing side-channels that could otherwise distinguish "wrong password" from "no password configured" or "invalid hash".

Once the password is accepted, the login window closes and the main window opens, with the current Windows username shown in the top bar.

As an additional hardening measure, `main.py` strips all command-line arguments at startup (`sys.argv = sys.argv[:1]`) before creating the Qt application. This blocks Qt argument injection (`-platform`, `-style`, `-plugin`, and similar) through the packaged executable.

---

## 3. Interface layout

```
┌─────────────────────────────────────────────┐
│  Top Bar   (logo · user · theme · language)  │
├──────────────┬──────────────────────────────┤
│  Tool Panel  │  Work area                    │
│  (side menu) │  (dynamic views)              │
│              │                               │
├──────────────┴──────────────────────────────┤
│  Log Panel   (collapsible)                   │
└─────────────────────────────────────────────┘
```

- **Top Bar** (`gui/top_bar.py`) — displays the application logo (loaded from `assets/logo-home.png`), the logged-in Windows username, and the controls for switching theme (light/dark) and language. The language selector offers all seven supported locales. If the logo image cannot be loaded, the top bar falls back to displaying the creator name as text.
- **Tool Panel** (`gui/tool_panel.py`) — the left-hand side menu containing the buttons for the main functions.
- **Main Window** (`gui/main_window.py`) — orchestrates the menu, loads the robot backup folder, and hosts the dynamic views in the central work area.
- **Log Panel** — a collapsible area at the bottom that displays application events (actions, generated files, warnings, errors) in real time.

The whole application uses a custom **"Claude orange"** palette: the default Windows blue highlight/selection colour is replaced application-wide with orange (`#FF9248`), including selection backgrounds and focus rings. Per-widget stylesheets can still override this locally.

---

## 4. Available functions

All robot-documentation functions require the user to first select the **robot backup folder** — the directory containing the files exported from the YRC1000 controller.

### 4.1 Robot documentation (main menu)

| Menu entry | Module | Description |
|---|---|---|
| Targhetta (Nameplate) | `docs/targhetta.py` | Reads `SYSTEM.SYS` and generates a robot identification sheet (model, software version, axis configuration). |
| Panel | `docs/panel.py` | Reads `PANELBOX.LOG` and documents the operator-panel configuration. |
| Completa (Full report) | `docs/completa.py` | Generates the complete PDF by merging every module in order: Nameplate → Table of Contents → Panel → Jobs → Parameters → User Frames / Tools → Attachments. |
| Help | `gui/help_view.py` | Displays the embedded YRC1000 parameter guide (`docs/help_data.py`), which is searchable and filterable. |
| Log (Registro) | — | Shows the session log with the option to export it. |

### 4.2 Parsing and PDF-generation modules

Each module is responsible for parsing one family of backup files and rendering the corresponding PDF section. Modules can be run individually, or combined automatically by the "Full report" function.

| Module | Source file | Function |
|---|---|---|
| Jobs / INFORM | `docs/jobs.py` | Reads `.JBI` files and documents the INFORM program code (listing + instruction table). |
| Parameters | `docs/params.py` | Reads `.PRM` files (`ALL.PRM`, etc.) and produces parameter tables with the current values. |
| Robot points | `docs/points.py` | Extracts the taught positions from `.JBI` files. |
| User Frames / Tools | `docs/uf_tools.py` | Reads tool-calibration data and user-frame definitions. |
| Variable / I/O names | `docs/names.py` | Reads `IONAME.DAT`, `VARNAME.DAT`, `EXIONAME.DAT` and documents the custom names. |
| User groups | `docs/usrgrp.py` | Reads `USRGRPIN.DAT` / `USRGRPOT.DAT` (user I/O groups). |
| Variable backup | `docs/backup.py` | Reads `VAR.DAT` and documents the state of the variables (B, I, D, R, S, P). |
| Data log | `docs/logdata.py` | Reads `LOGDATA.DAT` and generates a multi-column report of the recorded events. |
| Interference cubes | `docs/cubeintf.py` | Reads `CUBEINTF.CND` and documents the cubic interference areas (up to 64 cubes). |
| Form cutting | `docs/formcut.py` | Reads `FORMCUT.CND` and documents the geometric form-cutting conditions. |
| IF Panel | `docs/ifpanel.py` | Reads `IFPANEL.DAT` and documents the configuration of the 15 IF panels. |
| Network | `docs/ipnet.py` | Reads `IPNETCFG.DAT` / `IPNETEX.DAT` and documents the network configuration. |
| JBI flowchart | `docs/flowchart.py` | Generates a graphical flowchart (PDF + draw.io XML) of the execution flow of an INFORM job. |
| Drive (GA500) | `docs/drive.py` | Reads `.YDWIProj` files from DriveWizard Industrial and generates GA500 inverter parameter reports. |

Shared rendering helpers live in `docs/pdf_header.py` (the common page header: logo + creator name + accent bar) and `docs/utils.py`. The creator name shown in the PDF header is read at generation time from `app_state.creator_name` (see §8), so every PDF produced during a session reflects the currently configured name without requiring a rebuild.

### 4.3 Specialised GUI views

Some modules are paired with an interactive view so the data can be inspected — and in some cases edited — on screen before being exported.

| View | Module | Description |
|---|---|---|
| IF Panel View | `gui/ifpanel_view.py` | Interactive visualisation of the IF panels with colours and I/O assignments. |
| Flowchart View | `gui/flowchart_view.py` | Preview of the INFORM flowchart before exporting. |
| UF Tools View | `gui/uf_tools_view.py` | Editable table of tool / user-frame data. |
| UFrame View | `gui/uframe_view.py` | Dedicated user-frame view. |
| Usrgrp View | `gui/usrgrp_view.py` | Visualisation of user I/O groups. |
| Help View | `gui/help_view.py` | S-code parameter guide with search and filter. |

---

## 5. Supported input files

| File | Content |
|---|---|
| `SYSTEM.SYS` | Robot identification and system configuration |
| `PANELBOX.LOG` | Operator-panel event log |
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

## 6. Logging

The `logger.py` module handles writing both to the log file and to the in-app log panel. The log file, `YASKAWAToolsLog.log`, is saved in the same directory as the executable (falling back to `%APPDATA%\YaskawaTools`). Rotation is automatic — the file is capped at **10 MB** — so the log never grows without bound.

Every log message is internationalised through the keys defined in `translations.py`, so the log is written in the language currently selected in the interface. The log records user actions, the paths of generated files, warnings, and errors, giving a complete audit trail of a documentation session.

---

## 7. Internationalisation

The `translations.py` module contains the interface strings for all supported languages:

| Code | Language |
|---|---|
| `IT` | Italiano (Italian) |
| `EN` | English *(default)* |
| `FR` | Français (French) |
| `DE` | Deutsch (German) |
| `ES` | Español (Spanish) |
| `UA` | Українська (Ukrainian) |
| `JA` | 日本語 (Japanese) |

The language is selected from the Top Bar and applied for the current session. When a string is missing for the active language, the application falls back to a defined default so the interface never shows an empty label. Domain-specific string sets (for example the Cubeintf and Form-cutting modules) carry their own per-language tables in the same file.

CJK rendering is enabled application-wide by configuring a font family stack (`Segoe UI`, `Meiryo`, `Yu Gothic`, `Noto Sans CJK JP`, `MS UI Gothic`), so Japanese menu items and labels display correctly.

---

## 8. Paths, security, and user settings

The `secure_paths.py` module centralises the application paths under `%APPDATA%\YaskawaTools`. Writing state files into this directory has two benefits: the data lands in a location whose default ACLs restrict access to the current Windows user, and the application never needs administrator privileges to run.

The following files are written under that directory:

| File | Purpose |
|---|---|
| `auth_state.json` | Persistent lockout counter and lockout-until timestamp (HMAC-signed) |
| `YASKAWAToolsLog.log` | Rotating application log (10 MB cap) |
| `config.json` | User settings: currently the editable creator name |

### Creator name

The creator name is the string displayed in the header of every generated PDF (right of the logo). It defaults to `0THack1A` and can be changed without rebuilding the application:

1. Open **Help → About**.
2. Edit the text field in the **Creator** section.
   The field accepts only Western-alphabet characters, digits, spaces, and `_`, `-`, `.` (enforced client-side by a `QRegularExpressionValidator` with pattern `^[A-Za-zÀ-ÖØ-öø-ÿ0-9 _\-\.]*$`).
3. Press **Save name**.

`config.py` (`save_creator_name`) writes the value atomically (temp file + `os.replace`) to `%APPDATA%\YaskawaTools\config.json`. On next startup, `main.py` calls `config.load_creator_name()` and stores the result in `AppState.creator_name`. All PDF modules call `docs/pdf_header._get_company()` at render time, which reads `main.app_state.creator_name` directly, so the header always reflects the most recently saved name.

The `auth.py` module provides authentication with the following protections:

- **Argon2id** password hashing (`m=131072` / 128 MiB, `t=4`, `p=4`).
- **Persistent lockout** — 3 failed attempts trigger a 5-minute block that survives application restarts.
- **HMAC-protected state file** — the lockout counter and timestamp are integrity-protected with `HMAC-SHA256` keyed by a pepper bound to the machine name; a tampered or transplanted state file fails closed.
- **Constant-time verification floor** of 500 ms per call to defeat timing attacks.

Together with the command-line argument stripping performed in `main.py`, these measures keep the attack surface of the packaged executable small.

---

## 9. Building the executable

The executable is produced with **PyInstaller** from the platform-specific spec file:

```bash
# Windows
pyinstaller main.spec

# macOS
pyinstaller main_macos.spec

# Linux
pyinstaller main_linux.spec
```

The output is placed in `dist/YaskawaTools[.exe|.app|]`. The Windows build is **one-file** (everything packed into a single `.exe`), runs **without a console window** (`console=False`), and is compressed with **UPX**.

Bundled resources (packed into the `assets/` subdirectory of the MEIPASS tree so that `get_resource_path("assets/...")` resolves correctly in both development and frozen mode):

| Resource | Purpose |
|---|---|
| `assets/logo-home.png` | Application logo shown in the top bar and PDF page header |
| `assets/Foto_profilo.jpg` | Profile image shown in the About dialog (Creator section) |
| `langdetect` profiles | Automatic language detection inside JBI files |

Equivalent spec files are provided for the other platforms: `main_linux.spec` (Linux one-file binary) and `main_macos.spec` (macOS `.app` bundle, packaged into a `.dmg` by the CI workflow). Built binaries are distributed via **GitHub Releases**, not committed to the repository.

---

## 10. Python dependencies

```
PySide6
reportlab
openpyxl
pypdf
Pillow
psutil
argon2-cffi
langdetect
deep-translator
beautifulsoup4
```

Install them with:

```bash
pip install -r requirements.txt
```
