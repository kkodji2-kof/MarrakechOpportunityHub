from __future__ import annotations
import re
import unicodedata
from urllib.parse import urlparse
import pandas as pd

def strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
def norm_key(text) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return re.sub(r"[^a-z0-9]", "", strip_accents(text).lower())
def clean_spaces(text) -> str | None:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    out = re.sub(r"\s+", " ", str(text)).strip()
    return out or None
def to_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None

EMAIL_STRICT = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.[a-z]{2,}$")
BAD_LOCAL = {"needhelp", "exemple", "example", "email", "test", "votre", "nom", "name",
             "user", "you", "xxx", "john", "jane"}
BAD_DOMAINS = {"company.com", "address.com", "monsite.fr", "votresite.com", "votredomaine.com",
               "email.com", "example.com", "exemple.com", "domain.com", "sentry.io",
               "wixpress.com", "sentry-next.wixpress.com"}
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "svg", "webp"}
FREE_MAIL = {"gmail.com", "hotmail.com", "hotmail.fr", "yahoo.fr", "yahoo.com", "outlook.com", "outlook.fr"}
GENERIC_TLD = {"co", "pro", "me", "io", "ai", "com", "net", "org", "tech", "dev", "app", "info", "biz"}
PRIORITY_LOCALS = ["recrut", "rh", "hr", "job", "career", "carri", "stage", "talent", "emploi"]


def extract_emails(raw) -> tuple[list[str], list[str]]:
    """Retourne (emails à la syntaxe valide, adresses à la syntaxe invalide).

    Retire le HTML résiduel (<span>), les préfixes http:// / mailto: et sépare les
    cellules contenant plusieurs adresses.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return [], []
    text = re.sub(r"<[^>]+>", "", str(raw))
    text = re.sub(r"(?i)mailto:|https?://", "", text)
    valid, invalid = [], []
    for token in re.split(r"[;,\s]+", text):
        token = token.strip(".,;()[]").lower()
        if "@" not in token:
            continue
        bucket = valid if EMAIL_STRICT.match(token) else invalid
        if token not in bucket:
            bucket.append(token)
    return valid, invalid


def registered_domain(host: str) -> str:
    host = re.sub(r"^www\.", "", host.lower().split(":")[0])
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def site_domain(url) -> str | None:
    if url is None or (isinstance(url, float) and pd.isna(url)) or not str(url).strip():
        return None
    value = str(url).strip()
    value = value if value.startswith("http") else "http://" + value
    try:
        host = urlparse(value).netloc
    except ValueError:
        return None
    return registered_domain(host) if host else None


def check_email(email: str, site=None) -> tuple[str, str]:
    """Contrôle un email. Statuts : « Validé », « À vérifier », « Rejeté ».

    « Validé » signifie : syntaxe correcte, pas d'adresse modèle, domaine cohérent avec
    le site de l'entreprise. Le script ne teste PAS si la boîte existe réellement.
    """
    local, domain = email.split("@")
    tld = domain.split(".")[-1]
    if local in BAD_LOCAL or domain in BAD_DOMAINS:
        return "Rejeté", "adresse modèle / placeholder"
    if tld in IMAGE_EXT:
        return "Rejeté", "faux email (nom de fichier image)"
    if domain in FREE_MAIL:
        return "À vérifier", "messagerie gratuite (gmail, hotmail…) : à confirmer"
    site_dom = site_domain(site)
    email_dom = registered_domain(domain)
    if site_dom:
        a, b = site_dom.split(".")[0], email_dom.split(".")[0]
        if a != b and a not in b and b not in a:
            return "À vérifier", "domaine de l'email différent du site de l'entreprise"
    foreign = len(tld) == 2 and tld != "ma" and tld not in GENERIC_TLD
    if foreign and (not site_dom or site_dom.split(".")[-1] != tld):
        return "À vérifier", "domaine pays étranger (hors Maroc)"
    return "Validé", "format OK + domaine cohérent" if site_dom else "format OK (pas de site pour croiser)"

def rank_email(email: str) -> int:
    """Plus le rang est bas, plus l'adresse est adaptée à une candidature (recrutement > contact)."""
    local = email.split("@")[0]
    for i, key in enumerate(PRIORITY_LOCALS):
        if key in local:
            return i
    return 50 if local == "contact" else 60

def normalize_phone(raw) -> str | None:
    """Met les numéros marocains au format +212XXXXXXXXX ; garde les autres tels quels."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("00212"):
        digits = digits[2:]
    if digits.startswith("212") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 10 and digits.startswith("0") and digits[1] in "5678":
        return "+212" + digits[1:]
    return clean_spaces(raw)

def detect_city(address) -> str:
    """Ville déduite de l'adresse."""
    if address is None or (isinstance(address, float) and pd.isna(address)):
        return "Inconnue"
    text = str(address)
    if re.search(r"marrakech|marrakesh|مراكش", text, re.I):
        return "Marrakech"
    for city in ["Casablanca", "Rabat", "Tangier", "Tanger", "Agadir", "Fès", "Fes", "Lausanne", "Paris"]:
        if re.search(city, text, re.I):
            return city
    match = re.search(r",\s*([A-Za-zÀ-ÿ' \-]+?)\s*\d{4,5}\s*$", text)
    return match.group(1).strip() if match else "Inconnue"
