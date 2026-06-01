# YASKAWA Tools — User Guide

A practical guide to installing and using **YASKAWA Tools**, the desktop application
that turns a **YASKAWA YRC1000** controller backup into ready-to-print PDF
documentation, and produces parameter reports for **GA500** inverters.

> This guide is for end users. For the technical/architecture overview see
> [`docs/OVERVIEW.md`](docs/OVERVIEW.md).

---

## 🔑 Getting access (password required)

The application is protected by a password. **It is not published here.**

**To obtain the password, request it via direct message (DM) to the author — `0THack1A`.**
Do **not** open a public issue with password requests.

Security notes you should know:
- After **3 wrong attempts** the app locks for **5 minutes**. The lockout is
  persistent — closing and reopening the app does **not** reset it.
- The password is checked against an Argon2id hash; the plaintext is never stored.

---

## 1. Download & install

1. Go to the [**Releases**](../../releases) page.
2. Download the build for your operating system:
   | OS | File |
   |---|---|
   | Windows 10/11 (64-bit) | `YaskawaTools.exe` |
   | Linux | `YaskawaTools` |
   | macOS | `YaskawaTools.dmg` |
3. **(Recommended) Verify the download** against the SHA-256 published in the
   project [README](README.md#digest-control):
   ```powershell
   # Windows (PowerShell)
   Get-FileHash .\YaskawaTools.exe -Algorithm SHA256
   ```
   ```bash
   # Linux / macOS
   sha256sum YaskawaTools        # Linux
   shasum -a 256 YaskawaTools.dmg # macOS
   ```

No installation is needed — the program is a single self-contained executable.

### Windows SmartScreen note
The executable is not code-signed, so Windows may show
*"Windows protected your PC"*. If you trust the source, click **More info →
Run anyway**. (Verifying the SHA-256 first is the safe way to confirm integrity.)

---

## 2. First launch & login

1. Double-click the downloaded file to start the app.
2. At the login window, enter the password you received by DM and confirm.
3. On success the main window opens with your Windows username shown in the top bar.

---

## 3. Loading a robot backup

Most functions work on a **robot backup folder** — the folder you exported from the
YRC1000 controller, containing files such as `SYSTEM.SYS`, `ALL.PRM`, `*.JBI`,
`*.DAT`, `*.CND`, etc.

1. Use the menu/side panel to pick a function.
2. When prompted, **select the backup folder** (not a single file).
3. The app parses the relevant files and shows a preview or generates a PDF.

> Tip: you can set a default **work folder** so you don't have to browse every time.

---

## 4. What you can do

### Generate the full documentation (one PDF)
Produces a single comprehensive PDF for the whole robot cell — cover page, table of
contents, panel log, jobs, parameters, user frames, tool files, and attachments —
all merged automatically. Best when you need a complete dossier of an installation.

### Generate individual section reports
Each section can also be produced on its own:

| Section | Source files | What you get |
|---|---|---|
| Nameplate (Targhetta) | `SYSTEM.SYS` | Robot model, software version, axis configuration |
| Panel | `PANELBOX.LOG` | Operator-panel configuration |
| Jobs / INFORM | `*.JBI` | Job code listing + instruction tables |
| Parameters | `*.PRM` (`ALL.PRM`, …) | Parameter tables with current values |
| Robot points | `*.JBI` | Taught positions |
| User frames / Tools | tool & frame data | Calibration data |
| Variable / I/O names | `IONAME.DAT`, `VARNAME.DAT`, `EXIONAME.DAT` | Custom names |
| User groups | `USRGRPIN.DAT`, `USRGRPOT.DAT` | User I/O groups |
| Variable backup | `VAR.DAT` | Variable state (B, I, D, R, S, P) |
| Data log | `LOGDATA.DAT` | Recorded events report |
| Interference cubes | `CUBEINTF.CND` | Cubic interference areas (up to 64) |
| Form cutting | `FORMCUT.CND` | Form-cutting conditions |
| IF panel | `IFPANEL.DAT` | The 15 IF panels |
| Network | `IPNETCFG.DAT`, `IPNETEX.DAT` | Network configuration |

### INFORM flowchart
Generates a graphical flowchart of a JBI job's execution flow, exportable as **PDF**
and as **draw.io XML** for further editing.

### Interactive IF Panel viewer/editor
Visualises the 15 IF panel pages with colours and I/O assignments; you can edit
cells and export an updated `IFPANEL.DAT`.

### Edit & export back to the controller
Some views are editable and can write controller-format files back out:
- **Tools** — configure up to 64 TCP tool frames and export `TOOL.CND`.
- **User Frames** — view/edit the 63 user frames and export `UFRAME.CND`.
- **Names** — fill an Excel template with variable/I/O names and generate the
  corresponding `*.DAT` files.
- **Compile** — write values into `VAR.DAT`.

### GA500 inverter report
Open a **DriveWizard Industrial** project file (`.YDWIProj`) to parse the GA500
parameters and produce a parameter report (PDF/Excel) with descriptions for all
600+ parameters.

---

## 5. Previews & exporting

When a document is generated, the app shows a **PDF preview** where you can:
- zoom in/out and scroll,
- click table-of-contents entries to jump to a section,
- **Save** the PDF to a folder of your choice (it then offers to open that folder),
- where available, **export to Excel** instead of PDF.

---

## 6. Interface basics

- **Theme** — toggle light/dark from the top bar.
- **Language** — switch at runtime between **English, Italian, French, German,
  Spanish, Ukrainian, and Japanese**.
- **Log panel** — a collapsible panel shows actions, generated files, warnings and
  errors in real time. A rotating log file (`YASKAWAToolsLog.log`, capped at 10 MB)
  is also written under `%APPDATA%\YaskawaTools`.

---

## 7. Troubleshooting

| Symptom | What to do |
|---|---|
| *"Windows protected your PC"* on launch | The app isn't code-signed — choose **More info → Run anyway** (verify the SHA-256 first). |
| Locked out after wrong passwords | Wait **5 minutes**; the lockout is intentional and persists across restarts. |
| A function asks for a folder and finds nothing | Make sure you selected the **backup folder**, and that it contains the expected files (see the tables above). |
| Japanese / Cyrillic text not rendering | The app falls back to system fonts; on Windows 10/11 the required fonts are present by default. |
| Need to report a bug | Open an issue on the repository — but **never post the password** there. |

---

## License

MIT — see [LICENSE](LICENSE).
