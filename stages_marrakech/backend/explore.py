from __future__ import annotations
import re
from datetime import date
import pandas as pd
from . import config
from .utils import strip_accents
STOPWORDS = {"pour", "dans", "avec", "vous", "nous", "chez", "recherche", "recrute", "poste", "offre",
             "junior", "confirme", "senior", "stage", "stagiaire", "cdi", "cdd", "responsable"}
OFFER_QUALITY_COLUMNS = ["id_offre", "recouvrement_titre_description", "anomalies", "nb_anomalies", "fiabilite"]
def completeness(df: pd.DataFrame) -> pd.DataFrame:
    """Pourcentage de valeurs renseignées par colonne."""
    pct = (df.notna().mean() * 100).round(1)
    return pct.rename("renseigne_%").reset_index().rename(columns={"index": "colonne"})
def _tokens(text) -> set[str]:
    plain = strip_accents(str(text or "")).lower()
    # « intelligence artificielle », « IA » et « AI » désignent la même chose : on les unifie
    plain = re.sub(r"intelligence artificielle|artificial intelligence|\bia\b|\bai\b", " iiaa ", plain)
    words = re.findall(r"[a-z]{4,}", plain)
    return {w[:5] for w in words if w not in STOPWORDS}  # radical de 5 lettres : développeur ~ développement
def title_description_overlap(title, description) -> float:
    """Part des mots du titre retrouvés dans la description (0 = aucun lien)."""
    t, d = _tokens(title), _tokens(description)
    return round(len(t & d) / len(t), 2) if t else 0.0
def _has_text(value) -> bool:
    """Vrai seulement pour un vrai texte (une cellule vide lue depuis un CSV devient NaN et ne compte pas)."""
    return isinstance(value, str) and bool(value.strip())
# ----------------------------------------------------------------------------
# Entreprises
# ----------------------------------------------------------------------------
def quality_companies(companies: pd.DataFrame) -> pd.DataFrame:
    """Une ligne de contrôle par entreprise, avec un score de qualité sur 100."""
    df = companies.copy()
    checks = pd.DataFrame({
        "id_entreprise": df["id_entreprise"],
        "email_valide": df["statut_email"].eq("Validé"),
        "site_renseigne": df["site_web"].notna(),
        "telephone_renseigne": df["telephone"].notna(),
        "note_renseignee": df["note"].notna(),
        "adresse_marrakech": df["ville"].eq(config.VILLE_CIBLE),
    })
    weights = {"email_valide": 30, "site_renseigne": 20, "telephone_renseigne": 15,
               "note_renseignee": 15, "adresse_marrakech": 20}
    checks["score_qualite"] = sum(checks[c].astype(int) * w for c, w in weights.items())
    return checks
# ----------------------------------------------------------------------------
# Offres
# ----------------------------------------------------------------------------
def quality_offers(offers: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Détecte les offres douteuses : date future, email invalide, description absente, et — pour les
    offres NON réelles seulement — description sans lien avec le titre, lien numéroté artificiel,
    titre répété par de nombreuses entreprises.

    Une offre « réelle » (saisie ou lue par toi depuis une vraie annonce) n'est pas soumise aux trois
    derniers contrôles : ils servent à repérer les offres simulées et rejetteraient à tort de vraies annonces.
    """
    # Sécurité : sans offre, on renvoie un tableau vide mais avec les bonnes colonnes
    if offers.empty:
        return pd.DataFrame(columns=OFFER_QUALITY_COLUMNS)
    today = pd.Timestamp(today or config.TODAY)
    df = offers.copy()
    # Colonne du titre : « titre » (ou « title » si le fichier vient d'ailleurs)
    title_col = "titre" if "titre" in df.columns else ("title" if "title" in df.columns else None)
    if title_col:
        title_counts = df[title_col].map(df[title_col].value_counts())
    else:
        title_counts = pd.Series(0, index=df.index)
    rows = []
    for i, row in df.iterrows():
        reasons = []
        title = row[title_col] if title_col and pd.notna(row[title_col]) else ""
        description = row.get("description")
        is_real = row.get("origine") == "réelle"
        is_simulated = row.get("origine") == "simulée"
        if pd.notna(row.get("date")) and row["date"] > today:
            reasons.append("date de publication dans le futur")
        if row.get("email_statut") in {"Rejeté"}:
            reasons.append("email invalide")
        if not _has_text(description):
            reasons.append("description absente")

        overlap = title_description_overlap(title, description)
        if not is_real:  # contrôles anti-simulation : pas pour les offres réelles
            if _has_text(description) and overlap < 0.2:
                reasons.append("description sans lien avec le titre")
            if row.get("url") and re.search(r"ref-\d{4}", str(row["url"])):
                reasons.append("lien numéroté artificiel (ref-xxxx)")
            if title_counts[i] >= 5:
                reasons.append("même titre répété pour de nombreuses entreprises")

        reliable = not reasons and not is_simulated
        rows.append({
            "id_offre": row["id_offre"],
            "recouvrement_titre_description": overlap,
            "anomalies": "; ".join(reasons),
            "nb_anomalies": len(reasons),
            "fiabilite": "Fiable" if reliable else ("Simulée" if is_simulated else "Suspecte"),
        })

    return pd.DataFrame(rows, columns=OFFER_QUALITY_COLUMNS)
def quality_report(companies: pd.DataFrame, offers: pd.DataFrame, today: date | None = None) -> dict[str, pd.DataFrame]:
    qc, qo = quality_companies(companies), quality_offers(offers, today)

    # Sécurité : sans offre, tous les compteurs d'offres valent 0
    if qo.empty:
        reliable = suspect = simulated = future_dates = no_link = 0
    else:
        reliable = int((qo["fiabilite"] == "Fiable").sum())
        suspect = int((qo["fiabilite"] == "Suspecte").sum())
        simulated = int((qo["fiabilite"] == "Simulée").sum())
        future_dates = int(qo["anomalies"].str.contains("futur").sum())
        no_link = int(qo["anomalies"].str.contains("sans lien").sum())

    summary = pd.DataFrame([
        ("Score qualité moyen des entreprises (/100)", round(qc["score_qualite"].mean(), 1)),
        ("Entreprises avec email validé (%)", round(100 * qc["email_valide"].mean(), 1)),
        ("Entreprises hors Marrakech", int((~qc["adresse_marrakech"]).sum())),
        ("Offres fiables", reliable),
        ("Offres suspectes", suspect),
        ("Offres simulées (exclues de l'analyse)", simulated),
        ("Offres à date future", future_dates),
        ("Offres dont la description ne correspond pas au titre", no_link),
    ], columns=["Contrôle", "Résultat"])

    return {
        "Resume_qualite": summary,
        "Qualite_entreprises": qc,
        "Qualite_offres": qo,
        "Completude_entreprises": completeness(companies),
        "Completude_offres": completeness(offers),
    }

def reliable_offers(offers: pd.DataFrame, quality_offers_df: pd.DataFrame) -> pd.DataFrame:
    """Offres retenues pour l'analyse : fiables (ou simulées si config.INCLUDE_SIMULATED_OFFERS)."""
    allowed = {"Fiable"} | ({"Simulée", "Suspecte"} if config.INCLUDE_SIMULATED_OFFERS else set())
    keep = quality_offers_df.loc[quality_offers_df["fiabilite"].isin(allowed), "id_offre"]
    return offers[offers["id_offre"].isin(keep)].reset_index(drop=True)
