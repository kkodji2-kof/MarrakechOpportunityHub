
"""
ÉTAPE 1 — DATA COLLECTION
MarrakechOpportunityHub

Sources autorisées :
- Fichiers CSV et Excel importés.
- API officielle Google Places.
- Pages publiques des entreprises, avec respect de robots.txt.

Aucun scraping de LinkedIn ni de profils privés.
"""

from __future__ import annotations

import csv
import logging
import re
import time

from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

from . import config
from .errors import DataSourceError, GooglePlacesError
from .utils import extract_emails


log = logging.getLogger(__name__)


# ============================================================
# 1. CONFIGURATION
# ============================================================

COMPANY_COLUMNS = [
    "nom",
    "adresse",
    "telephone",
    "site_web",
    "google_maps",
    "note",
    "nombre_avis",
    "categories_google",
    "emails_bruts",
    "place_id",
    "source_dataset",
]

OFFER_COLUMNS = [
    "titre",
    "entreprise",
    "quartier",
    "localisation",
    "date",
    "contrat",
    "secteur",
    "experience",
    "email",
    "description",
    "url",
    "source",
    "origine",
    "statut_offre",
]

CSV_SEPARATORS = [",", ";", "\t", "|"]


# ============================================================
# 2. UTILITAIRES
# ============================================================

def normalize_column_name(value: str) -> str:
    """Normalise les noms des colonnes."""

    value = str(value).strip().lower()
    value = value.replace("\ufeff", "")

    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def clean_value(value):
    """Nettoie une valeur sans supprimer les informations utiles."""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    value = str(value).strip()

    if value.lower() in {
        "",
        "nan",
        "none",
        "null",
        "n/a",
        "na",
        "undefined",
    }:
        return None

    return value


def get_value(record: dict, *names):
    """Récupère une valeur à partir de plusieurs noms possibles."""

    normalized = {
        normalize_column_name(key): value
        for key, value in record.items()
    }

    for name in names:
        value = clean_value(normalized.get(normalize_column_name(name)))

        if value is not None:
            return value

    return None


def join_values(*values) -> str | None:
    """Combine plusieurs valeurs sans doublons."""

    result = []

    for value in values:
        value = clean_value(value)

        if value and value not in result:
            result.append(value)

    return " ; ".join(result) if result else None


# ============================================================
# 3. DÉTECTION DU SÉPARATEUR CSV
# ============================================================

def detect_separator(path: Path) -> str:
    """Détecte le séparateur CSV."""

    with open(path, "r", encoding="utf-8-sig", errors="replace") as file:
        sample = file.read(65536)

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=CSV_SEPARATORS
        )
        return dialect.delimiter

    except csv.Error:
        pass

    lines = [
        line for line in sample.splitlines()
        if line.strip()
    ][:20]

    best_separator = ","
    best_score = -1

    for separator in CSV_SEPARATORS:

        counts = [line.count(separator) for line in lines]

        if not counts:
            continue

        positive = [count for count in counts if count > 0]

        if not positive:
            continue

        # Favorise un séparateur présent régulièrement.
        score = len(positive) * 100 - (
            max(positive) - min(positive)
        )

        if score > best_score:
            best_score = score
            best_separator = separator

    return best_separator


# ============================================================
# 4. LECTURE CSV ROBUSTE
# ============================================================

def read_csv_robust(path: Path) -> pd.DataFrame:
    """
    Lit un CSV même si certaines lignes ont un nombre
    irrégulier de champs.

    Les champs excédentaires sont conservés dans la dernière
    colonne plutôt que d'être supprimés silencieusement.

    Les lignes corrigées sont signalées dans les logs.
    """

    separator = detect_separator(path)

    rows = []
    malformed = 0
    empty_rows = 0

    try:

        with open(
            path,
            "r",
            encoding="utf-8-sig",
            errors="replace",
            newline=""
        ) as file:

            reader = csv.reader(
                file,
                delimiter=separator,
                quotechar='"',
                strict=False
            )

            headers = next(reader, None)

            if not headers:
                raise DataSourceError(
                    f"En-tête absent dans {path.name}"
                )

            headers = [
                str(column).strip().replace("\ufeff", "")
                for column in headers
            ]

            expected = len(headers)

            if expected == 0:
                raise DataSourceError(
                    f"Aucune colonne dans {path.name}"
                )

            for line_number, row in enumerate(reader, start=2):

                if not row or not any(str(v).strip() for v in row):
                    empty_rows += 1
                    continue

                if len(row) != expected:
                    malformed += 1

                    if len(row) > expected:

                        # Préserve les champs supplémentaires.
                        row = (
                            row[:expected - 1]
                            + [
                                separator.join(row[expected - 1:])
                            ]
                        )

                    else:

                        # Complète les champs manquants.
                        row += [None] * (expected - len(row))

                rows.append(row)

        df = pd.DataFrame(rows, columns=headers)

        log.info(
            "CSV lu : %s | %d lignes | %d colonnes | séparateur=%r",
            path.name,
            len(df),
            len(df.columns),
            separator
        )

        if malformed:
            log.warning(
                "%s : %d lignes irrégulières normalisées. "
                "Vérification manuelle recommandée.",
                path.name,
                malformed
            )

        if empty_rows:
            log.info(
                "%s : %d lignes vides ignorées.",
                path.name,
                empty_rows
            )

        return df

    except DataSourceError:
        raise

    except Exception as exc:
        raise DataSourceError(
            f"Impossible de lire {path.name} : {exc}"
        ) from exc


# ============================================================
# 5. LECTURE CSV / EXCEL
# ============================================================

def read_table(path: Path) -> pd.DataFrame:
    """Lit un fichier CSV ou Excel."""

    path = Path(path)

    if not path.exists():
        raise DataSourceError(
            f"Fichier introuvable : {path.name}"
        )

    suffix = path.suffix.lower()

    try:

        if suffix == ".csv":
            df = read_csv_robust(path)

        elif suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(
                path,
                dtype=str
            )

        else:
            raise DataSourceError(
                f"Format non supporté : {suffix}"
            )

    except DataSourceError:
        raise

    except Exception as exc:
        raise DataSourceError(
            f"Impossible de lire {path.name} : {exc}"
        ) from exc

    if df.empty:
        raise DataSourceError(
            f"Le fichier {path.name} est vide."
        )

    # Harmonisation des en-têtes.
    df.columns = [
        normalize_column_name(column)
        for column in df.columns
    ]

    # Élimination des colonnes sans nom.
    df = df.loc[
        :,
        [column for column in df.columns if column]
    ]

    # Élimination des colonnes dupliquées.
    df = df.loc[:, ~df.columns.duplicated()]

    return df


# ============================================================
# 6. CHARGEMENT DES SOURCES
# ============================================================

