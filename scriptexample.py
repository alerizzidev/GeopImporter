from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from datetime import datetime
import time
import re
import html as html_parser
import os
import json
import hashlib
import sys
from zoneinfo import ZoneInfo

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    COLOR_ENABLED = True
except Exception:
    COLOR_ENABLED = False

    class _NoColor:
        BLACK = ""
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        WHITE = ""
        RESET_ALL = ""
        BRIGHT = ""

    Fore = _NoColor()
    Style = _NoColor()

ORANGE = "\033[38;5;208m" if COLOR_ENABLED else ""

# =========================
# CONFIG
# =========================
# GEOP
URL = "https://your-geop-domain.example/"
USERNAME = "YOUR_GEOP_USERNAME"
PASSWORD = "YOUR_GEOP_PASSWORD"

# MODIFICA QUI: data limite fino a cui importare lezioni/esami.
# Consiglio: imposta circa 1 settimana dopo l'ultimo evento visibile su GEOP.
END_DATE = datetime(2026, 7, 31)
TIMEZONE = "Europe/Rome"
OUTPUT_ICS = "exportGEOP.ics"

# Google Sync (calendario dedicato)
GOOGLE_SYNC_ENABLED = True
GOOGLE_CALENDAR_ID = "YOUR_GOOGLE_CALENDAR_ID"  # es: abcdef123456@group.calendar.google.com
GOOGLE_CLIENT_SECRET_FILE = "google_client_secret.json"
GOOGLE_TOKEN_FILE = "google_token.json"
GOOGLE_STATE_FILE = "sync_state.json"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# =========================
# HELPERS
# =========================
def parse_header_dates(driver):
    headers = driver.find_elements(By.CLASS_NAME, "fc-day-header")
    dates = []

    for h in headers:
        text = h.text.strip()
        m = re.search(r"(\d{1,2})/(\d{1,2})", text)
        if not m:
            continue

        day = int(m.group(1))
        month = int(m.group(2))
        dates.append(datetime(2026, month, day))

    return dates


def clean_html_text(html: str) -> str:
    text = html_parser.unescape(html)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
            .replace(";", r"\;")
            .replace(",", r"\,")
            .replace("\n", r"\n")
    )


def fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def print_divider(title: str = "") -> None:
    bar = "═" * 68
    if title:
        print(f"{Fore.CYAN}{Style.BRIGHT}\n{bar}\n  {title}\n{bar}{Style.RESET_ALL}")
    else:
        print(f"{Fore.CYAN}{Style.BRIGHT}{bar}{Style.RESET_ALL}")


def log_info(message: str) -> None:
    print(f"{Fore.BLUE}ℹ️  {message}{Style.RESET_ALL}")


def log_success(message: str) -> None:
    print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")


def log_warn(message: str) -> None:
    print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")


def log_step(message: str) -> None:
    print(f"{Fore.MAGENTA}➡️  {message}{Style.RESET_ALL}")


def log_hack(message: str) -> None:
    print(f"{Fore.CYAN}{Style.BRIGHT}{message}{Style.RESET_ALL}")


def log_orange(message: str) -> None:
    print(f"{ORANGE}{message}{Style.RESET_ALL}")


def validate_required_config() -> bool:
    missing = []

    if "your-geop-domain.example" in URL.lower() or not URL.strip():
        missing.append("URL")
    if USERNAME.strip() in {"", "YOUR_GEOP_USERNAME"}:
        missing.append("USERNAME")
    if PASSWORD.strip() in {"", "YOUR_GEOP_PASSWORD"}:
        missing.append("PASSWORD")

    if GOOGLE_SYNC_ENABLED and GOOGLE_CALENDAR_ID.strip() in {"", "YOUR_GOOGLE_CALENDAR_ID"}:
        missing.append("GOOGLE_CALENDAR_ID")

    if missing:
        log_warn("Configurazione incompleta: " + ", ".join(missing))
        log_info("Apri script.py e compila i valori placeholder prima di eseguire.")
        return False
    return True


def to_rfc3339(dt: datetime) -> str:
    return dt.replace(tzinfo=ZoneInfo(TIMEZONE)).isoformat()


def event_payload_hash(title: str, start_dt: datetime, end_dt: datetime, aula: str) -> str:
    raw = "|".join([title, start_dt.isoformat(), end_dt.isoformat(), aula or ""])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def extract_source_id(event_el, outer_html: str, title: str, aula: str) -> str:
    attr_candidates = ["data-event-id", "data-id", "data-uid", "id"]
    for attr in attr_candidates:
        value = (event_el.get_attribute(attr) or "").strip()
        if value:
            return f"attr:{value}"

    # Fallback: cerca un id numerico nel markup dell'evento
    m = re.search(r"(?:event|id)[-:=/'\"\\s]+([A-Za-z0-9_-]{4,})", outer_html, re.IGNORECASE)
    if m:
        return f"html:{m.group(1)}"

    # Ultimo fallback: fingerprint testuale (meno robusto ai rinvii, ma evita duplicati casuali)
    stable_text = re.sub(r"\s+", " ", f"{title}|{aula}").strip().lower()
    digest = hashlib.sha1(stable_text.encode("utf-8")).hexdigest()[:16]
    return f"fp:{digest}"


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"events": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("events"), dict):
            return data
    except Exception:
        pass
    return {"events": {}}


