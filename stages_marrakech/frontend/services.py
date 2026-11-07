
from __future__ import annotations

import datetime
import pandas as pd
import streamlit as st

from stages_marrakech.backend import analyze, config, quality, tracking
from stages_marrakech.backend.errors import DataSourceError

SCORED_FILE = config.CLEAN_DIR / "entreprises_scorees.csv"
OFFERS_FILE = config.CLEAN_DIR / "offres_nettoyees.csv"
OFFER_COLUMNS = ["id_offre", "titre", "entreprise", "localisation", "date", "contrat", "secteur",
                 "email", "description", "url", "origine", "fiabilite", "anomalies"]

def last_update_label() -> str:
    """Renvoie la date de dernière modification du fichier de données."""
    if SCORED_FILE.exists():
        mtime = datetime.datetime.fromtimestamp(SCORED_FILE.stat().st_mtime)
        return mtime.strftime("%d/%m/%Y à %H:%M")
    return "Aucune donnée"

def data_version() -> float:
    """Date de dernière modification des données : sert de clé de cache."""
    return SCORED_FILE.stat().st_mtime if SCORED_FILE.exists() else 0.0


def data_ready() -> bool:
    return SCORED_FILE.exists()


def _none_if_nan(df: pd.DataFrame) -> pd.DataFrame:
    return df.astype(object).where(df.notna(), None)


@st.cache_data(show_spinner="Chargement des données…")
def _load(version: float) -> dict:
    if version == 0.0:
        raise DataSourceError("Les données ne sont pas prêtes : le pipeline n'a pas encore été lancé.")
        
    companies = pd.read_csv(SCORED_FILE, encoding="utf-8-sig")
    
    if OFFERS_FILE.exists():
        offers = pd.read_csv(OFFERS_FILE, encoding="utf-8-sig", parse_dates=["date"])
    else:
        offers = pd.DataFrame(columns=OFFER_COLUMNS)
        
    offers_clean = _none_if_nan(offers)
  
    rapport_qualite_complet = quality.quality_report(companies, offers_clean)
    
    if len(offers):
        qo = quality.quality_offers(offers_clean)
        offers = offers.merge(qo[["id_offre", "fiabilite", "anomalies"]], on="id_offre", how="left")
        reliable = quality.reliable_offers(offers, qo)
    else:
        reliable = offers.copy()
        
    for frame in (offers, reliable):
        for col in OFFER_COLUMNS:
            if col not in frame.columns:
                frame[col] = None
                
    return {
        "entreprises": companies, 
        "offres": offers, 
        "offres_fiables": reliable.reset_index(drop=True),
        "qualite": rapport_qualite_complet  # On garde le dictionnaire complet
    }


def get_data() -> dict:
    """Données prêtes pour l'affichage. Lève DataSourceError si le pipeline n'a jamais tourné."""
    return _load(data_version())


@st.cache_data(show_spinner=False)
def get_tables(companies: pd.DataFrame, reliable_offers: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Tables d'exploration (étape 3 du backend) : KPIs, répartitions, etc."""
    return analyze.explore(companies, reliable_offers)

def refresh_pipeline(use_google: bool = False) -> dict:
    """Relance les 6 étapes du backend puis vide le cache pour afficher les nouvelles données."""
    from stages_marrakech.main import run
    result = run(use_google=use_google, top_n=20)
    st.cache_data.clear()
    return result

def get_tracking() -> pd.DataFrame:
    return tracking.load_tracking()


def save_tracking(df: pd.DataFrame) -> None:
    tracking.save_tracking(df)


def filter_companies(
    df: pd.DataFrame,
    query: str = "",
    sectors: list[str] | None = None,
    pertinence: list[str] | None = None,
    note_min: float = 0.0,
    only_email: bool = False,
    only_marrakech: bool = False
) -> pd.DataFrame:
    """
    Filtre les entreprises selon :
    - Nom ou secteur
    - Secteur d'activité
    - Pertinence IA/Tech
    - Note Google minimale
    - Disponibilité d'un email validé
    - Marrakech uniquement (optionnel)

    Par défaut, toutes les villes sont incluses.
    """

    out = df.copy()

    if query:
        q = query.strip().lower()

        haystack = (
            out["nom_affiche"].fillna("")
            + " "
            + out["secteur"].fillna("")
        ).str.lower()

        out = out[haystack.str.contains(q, regex=False)]

    if sectors:
        out = out[out["secteur"].isin(sectors)]

    if pertinence:
        out = out[out["pertinence"].isin(pertinence)]

    if note_min > 0:
        out = out[out["note"].fillna(0) >= note_min]

    if only_email:
        out = out[out["statut_email"] == "Validé"]

    # Filtre géographique facultatif
    # Toutes les villes sont incluses par défaut.
    if only_marrakech:
        out = out[
            out["ville"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
            .eq("marrakech".casefold())
        ]

    return (
        out.sort_values(
            "score_pertinence",
            ascending=False
        )
        .reset_index(drop=True)
    )
