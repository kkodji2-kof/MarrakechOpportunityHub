
"""ÉTAPE 4 — Data Quality : vérification de la fiabilité des données."""

from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

from . import config
from .utils import strip_accents


STOPWORDS = {
    "pour", "dans", "avec", "vous", "nous", "chez", "recherche",
    "recrute", "poste", "offre", "junior", "confirme", "senior",
    "stage", "stagiaire", "cdi", "cdd", "responsable",
}


# ----------------------------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------------------------

def safe_text(value) -> str:
    """Convertit une valeur en texte sans provoquer d'erreur sur NaN/NA."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()


def has_value(value) -> bool:
    """Vérifie qu'une valeur est réellement renseignée."""
    return bool(safe_text(value))


def get_column(df: pd.DataFrame, column: str, default=None) -> pd.Series:
    """Retourne une colonne ou une série par défaut si elle est absente."""
    if column in df.columns:
        return df[column]

    return pd.Series(default, index=df.index)


def normalize_date(value) -> pd.Timestamp:
    """
    Convertit une date en Timestamp sans fuseau horaire.

    Les dates sont d'abord interprétées en UTC.
    Cela évite les erreurs entre dates tz-aware et tz-naive.
    """
    if value is None:
        return pd.NaT

    try:
        if pd.isna(value):
            return pd.NaT

        result = pd.to_datetime(value, errors="coerce", utc=True)

        if pd.isna(result):
            return pd.NaT

        # Supprime le fuseau horaire après conversion UTC.
        return result.tz_convert(None)

    except (ValueError, TypeError, OverflowError):
        return pd.NaT


# ----------------------------------------------------------------------------
# Complétude
# ----------------------------------------------------------------------------