def save_state(path: str, state: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def build_google_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CLIENT_SECRET_FILE, GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)

        with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def sync_to_google(events_data: list) -> None:
    if not GOOGLE_SYNC_ENABLED:
        log_info("Sync Google disattivata (GOOGLE_SYNC_ENABLED=False)")
        return

    if not GOOGLE_CALENDAR_ID.strip():
        log_warn("Sync Google saltata: imposta GOOGLE_CALENDAR_ID nel file script.py")
        return

    try:
        service = build_google_service()
    except ModuleNotFoundError:
        log_warn("Dipendenze Google mancanti. Installa: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return
    except FileNotFoundError:
        log_warn(f"File OAuth mancante: {GOOGLE_CLIENT_SECRET_FILE}")
        return
    except Exception as e:
        log_warn(f"Impossibile inizializzare Google API: {e}")
        return

    old_state = load_state(GOOGLE_STATE_FILE)
    old_events = old_state.get("events", {})
    new_state_events = {}
    stats = {"created": 0, "updated": 0, "deleted": 0, "unchanged": 0}

    # Evita collisioni se source_id fallback produce lo stesso valore
    used_source_ids = set()

    for event in events_data:
        source_id = event["source_id"]
        if source_id in used_source_ids:
            source_id = f"{source_id}:{event['start'].strftime('%Y%m%dT%H%M')}"
        used_source_ids.add(source_id)

        payload_hash = event_payload_hash(event["title"], event["start"], event["end"], event["aula"])
        old_row = old_events.get(source_id, {})
        old_hash = old_row.get("payload_hash")
        old_google_event_id = old_row.get("google_event_id")

        body = {
            "summary": event["title"],
            "start": {"dateTime": to_rfc3339(event["start"]), "timeZone": TIMEZONE},
            "end": {"dateTime": to_rfc3339(event["end"]), "timeZone": TIMEZONE},
            "extendedProperties": {"private": {"geop_managed": "1", "geop_source_id": source_id}},
        }
        if event["aula"]:
            body["location"] = event["aula"]

        if not old_google_event_id:
            created = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=body).execute()
            new_state_events[source_id] = {
                "google_event_id": created["id"],
                "payload_hash": payload_hash,
            }
            stats["created"] += 1
            continue

        if payload_hash == old_hash:
            new_state_events[source_id] = old_row
            stats["unchanged"] += 1
            continue

        try:
            updated = service.events().update(
                calendarId=GOOGLE_CALENDAR_ID,
                eventId=old_google_event_id,
                body=body
            ).execute()
            new_state_events[source_id] = {
                "google_event_id": updated["id"],
                "payload_hash": payload_hash,
            }
            stats["updated"] += 1
        except Exception:
            # Se l'evento non esiste più su Google, ricrealo.
            recreated = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=body).execute()
            new_state_events[source_id] = {
                "google_event_id": recreated["id"],
                "payload_hash": payload_hash,
            }
            stats["created"] += 1

    # Cancella eventi non più presenti nel calendario GEOP
    for source_id, old_row in old_events.items():
        if source_id in new_state_events:
            continue
        event_id = old_row.get("google_event_id")
        if not event_id:
            continue
        try:
            service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()
            stats["deleted"] += 1
        except Exception:
            pass

    save_state(GOOGLE_STATE_FILE, {"events": new_state_events})
    log_success(
        "Sync Google completata -> "
        f"creati: {stats['created']}, aggiornati: {stats['updated']}, "
        f"eliminati: {stats['deleted']}, invariati: {stats['unchanged']}"
    )


# =========================
# BROWSER
# =========================
if not validate_required_config():
    raise SystemExit(1)

options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")

