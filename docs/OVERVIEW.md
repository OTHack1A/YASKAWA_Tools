# YASKAWA Tools — Documentazione applicativa

Versione: v1.1.0 build 1  
Piattaforma: Windows 10/11 (64-bit)  
Dipendenze principali: Python 3.x, PySide6, ReportLab, openpyxl, pypdf

<img width="1004" height="736" alt="image" src="https://github.com/user-attachments/assets/7255520b-ebcb-44b8-ba7a-0f5f8b18799f" />


---

## Panoramica

YASKAWA Tools è un'applicazione desktop per la gestione e la documentazione dei controllori **YASKAWA YRC1000**. Permette di caricare il backup del robot (cartella con i file `.DAT`, `.PRM`, `.JBI`, ecc.), analizzarne il contenuto e generare documentazione PDF strutturata.

L'interfaccia è protetta da password (Argon2id), supporta tema chiaro/scuro e tre lingue (IT / EN / JA).

---

## Avvio e autenticazione

All'avvio viene mostrata una finestra di login. Il sistema impone un massimo di **3 tentativi** prima di attivare un lockout di **5 minuti**. Lo stato del lockout è persistente (file `auth_state.json` in `%APPDATA%\YaskawaTools`), quindi non viene azzerato riaprendo l'applicazione.

La password è verificata con hash Argon2id. Ogni chiamata di verifica ha un tempo minimo di 500 ms per neutralizzare attacchi timing.

---

## Struttura dell'interfaccia

```
┌─────────────────────────────────────────┐
│  Top Bar  (logo · utente · tema · lingua)│
├──────────────┬──────────────────────────┤
│  Tool Panel  │  Area di lavoro          │
│  (menu       │  (viste dinamiche)       │
│   laterale)  │                          │
├──────────────┴──────────────────────────┤
│  Log Panel  (collassabile)              │
└─────────────────────────────────────────┘
```

- **Top Bar** (`gui/top_bar.py`): mostra il nome utente loggato, pulsanti per tema e lingua.
- **Tool Panel** (`gui/tool_panel.py`): pannello laterale con i pulsanti delle funzioni principali.
- **Main Window** (`gui/main_window.py`): gestisce il menu, carica la cartella robot, ospita le viste.
- **Log Panel**: area collassabile che mostra in tempo reale gli eventi applicativi.

---

## Funzioni disponibili

### Documentazione robot (menu principale)

Tutte le funzioni richiedono di selezionare la **cartella backup del robot** (contenente i file esportati dal YRC1000).

| Voce menu | Modulo | Descrizione |
|---|---|---|
| Targhetta | `docs/targhetta.py` | Legge `SYSTEM.SYS` e genera una scheda identificativa del robot (modello, versione SW, configurazione assi). |
| Panel | `docs/panel.py` | Legge `PANELBOX.LOG` e documenta la configurazione del pannello operatore. |
| Completa | `docs/completa.py` | Genera il PDF completo unendo tutti i moduli: Targhetta → TOC → Panel → JOB → Parametri → UF/Tools → Allegati. |
| Help | `gui/help_view.py` | Visualizza la guida embedded ai parametri YRC1000 (`docs/help_data.py`), consultabile e filtrabile. |
| Registro | — | Mostra il log di sessione con possibilità di esportarlo. |

### Moduli di parsing e generazione PDF

| Modulo | File sorgente | Funzione |
|---|---|---|
| JOB / INFORM | `docs/jobs.py` | Legge i file `.JBI` e genera documentazione del codice INFORM (listato + tabella istruzioni). |
| Parametri | `docs/params.py` | Legge i file `.PRM` (`ALL.PRM`, ecc.) e genera tabelle parametri con valori correnti. |
| Punti robot | `docs/points.py` | Estrae le posizioni insegnate dai file `.JBI`. |
| User Frames / Tools | `docs/uf_tools.py` | Legge i dati di calibrazione utensili e frame utente. |
| Nomi variabili/IO | `docs/names.py` | Legge `IONAME.DAT`, `VARNAME.DAT`, `EXIONAME.DAT` e documenta i nomi personalizzati. |
| Gruppi utente | `docs/usrgrp.py` | Legge `USRGRPIN.DAT` / `USRGRPOT.DAT` (gruppi I/O utente). |
| Backup variabili | `docs/backup.py` | Legge `VAR.DAT` e documenta lo stato delle variabili (B, I, D, R, S, P). |
| Log dati | `docs/logdata.py` | Legge `LOGDATA.DAT` e genera report multi-colonna degli eventi registrati. |
| Cubeintf | `docs/cubeintf.py` | Legge `CUBEINTF.CND` e documenta le aree di interferenza cubica (fino a 64 cubi). |
| Form Cutting | `docs/formcut.py` | Legge `FORMCUT.CND` e documenta le condizioni di taglio geometrico. |
| IF Panel | `docs/ifpanel.py` | Legge `IFPANEL.DAT` e documenta la configurazione dei 15 pannelli IF. |
| Rete | `docs/ipnet.py` | Legge `IPNETCFG.DAT` / `IPNETEX.DAT` e documenta la configurazione di rete. |
| Flowchart JBI | `docs/flowchart.py` | Genera un flowchart grafico (PDF + draw.io) del flusso di esecuzione dei JOB INFORM. |
| Drive (GA500) | `docs/drive.py` | Legge i file `.YDWIProj` di DriveWizard Industrial e genera report dei parametri inverter GA500. |

### Viste specializzate (GUI)

| Vista | Modulo | Descrizione |
|---|---|---|
| IF Panel View | `gui/ifpanel_view.py` | Visualizzazione interattiva dei pannelli IF con colori e configurazione I/O. |
| Flowchart View | `gui/flowchart_view.py` | Anteprima del flowchart INFORM prima dell'esportazione. |
| UF Tools View | `gui/uf_tools_view.py` | Tabella editabile dei dati utensile/frame utente. |
| UFrame View | `gui/uframe_view.py` | Vista dedicata ai frame utente. |
| Usrgrp View | `gui/usrgrp_view.py` | Visualizzazione gruppi I/O utente. |
| Help View | `gui/help_view.py` | Guida ai parametri S-code con ricerca e filtro. |

---

## Sistema di logging

Il modulo `logger.py` gestisce la scrittura su file e sul log panel in-app. Il file di log è `YASKAWAToolsLog.log`, salvato nella stessa directory dell'eseguibile (o in `%APPDATA%\YaskawaTools`). La rotazione del log è gestita automaticamente per evitare file di dimensioni eccessive.

Tutti i messaggi sono internazionalizzati tramite le chiavi in `translations.py`.

---

## Internazionalizzazione

Il modulo `translations.py` contiene le stringhe dell'interfaccia in tre lingue:

| Codice | Lingua |
|---|---|
| `IT` | Italiano |
| `EN` | English |
| `FR' | French |
| `DE` | Deutch|
| `ES` | Espagnol |
| `UA` | Uckranian |
| `JA` | 日本語 (Japanese) |

La lingua è selezionabile dalla Top Bar e viene mantenuta per la sessione corrente.

---

## Percorsi e sicurezza

Il modulo `secure_paths.py` centralizza i percorsi applicativi (`%APPDATA%\YaskawaTools`). Questo garantisce che i file di stato (lockout, log) vengano scritti in una directory con ACL ristretti all'utente Windows corrente, senza richiedere privilegi di amministratore.

Il modulo `auth.py` gestisce l'autenticazione con le seguenti protezioni:
- Hash Argon2id (m=65536, t=3, p=4)
- Lockout persistente (3 tentativi → 5 min di blocco)
- Tempo di verifica minimo di 500 ms (anti-timing attack)

---

## Build dell'eseguibile

L'eseguibile viene generato con **PyInstaller** usando il file `main.spec`.

```bash
pyinstaller main.spec
```

L'output viene prodotto in `dist/YaskawaTools.exe`. Il build è one-file (tutto impacchettato in un singolo `.exe`), senza finestra console (`console=False`), con compressione UPX abilitata.

Le risorse bundled sono:
- `assets/logo-home.png` — icona applicazione
- `assets/Foto_profilo.jpg` — immagine profilo nella Top Bar
- Profili `langdetect` — per il rilevamento automatico della lingua nei file JBI

---

## Dipendenze Python

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

Installazione:

```bash
pip install -r requirements.txt
```
