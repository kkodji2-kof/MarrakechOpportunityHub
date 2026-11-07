
"""
MarrakechOpportunityHub
Application principale avec authentification SQLite/Argon2
et navigation Streamlit.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import streamlit as st


# =====================================================
# 1. CONFIGURATION STREAMLIT
# =====================================================

st.set_page_config(
    page_title="Marrakech OpportunityHub",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =====================================================
# 2. CHEMINS DU PROJET
# =====================================================

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = Path(__file__).resolve().parent
PAGES_DIR = FRONTEND_DIR / "pages"
ASSETS_DIR = FRONTEND_DIR / "assets"

THEME_BARRE = "sombre"

LOGO_PATH = ASSETS_DIR / (
    "logo_sidebar.png"
    if THEME_BARRE == "sombre"
    else "logo_light.png"
)

LOGO_ICON_PATH = ASSETS_DIR / "logo_icon.png"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# =====================================================
# 3. ENVIRONNEMENT
# =====================================================

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")

except ImportError:
    pass



# =====================================================
# 6. MESSAGES DE SESSION
# =====================================================

try:

    safe = importlib.import_module(
        "stages_marrakech.frontend.safe"
    )

    afficher_messages = getattr(safe, "show_flash", None)

    if callable(afficher_messages):
        afficher_messages()

except Exception as erreur:

    st.sidebar.warning(
        f"Messages de session indisponibles : {erreur}"
    )


# =====================================================
# 7. LOGO
# =====================================================

if LOGO_PATH.exists():

    try:

        icone = (
            str(LOGO_ICON_PATH)
            if LOGO_ICON_PATH.exists()
            else None
        )

        st.logo(
            str(LOGO_PATH),
            icon_image=icone,
            size="large",
        )

    except Exception as erreur:

        st.sidebar.warning(
            f"Impossible d'afficher le logo : {erreur}"
        )

else:

    st.sidebar.caption(
        "Logo non disponible."
    )


# =====================================================
# 8. DESIGN DE LA BARRE LATÉRALE
# =====================================================

CSS_BASE = """
<style>

[data-testid="stSidebarHeader"] {
    height: auto !important;
    padding-top: 1rem !important;
    padding-bottom: 0.5rem !important;
}

[data-testid="stSidebarLogo"] {
    height: 3.2rem !important;
    max-width: 100% !important;
}

[data-testid="stSidebarNav"] ul {
    gap: 0.35rem !important;
}

[data-testid="stSidebarNavLink"] {
    display: flex !important;
    align-items: center !important;
    min-height: 2.75rem !important;
    padding: 0.55rem 0.9rem !important;
    border-radius: 10px !important;
    margin-bottom: 0.3rem !important;
}

</style>
"""

CSS_SOMBRE = """
<style>

[data-testid="stSidebar"] {
    background: #0F172A !important;
    border-right: 1px solid rgba(255,255,255,.06);
}

[data-testid="stSidebarNavLink"] {
    color: #CBD5E1 !important;
}

[data-testid="stSidebarNavLink"]:hover {
    background: rgba(255,255,255,.08) !important;
    color: white !important;
}

[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: #2563EB !important;
    color: white !important;
    font-weight: 600 !important;
}

[data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNavLink"] p {
    color: inherit !important;
}

[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,.12) !important;
}

</style>
"""

CSS_CLAIR = """
<style>

[data-testid="stSidebar"] {
    background: #F8FAFC !important;
}

[data-testid="stSidebarNavLink"] {
    color: #334155 !important;
}

[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: #2563EB !important;
    color: white !important;
}

</style>
"""

st.markdown(
    CSS_BASE + (
        CSS_SOMBRE
        if THEME_BARRE == "sombre"
        else CSS_CLAIR
    ),
    unsafe_allow_html=True,
)

# =====================================================
# 11. IMPORTATION DU CHATBOT
# =====================================================

afficher_chatbot_flottant = None

try:

    module_chatbot = importlib.import_module(
        "stages_marrakech.frontend.agent_chat"
    )

    afficher_chatbot_flottant = getattr(
        module_chatbot,
        "afficher_chatbot_flottant",
        None,
    )

except Exception as erreur:

    st.sidebar.warning(
        f"Chatbot indisponible : {erreur}"
    )


# =====================================================
# 12. CONFIGURATION DES PAGES
# =====================================================

configuration_pages = [

    {
        "fichier": "dashboard.py",
        "titre": "Tableau de bord",
        "icone": ":material/dashboard:",
    },

    {
        "fichier": "entreprises.py",
        "titre": "Entreprises",
        "icone": ":material/apartment:",
    },

    {
        "fichier": "offres.py",
        "titre": "Offres d'emploi",
        "icone": ":material/work:",
    },

    {
        "fichier": "tracker.py",
        "titre": "Suivi des candidatures",
        "icone": ":material/assignment_turned_in:",
    },

    {
        "fichier": "creer_cv.py",
        "titre": "Créer mon CV",
        "icone": ":material/edit_document:",
    },

    {
        "fichier": "evaluation_cv.py",
        "titre": "Évaluation du CV",
        "icone": ":material/fact_check:",
    },

    {
        "fichier": "profil.py",
        "titre": "Mon profil",
        "icone": ":material/person:",
    },
]


# =====================================================
# 13. CONSTRUCTION DE LA NAVIGATION
# =====================================================

pages = []
erreurs_pages = []

for page_config in configuration_pages:

    chemin = PAGES_DIR / page_config["fichier"]

    if not chemin.is_file():

        erreurs_pages.append(
            f"Page introuvable : {page_config['fichier']}"
        )

        continue

    parametres = {
        "page": str(chemin),
        "title": page_config["titre"],
        "icon": page_config["icone"],
    }

    if page_config["fichier"] == "dashboard.py":
        parametres["default"] = True

    pages.append(
        st.Page(**parametres)
    )


# =====================================================
# 14. AFFICHAGE DES ERREURS
# =====================================================

for erreur in erreurs_pages:

    st.sidebar.warning(erreur)


# =====================================================
# 15. NAVIGATION PRINCIPALE
# =====================================================

if not pages:

    st.error(
        "Aucune page disponible. "
        "Vérifiez le dossier frontend/pages."
    )

    st.stop()


navigation = st.navigation(pages)

navigation.run()


# =====================================================
# 16. CHATBOT FLOTTANT
# =====================================================

if callable(afficher_chatbot_flottant):

    try:

        afficher_chatbot_flottant()

    except Exception as erreur:

        st.sidebar.warning(
            f"Chatbot indisponible : {erreur}"
        )