def load_sources(
    raw_dir: Path | None = None
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """
    Charge toutes les sources déclarées dans config.SOURCES.

    Une source manquante ne bloque pas les autres.
    """

    if raw_dir is None:
        raw_dir = config.RAW_DIR

    raw_dir = Path(raw_dir)

    frames = {}
    errors = []

    if not raw_dir.exists():
        raise DataSourceError(
            f"Dossier des données introuvable : {raw_dir}"
        )

    for src in config.SOURCES:

        label = src["label"]
        filename = src["file"]

        try:

            file_path = raw_dir / filename

            df = read_table(file_path)

            frames[label] = df

            log.info(
                "Source chargée : %s (%d lignes, %d colonnes)",
                label,
                len(df),
                len(df.columns)
            )

        except DataSourceError as exc:

            errors.append(str(exc))

            log.warning(
                "Source ignorée : %s",
                exc
            )

    return frames, errors


# ============================================================
# 7. HARMONISATION DES ENTREPRISES
# ============================================================

def harmonize_companies(
    frames: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Harmonise les fichiers d'entreprises.

    Reconnaît notamment :
    - dataset Google Maps enrichi ;
    - contacts publics ;
    - fichiers avant nettoyage ;
    - exports CSV personnalisés.
    """

    rows = []

    for src in config.SOURCES:

        if src["kind"] != "companies":
            continue

        label = src["label"]

        if label not in frames:
            continue

        df = frames[label]

        for record in df.to_dict("records"):

            name = get_value(
                record,
                "nom",
                "name",
                "entreprise",
                "company",
                "business_name",
                "nom_entreprise"
            )

            address = get_value(
                record,
                "adresse",
                "address",
                "location",
                "adresse_complete"
            )

            phone = get_value(
                record,
                "telephone",
                "phone",
                "phone_number",
                "telephone_entreprise"
            )

            website = get_value(
                record,
                "site_web",
                "website",
                "url",
                "site",
                "website_url"
            )

            maps = get_value(
                record,
                "google_maps",
                "maps_url",
                "google_maps_url"
            )

            rating = get_value(
                record,
                "note",
                "rating",
                "google_rating"
            )

            reviews = get_value(
                record,
                "nombre_avis",
                "reviews_count",
                "user_rating_count",
                "nb_avis"
            )

            categories = get_value(
                record,
                "categories_google",
                "category",
                "categorie",
                "domaine",
                "secteur"
            )

            emails = join_values(
                get_value(record, "email"),
                get_value(record, "email_scrape"),
                get_value(record, "email_candidature"),
                get_value(record, "emails"),
                get_value(record, "email_contact")
            )

            place_id = get_value(
                record,
                "place_id",
                "google_place_id"
            )

            # Une ligne sans nom ne constitue pas
            # une entreprise exploitable.
            if not name:
                log.warning(
                    "Entreprise sans nom ignorée dans %s",
                    label
                )
                continue

            rows.append({
                "nom": name,
                "adresse": address,
                "telephone": phone,
                "site_web": website,
                "google_maps": maps,
                "note": rating,
                "nombre_avis": reviews,
                "categories_google": categories,
                "emails_bruts": emails,
                "place_id": place_id,
                "source_dataset": label
            })

    result = pd.DataFrame(
        rows,
        columns=COMPANY_COLUMNS
    )

    log.info(
        "Harmonisation entreprises : %d lignes",
        len(result)
    )

    return result


# ============================================================
# 8. HARMONISATION DES OFFRES
# ============================================================

def harmonize_offers(
    frames: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Harmonise les offres simulées et réelles.

    Conserve les descriptions complètes et les informations
    disponibles dans les sources.
    """

    output = []

    aliases = {
        "titre": [
            "titre_offre",
            "title",
            "intitule",
            "poste"
        ],
        "entreprise": [
            "nom_entreprise",
            "company",
            "company_name"
        ],
        "quartier": [
            "neighborhood",
            "district"
        ],
        "localisation": [
            "ville",
            "lieu",
            "location",
            "city"
        ],
        "date": [
            "date_publication",
            "published_at",
            "publication_date"
        ],
        "contrat": [
            "type_contrat",
            "employment_type",
            "contract_type"
        ],
        "secteur": [
            "domaine",
            "sector"
        ],
        "experience": [
            "niveau_experience",
            "experience_requise"
        ],
        "email": [
            "email_candidature",
            "email_public_connu",
            "application_email"
        ],
        "description": [
            "description_offre",
            "job_description",
            "details"
        ],
        "url": [
            "lien",
            "lien_offre",
            "url_source",
            "application_url",
            "link"
        ],
        "source": [
            "source_offre",
            "plateforme"
        ]
    }

    for src in config.SOURCES:

        kind = src["kind"]
        label = src["label"]

        if kind not in {"offers_sim", "offers_real"}:
            continue

        if label not in frames:
            continue

        df = frames[label].copy()

        # Normalise les colonnes.
        df.columns = [
            normalize_column_name(col)
            for col in df.columns
        ]

        for target, alternatives in aliases.items():

            if target in df.columns:
                continue

            for alternative in alternatives:

                normalized = normalize_column_name(alternative)

                if normalized in df.columns:

                    df[target] = df[normalized]
                    break

        # Champs indispensables ou optionnels.
        for col in OFFER_COLUMNS:
            if col not in df.columns:
                df[col] = None

        df["origine"] = (
            "réelle"
            if kind == "offers_real"
            else "simulée"
        )

        # Source réelle si la colonne est absente.
        df["source"] = df["source"].apply(
            clean_value
        )

        df["source"] = df["source"].fillna(label)

        # On conserve toutes les colonnes standardisées.
        output.append(
            df[OFFER_COLUMNS].copy()
        )

    if not output:
        return pd.DataFrame(columns=OFFER_COLUMNS)

    result = pd.concat(
        output,
        ignore_index=True
    )

    # Nettoyage des champs textuels sans tronquer
    # les descriptions.
    for column in OFFER_COLUMNS:
        if column != "description":
            result[column] = result[column].apply(clean_value)

    log.info(
        "Harmonisation offres : %d lignes",
        len(result)
    )

    return result


# ============================================================
# 9. GOOGLE PLACES API
# ============================================================

PLACES_URL = (
    "https://places.googleapis.com/v1/places:searchText"
)

PLACES_FIELDS = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.nationalPhoneNumber,"
    "places.websiteUri,"
    "places.rating,"
    "places.userRatingCount,"
    "places.googleMapsUri,"
    "places.types,"
    "places.location"
)


def google_places_search(
    query: str,
    api_key: str | None = None,
    max_results: int = 20
) -> pd.DataFrame:
    """Recherche des entreprises via Google Places API."""

    api_key = api_key or config.GOOGLE_API_KEY

    if not api_key:
        raise GooglePlacesError(
            "Clé Google Places absente : "
            "définis GOOGLE_PLACES_API_KEY."
        )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": PLACES_FIELDS
    }

    body = {
        "textQuery": query,
        "languageCode": "fr",
        "pageSize": min(max_results, 20)
    }

    try:

        response = requests.post(
            PLACES_URL,
            json=body,
            headers=headers,
            timeout=config.HTTP_TIMEOUT
        )

        response.raise_for_status()

    except requests.RequestException as exc:

        raise GooglePlacesError(
            f"Connexion à Google Places échouée : {exc}"
        ) from exc

    data = response.json()

    rows = []

    for place in data.get("places", []):

        location = place.get("location", {})

        rows.append({
            "nom": place.get(
                "displayName", {}
            ).get("text"),

            "adresse": place.get(
                "formattedAddress"
            ),

            "telephone": place.get(
                "nationalPhoneNumber"
            ),

            "site_web": place.get(
                "websiteUri"
            ),

            "google_maps": place.get(
                "googleMapsUri"
            ),

            "note": place.get("rating"),

            "nombre_avis": place.get(
                "userRatingCount"
            ),

            "categories_google": "; ".join(
                place.get("types", [])
            ),

            "emails_bruts": None,

            "place_id": place.get("id"),

            "source_dataset": "google_places_api",

            "latitude": location.get("latitude"),

            "longitude": location.get("longitude")
        })

    return pd.DataFrame(rows)


