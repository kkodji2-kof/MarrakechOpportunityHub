
from pathlib import Path

import pandas as pd
import pytest

from stages_marrakech.backend.errors import DataSourceError, ValidationError
from stages_marrakech.frontend import errors_ui, services

APP = Path(__file__).resolve().parent / "app.py"


def _companies() -> pd.DataFrame:
    return pd.DataFrame({
        "nom_affiche": ["Agence IA", "Riad Soleil", "Web Lab"],
        "secteur": ["IA / Data", "Hors cible", "Agence web / digital"],
        "pertinence": ["Cible IA/Tech", "Hors cible", "Cible IA/Tech"],
        "ville": ["Marrakech", "Marrakech", "Rabat"],
        "note": [4.8, 3.0, None],
        "statut_email": ["Validé", "Aucun", "Validé"],
        "score_pertinence": [90.0, 10.0, 60.0],
    })

def test_filtre_par_pertinence_et_tri_par_score():
    out = services.filter_companies(_companies(), pertinence=["Cible IA/Tech"])
    assert out["nom_affiche"].tolist() == ["Agence IA", "Web Lab"]


def test_filtres_combines():
    out = services.filter_companies(_companies(), only_email=True, only_marrakech=True, note_min=4)
    assert out["nom_affiche"].tolist() == ["Agence IA"]


def test_recherche_texte():
    assert services.filter_companies(_companies(), query="riad")["nom_affiche"].tolist() == ["Riad Soleil"]

@pytest.mark.parametrize("exc,titre", [
    (DataSourceError("x"), "Données introuvables ou illisibles"),
    (ValidationError("x"), "Saisie invalide"),
    (PermissionError("suivi.csv"), "Fichier verrouillé"),
    (KeyError("note"), "Colonne manquante dans les données"),
    (RuntimeError("boom"), "Erreur inattendue"),
])
def test_chaque_erreur_a_un_message_clair(exc, titre):
    info = errors_ui.describe(exc)
    assert info["titre"] == titre and info["action"]

def test_l_application_demarre_sans_exception_non_geree():
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception