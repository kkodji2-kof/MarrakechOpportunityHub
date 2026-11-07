import os
from datetime import date
from pathlib import Path
# ============================================================
# 1. CHEMINS DU PROJET
# ============================================================

PACKAGE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PACKAGE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
TRACK_DIR = DATA_DIR / "tracking"
REPORT_DIR = DATA_DIR / "reports"
# Création automatique des dossiers.
for directory in [
    RAW_DIR,
    CLEAN_DIR,
    TRACK_DIR,
    REPORT_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
# ============================================================
# 2. PARAMÈTRES GÉNÉRAUX
# ============================================================
VILLE_CIBLE = "Marrakech"
TODAY = date.today()

# ============================================================
# 3. SOURCES DE DONNÉES
# ============================================================

SOURCES = [
    {
        "file": "Avant_le_nettoyage.csv",
        "kind": "companies",
        "label": "Avant_le_nettoyage",
    },
    {
        "file": "entreprises_ia_marrakech_contacts_publics.csv",
        "kind": "companies",
        "label": "entreprises_contacts_publics",
    },
    {
        "file": "dataset__2_.csv",
        "kind": "companies",
        "label": "dataset__2_",
    },
    {
        "file": "offres_marrakech_ia_data_avec_url.csv",
        "kind": "offers_sim",
        "label": "offres_simulees",
    },
    {
        "file": "offres_reelles_marrakech.csv",
        "kind": "offers_real",
        "label": "offres_reelles",
    },
]


# ============================================================
# 4. GOOGLE PLACES API
# ============================================================

GOOGLE_API_KEY = os.getenv(
    "GOOGLE_PLACES_API_KEY",
    ""
)

GOOGLE_QUERIES = [
    "agence web Marrakech",
    "entreprise informatique Marrakech",
    "société intelligence artificielle Marrakech",
    "ESN Marrakech",
    "agence marketing digital Marrakech",
    "startup data Marrakech",
]

HTTP_TIMEOUT = 20

USER_AGENT = (
    "MarrakechOpportunityHub/1.0 "
    "(projet personnel de recherche de stage)"
)


# ============================================================
# 5. SCORING DE PERTINENCE
# ============================================================

SCORE_WEIGHTS = {
    "adequation": 35,
    "recrutement": 20,
    "reputation": 15,
    "localisation": 10,
    "contact": 20,
}

SECTOR_SCORES = {
    "IA / Data": 100,
    "Développement logiciel": 90,
    "Cybersécurité": 75,
    "Agence web / digital": 70,
    "Services informatiques": 65,
    "Communication & marketing": 40,
    "Conseil": 30,
    "À qualifier": 20,
    "Hors cible": 0,
}

PRIORITE_HAUTE = 70

PRIORITE_MOYENNE = 50


# ============================================================
# 6. GESTION DES OFFRES SIMULÉES
# ============================================================

# False : ne pas utiliser les offres simulées
# dans les analyses et le suivi final.

INCLUDE_SIMULATED_OFFERS = False


# ============================================================
# 7. SUIVI DES CANDIDATURES
# ============================================================

STATUTS = [
    "À contacter",
    "Candidature envoyée",
    "Relance à faire",
    "Réponse reçue",
    "Entretien",
    "Acceptée",
    "Refusée",
    "Sans réponse",
]

RELANCE_DELAI_JOURS = 7

TOP_N_SUIVI = 30
