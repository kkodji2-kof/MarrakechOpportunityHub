from __future__ import annotations
import logging
import re
import pandas as pd
from .utils import (check_email, clean_spaces, detect_city, extract_emails, norm_key,
                       normalize_phone, rank_email, site_domain, strip_accents, to_float)
log = logging.getLogger(__name__)
SECTOR_RULES = [
    ("IA / Data", r"\bia\b|\bai\b|intelligen|machine learning|data"),
    ("Cybersécurité", r"cyber|securit"),
    ("Développement logiciel", r"logiciel|software|\bsoft\b|develop|\bdev\b|\besn\b|offshore|nearshore|\berp\b|odoo|saas|application|solutions"),
    ("Agence web / digital", r"agence web|web agency|site (web|internet)|web ?design|digital|numerique|\bweb\b"),
    ("Communication & marketing", r"communication|marketing|\bseo\b|influenc|branding|publicit"),
    ("Services informatiques", r"informatique|\bit\b|\binfo\b|tech|computer|\bpc\b|reseau"),
    ("Conseil", r"consult|conseil"),
]
CATEGORY_RULES = [
    ("Services informatiques", r"software|information_technology|it_company|computer|electronics_store"),
    ("Conseil", r"consultant"),
]
NOISE = (r"nanny|riad|hotel|architect|immobili|voyage|travel|golf|\bspa\b|restaurant|ecole|institut|"
         r"universit|clinique|boutique|cafe|wafacash|jardin|avocat|beaute|beauty|poterie|excursion|"
         r"evenement|events|camera de surveillance|cosmetik")
TECH_SECTORS = {"IA / Data", "Développement logiciel", "Cybersécurité", "Agence web / digital", "Services informatiques"}
GENERIC_DOMAINS = {"facebook.com", "instagram.com", "linkedin.com", "linktr.ee", "wixsite.com", "business.site"}
# ----------------------------------------------------------------------------
# Secteur et pertinence
# ----------------------------------------------------------------------------
def classify_sector(nom, categories=None) -> str:
    name = strip_accents(nom or "").lower()
    cats = str(categories or "").lower()
    sector = "À qualifier"
    for label, pattern in SECTOR_RULES:
        if re.search(pattern, name):
            sector = label
            break
    else:
        for label, pattern in CATEGORY_RULES:
            if re.search(pattern, cats):
                sector = label
                break
    if re.search(NOISE, name) and sector not in {"IA / Data", "Développement logiciel"}:
        return "Hors cible"
    return sector
def pertinence_label(sector: str) -> str:
    if sector in TECH_SECTORS:
        return "Cible IA/Tech"
    return "Hors cible" if sector == "Hors cible" else "À qualifier"
def _clean_url(value) -> str | None:
    value = clean_spaces(value)
    if not value:
        return None
    if not value.startswith("http"):
        value = "https://" + value
    return re.sub(r"\?utm_[^ ]*$", "", value)
def _first(series: pd.Series):
    series = series.dropna()
    return series.iloc[0] if len(series) else None
