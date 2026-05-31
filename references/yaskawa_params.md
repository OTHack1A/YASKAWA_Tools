# YASKAWA YRC1000 — Parametri di riferimento

Parametri S-code e di configurazione del controllore YRC1000.  
Colonna **Valore** = impostazione consigliata/utilizzata (vuota = solo riferimento descrittivo).

---

## S0C — Sistema generale

| Codice | Valore | Descrizione |
|---|---|---|
| S0C682 | | Limita la creazione del file di backup automatico a una sola volta al giorno (0: Disabilitato, 1: Abilitato). |

---

## S1C — Parametri di controllo assi

| Codice | Valore | Descrizione |
|---|---|---|
| S1C1G33 | 12500 | Micro di raccordo nelle movimentazioni in PL=1. |
| S1CxG000 | | Limite superiore di velocità per l'operazione "IN-GUARD-SAFE" (unità: 0,01%). |
| S1CxG045 | | Velocità di collegamento per l'operazione di Jog al livello "LOW". |
| S1CxG046 | | Velocità di collegamento per l'operazione di Jog al livello "MEDIUM". |
| S1CxG047 | | Velocità di collegamento per l'operazione di Jog al livello "HIGH". |
| S1CxG048 | | Velocità di collegamento per l'operazione di Jog al livello "HIGH SPEED". |
| S1CxG056 | | Velocità di ritorno alla posizione di "WORK HOME" rispetto alla velocità massima (unità: 0,01%). |
| S1CxG057 | | Velocità massima per le funzioni di ricerca (Search) (unità: 0,1 mm/s). |
| S1CxG060 | | Limitazione velocità manuale per il funzionamento passo-passo (unità: 0,01%). |
| S1CxG061 | | Limitazione velocità manuale per il funzionamento "Bassa" (unità: 0,01%). |
| S1CxG062 | | Limitazione velocità manuale per il funzionamento "Mid" (unità: 0,01%). |
| S1CxG202 | | Specifica (in bit) l'asse per l'output della posizione attuale (comando) nei registri. |
| S1CxG203 | | Specifica (in bit) l'asse per l'output della posizione attuale (feedback) nei registri. |

---

## S2C — Parametri di sistema operativo

| Codice | Valore | Descrizione |
|---|---|---|
| S2C196 | | Definisce se le coordinate del robot sono ad angolo retto (0) o cilindriche (1). |
| S2C201 | | Controllo della postura durante l'operazione cartesiana di Jog. |
| S2C203 | | Permette (0) o blocca (1) la sola modifica dei passi nel programma. |
| S2C206 | | Inserimento istruzione MOVE: sotto la riga (0) o dopo il prossimo passo (1). |
| S2C211 | | Definisce il livello del linguaggio INFORM (0: Base, 1: Standard, 2: Esteso). |
| S2C214 | | Abilita (1) o disabilita (0) il mantenimento dei valori delle istruzioni nella riga messaggio. |
| S2C231 | | Imposta la modalità Passo/Procedura di test su "FACILE" (0) o "TUTTO" (1). |
| S2C234 | | Protezione in scrittura del numero utensile per il post-teach. |
| S2C320 | | Consente (0) o blocca (1) il post-teach del solo gruppo di assi spostato. |
| S2C333 | | Abilita (1) o disabilita (0) la funzione di commutazione del numero utensile (TOOL NO. SWITCHING). |
| S2C395 | 0 | Permette di caricare IONAME.DAT con i nomi personalizzati (disabilita ALIAS FUNCTION). |
| S2C396 | 0 | Permette di caricare VARNAME.DAT con i nomi personalizzati (disabilita ALIAS FUNCTION). |
| S2C400 | | Parametro necessario per abilitare l'uso del comando `SETUALM` (Allarme utente). |
| S2C413 | | Attiva (1) o disabilita (0) il "cestino" per il ripristino dei JOB cancellati. |
| S2C0230 | 63 | Abilita determinate possibilità (tra cui lo start del programma da PP) anche se il PP è in remoto. |
| S2C0231 | 1 | Abilita la possibilità di comandare il PSTART anche in TEST START. |
| S2C0232 | 1 | Abilita la possibilità di comandare il PSTART anche in TEST START. |
| S2C0235 | 0 | Mantiene i valori dei GPO al riavvio. |
| S2C0264 | 1 | Permette di leggere il valore in mm degli assi esterni (altrimenti solo in PULSE). |
| S2C0265 | 1 | Permette di leggere il valore in mm degli assi esterni (altrimenti solo in PULSE). |
| S2C0266 | 1 | Permette di leggere il valore in mm degli assi esterni (altrimenti solo in PULSE). |
| S2C0421 | 1 | Abilita System JOB. |
| S2C0422 | 1 | Abilita System JOB. |
| S2C0430 | 2 | Smoothing movimenti (per evitare allarme EXCESSIVE SPEED). |
| S2C0431 | | Permette (0) o blocca (1) l'uso di 64 file utensile (TCP). |
| S2C0432 | | Metodo calibrazione utensile: solo coordinate (0), solo posizione (1), coordinate e posizione (2). |
| S2C0433 | | Attiva (0) o disattiva (1) il segnale acustico (bip) durante il teach delle posizioni. |
| S2C0434 | | Abilita (1) o disabilita (0) la visualizzazione delle coordinate doppie con funzione SHIFT. |
| S2C0437 | 1 | Ricorda il punto del cursore sul PP ed esegue la domanda nel caso in cui venga spostato. |
| S2C0438 | 1 | Permette di vedere la chiamata di una macro come una CALL (ci entra dentro). |
| S2C0450 | 1 | Abilita la possibilità di modificare il tool dinamicamente anche con FSU attivo (solo YASKAWA MODE). |
| S2C0688 | | Permette o blocca il passo all'indietro (BWD) senza gruppo asse o in job paralleli. |
| S2C0699 | 13 | Imposta la velocità a LOW ad ogni cambio PLAY→TEACH, SERVO ON e modifica coordinate di esercizio. |
| S2C0700 | 2 | Permette la modifica delle coordinate cartesiane dei frame. |
| S2C0701 | 1 | Permette la modifica dinamica dell'override. |
| S2C0702 | 1 | Per impostazione override da IF/Panel. |
| S2C0709 | 1 | |
| S2C1291 | 1 | Evita che il robot si fermi quando incontra un WAIT già verificato. |
| S2C1364 | 1 | Abilita l'autostart del Remote Pendant Server all'avvio del robot. |
| S2C1503 | | Funzione di miglioramento dell'elaborazione della visualizzazione degli allarmi. |
| S2C1590 | 7 | |
| S2C1699 | 1 | Abilita la gestione dello STOP MODE nel SETUALM anche dentro al System Job. |
| S2C1809 | 1 | |