# ============================================================
# 10. COLLECTE GOOGLE PLACES
# ============================================================

def google_places_collect(
    queries: list[str] | None = None,
    pause: float = 1.0
) -> tuple[pd.DataFrame, list[str]]:
    """
    Lance plusieurs requêtes Google Places.

    Les erreurs d'une requête ne bloquent pas les suivantes,
    sauf si la clé API est absente.
    """

    frames = []
    errors = []

    queries = queries or config.GOOGLE_QUERIES

    for query in queries:

        try:

            df = google_places_search(query)

            if not df.empty:
                frames.append(df)

            log.info(
                "Google Places : %s (%d résultats)",
                query,
                len(df)
            )

        except GooglePlacesError as exc:

            errors.append(
                f"{query} : {exc}"
            )

            log.warning(
                "Erreur Google Places : %s",
                exc
            )

            if "absente" in str(exc).lower():
                break

        time.sleep(pause)

    if frames:
        result = pd.concat(
            frames,
            ignore_index=True
        )
    else:
        result = pd.DataFrame(
            columns=COMPANY_COLUMNS
        )

    return result, errors


# ============================================================
# 11. VÉRIFICATION ROBOTS.TXT
# ============================================================

def _allowed_by_robots(url: str) -> bool:
    """
    Vérifie robots.txt avant de consulter une page.

    En cas de problème, on refuse la consultation par prudence.
    """

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    robots_url = (
        f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    )

    parser = robotparser.RobotFileParser()

    try:

        response = requests.get(
            robots_url,
            headers={
                "User-Agent": config.USER_AGENT
            },
            timeout=config.HTTP_TIMEOUT
        )

        if response.status_code in {401, 403}:
            return False

        if response.status_code >= 400:
            return False

        parser.set_url(robots_url)

        parser.parse(
            response.text.splitlines()
        )

        return parser.can_fetch(
            config.USER_AGENT,
            url
        )

    except requests.RequestException as exc:

        log.warning(
            "robots.txt inaccessible : %s",
            robots_url
        )

        return False


