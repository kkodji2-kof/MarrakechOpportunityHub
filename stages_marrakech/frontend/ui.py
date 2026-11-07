
"""ÉTAPE 2 — Affichage correct des données :
tableaux, KPIs, graphiques clairs et lisibles.
"""

from __future__ import annotations

import hmac
import pandas as pd
import streamlit as st

from stages_marrakech.backend import config


# ============================================================
# CONFIGURATION ET PROTECTION
# ============================================================

def page_setup(config_page: bool = False) -> None:
    """
    Prépare l'affichage de la page.

    config_page=True uniquement si cette fonction est appelée
    avant tout autre élément Streamlit dans l'application.
    """
    if config_page:
        st.set_page_config(
            page_title="Marrakech OpportunityHub",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded",
        )

    _password_gate()
    _sidebar()


def _password_gate() -> None:
    """Protège l'application si APP_PASSWORD est défini."""

    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None

    if not expected or st.session_state.get("auth_ok"):
        return

    st.title("Marrakech OpportunityHub")
    st.subheader("Accès sécurisé")

    typed = st.text_input(
        "Mot de passe",
        type="password",
        key="app_password_input",
    )

    if st.button("Se connecter", use_container_width=True):
        if hmac.compare_digest(typed, str(expected)):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")

    st.stop()


def _sidebar() -> None:
    """Configuration de la barre latérale."""
    # La navigation principale est gérée par app.py.
    pass


# ============================================================
# INDICATEURS KPI
# ============================================================

def kpi_row(items: list[tuple]) -> None:
    """
    Affiche une rangée de KPIs.

    Exemple :
    kpi_row([
        ("Entreprises", 129, "Nombre total"),
        ("Score moyen", 56.5, "Sur 100"),
    ])
    """

    if not items:
        st.info("Aucun indicateur disponible.")
        return

    columns = st.columns(len(items))

    for col, item in zip(columns, items):
        label = item[0]
        value = item[1]
        help_text = item[2] if len(item) > 2 else None

        if value is None:
            display_value = "—"
        elif isinstance(value, float) and pd.isna(value):
            display_value = "—"
        else:
            display_value = value

        col.metric(
            label=label,
            value=display_value,
            help=help_text,
        )


# ============================================================
# GRAPHIQUES
# ============================================================

def show_figure(fig, key: str) -> None:
    """Affiche un graphique Plotly avec une largeur adaptée."""

    if fig is None:
        st.info("Graphique indisponible pour le moment.")
        return

    try:
        st.plotly_chart(
            fig,
            key=key,
            width="stretch",
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "responsive": True,
            },
        )
    except Exception as error:
        st.warning(f"Impossible d'afficher le graphique : {error}")


# ============================================================
# ÉTATS VIDES
# ============================================================

def empty_state(message: str) -> None:
    """Affiche un message lorsqu'aucune donnée n'est disponible."""
    st.info(message)


# ============================================================
# CONFIGURATION DU TABLEAU ENTREPRISES
# ============================================================

COMPANY_COLUMNS = {
    "nom_affiche": st.column_config.TextColumn(
        "Entreprise",
        width="large",
    ),
    "secteur": st.column_config.TextColumn("Secteur"),
    "ville": st.column_config.TextColumn("Ville"),
    "email_principal": st.column_config.TextColumn(
        "Email de candidature"
    ),
    "note": st.column_config.NumberColumn(
        "Note",
        format="%.1f",
    ),
    "nombre_avis": st.column_config.NumberColumn(
        "Avis",
        format="%d",
    ),
    "score_pertinence": st.column_config.ProgressColumn(
        "Score /100",
        min_value=0,
        max_value=100,
        format="%.0f",
    ),
    "priorite": st.column_config.TextColumn("Priorité"),
    "site_web": st.column_config.LinkColumn(
        "Site web",
        display_text="ouvrir",
    ),
}


def companies_table(df: pd.DataFrame) -> None:
    """Affiche les entreprises avec les colonnes disponibles."""

    if df is None or df.empty:
        empty_state("Aucune entreprise à afficher.")
        return

    cols = [col for col in COMPANY_COLUMNS if col in df.columns]

    if not cols:
        st.warning(
            "Aucune colonne entreprise reconnue. "
            "Vérifie les colonnes de ton fichier CSV."
        )
        st.caption(f"Colonnes disponibles : {list(df.columns)}")
        return

    st.dataframe(
        df[cols],
        hide_index=True,
        column_config={
            col: COMPANY_COLUMNS[col] for col in cols
        },
        width="stretch",
        height=450,
    )


# ============================================================
# CONFIGURATION DU TABLEAU DES OFFRES
# ============================================================

OFFER_COLUMNS = {
    "titre": st.column_config.TextColumn(
        "Offre",
        width="large",
    ),
    "entreprise": st.column_config.TextColumn("Entreprise"),
    "localisation": st.column_config.TextColumn("Lieu"),
    "contrat": st.column_config.TextColumn("Contrat"),
    "url": st.column_config.LinkColumn(
        "Annonce",
        display_text="ouvrir",
    ),
}


def offers_table(df: pd.DataFrame) -> None:
    """Affiche les offres d'emploi et de stage."""

    if df is None or df.empty:
        empty_state("Aucune offre disponible.")
        return

    cols = [col for col in OFFER_COLUMNS if col in df.columns]

    if not cols:
        st.warning(
            "Aucune colonne offre reconnue. "
            "Vérifie le format de ton fichier offres.csv."
        )
        st.caption(f"Colonnes disponibles : {list(df.columns)}")
        return

    st.dataframe(
        df[cols],
        hide_index=True,
        column_config={
            col: OFFER_COLUMNS[col] for col in cols
        },
        width="stretch",
        height=450,
    )


# ============================================================
# EXPORT CSV
# ============================================================

def download_csv(
    df: pd.DataFrame,
    filename: str,
    label: str,
    key: str,
) -> None:
    """Permet de télécharger un DataFrame au format CSV."""

    if df is None or df.empty:
        st.info("Aucune donnée disponible pour l'export.")
        return

    csv_data = df.to_csv(
        index=False,
        encoding="utf-8-sig",
    )

    st.download_button(
        label=label,
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        key=key,
        width="content",
    )
