<p align="center">
  <img src="./logo.png" alt="Logo GEOP Importer" width="140">
</p>

# GEOP Importer (Sincronizzazione Google Calendar)
<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Copyright" src="https://img.shields.io/badge/Copyright-Alessandro%20Rizzi-0A66C2">
</p>

## ✨ Panoramica
Automatizza:
- estrazione lezioni/esami da GEOP
- export ICS (`exportGEOP.ics`)
- sincronizzazione su un calendario Google dedicato (create / update / delete)

Progetto pensato per Windows con avvio automatico al login.

## 🧭 Navigazione Rapida
- 🚀 Setup: sezioni 2-9
- 🔁 Avvio automatico: sezione 11
- 🛠 Risoluzione problemi: sezione 13
- 🔒 Sicurezza: sezione 14

## ⚙️ 1) Cosa fa lo script

Ad ogni esecuzione:
1. Fa login su GEOP con Selenium.
2. Legge gli eventi settimana per settimana fino a `END_DATE`.
3. Normalizza gli eventi (titolo, inizio, fine, posizione).
4. Genera il file ICS (`exportGEOP.ics`).
5. Sincronizza con Google Calendar:
- crea eventi nuovi
- aggiorna eventi modificati
- elimina eventi rimossi da GEOP

## 📋 2) Prerequisiti

- Windows 10/11
- Python 3.10+
- Google Chrome installato
- Account Google
- Accesso al portale GEOP

## 📦 3) Clone del repository

```powershell
git clone https://github.com/alerizzidev/GeopImporter.git
cd GeopImporter
```

## 🧪 4) Crea ambiente virtuale

```powershell
python -m venv geop-env
.\geop-env\Scripts\activate
```

## 📥 5) Installa dipendenze

```powershell
pip install selenium webdriver-manager colorama google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## 🛠️ 6) Prepara file script

1. Rinomina `scriptexample.py` in `script.py`.
2. Apri `script.py` e imposta:

```python
# GEOP
URL = "https://your-geop-domain.example/"
USERNAME = "YOUR_GEOP_USERNAME"
PASSWORD = "YOUR_GEOP_PASSWORD"
END_DATE = datetime(2026, 7, 31)

# Google Sync
GOOGLE_SYNC_ENABLED = True
GOOGLE_CALENDAR_ID = "YOUR_GOOGLE_CALENDAR_ID"
GOOGLE_CLIENT_SECRET_FILE = "google_client_secret.json"
GOOGLE_TOKEN_FILE = "google_token.json"
GOOGLE_STATE_FILE = "sync_state.json"
```

Note:
- Usa un **calendario Google dedicato** a questa integrazione.
- Lascia `GOOGLE_SYNC_ENABLED = True` per avere sincronizzazione attiva.
- Ad oggi, `scriptexample.py` usa `END_DATE = datetime(2026, 7, 31)`.
- Puoi personalizzare questa data in base alla durata del tuo anno.
- In caso di modifiche su GEOP, imposta `END_DATE` a circa **1 settimana dopo l'ultimo evento visibile su GEOP**.

## 🔐 7) Crea credenziali OAuth Google

In Google Cloud Console:
1. Crea/seleziona progetto.
2. Abilita **Google Calendar API**.
3. Configura schermata consenso OAuth.
4. Crea OAuth client ID di tipo **Desktop app**.
5. Scarica il file JSON delle credenziali.

Metti il file nella root progetto con nome:
- `google_client_secret.json`

## 🆔 8) Recupera il Calendar ID

In Google Calendar Web:
1. Impostazioni
2. Seleziona il calendario dedicato
3. "Integra calendario"
4. Copia "ID calendario"

Incollalo in `GOOGLE_CALENDAR_ID` dentro `script.py`.

## ▶️ 9) Primo avvio (autorizzazione OAuth)

```powershell
.\geop-env\Scripts\python.exe .\script.py
```

Al primo avvio:
- in automatico si apre login/consenso (al termine dell'esecuzione dello script) Google OAuth
- viene creato `google_token.json`

Dalle esecuzioni successive non serve rifare login OAuth.

## 🗂️ 10) File generati (solo locale)

Durante l'esecuzione vengono creati:
- `exportGEOP.ics`
- `google_token.json`
- `sync_state.json`

Non vanno pushati su GitHub.

## 🔁 11) Avvio automatico al login Windows

Crea il file:
- `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GEOP-Sync-Auto.cmd`

Contenuto:

```bat
@echo off
cd /d C:\percorso\del\repo
C:\percorso\del\repo\geop-env\Scripts\python.exe C:\percorso\del\repo\script.py
```

Da quel momento lo script parte ad ogni accesso utente.

## 🔄 12) Come funziona l'aggiornamento

La sync usa `sync_state.json`:
- evento nuovo -> create su Google
- evento modificato -> update su Google
- evento non più presente in GEOP -> delete su Google

Così il calendario Google resta allineato ai cambiamenti GEOP.

## 🧯 13) Problemi comuni e soluzioni

### Non trova eventi
- Controlla `URL`, `USERNAME`, `PASSWORD`
- Verifica di essere sulla vista calendario corretta in GEOP
- Se GEOP è lento, aumenta timeout

### OAuth non si apre
- Verifica presenza di `google_client_secret.json` nella root progetto
- Verifica Google Calendar API abilitata
- Elimina `google_token.json` corrotto e rilancia

### Errori permessi API
- Verifica che il tuo account sia tra i test users OAuth
- Verifica che il calendario (`GOOGLE_CALENDAR_ID`) sia tuo o condiviso con permessi scrittura

### Calendario vuoto o non aggiornato
- Elimina `sync_state.json` e rilancia una volta per ricostruire la mappa

## 🔒 14) Sicurezza consigliata

- Non committare mai credenziali personali.
- Tieni `google_client_secret.json`, `google_token.json` e file personali solo in locale.
- Se una credenziale viene esposta, ruotala subito.

## ✅ 15) Routine consigliata

1. Configura una volta lo script.
2. Lascialo in auto-avvio al login.
3. Se serve aggiornamento immediato, eseguilo manualmente.
4. Su iPhone usa lo stesso account Google per vedere aggiornamenti automatici.

## ©️ 16) Copyright e attribuzione

Copyright (c) Alessandro Rizzi.

Questo progetto puo' essere usato, copiato e adattato da chiunque per uso personale o didattico, ma l'attribuzione deve essere mantenuta.
Non rimuovere il credito all'autore originale e non presentare questo progetto come lavoro originale proprio.