# ----------------------------------------------------------------------------
# Entreprises
# ----------------------------------------------------------------------------
def clean_companies(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Retourne (entreprises nettoyées, emails rejetés ou à vérifier, journal de nettoyage)."""
    df = raw.copy()
    report: dict = {"lignes_brutes": len(df)}
    for col in ("nom", "adresse", "categories_google"):
        df[col] = df[col].map(clean_spaces)
    df = df[df["nom"].notna()].copy()
    df["note"] = df["note"].map(to_float)
    df["nombre_avis"] = pd.to_numeric(df["nombre_avis"], errors="coerce")
    df["telephone"] = df["telephone"].map(normalize_phone)
    df["site_web"] = df["site_web"].map(_clean_url)
    df["domaine_site"] = df["site_web"].map(site_domain)

    # --- fusion des doublons (même domaine de site OU même nom normalisé) ----
    groups: list[list] = []
    by_domain: dict[str, int] = {}
    by_name: dict[str, int] = {}
    for idx, row in df.iterrows():
        dom, key = row["domaine_site"], norm_key(row["nom"])
        use_dom = bool(dom) and dom not in GENERIC_DOMAINS
        gid = by_domain.get(dom) if use_dom else None
        if gid is None:
            gid = by_name.get(key)
        if gid is None:
            gid = len(groups)
            groups.append([])
        groups[gid].append(idx)
        if use_dom:
            by_domain.setdefault(dom, gid)
        by_name.setdefault(key, gid)
    report["doublons_fusionnes"] = len(df) - len(groups)

    records, rejected = [], []
    for gid, idxs in enumerate(groups, start=1):
        sub = df.loc[idxs]
        rec = {col: _first(sub[col]) for col in
               ["nom", "adresse", "telephone", "site_web", "domaine_site", "google_maps", "note",
                "nombre_avis", "categories_google", "place_id"]}
        for geo in ("latitude", "longitude"):
            rec[geo] = _first(sub[geo]) if geo in sub.columns else None
        rec["sources"] = " + ".join(dict.fromkeys(sub["source_dataset"].dropna()))

        good, doubtful = [], []
        for raw_cell in sub["emails_bruts"]:
            valid, invalid = extract_emails(raw_cell)
            for bad in invalid:
                rejected.append({"entreprise": rec["nom"], "email": bad, "statut": "Rejeté",
                                 "motif": "syntaxe invalide", "type": "Entreprise"})
            for mail in valid:
                status, reason = check_email(mail, rec["site_web"])
                if status == "Validé":
                    if mail not in good:
                        good.append(mail)
                else:
                    doubtful.append(mail)
                    rejected.append({"entreprise": rec["nom"], "email": mail, "statut": status,
                                     "motif": reason, "type": "Entreprise"})
        good.sort(key=rank_email)
        rec["email_principal"] = good[0] if good else None
        rec["autres_emails"] = "; ".join(good[1:]) or None
        rec["statut_email"] = "Validé" if good else ("À vérifier" if doubtful else "Aucun")
        rec["ville"] = detect_city(rec["adresse"])
        rec["nom_affiche"] = rec["nom"] if len(rec["nom"]) <= 70 else rec["nom"][:67].rstrip(" -|") + "…"
        rec["secteur"] = classify_sector(rec["nom"], rec["categories_google"])
        rec["pertinence"] = pertinence_label(rec["secteur"])
        rec["id_entreprise"] = f"E{gid:03d}"
        records.append(rec)

    clean = pd.DataFrame(records)
    cols = ["id_entreprise", "nom_affiche", "nom", "secteur", "pertinence", "ville", "adresse", "telephone",
            "site_web", "domaine_site", "email_principal", "autres_emails", "statut_email", "note",
            "nombre_avis", "google_maps", "latitude", "longitude", "place_id", "sources"]
    clean = clean[cols].sort_values(["pertinence", "nom_affiche"]).reset_index(drop=True)
    report.update({"lignes_propres": len(clean),
                   "emails_valides": int((clean["statut_email"] == "Validé").sum())})
    rej = pd.DataFrame(rejected, columns=["entreprise", "email", "statut", "motif", "type"]).drop_duplicates()
    return clean, rej, report


# ----------------------------------------------------------------------------
# Offres
# ----------------------------------------------------------------------------
def clean_offers(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Nettoie les offres : dates, textes, emails, doublons (même entreprise + titre + email)."""
    df = raw.copy()
    for col in ("titre", "entreprise", "quartier", "localisation", "contrat", "secteur", "description", "url"):
        df[col] = df[col].map(clean_spaces)
    df = df[df["titre"].notna() & df["entreprise"].notna()].copy()
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

    rejected, emails, statuses, motifs = [], [], [], []
    for _, row in df.iterrows():
        valid, invalid = extract_emails(row["email"])
        for bad in invalid:
            rejected.append({"entreprise": row["entreprise"], "email": bad, "statut": "Rejeté",
                             "motif": "syntaxe invalide (caractère interdit : &, accent, espace)", "type": "Offre"})
        if valid:
            status, reason = check_email(valid[0])
            emails.append(valid[0]); statuses.append(status); motifs.append(reason)
        else:
            emails.append(None); statuses.append("Aucun" if not invalid else "Rejeté")
            motifs.append("pas d'email" if not invalid else "syntaxe invalide")
    df["email"], df["email_statut"], df["email_motif"] = emails, statuses, motifs

    df["_cle"] = (df["entreprise"].map(norm_key) + "|" + df["titre"].map(norm_key) + "|" + df["email"].fillna(""))
    df = df.sort_values("date", ascending=False, na_position="last")
    df["nb_annonces"] = df.groupby("_cle")["titre"].transform("size")
    df = df.drop_duplicates("_cle").drop(columns="_cle").reset_index(drop=True)
    df.insert(0, "id_offre", [f"O{i:03d}" for i in range(1, len(df) + 1)])
    rej = pd.DataFrame(rejected, columns=["entreprise", "email", "statut", "motif", "type"]).drop_duplicates()
    return df, rej


# ----------------------------------------------------------------------------
# Comparaison avant / après
# ----------------------------------------------------------------------------
def cleaning_comparison(raw: pd.DataFrame, clean: pd.DataFrame, rejected: pd.DataFrame) -> pd.DataFrame:
    """Tableau « avant / après » pour la présentation du projet."""
    notes_virgule = int(raw["note"].astype(str).str.contains(",", regex=False).sum())
    rows = [
        ("Nombre de lignes", len(raw), len(clean)),
        ("Doublons de nom", int(raw["nom"].map(norm_key).duplicated().sum()), 0),
        ("Notes avec virgule décimale", notes_virgule, 0),
        ("Téléphones manquants", int(raw["telephone"].isna().sum()), int(clean["telephone"].isna().sum())),
        ("Sites web manquants", int(raw["site_web"].isna().sum()), int(clean["site_web"].isna().sum())),
        ("Notes manquantes", int(raw["note"].map(to_float).isna().sum()), int(clean["note"].isna().sum())),
        ("Cellules d'email renseignées", int(raw["emails_bruts"].notna().sum()), int(clean["email_principal"].notna().sum())),
        ("Emails rejetés ou à vérifier", 0, len(rejected)),
        ("Entreprises hors Marrakech", 0, int((clean["ville"] != "Marrakech").sum())),
    ]
    return pd.DataFrame(rows, columns=["Indicateur", "Avant nettoyage", "Après nettoyage"])