def completeness(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule le pourcentage de valeurs renseignées par colonne."""

    if df.empty:
        return pd.DataFrame(columns=["colonne", "renseigne_%"])

    # Les chaînes vides sont également considérées comme manquantes.
    cleaned = df.copy()

    for column in cleaned.columns:
        cleaned[column] = cleaned[column].apply(
            lambda value: pd.NA if not has_value(value) else value
        )

    pct = (cleaned.notna().mean() * 100).round(1)

    return (
        pct.rename("renseigne_%")
        .reset_index()
        .rename(columns={"index": "colonne"})
    )


# ----------------------------------------------------------------------------
# Analyse du texte
# ----------------------------------------------------------------------------

def _tokens(text) -> set[str]:
    """Extrait les mots significatifs d'un texte."""

    plain = strip_accents(safe_text(text)).lower()

    # Uniformise quelques expressions liées à l'intelligence artificielle.
    plain = re.sub(
        r"intelligence artificielle|artificial intelligence|\bia\b|\bai\b",
        " iiaa ",
        plain,
    )

    words = re.findall(r"[a-z]{4,}", plain)

    return {
        word[:5]
        for word in words
        if word not in STOPWORDS
    }


def title_description_overlap(title, description) -> float:
    """
    Mesure la proportion de mots du titre retrouvés dans la description.
    0 = aucun mot commun.
    """

    title_tokens = _tokens(title)
    description_tokens = _tokens(description)

    if not title_tokens:
        return 0.0

    return round(
        len(title_tokens & description_tokens) / len(title_tokens),
        2,
    )


# ----------------------------------------------------------------------------
# Entreprises
# ----------------------------------------------------------------------------

def quality_companies(companies: pd.DataFrame) -> pd.DataFrame:
    """Produit un score de qualité sur 100 pour chaque entreprise."""

    df = companies.copy()

    if df.empty:
        return pd.DataFrame(columns=[
            "id_entreprise",
            "email_valide",
            "site_renseigne",
            "telephone_renseigne",
            "note_renseignee",
            "adresse_marrakech",
            "score_qualite",
        ])

    ids = get_column(df, "id_entreprise", default=None)

    if ids.isna().all():
        ids = pd.Series(range(1, len(df) + 1), index=df.index)

    checks = pd.DataFrame(index=df.index)

    checks["id_entreprise"] = ids

    checks["email_valide"] = (
        get_column(df, "statut_email")
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("Validé")
    )

    checks["site_renseigne"] = (
        get_column(df, "site_web")
        .apply(has_value)
    )

    checks["telephone_renseigne"] = (
        get_column(df, "telephone")
        .apply(has_value)
    )

    checks["note_renseignee"] = (
        get_column(df, "note")
        .apply(has_value)
    )

    checks["adresse_marrakech"] = (
        get_column(df, "ville")
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .eq(config.VILLE_CIBLE.lower())
    )

    weights = {
        "email_valide": 30,
        "site_renseigne": 20,
        "telephone_renseigne": 15,
        "note_renseignee": 15,
        "adresse_marrakech": 20,
    }

    checks["score_qualite"] = sum(
        checks[column].astype(int) * weight
        for column, weight in weights.items()
    )

    return checks.reset_index(drop=True)


# ----------------------------------------------------------------------------
# Offres
# ----------------------------------------------------------------------------

def quality_offers(
    offers: pd.DataFrame,
    today: date | datetime | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Détecte les offres douteuses :
    - date de publication future ;
    - email invalide ;
    - description sans lien avec le titre ;
    - lien numéroté artificiel ;
    - titre répété ;
    - description absente ;
    - origine simulée.
    """

    df = offers.copy()

    columns = [
        "id_offre",
        "recouvrement_titre_description",
        "anomalies",
        "nb_anomalies",
        "fiabilite",
    ]

    if df.empty:
        return pd.DataFrame(columns=columns)

    # Normalisation de la date actuelle : une seule fois.
    today_value = today if today is not None else config.TODAY
    today_normalized = normalize_date(today_value)

    # Récupération sécurisée des colonnes.
    titles = get_column(df, "titre", default="")
    descriptions = get_column(df, "description", default="")
    dates = get_column(df, "date", default=pd.NaT)
    email_statuses = get_column(df, "email_statut", default="")
    urls = get_column(df, "url", default="")
    origins = get_column(df, "origine", default="")
    offer_ids = get_column(df, "id_offre", default=None)

    # Comptage des titres répétés.
    normalized_titles = titles.apply(
        lambda value: safe_text(value).lower()
    )

    title_counts = normalized_titles.value_counts()

    rows = []

    for position, (index, row) in enumerate(df.iterrows()):

        reasons = []

        title = safe_text(row.get("titre", ""))
        description = safe_text(row.get("description", ""))
        publication_date = normalize_date(row.get("date"))

        email_status = safe_text(row.get("email_statut", ""))
        url = safe_text(row.get("url", ""))
        origin = safe_text(row.get("origine", "")).lower()

        # 1. Vérification de la date de publication.
        if (
            pd.notna(publication_date)
            and pd.notna(today_normalized)
            and publication_date.normalize() > today_normalized.normalize()
        ):
            reasons.append("date de publication dans le futur")

        # 2. Vérification du statut de l'email.
        if email_status == "Rejeté":
            reasons.append("email invalide")

        # 3. Vérification de la cohérence titre-description.
        overlap = title_description_overlap(title, description)

        if description and overlap < 0.2:
            reasons.append("description sans lien avec le titre")

        # 4. Vérification d'un lien artificiel.
        if url and re.search(r"ref-\d{4}", url, flags=re.IGNORECASE):
            reasons.append("lien numéroté artificiel (ref-xxxx)")

        # 5. Vérification des titres trop répétés.
        title_key = title.lower()
        if title_key and title_counts.get(title_key, 0) >= 5:
            reasons.append(
                "même titre répété pour de nombreuses entreprises"
            )

        # 6. Vérification de la description.
        if not description:
            reasons.append("description absente")

        # 7. Détection des offres simulées.
        origin_sim = origin in {"simulée", "simulee", "simulated"}

        # Identifiant de l'offre.
        offer_id = row.get("id_offre")

        if not has_value(offer_id):
            offer_id = position + 1

        # Fiabilité finale.
        if origin_sim:
            reliability = "Simulée"
        elif not reasons:
            reliability = "Fiable"
        else:
            reliability = "Suspecte"

        rows.append({
            "id_offre": offer_id,
            "recouvrement_titre_description": overlap,
            "anomalies": "; ".join(reasons),
            "nb_anomalies": len(reasons),
            "fiabilite": reliability,
        })

    return pd.DataFrame(rows, columns=columns)


# ----------------------------------------------------------------------------
# Rapport global de qualité
# ----------------------------------------------------------------------------

def quality_report(
    companies: pd.DataFrame,
    offers: pd.DataFrame,
    today: date | None = None,
) -> dict[str, pd.DataFrame]:
    """Construit les tableaux de contrôle qualité."""

    qc = quality_companies(companies)
    qo = quality_offers(offers, today)

    if qc.empty:
        average_score = 0.0
        email_percentage = 0.0
        outside_marrakech = 0
    else:
        average_score = round(qc["score_qualite"].mean(), 1)
        email_percentage = round(
            100 * qc["email_valide"].mean(), 1
        )
        outside_marrakech = int(
            (~qc["adresse_marrakech"]).sum()
        )

    summary = pd.DataFrame([
        (
            "Score qualité moyen des entreprises (/100)",
            average_score,
        ),
        (
            "Entreprises avec email validé (%)",
            email_percentage,
        ),
        (
            "Entreprises hors Marrakech",
            outside_marrakech,
        ),
        (
            "Offres fiables",
            int((qo["fiabilite"] == "Fiable").sum()),
        ),
        (
            "Offres suspectes",
            int((qo["fiabilite"] == "Suspecte").sum()),
        ),
        (
            "Offres simulées (exclues de l'analyse)",
            int((qo["fiabilite"] == "Simulée").sum()),
        ),
        (
            "Offres à date future",
            int(qo["anomalies"].str.contains(
                "futur", case=False, na=False
            ).sum()),
        ),
        (
            "Offres dont la description ne correspond pas au titre",
            int(qo["anomalies"].str.contains(
                "sans lien", case=False, na=False
            ).sum()),
        ),
    ], columns=["Contrôle", "Résultat"])

    return {
        "Resume_qualite": summary,
        "Qualite_entreprises": qc,
        "Qualite_offres": qo,
        "Completude_entreprises": completeness(companies),
        "Completude_offres": completeness(offers),
    }


# ----------------------------------------------------------------------------
# Filtrage des offres fiables
# ----------------------------------------------------------------------------

def reliable_offers(
    offers: pd.DataFrame,
    quality_offers_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Sélectionne les offres fiables.

    Si INCLUDE_SIMULATED_OFFERS est True, les offres simulées
    et suspectes sont également conservées.
    """

    if offers.empty or quality_offers_df.empty:
        return offers.iloc[0:0].copy()

    allowed = {"Fiable"}

    if config.INCLUDE_SIMULATED_OFFERS:
        allowed.update({"Simulée", "Suspecte"})

    keep = quality_offers_df.loc[
        quality_offers_df["fiabilite"].isin(allowed),
        "id_offre",
    ]

    return (
        offers[offers["id_offre"].isin(keep)]
        .reset_index(drop=True)
    )
