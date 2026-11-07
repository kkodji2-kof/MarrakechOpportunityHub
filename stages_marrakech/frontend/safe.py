
from __future__ import annotations
from contextlib import contextmanager
import streamlit as st
from stages_marrakech.backend.errors import OpportunityHubError
from stages_marrakech.frontend import errors_ui, services


@contextmanager
def safe_section(contexte: str):
    """Entoure un bloc d'affichage : `with safe_section("Graphiques"): ...`

    st.stop() et st.rerun() ne sont pas interceptés (ce ne sont pas des `Exception`).
    """
    try:
        yield
    except Exception as exc:
        errors_ui.log_error(contexte, exc)
        errors_ui.show_error(contexte, exc)

def require_data() -> dict:
    """Retourne les données du backend ; prépare le pipeline au premier lancement ; sinon stoppe la page proprement."""
    if not services.data_ready():
        try:
            with st.spinner("Première préparation des données (collecte, nettoyage, analyse)…"):
                services.refresh_pipeline()
        except Exception as exc:  
            _stop_with_error("Préparation des données", exc)
    try:
        return services.get_data()
    except Exception as exc:  
        _stop_with_error("Chargement des données", exc)

def _stop_with_error(contexte: str, exc: BaseException):
    errors_ui.log_error(contexte, exc)
    errors_ui.show_error(contexte, exc)
    if isinstance(exc, OpportunityHubError) or isinstance(exc, FileNotFoundError):
        if st.button("Lancer le pipeline maintenant", key=f"retry_{contexte}"):
            try:
                services.refresh_pipeline()
                st.rerun()
            except Exception as retry_exc:
                errors_ui.log_error("Relance du pipeline", retry_exc)
                errors_ui.show_error("Relance du pipeline", retry_exc)
    st.stop()

def flash(message: str) -> None:
    """Message à afficher après un rechargement de la page (ex. « Suivi mis à jour »)."""
    st.session_state["flash"] = message

def show_flash() -> None:
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)