log_orange("🚀 Script in esecuzione...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(URL)
wait = WebDriverWait(driver, 40)

# =========================
# LOGIN
# =========================
wait.until(EC.presence_of_element_located((By.NAME, "username")))
driver.find_element(By.NAME, "username").send_keys(USERNAME)
driver.find_element(By.NAME, "password").send_keys(PASSWORD)

try:
    driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']").click()
except Exception:
    driver.execute_script("document.getElementById('frm_login').submit();")

log_success("🔐 Accesso a GEOP eseguito")

try:
    wait.until(
        lambda d: d.find_elements(By.CLASS_NAME, "fc-toolbar")
        or d.find_elements(By.CLASS_NAME, "fc-view-container")
    )
except TimeoutException:
    # Retry submit in headless mode: some pages ignore the first click.
    log_warn("Login non confermato al primo tentativo, retry submit...")
    driver.execute_script("document.getElementById('frm_login').submit();")
    wait.until(
        lambda d: d.find_elements(By.CLASS_NAME, "fc-toolbar")
        or d.find_elements(By.CLASS_NAME, "fc-view-container")
    )

log_success("✅ Calendario caricato")

# =========================
# STORAGE
# =========================
events_data = []
seen = set()
week = 0

# =========================
# LOOP SETTIMANE
# =========================
while True:
    week += 1
    print_divider(f"🧠 SCAN SETTIMANA {week}")
    time.sleep(2)

    dates = parse_header_dates(driver)
    log_warn(f"ℹ️ Timeline rilevata: {dates}")

    if not dates:
        break

    # PRENDI LE COLONNE GIORNO
    containers = driver.find_elements(By.CLASS_NAME, "fc-event-container")
    log_orange(f"🧩 Nodi giorno agganciati: {len(containers)}")

    for col_index, container in enumerate(containers):

        if col_index >= len(dates):
            continue

        day_date = dates[col_index]

        events = container.find_elements(By.CLASS_NAME, "fc-time-grid-event")

        for ev in events:
            try:
                html = ev.get_attribute("innerHTML")
                outer_html = ev.get_attribute("outerHTML") or html or ""
                if not html:
                    continue

                # ORARIO
                try:
                    time_el = ev.find_element(By.CLASS_NAME, "fc-time")
                    time_text = time_el.get_attribute("data-full") or time_el.text
                except Exception:
                    continue

                time_text = time_text.replace("–", "-").replace("—", "-")

                m = re.search(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", time_text)
                if not m:
                    continue

                start_time = m.group(1)
                end_time = m.group(2)

                # TESTO
                text = clean_html_text(html)

                # AULA
                aula = ""
                aula_match = re.search(r"Aula:\s*(.+)$", text, re.IGNORECASE)
                if aula_match:
                    raw_aula = aula_match.group(1).strip()
                    normalized_aula = re.sub(r"<br\s*/?>", "", raw_aula, flags=re.IGNORECASE)
                    normalized_aula = normalized_aula.strip("[](){} ").strip()
                    if normalized_aula.upper() == "ESTERNA":
                        normalized_aula = "Esterna"
                    aula = f"AULA: {normalized_aula}"

                # EMOJI
                emoji = "📝" if "ESAME" in text.upper() else "📚"

                # TITOLO PULITO
                title = re.sub(r"\d{2}:\d{2}\s*-\s*\d{2}:\d{2}", "", text)
                title = re.sub(r"Aula:.*", "", title)
                title = re.sub(r"\s+", " ", title).strip(" -")

                final_title = f"{emoji} {title}"
                source_id = extract_source_id(ev, outer_html, final_title, aula)

                # DATETIME
                start_dt = datetime.strptime(f"{day_date.date()} {start_time}", "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(f"{day_date.date()} {end_time}", "%Y-%m-%d %H:%M")

                # DUPLICATI
                key = (source_id, final_title, start_dt, end_dt, aula)
                if key in seen:
                    continue
                seen.add(key)

                events_data.append({
                    "source_id": source_id,
                    "title": final_title,
                    "start": start_dt,
                    "end": end_dt,
                    "aula": aula,
                })

                log_success(f"Evento estratto -> {final_title} | {day_date.date()}")

            except Exception as e:
                print(f"{Fore.RED}⚠️  Evento scartato: {e}{Style.RESET_ALL}")

    # STOP RANGE
    if all(d > END_DATE for d in dates):
        print(f"{Fore.RED}🛑 Fine range raggiunto: stop scansione{Style.RESET_ALL}")
        break

    # NEXT WEEK
    try:
        header_before = driver.find_element(By.CLASS_NAME, "fc-toolbar").text
        driver.find_element(By.CLASS_NAME, "fc-next-button").click()

        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CLASS_NAME, "fc-toolbar").text != header_before
        )
        log_step("Shift alla settimana successiva")
    except Exception:
        break

driver.quit()

# =========================
# CREA ICS
# =========================
with open(OUTPUT_ICS, "w", encoding="utf-8", newline="") as f:
    f.write("BEGIN:VCALENDAR\r\n")
    f.write("VERSION:2.0\r\n")
    f.write("PRODID:-//GEOP Importer//IT\r\n")

    for i, event in enumerate(events_data, start=1):
        title = event["title"]
        start = event["start"]
        end = event["end"]
        aula = event["aula"]
        f.write("BEGIN:VEVENT\r\n")
        f.write(f"UID:geop-{i}-{fmt(start)}@local\r\n")
        f.write(f"DTSTAMP:{fmt(datetime.now())}\r\n")
        f.write(f"DTSTART:{fmt(start)}\r\n")
        f.write(f"DTEND:{fmt(end)}\r\n")
        f.write(f"SUMMARY:{ics_escape(title)}\r\n")
        if aula:
            f.write(f"LOCATION:{ics_escape(aula)}\r\n")
        f.write("END:VEVENT\r\n")

    f.write("END:VCALENDAR\r\n")

print_divider("💾 EXPORT COMPLETATO")
log_success(f"✅ Build ICS completata: {len(events_data)} eventi in {OUTPUT_ICS}")
sync_to_google(events_data)