# ============================================================
# 12. COLLECTE DES EMAILS PUBLICS
# ============================================================

def fetch_public_emails(
    site_url: str
) -> tuple[list[str], str]:
    """
    Recherche des emails publics uniquement sur :
    - page d'accueil ;
    - /contact ;
    - /contactez-nous.

    Respecte robots.txt pour chaque URL.
    """

    if not site_url:
        return [], "pas de site web"

    site_url = str(site_url).strip()

    if not site_url.startswith(("http://", "https://")):
        site_url = "https://" + site_url

    parsed = urlparse(site_url)

    if not parsed.netloc:
        return [], "URL invalide"

    base = f"{parsed.scheme}://{parsed.netloc}/"

    paths = [
        "",
        "contact",
        "contactez-nous"
    ]

    found = []
    robots_blocked = False

    for path in paths:

        url = urljoin(base, path)

        if not _allowed_by_robots(url):
            robots_blocked = True
            continue

        try:

            response = requests.get(
                url,
                headers={
                    "User-Agent": config.USER_AGENT
                },
                timeout=config.HTTP_TIMEOUT
            )

            if response.status_code != 200:
                continue

            # Extraction des emails depuis le HTML.
            html = response.text

            html = re.sub(
                r"(?i)\s*\[at\]\s*|\s*\(at\)\s*",
                "@",
                html
            )

            emails, _ = extract_emails(html)

            for email in emails:

                email = email.strip().lower()

                if email and email not in found:
                    found.append(email)

            time.sleep(1)

        except requests.RequestException as exc:

            log.warning(
                "Erreur consultation %s : %s",
                url,
                exc
            )

            continue

    if found:
        return found, "ok"

    if robots_blocked:
        return [], "robots.txt interdit ou inaccessible"

    return [], "aucun email public trouvé"


# ============================================================
# 13. FONCTION PRINCIPALE DE COLLECTE
# ============================================================

def collect_all(
    raw_dir: Path | None = None,
    include_google: bool = False
) -> dict:
    """
    Exécute la collecte des sources locales.

    Retourne :
    - entreprises ;
    - offres ;
    - sources chargées ;
    - erreurs.
    """

    log.info("Début de la collecte des données")

    frames, errors = load_sources(raw_dir)

    companies = harmonize_companies(frames)

    offers = harmonize_offers(frames)

    # Google Places est facultatif.
    if include_google:

        google_df, google_errors = google_places_collect()

        errors.extend(google_errors)

        if not google_df.empty:

            companies = pd.concat(
                [companies, google_df],
                ignore_index=True
            )

            log.info(
                "Ajout Google Places : %d entreprises",
                len(google_df)
            )

    log.info(
        "Collecte terminée : %d entreprises, %d offres",
        len(companies),
        len(offers)
    )

    return {
        "companies": companies,
        "offers": offers,
        "sources": frames,
        "errors": errors
    }
