
from __future__ import annotations

from datetime import datetime

import streamlit as st

from stages_marrakech.backend.errors import (DataSourceError, GooglePlacesError, OpportunityHubError,
                                             ValidationError)

CATALOGUE: list[tuple[type, str, str]] = [
    (DataSourceError, "Données introuvables ou illisibles",
     "Vérifie les fichiers dans data/raw, puis clique sur « Relancer le pipeline »."),
    (GooglePlacesError, "Google Places indisponible",
     "Vérifie la variable GOOGLE_PLACES_API_KEY et ta connexion. Les autres données restent disponibles."),
    (ValidationError, "Saisie invalide", "Corrige la valeur saisie puis réessaie."),
    (OpportunityHubError, "Erreur de l'application", "Réessaie ; si le problème continue, relance le pipeline."),
    (PermissionError, "Fichier verrouillé",
     "Ferme le fichier (par exemple suivi.csv ouvert dans Excel) puis réessaie."),
    (FileNotFoundError, "Fichier introuvable", "Relance le pipeline pour recréer les fichiers manquants."),
    (KeyError, "Colonne manquante dans les données",
     "Les fichiers ne correspondent pas à la version du code : relance le pipeline."),
    (ValueError, "Valeur incorrecte dans les données", "Relance le pipeline ou vérifie le fichier source."),
    (Exception, "Erreur inattendue", "Recharge la page. Si l'erreur revient, copie le détail technique."),
]


def describe(exc: BaseException) -> dict:
    """Transforme une exception en message clair pour l'utilisateur."""
    for exc_type, title, action in CATALOGUE:
        if isinstance(exc, exc_type):
            detail = str(exc) if isinstance(exc, OpportunityHubError) else ""
            return {"titre": title, "message": detail, "action": action, "type": type(exc).__name__}
    return {"titre": "Erreur", "message": str(exc), "action": "", "type": type(exc).__name__}


def log_error(contexte: str, exc: BaseException) -> None:
    """Ajoute l'erreur à la liste de la session (affichée dans la barre latérale)."""
    info = describe(exc)
    st.session_state.setdefault("erreurs", []).append({
        "heure": datetime.now().strftime("%H:%M:%S"), "contexte": contexte, **info,
        "technique": f"{type(exc).__name__}: {exc}"})


def show_error(contexte: str, exc: BaseException) -> None:
    """Affiche un message d'erreur lisible dans la page (sans casser le reste de l'application)."""
    info = describe(exc)
    body = f"**{info['titre']}** — {contexte}"
    if info["message"]:
        body += f"\n\n{info['message']}"
    if info["action"]:
        body += f"\n\n {info['action']}"
    st.error(body)
    with st.expander("Détail technique"):
        st.code(f"{type(exc).__name__}: {exc}")


def render_error_list() -> None:
    """Panneau « Liste des erreurs » de la barre latérale."""
    errors = st.session_state.get("erreurs", [])
    with st.sidebar.expander(f" Liste des erreurs ({len(errors)})", expanded=bool(errors)):
        if not errors:
            st.caption("Aucune erreur pour le moment.")
        for e in reversed(errors[-8:]):
            st.markdown(f"**{e['heure']}** · {e['contexte']}  \n{e['titre']}")
        if errors and st.button("Effacer la liste", key="clear_errors"):
            errors.clear()
            st.rerun()