---

## S3C — Parametri di limite e cinematica

| Codice | Valore | Descrizione |
|---|---|---|
| S3C008-011 | | Limiti software per il Robot 2 sui lati positivi e negativi degli assi X, Y e Z. |
| S3C1192 | 999999999 | Aumenta il limite massimo di spostamento del tool attraverso la funzione SET TOOL. |
| S3C1193 | 999999999 | Aumenta il limite massimo di spostamento del tool attraverso la funzione SET TOOL. |

---

## S4C — Parametri I/O e sicurezza funzionale (FSU)

| Codice | Valore | Descrizione |
|---|---|---|
| S4C032-047 | | Specifica se i dati dei gruppi di input (1-256) sono gestiti come binari o BCD. |
| S4C048-063 | | Specifica se i dati dei gruppi di output (1-256) sono gestiti come binari o BCD. |
| S4C0083 | 65535 | Rende ritentivi tutti gli Auxiliary Relay dal #71930 al #72567. |
| S4C0084 | 65535 | Rende ritentivi tutti gli Auxiliary Relay dal #72570 al #73207. |
| S4C0085 | 65535 | Rende ritentivi tutti gli Auxiliary Relay dal #73210 al #73847. |
| S4C0086 | 65535 | Rende ritentivi tutti gli Auxiliary Relay dal #73850 al #74487. |
| S4C0087 | 65535 | Rende ritentivi tutti gli Auxiliary Relay dal #74490 al #75127. |
| S4C0287 | 50 | Byte di GPI da utilizzare per il cambio override dinamico. |
| S4C0288 | 0 | Valore % di override preso dal byte indicato in S4C0287. |
| S4C0295 | 0 | |
| S4C1132-1147 | | Gestione dati (binario/BCD) per i gruppi di input da 257 a 512. |
| S4C1148-1163 | | Gestione dati (binario/BCD) per i gruppi di output da 257 a 512. |
| S4C1180 | | Parametro relativo al File Utensile (Tool File) nella sicurezza funzionale (FSU). |
| S4C1181 | | File di protezione dalle interferenze dell'utensile (FSU). |
| S4C1182 | | Dati di calibrazione della posizione Home (FSU). |
| S4C1183 | | Dati del limite del raggio d'azione degli assi (FSU). |
| S4C1184 | | Dati di monitoraggio della velocità degli assi (FSU). |
| S4C1185 | | Dati del limite del raggio d'azione del robot (FSU). |
| S4C1186 | | Dati del limite di velocità (FSU). |
| S4C1187 | | Dati di monitoraggio dell'angolo dell'utensile (FSU). |
| S4C1188 | | Monitoraggio cambio utensile / Selezione numero utensile (FSU). |
| S4C1189-1192 | | Parametri di definizione funzionale, sistema, SERVO e servomotore (FSU). |
| S4C1193 | | Parametro di corrispondenza robot (Robot match parameter) per l'istruzione `SETTOOL`. |

---

## RS — Parametri di sistema remoto/FTP

| Codice | Valore | Descrizione |
|---|---|---|
| RS59 | 3 | Possibilità di sovrascrivere i Job caricati dalla USB senza doverli cancellare. |
| RS89 | 1 | Scambio comunicazione FTP. |
| RS214 | 1 | Possibilità di sovrascrivere i Job da FTP. |

---

## R — Parametri robot e cinematica

| Codice | Valore | Descrizione |
|---|---|---|
| R01Gx013 | -30000 | Inclinazione su asse X — inclinazione robot (modificabile solo da Yaskawa). |
| R01Gx014 | -30000 | Inclinazione su asse Y — inclinazione robot (modificabile solo da Yaskawa). |

---

## Relay ausiliari

| Codice | Valore | Descrizione |
|---|---|---|
| #87015 | ON | Permette di eseguire in Remote le stesse operazioni disponibili in Play. |

---

## AxP — Parametri applicazione

| Codice | Valore | Descrizione |
|---|---|---|
| AxP000 | | Specifica l'applicazione (es. "0" per la saldatura ad arco). |
| AxP003 | | Assegnazione file condizioni inizio saldatura per la sorgente di alimentazione 2. |
