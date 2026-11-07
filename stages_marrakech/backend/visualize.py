from __future__ import annotations
from pathlib import Path
from html import escape
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import unicodedata
import re
import unicodedata
import pandas as pd
import plotly.express as px

# ============================================================
# CONFIGURATION
# ============================================================

COLORS = {
    "Haute": "#2e7d32",
    "Moyenne": "#f9a825",
    "Basse": "#c62828",
}

TEMPLATE = "plotly_white"


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def _empty(message: str) -> go.Figure:
    """Retourne un graphique vide avec un message explicatif."""

    fig = go.Figure()

    fig.add_annotation(
        text=message,
        showarrow=False,
        font={"size": 16}
    )

    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)

    fig.update_layout(
        template=TEMPLATE,
        height=400
    )

    return fig


def _safe_dataframe(data) -> pd.DataFrame:
    """Convertit une entrée en DataFrame exploitable."""

    if data is None:
        return pd.DataFrame()

    if isinstance(data, pd.DataFrame):
        return data.copy()

    return pd.DataFrame()


def _numeric_column(df, column, default=0):
    """Convertit une colonne en valeurs numériques."""

    if column not in df.columns:
        df[column] = default

    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(default)

    return df


def _ensure_column(df, target, alternatives, default=None):
    """
    Crée une colonne cible à partir d'une colonne alternative.

    Exemple :
        score_pertinence <- score_global
    """

    if target in df.columns:
        return df

    for alternative in alternatives:
        if alternative in df.columns:
            df[target] = df[alternative]
            return df

    df[target] = default

    return df


# ============================================================
# 1. ENTREPRISES PAR SECTEUR
# ============================================================

def fig_secteurs(by_sector: pd.DataFrame) -> go.Figure:
    """
    Graphique du nombre d'entreprises par secteur.

    Colonnes acceptées :
        secteur
        nombre_entreprises
        entreprises
        score_moyen
    """

    df = _safe_dataframe(by_sector)

    if df.empty:
        return _empty(
            "Aucune donnée sectorielle disponible"
        )

    if "secteur" not in df.columns:
        df["secteur"] = "Non renseigné"

    # Harmonisation du nombre d'entreprises
    df = _ensure_column(
        df,
        "entreprises",
        ["nombre_entreprises", "nombre", "total"],
        0
    )

    _numeric_column(df, "entreprises")

    df["secteur"] = (
        df["secteur"]
        .fillna("Non renseigné")
        .astype(str)
    )

    df = df.sort_values(
        "entreprises",
        ascending=True
    )

    fig = px.bar(
        df,
        x="entreprises",
        y="secteur",
        orientation="h",
        text="entreprises",
        title="Nombre d'entreprises par secteur",
        labels={
            "entreprises": "Nombre d'entreprises",
            "secteur": "Secteur"
        },
        template=TEMPLATE
    )

    fig.update_traces(
        textposition="outside"
    )

    fig.update_layout(
        yaxis={
            "categoryorder": "total ascending"
        },
        height=450
    )

    return fig


# ============================================================
# 2. DISTRIBUTION DES SCORES
# ============================================================

def fig_scores(scored: pd.DataFrame) -> go.Figure:
    """
    Distribution des scores de pertinence.

    Accepte :
        score_global
        score_pertinence
    """

    df = _safe_dataframe(scored)

    if df.empty:
        return _empty(
            "Aucun score disponible"
        )

    # Compatibilité avec analyze.py
    df = _ensure_column(
        df,
        "score_pertinence",
        ["score_global", "score"],
        None
    )

    if df["score_pertinence"].isna().all():
        return _empty(
            "Aucun score de pertinence renseigné"
        )

    _numeric_column(
        df,
        "score_pertinence"
    )

    fig = px.histogram(
        df,
        x="score_pertinence",
        nbins=20,
        title="Distribution des scores de pertinence",
        labels={
            "score_pertinence": "Score /100"
        },
        template=TEMPLATE
    )

    fig.update_layout(
        yaxis_title="Nombre d'entreprises",
        xaxis_title="Score de pertinence"
    )

    return fig


# ============================================================
# 3. DISTRIBUTION DES NOTES GOOGLE
# ============================================================

def fig_notes(distribution: pd.DataFrame) -> go.Figure:
    """
    Répartition des notes Google.

    Colonnes attendues :
        tranche
        entreprises ou nombre_entreprises
    """

    df = _safe_dataframe(distribution)

    if df.empty:
        return _empty(
            "Aucune note disponible"
        )

    if "tranche" not in df.columns:
        df["tranche"] = "Non renseignée"

    df = _ensure_column(
        df,
        "entreprises",
        ["nombre_entreprises", "nombre", "total"],
        0
    )

    _numeric_column(df, "entreprises")

    fig = px.bar(
        df,
        x="tranche",
        y="entreprises",
        text="entreprises",
        title="Répartition des notes Google",
        labels={
            "tranche": "Tranche de notes",
            "entreprises": "Nombre d'entreprises"
        },
        template=TEMPLATE
    )

    fig.update_layout(
        xaxis_title="Note",
        yaxis_title="Nombre d'entreprises"
    )

    return fig


# ============================================================
# 4. TOP ENTREPRISES PRIORITAIRES
# ============================================================

def fig_top_priorites(
    priorities: pd.DataFrame,
    n: int = 10
) -> go.Figure:
    """
    Affiche les entreprises prioritaires.

    Colonnes acceptées :
        score_global ou score_pertinence
        nom_affiche ou nom
        priorite
    """

    df = _safe_dataframe(priorities)

    if df.empty:
        return _empty(
            "Aucune entreprise prioritaire disponible"
        )

    # Harmonisation du score
    df = _ensure_column(
        df,
        "score_pertinence",
        ["score_global", "score"],
        0
    )

    # Harmonisation du nom
    df = _ensure_column(
        df,
        "nom_affiche",
        ["nom", "entreprise"],
        "Entreprise inconnue"
    )

    # Harmonisation de la priorité
    if "priorite" not in df.columns:
        df["priorite"] = "Moyenne"

    _numeric_column(
        df,
        "score_pertinence"
    )

    df = df.sort_values(
        "score_pertinence",
        ascending=False
    ).head(n)

    fig = px.bar(
        df,
        x="score_pertinence",
        y="nom_affiche",
        orientation="h",
        color="priorite",
        color_discrete_map=COLORS,
        title=f"Top {len(df)} entreprises à contacter",
        labels={
            "score_pertinence": "Score /100",
            "nom_affiche": "Entreprise",
            "priorite": "Priorité"
        },
        template=TEMPLATE
    )

    fig.update_layout(
        yaxis={
            "categoryorder": "total ascending"
        },
        xaxis_title="Score de pertinence",
        yaxis_title="",
        height=max(400, len(df) * 35)
    )

    return fig


# ============================================================
# 5. ÉVOLUTION DES OFFRES DANS LE TEMPS
# ============================================================

def fig_offres_temps(
    per_week: pd.DataFrame
) -> go.Figure:
    """
    Évolution du nombre d'offres par semaine.

    Colonnes :
        semaine
        offres
    """

    df = _safe_dataframe(per_week)

    if df.empty:
        return _empty(
            "Aucune offre datée à afficher"
        )

    if "semaine" not in df.columns:
        return _empty(
            "Colonne semaine indisponible"
        )

    df = _ensure_column(
        df,
        "offres",
        ["nombre_offres", "nombre"],
        0
    )

    _numeric_column(df, "offres")

    fig = px.line(
        df,
        x="semaine",
        y="offres",
        markers=True,
        title="Évolution des offres par semaine",
        labels={
            "semaine": "Semaine",
            "offres": "Nombre d'offres"
        },
        template=TEMPLATE
    )

    fig.update_layout(
        xaxis_title="Semaine",
        yaxis_title="Nombre d'offres"
    )

    return fig


# ============================================================
# 6. OFFRES PAR TYPE DE CONTRAT
# ============================================================

def fig_offres_contrat(
    by_contract: pd.DataFrame
) -> go.Figure:
    """
    Répartition des offres par type de contrat.

    Colonnes :
        contrat
        offres
    """

    df = _safe_dataframe(by_contract)

    if df.empty:
        return _empty(
            "Aucune donnée sur les contrats"
        )

    if "contrat" not in df.columns:
        df["contrat"] = "Non renseigné"

    df = _ensure_column(
        df,
        "offres",
        ["nombre_offres", "nombre"],
        0
    )

    _numeric_column(df, "offres")

    df["contrat"] = (
        df["contrat"]
        .fillna("Non renseigné")
        .astype(str)
    )

    fig = px.pie(
        df,
        names="contrat",
        values="offres",
        hole=0.45,
        title="Offres par type de contrat",
        template=TEMPLATE
    )

    return fig


# ============================================================
# 7. RELANCES ET CANDIDATURES
# ============================================================

def fig_relances(
    summary_df: pd.DataFrame
) -> go.Figure:
    """
    Graphique des candidatures et relances.

    Colonnes :
        categorie
        nombre
    """

    df = _safe_dataframe(summary_df)

    if df.empty:
        return _empty(
            "Aucune candidature suivie pour le moment"
        )

    if "categorie" not in df.columns:
        df["categorie"] = "Non renseigné"

    if "nombre" not in df.columns:
        return _empty(
            "Colonne nombre indisponible"
        )

    _numeric_column(df, "nombre")

    df = df[df["nombre"] > 0]

    if df.empty:
        return _empty(
            "Aucune candidature suivie pour le moment"
        )

    fig = px.pie(
        df,
        names="categorie",
        values="nombre",
        hole=0.5,
        title="Candidatures et relances à traiter",
        template=TEMPLATE
    )

    return fig


# ============================================================
# 8. ENTONNOIR DE CANDIDATURE
# ============================================================

def fig_entonnoir(
    tracking: pd.DataFrame
) -> go.Figure:
    """
    Entonnoir de suivi des candidatures.

    Utilise la colonne statut.
    """

    df = _safe_dataframe(tracking)

    if df.empty:
        return _empty(
            "Aucune candidature disponible"
        )

    if "statut" not in df.columns:
        if "statut_suivi" in df.columns:
            df["statut"] = df["statut_suivi"]
        else:
            return _empty(
                "Colonne statut indisponible"
            )

    order = [
        "À contacter",
        "Candidature préparée",
        "Candidature envoyée",
        "Réponse reçue",
        "Entretien",
        "Acceptée"
    ]

    counts = [
        int(
            df["statut"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
            .eq(status.casefold())
            .sum()
        )
        for status in order
    ]

    fig = go.Figure(
        go.Funnel(
            y=order,
            x=counts
        )
    )

    fig.update_layout(
        title="Entonnoir de candidature",
        template=TEMPLATE
    )

    return fig


# ============================================================
# 9. QUALITÉ ET COMPLÉTUDE DES DONNÉES
# ============================================================

def fig_qualite(
    completeness_df: pd.DataFrame
) -> go.Figure:
    """
    Affiche le pourcentage de complétude par colonne.

    Colonnes acceptées :
        colonne
        renseigne_%
        renseigne_pct
        pourcentage
    """

    df = _safe_dataframe(completeness_df)

    if df.empty:
        return _empty(
            "Aucune donnée de qualité disponible"
        )

    if "colonne" not in df.columns:
        return _empty(
            "Colonne colonne indisponible"
        )

    df = _ensure_column(
        df,
        "renseigne_pct",
        [
            "renseigne_%",
            "pourcentage",
            "completude"
        ],
        0
    )

    _numeric_column(
        df,
        "renseigne_pct"
    )

    df = df.sort_values(
        "renseigne_pct",
        ascending=True
    )

    fig = px.bar(
        df,
        x="renseigne_pct",
        y="colonne",
        orientation="h",
        title=(
            "Complétude des données "
            "(% de valeurs renseignées)"
        ),
        labels={
            "renseigne_pct": "Complétude (%)",
            "colonne": "Colonne"
        },
        template=TEMPLATE
    )

    fig.update_xaxes(
        range=[0, 100]
    )

    fig.update_layout(
        height=max(400, len(df) * 30)
    )

    return fig


# ============================================================
# 10. CARTE DES ENTREPRISES
# ============================================================

def fig_carte(
    companies: pd.DataFrame
) -> go.Figure | None:
    """
    Carte des entreprises de Marrakech.

    Nécessite :
        latitude
        longitude

    Retourne None si les coordonnées sont indisponibles.
    """

    df = _safe_dataframe(companies)

    if df.empty:
        return None

    required = [
        "latitude",
        "longitude"
    ]

    if not all(
        column in df.columns
        for column in required
    ):
        return None

    df["latitude"] = pd.to_numeric(
        df["latitude"],
        errors="coerce"
    )

    df["longitude"] = pd.to_numeric(
        df["longitude"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "latitude",
            "longitude"
        ]
    )

    if df.empty:
        return None

    df = _ensure_column(
        df,
        "nom_affiche",
        ["nom", "entreprise"],
        "Entreprise inconnue"
    )

    if "secteur" not in df.columns:
        df["secteur"] = "Non renseigné"

    # Vérification des coordonnées géographiques
    df = df[
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
    ]

    if df.empty:
        return None

    fig = px.scatter_map(
        df,
        lat="latitude",
        lon="longitude",
        hover_name="nom_affiche",
        color="secteur",
        zoom=11,
        title="Carte des entreprises de Marrakech",
        template=TEMPLATE
    )

    return fig


# ============================================================
# 11. ANALYSE MULTIVARIÉE (CORRÉLATIONS, ACP, GROUPES)
# ============================================================
# Les tableaux utilisés ici proviennent de
# analyze.multivariate_analysis() :
#   Correlations, ACP_coordonnees, ACP_variance, ACP_variables

def _axis_label(variance, component: str) -> str:
    """Libellé d'axe avec le pourcentage de variance expliquée."""

    if isinstance(variance, pd.DataFrame) and not variance.empty:

        if {"composante", "variance_expliquee"}.issubset(variance.columns):

            row = variance.loc[variance["composante"] == component]

            if not row.empty:
                value = float(row["variance_expliquee"].iloc[0])
                return f"{component} ({value:.1f} %)"

    return component


def fig_correlations(corr: pd.DataFrame) -> go.Figure:
    """
    Heatmap de la matrice de corrélations.

    Entrée :
        DataFrame carré (index et colonnes = variables)
    """

    if not isinstance(corr, pd.DataFrame) or corr.empty:
        return _empty(
            "Corrélations indisponibles"
        )

    fig = px.imshow(
        corr,
        text_auto=".2f",
        zmin=-1,
        zmax=1,
        color_continuous_scale="RdBu_r",
        aspect="auto",
        title="Matrice de corrélations",
        template=TEMPLATE
    )

    fig.update_layout(
        height=480,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        coloraxis_colorbar={"title": "r"}
    )

    return fig


def fig_acp_individus(
    coords: pd.DataFrame,
    variance: pd.DataFrame | None = None
) -> go.Figure:
    """
    Nuage des entreprises sur le plan factoriel PC1 / PC2,
    coloré par groupe.

    Colonnes attendues :
        entreprise, secteur, priorite, score_global,
        PC1, PC2, groupe
    """

    df = _safe_dataframe(coords)

    if df.empty:
        return _empty(
            "ACP indisponible"
        )

    required = ["PC1", "PC2"]

    if not all(column in df.columns for column in required):
        return _empty(
            "Colonnes PC1 / PC2 indisponibles"
        )

    df = _ensure_column(
        df,
        "entreprise",
        ["nom_affiche", "nom"],
        "Entreprise inconnue"
    )

    if "groupe" not in df.columns:
        df["groupe"] = "Toutes"

    hover = {
        "PC1": ":.2f",
        "PC2": ":.2f",
        "groupe": False
    }

    for column, fmt in [
        ("secteur", True),
        ("priorite", True),
        ("score_global", ":.1f")
    ]:
        if column in df.columns:
            hover[column] = fmt

    fig = px.scatter(
        df,
        x="PC1",
        y="PC2",
        color="groupe",
        hover_name="entreprise",
        hover_data=hover,
        title="Plan factoriel des entreprises (ACP)",
        template=TEMPLATE
    )

    fig.update_traces(
        marker={
            "size": 10,
            "opacity": 0.8,
            "line": {"width": 0.5, "color": "white"}
        }
    )

    fig.add_hline(
        y=0,
        line_width=1,
        line_dash="dot",
        opacity=0.5
    )

    fig.add_vline(
        x=0,
        line_width=1,
        line_dash="dot",
        opacity=0.5
    )

    fig.update_layout(
        xaxis_title=_axis_label(variance, "PC1"),
        yaxis_title=_axis_label(variance, "PC2"),
        legend_title_text="Groupe",
        height=480,
        margin={"l": 10, "r": 10, "t": 50, "b": 10}
    )

    return fig


def fig_acp_cercle(
    variables: pd.DataFrame,
    variance: pd.DataFrame | None = None
) -> go.Figure:
    """
    Cercle des corrélations : poids des variables sur PC1 / PC2.

    Colonnes attendues :
        variable, PC1, PC2
    """

    df = _safe_dataframe(variables)

    if df.empty:
        return _empty(
            "Cercle des corrélations indisponible"
        )

    if not all(
        column in df.columns
        for column in ["variable", "PC1", "PC2"]
    ):
        return _empty(
            "Colonnes variable / PC1 / PC2 indisponibles"
        )

    theta = np.linspace(0, 2 * np.pi, 200)

    fig = go.Figure()

    # Cercle unité
    fig.add_trace(
        go.Scatter(
            x=np.cos(theta),
            y=np.sin(theta),
            mode="lines",
            line={"width": 1, "dash": "dot"},
            hoverinfo="skip",
            showlegend=False
        )
    )

    # Flèches depuis l'origine
    for _, row in df.iterrows():
        fig.add_annotation(
            x=row["PC1"],
            y=row["PC2"],
            ax=0,
            ay=0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.6
        )

    # Libellés des variables
    fig.add_trace(
        go.Scatter(
            x=df["PC1"],
            y=df["PC2"],
            mode="markers+text",
            text=df["variable"],
            textposition="top center",
            marker={"size": 7},
            hovertemplate=(
                "%{text}<br>PC1 = %{x:.2f}"
                "<br>PC2 = %{y:.2f}<extra></extra>"
            ),
            showlegend=False
        )
    )

    fig.update_layout(
        title="Cercle des corrélations",
        template=TEMPLATE,
        xaxis={
            "title": _axis_label(variance, "PC1"),
            "range": [-1.15, 1.15],
            "zeroline": True
        },
        yaxis={
            "title": _axis_label(variance, "PC2"),
            "range": [-1.15, 1.15],
            "zeroline": True,
            "scaleanchor": "x",
            "scaleratio": 1
        },
        height=480,
        margin={"l": 10, "r": 10, "t": 50, "b": 10}
    )

    return fig


# ============================================================
# 12. GRAPHES MULTIVARIÉS DU TABLEAU DE BORD
# ============================================================
# Tableaux attendus (préparés par analyze.py) :
#   companies : analyze.add_offer_counts(scored, offers)
#   offers    : analyze.enrich_offers(offers, scored)
#
# Chaque fonction renvoie une figure Plotly (ou un graphique vide
# avec un message si les données nécessaires manquent).

def _top_categories(series, n: int = 8, other: str = "Autres"):
    """Garde les n catégories les plus fréquentes, regroupe le reste."""

    values = series.fillna("Non renseigné").astype(str)
    top = values.value_counts().head(n).index

    return values.where(values.isin(top), other)


def _has(df, columns) -> bool:
    """Vrai si df est un DataFrame non vide contenant toutes les colonnes."""

    return (
        isinstance(df, pd.DataFrame)
        and not df.empty
        and all(column in df.columns for column in columns)
    )


def _num(df, column) -> pd.Series:
    """Colonne numérique (NaN si absente ou illisible)."""

    if isinstance(df, pd.DataFrame) and column in df.columns:
        return pd.to_numeric(df[column], errors="coerce")

    return pd.Series(dtype=float)


# ------------------------------------------------------------
# Relations


def fig_bulles(offres: pd.DataFrame) -> go.Figure:
    """
    Graphique à bulles des offres d'emploi.

    Axe X : expérience demandée en années
    Axe Y : niveau d'études
    Taille : salaire mensuel en MAD lorsqu'il est connu
    Couleur : niveau d'études

    Les salaires inconnus sont affichés avec une croix grise.
    Aucune valeur manquante n'est inventée.
    """

    import re
    import unicodedata

    # ----------------------------------------------------
    # 1. Vérifier les données
    # ----------------------------------------------------
    if not isinstance(offres, pd.DataFrame) or offres.empty:
        return _empty("Aucune offre disponible pour le graphique")

    df = offres.copy()

    # ----------------------------------------------------
    # 2. Normaliser les noms de colonnes
    # ----------------------------------------------------
    def normaliser_colonne(colonne):
        texte = unicodedata.normalize("NFKD", str(colonne).lower().strip())
        texte = "".join(
            c for c in texte
            if not unicodedata.combining(c)
        )
        return re.sub(r"[^a-z0-9]+", "_", texte).strip("_")

    df.columns = [normaliser_colonne(c) for c in df.columns]

    # Accepter plusieurs noms possibles
    alias = {
        "experience": [
            "experience_requise",
            "experience_demande",
            "annees_experience",
            "expérience"
        ],
        "niveau_etudes": [
            "niveau_etude",
            "niveau_d_etudes",
            "niveau_formation",
            "formation"
        ],
        "salaire": [
            "remuneration",
            "salaire_mensuel"
        ],
        "ville": [
            "localisation",
            "lieu",
            "ville_recherchee"
        ],
        "entreprise": [
            "company",
            "company_name",
            "nom_entreprise"
        ],
        "titre": [
            "title",
            "poste",
            "intitule"
        ]
    }

    for cible, alternatives in alias.items():
        if cible not in df.columns:
            for alternative in alternatives:
                alternative = normaliser_colonne(alternative)
                if alternative in df.columns:
                    df[cible] = df[alternative]
                    break

    # Colonnes obligatoires
    obligatoires = ["experience", "niveau_etudes"]
    manquantes = [c for c in obligatoires if c not in df.columns]

    if manquantes:
        return _empty(
            "Colonnes manquantes : " + ", ".join(manquantes)
        )

    # ----------------------------------------------------
    # 3. Filtrer les offres de Marrakech
    # ----------------------------------------------------
    if "ville" in df.columns:
        villes = df["ville"].fillna("").astype(str)

        df = df[
            villes.str.contains("Marrakech", case=False, na=False)
        ].copy()

    if df.empty:
        return _empty(
            "Aucune offre de Marrakech après le filtrage"
        )

    # ----------------------------------------------------
    # 4. Convertir l'expérience en années
    # ----------------------------------------------------
    def convertir_experience(valeur):

        if pd.isna(valeur):
            return None

        texte = str(valeur).lower().strip()

        if not texte:
            return None

        # Expérience explicitement nulle
        expressions_zero = [
            "sans experience",
            "sans expérience",
            "aucune experience",
            "aucune expérience",
            "debutant",
            "débutant",
            "aucune",
            "0 an",
            "0 année"
        ]

        if any(mot in texte for mot in expressions_zero):
            return 0.0

        texte = texte.replace(",", ".")

        nombres = re.findall(r"\d+(?:\.\d+)?", texte)

        if not nombres:
            return None

        valeurs = [float(n) for n in nombres[:2]]

        # Pour une fourchette, calculer la moyenne
        resultat = sum(valeurs) / len(valeurs)

        # Conversion des mois en années
        if "mois" in texte:
            resultat /= 12

        return resultat

    df["experience_graph"] = df["experience"].apply(
        convertir_experience
    )

    # ----------------------------------------------------
    # 5. Convertir le salaire en MAD mensuels
    # ----------------------------------------------------
    def convertir_salaire(valeur):

        if pd.isna(valeur):
            return None

        texte = str(valeur).lower().strip()

        if not texte:
            return None

        expressions_inconnues = [
            "negociable",
            "négociable",
            "confidentiel",
            "non communique",
            "non communiqué",
            "non precise",
            "non précisé",
            "selon profil",
            "a discuter",
            "à discuter"
        ]

        if any(mot in texte for mot in expressions_inconnues):
            return None

        # Retirer les espaces séparant les milliers
        texte = re.sub(
            r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?:\D|$))",
            "",
            texte
        )

        nombres = re.findall(
            r"\d+(?:[.,]\d+)?",
            texte
        )

        if not nombres:
            return None

        valeurs = [
            float(n.replace(",", "."))
            for n in nombres[:2]
        ]

        salaire = sum(valeurs) / len(valeurs)

        # Conversion annuelle en mensuelle
        if any(mot in texte for mot in [
            "/an", "par an", "annuel", "annuelle"
        ]):
            salaire /= 12

        # Conversion horaire en estimation mensuelle
        elif any(mot in texte for mot in [
            "/heure", "par heure", "horaire"
        ]):
            salaire *= 173.33

        return salaire if salaire > 0 else None

    if "salaire" in df.columns:
        df["salaire_graph"] = df["salaire"].apply(
            convertir_salaire
        )
    else:
        df["salaire_graph"] = None

    # ----------------------------------------------------
    # 6. Préparer le niveau d'études
    # ----------------------------------------------------
    df["niveau_graph"] = (
        df["niveau_etudes"]
        .fillna("Non renseigné")
        .astype(str)
        .str.strip()
        .replace("", "Non renseigné")
    )

    # Garder uniquement les expériences exploitables
    df = df.dropna(subset=["experience_graph"]).copy()

    df = df[df["experience_graph"] >= 0].copy()

    if df.empty:
        return _empty(
            "Aucune expérience exploitable. "
            "Vérifiez les valeurs de la colonne experience dans le CSV."
        )

    # ----------------------------------------------------
    # 7. Séparer les salaires connus et inconnus
    # ----------------------------------------------------
    df_avec_salaire = df[
        df["salaire_graph"].notna()
        & (df["salaire_graph"] > 0)
    ].copy()

    df_sans_salaire = df[
        df["salaire_graph"].isna()
        | (df["salaire_graph"] <= 0)
    ].copy()

    # ----------------------------------------------------
    # 8. Construire le graphique
    # ----------------------------------------------------
    fig = go.Figure()

    colonnes_hover = [
        c for c in [
            "entreprise",
            "titre",
            "ville",
            "contrat",
            "experience",
            "niveau_etudes",
            "salaire",
            "source"
        ]
        if c in df.columns
    ]

    # Offres avec salaire connu
    if not df_avec_salaire.empty:

        hover_data = {
            c: True for c in colonnes_hover
        }

        fig_salaire = px.scatter(
            df_avec_salaire,
            x="experience_graph",
            y="niveau_graph",
            size="salaire_graph",
            color="niveau_graph",
            hover_name=(
                "entreprise"
                if "entreprise" in df_avec_salaire.columns
                else "titre"
                if "titre" in df_avec_salaire.columns
                else None
            ),
            hover_data=hover_data,
            size_max=48,
            opacity=0.80,
            labels={
                "experience_graph": "Expérience (années)",
                "niveau_graph": "Niveau d'études",
                "salaire_graph": "Salaire mensuel estimé (MAD)"
            }
        )

        for trace in fig_salaire.data:
            fig.add_trace(trace)

    # Offres sans salaire connu
    if not df_sans_salaire.empty:

        fig.add_trace(
            go.Scatter(
                x=df_sans_salaire["experience_graph"],
                y=df_sans_salaire["niveau_graph"],
                mode="markers",
                name="Salaire non renseigné",
                marker={
                    "size": 13,
                    "color": "gray",
                    "symbol": "x",
                    "line": {"width": 2}
                },
                customdata=df_sans_salaire[
                    colonnes_hover
                ].fillna("Non renseigné").astype(str).values
                if colonnes_hover else None,
                hovertemplate=(
                    "Expérience : %{x:.1f} ans<br>"
                    "Formation : %{y}<br>"
                    "Salaire : Non renseigné"
                    "<extra></extra>"
                )
            )
        )

    # ----------------------------------------------------
    # 9. Mise en forme finale
    # ----------------------------------------------------
    fig.update_layout(
        title={
            "text": (
                "Offres de Marrakech : expérience, "
                "formation et salaire"
            ),
            "x": 0.5
        },
        template="plotly_white",
        height=550,
        xaxis_title="Expérience demandée (années)",
        yaxis_title="Niveau d'études",
        legend_title="Niveau d'études",
        margin={
            "l": 40,
            "r": 30,
            "t": 85,
            "b": 50
        }
    )

    fig.update_xaxes(
        rangemode="tozero"
    )

    return fig



def fig_coordonnees_paralleles(offers: pd.DataFrame) -> go.Figure:
    """Coordonnées parallèles : secteur, contrat, études, score, expérience, salaire."""

    if not _has(offers, ["secteur"]):
        return _empty("Aucune offre disponible")

    df = offers.copy()
    dimensions = []

    def add_category(column, label):
        if column not in df.columns:
            return

        values = _top_categories(df[column], n=6)
        categories = sorted(values.unique())

        if len(categories) < 2:
            return

        codes = pd.Categorical(values, categories=categories).codes

        dimensions.append({
            "label": label,
            "values": codes,
            "tickvals": list(range(len(categories))),
            "ticktext": categories,
            "range": [0, len(categories) - 1]
        })

    def add_number(column, label):
        series = _num(df, column)

        if series.notna().sum() >= 3 and series.std(ddof=0) > 0:
            dimensions.append({
                "label": label,
                "values": series.fillna(series.median())
            })

    add_category("secteur", "Secteur")
    add_category("contrat", "Contrat")
    add_category("niveau_etudes", "Études")
    add_number("score_entreprise", "Score entreprise")
    add_number("experience_ans", "Expérience (ans)")
    add_number("salaire_num", "Salaire (MAD)")

    if len(dimensions) < 3:
        return _empty("Pas assez de variables renseignées (3 minimum)")

    color = _num(df, "score_entreprise").fillna(0)

    fig = go.Figure(
        go.Parcoords(
            line={
                "color": color,
                "colorscale": "Viridis",
                "showscale": True
            },
            dimensions=dimensions
        )
    )

    fig.update_layout(
        title="Comparaison multicritère des offres (coordonnées parallèles)",
        template=TEMPLATE,
        height=480,
        margin={"l": 60, "r": 40, "t": 80, "b": 20}
    )

    return fig


def fig_scatter3d(
    offers: pd.DataFrame,
    companies: pd.DataFrame | None = None
) -> go.Figure:
    """
    Nuage 3D : score, expérience, salaire (offres).
    À défaut, adéquation, réputation, contact (entreprises).
    """

    if _has(offers, ["score_entreprise", "experience_ans", "salaire_num"]):

        df = offers.copy()

        for column in ["score_entreprise", "experience_ans", "salaire_num"]:
            df[column] = _num(df, column)

        df = df.dropna(
            subset=["score_entreprise", "experience_ans", "salaire_num"]
        )

        if len(df) >= 3:

            df["secteur_groupe"] = _top_categories(df["secteur"])

            fig = px.scatter_3d(
                df,
                x="score_entreprise",
                y="experience_ans",
                z="salaire_num",
                color="secteur_groupe",
                hover_name="titre" if "titre" in df.columns else None,
                labels={
                    "score_entreprise": "Score",
                    "experience_ans": "Expérience (ans)",
                    "salaire_num": "Salaire (MAD)",
                    "secteur_groupe": "Secteur"
                },
                title="Score, expérience et salaire des offres",
                template=TEMPLATE
            )

            fig.update_layout(height=520)

            return fig

    columns = ["score_adequation", "score_reputation", "score_contact"]

    if _has(companies, columns + ["secteur"]):

        df = companies.copy()
        df["secteur_groupe"] = _top_categories(df["secteur"])

        fig = px.scatter_3d(
            df,
            x="score_adequation",
            y="score_reputation",
            z="score_contact",
            color="secteur_groupe",
            hover_name="nom_affiche" if "nom_affiche" in df.columns else None,
            labels={
                "score_adequation": "Adéquation",
                "score_reputation": "Réputation",
                "score_contact": "Contact",
                "secteur_groupe": "Secteur"
            },
            title=(
                "Adéquation, réputation et contact des entreprises "
                "(salaire / expérience non renseignés)"
            ),
            template=TEMPLATE
        )

        fig.update_layout(height=520)

        return fig

    return _empty("Données insuffisantes pour le nuage de points 3D")


# ------------------------------------------------------------
# Comparaisons
# ------------------------------------------------------------

def fig_barres_empilees(offers: pd.DataFrame) -> go.Figure:
    """Barres empilées : offres par secteur et par type de contrat."""

    if not _has(offers, ["secteur", "contrat"]):
        return _empty("Aucune offre disponible")

    df = pd.DataFrame({
        "secteur": _top_categories(offers["secteur"], n=10),
        "contrat": _top_categories(offers["contrat"], n=6)
    })

    grouped = (
        df.groupby(["secteur", "contrat"])
        .size()
        .reset_index(name="offres")
    )

    fig = px.bar(
        grouped,
        x="offres",
        y="secteur",
        color="contrat",
        orientation="h",
        barmode="stack",
        title="Offres par secteur et type de contrat",
        labels={
            "offres": "Nombre d'offres",
            "secteur": "Secteur",
            "contrat": "Contrat"
        },
        template=TEMPLATE
    )

    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        height=480
    )

    return fig


def fig_boxplot(
    companies: pd.DataFrame,
    offers: pd.DataFrame
) -> go.Figure:
    """Boîtes à moustaches : score par secteur (entreprises) et salaire par secteur (offres)."""

    has_scores = _has(companies, ["score_global", "secteur"])
    has_salaries = (
        _has(offers, ["salaire_num", "secteur"])
        and _num(offers, "salaire_num").notna().sum() >= 3
    )

    if not has_scores and not has_salaries:
        return _empty("Aucun score ni salaire disponible")

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Score de pertinence par secteur",
            "Salaire (MAD) par secteur"
        )
    )

    if has_scores:
        df = companies.copy()
        df["groupe"] = _top_categories(df["secteur"])
        df["valeur"] = _num(df, "score_global")

        for name, sub in df.groupby("groupe"):
            fig.add_trace(
                go.Box(y=sub["valeur"], name=str(name), showlegend=False),
                row=1,
                col=1
            )

    if has_salaries:
        df = offers.copy()
        df["groupe"] = _top_categories(df["secteur"])
        df["valeur"] = _num(df, "salaire_num")
        df = df.dropna(subset=["valeur"])

        for name, sub in df.groupby("groupe"):
            fig.add_trace(
                go.Box(y=sub["valeur"], name=str(name), showlegend=False),
                row=1,
                col=2
            )
    else:
        fig.add_annotation(
            text="Salaires non renseignés",
            xref="x2 domain",
            yref="y2 domain",
            x=0.5,
            y=0.5,
            showarrow=False
        )

    fig.update_layout(
        template=TEMPLATE,
        height=480,
        title="Distribution des scores et des salaires par secteur"
    )

    return fig


def fig_violin(
    offers: pd.DataFrame,
    companies: pd.DataFrame | None = None
) -> go.Figure:
    """Violons par secteur : salaire, sinon expérience, sinon score de pertinence."""

    candidates = [
        ("salaire_num", "Salaire (MAD)", offers),
        ("experience_ans", "Expérience requise (ans)", offers),
        ("score_global", "Score de pertinence", companies)
    ]

    for column, label, source in candidates:

        if (
            _has(source, [column, "secteur"])
            and _num(source, column).notna().sum() >= 5
        ):
            df = source.copy()
            df["groupe"] = _top_categories(df["secteur"])
            df["valeur"] = _num(df, column)
            df = df.dropna(subset=["valeur"])

            fig = px.violin(
                df,
                x="groupe",
                y="valeur",
                color="groupe",
                box=True,
                points="outliers",
                labels={"groupe": "Secteur", "valeur": label},
                title=f"Distribution — {label} par secteur",
                template=TEMPLATE
            )

            fig.update_layout(showlegend=False, height=480)

            return fig

    return _empty("Pas assez de valeurs numériques pour les violons")


def fig_radar(priorities: pd.DataFrame, n: int = 5) -> go.Figure:
    """Radar des 5 sous-scores pour les entreprises prioritaires."""

    mapping = {
        "score_adequation": "Adéquation",
        "score_recrutement": "Recrutement",
        "score_reputation": "Réputation",
        "score_localisation": "Localisation",
        "score_contact": "Contact"
    }

    df = _safe_dataframe(priorities)

    columns = [column for column in mapping if column in df.columns]

    if df.empty or len(columns) < 3:
        return _empty("Sous-scores indisponibles pour le radar")

    df = _ensure_column(df, "nom_affiche", ["nom", "entreprise"], "Entreprise inconnue")

    labels = [mapping[column] for column in columns]

    fig = go.Figure()

    for _, row in df.head(n).iterrows():

        values = [
            float(pd.to_numeric(row[column], errors="coerce") or 0)
            for column in columns
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values + values[:1],
                theta=labels + labels[:1],
                fill="toself",
                opacity=0.55,
                name=str(row["nom_affiche"])
            )
        )

    fig.update_layout(
        title=f"Profil des {min(n, len(df))} entreprises prioritaires",
        template=TEMPLATE,
        polar={"radialaxis": {"visible": True, "range": [0, 100]}},
        height=480
    )

    return fig


# ------------------------------------------------------------
# Structure et flux
# ------------------------------------------------------------

def _offers_by_company_sector(offers: pd.DataFrame, extra=None, top: int = 40):
    """Compte les offres par secteur / entreprise (/ colonne supplémentaire)."""

    keys = ["secteur", "entreprise_nom"] + ([extra] if extra else [])

    grouped = (
        offers.groupby(keys)
        .size()
        .reset_index(name="offres")
    )

    best = (
        grouped.groupby("entreprise_nom")["offres"]
        .sum()
        .nlargest(top)
        .index
    )

    return grouped[grouped["entreprise_nom"].isin(best)]


def fig_treemap(offers: pd.DataFrame) -> go.Figure:
    """Treemap : secteurs puis entreprises, selon le nombre d'offres."""

    if not _has(offers, ["secteur", "entreprise_nom"]):
        return _empty("Aucune offre disponible")

    grouped = _offers_by_company_sector(offers, top=40)

    fig = px.treemap(
        grouped,
        path=[px.Constant("Marché"), "secteur", "entreprise_nom"],
        values="offres",
        color="secteur",
        title="Secteurs et entreprises qui concentrent les offres",
        template=TEMPLATE
    )

    fig.update_layout(height=520, margin={"l": 10, "r": 10, "t": 50, "b": 10})

    return fig


def fig_sunburst(offers: pd.DataFrame) -> go.Figure:
    """Sunburst : secteur, entreprise, type de contrat."""

    if not _has(offers, ["secteur", "entreprise_nom", "contrat"]):
        return _empty("Aucune offre disponible")

    grouped = _offers_by_company_sector(offers, extra="contrat", top=25)

    fig = px.sunburst(
        grouped,
        path=["secteur", "entreprise_nom", "contrat"],
        values="offres",
        title="Structure du marché : secteur, entreprise, contrat",
        template=TEMPLATE
    )

    fig.update_layout(height=520, margin={"l": 10, "r": 10, "t": 50, "b": 10})

    return fig


def fig_sankey(
    offers: pd.DataFrame,
    tracking: pd.DataFrame | None = None
) -> go.Figure:
    """
    Sankey : secteur -> contrat -> statut de candidature.

    Le statut vient du suivi (par nom d'entreprise) ;
    sans candidature, les offres sont « Non postulé ».
    """

    if not _has(offers, ["secteur", "contrat", "entreprise_nom"]):
        return _empty("Aucune offre disponible")

    df = offers.copy()

    def key(value):
        return str(value).strip().casefold()

    status_by_company = {}

    track = _safe_dataframe(tracking)

    if not track.empty:

        company_column = next(
            (
                column for column in
                ["entreprise", "nom_entreprise", "company", "nom_affiche", "nom"]
                if column in track.columns
            ),
            None
        )

        status_column = next(
            (
                column for column in ["statut", "statut_suivi"]
                if column in track.columns
            ),
            None
        )

        if company_column and status_column:
            for company, status in zip(
                track[company_column],
                track[status_column]
            ):
                if pd.notna(company) and pd.notna(status):
                    status_by_company[key(company)] = str(status)

    df["secteur_g"] = _top_categories(df["secteur"], n=8)
    df["contrat_g"] = _top_categories(df["contrat"], n=5)
    df["statut"] = df["entreprise_nom"].map(
        lambda name: status_by_company.get(key(name), "Non postulé")
    )

    levels = ["secteur_g", "contrat_g", "statut"]

    nodes = []
    index = {}

    for level in levels:
        for value in df[level].unique():
            index[(level, value)] = len(nodes)
            nodes.append(str(value))

    sources, targets, values = [], [], []

    for left, right in zip(levels[:-1], levels[1:]):
        for (a, b), count in df.groupby([left, right]).size().items():
            sources.append(index[(left, a)])
            targets.append(index[(right, b)])
            values.append(int(count))

    fig = go.Figure(
        go.Sankey(
            node={"label": nodes, "pad": 15, "thickness": 16},
            link={"source": sources, "target": targets, "value": values}
        )
    )

    fig.update_layout(
        title="Flux des offres : secteur → contrat → statut de candidature",
        template=TEMPLATE,
        height=520
    )

    return fig


def fig_mosaique(
    offers: pd.DataFrame,
    ligne: str = "secteur",
    colonne: str = "contrat"
) -> go.Figure:
    """Mosaïque : largeur = poids de la catégorie en colonne, hauteur = répartition interne."""

    if not _has(offers, [ligne, colonne]):
        return _empty("Aucune offre disponible")

    a = _top_categories(offers[ligne], n=6)
    b = _top_categories(offers[colonne], n=5)

    table = pd.crosstab(a, b)

    if table.empty:
        return _empty("Aucune offre disponible")

    totals = table.sum(axis=1)
    widths = totals / totals.sum()
    centers = widths.cumsum() - widths / 2

    labels = {
        "secteur": "secteur",
        "contrat": "contrat",
        "niveau_etudes": "niveau d'études",
        "ville": "ville"
    }

    fig = go.Figure()

    for category in table.columns:

        counts = table[category]

        fig.add_trace(
            go.Bar(
                x=centers.values,
                y=(counts / totals * 100).values,
                width=(widths * 0.97).values,
                name=str(category),
                text=[str(int(c)) if c > 0 else "" for c in counts.values],
                textposition="inside",
                customdata=list(table.index),
                hovertemplate=(
                    "%{customdata}<br>"
                    + str(category).replace("<", "")
                    + " : %{text}<extra></extra>"
                )
            )
        )

    fig.update_layout(
        barmode="stack",
        title=(
            f"Mosaïque {labels.get(ligne, ligne)} × "
            f"{labels.get(colonne, colonne)}"
        ),
        template=TEMPLATE,
        height=480,
        xaxis={
            "tickvals": list(centers.values),
            "ticktext": [
                f"{name}<br>({int(totals[name])})"
                for name in table.index
            ],
            "range": [0, 1],
            "title": f"{labels.get(ligne, ligne).capitalize()} (largeur = nombre d'offres)"
        },
        yaxis={"title": "Répartition (%)", "range": [0, 100]},
        legend_title_text=labels.get(colonne, colonne).capitalize()
    )

    return fig


def fig_parallel_sets(offers: pd.DataFrame) -> go.Figure:
    """Parallel sets : secteur, ville, contrat, niveau d'études."""

    if not _has(offers, ["secteur"]):
        return _empty("Aucune offre disponible")

    mapping = {
        "secteur": "Secteur",
        "ville": "Ville",
        "contrat": "Contrat",
        "niveau_etudes": "Niveau d'études"
    }

    df = pd.DataFrame(index=offers.index)
    dimensions = []

    for column, label in mapping.items():

        if column not in offers.columns:
            continue

        values = _top_categories(offers[column], n=6)

        if values.nunique() < 2:
            continue

        df[label] = values
        dimensions.append(label)

    if len(dimensions) < 2:
        return _empty("Pas assez de variables catégorielles variées")

    df["score"] = _num(offers, "score_entreprise").fillna(0)

    fig = px.parallel_categories(
        df,
        dimensions=dimensions,
        color="score",
        color_continuous_scale="Viridis",
        title="Combinaisons de catégories (parallel sets)",
        template=TEMPLATE
    )

    fig.update_layout(height=480, margin={"l": 60, "r": 60, "t": 80, "b": 20})

    return fig


def fig_dendrogramme(
    features: pd.DataFrame,
    meta: pd.DataFrame,
    top: int = 40
) -> go.Figure:
    """Dendrogramme (Ward) des entreprises les mieux classées."""

    try:
        import plotly.figure_factory as ff
        import scipy.cluster.hierarchy as hierarchy
    except ImportError:
        return _empty("scipy est requis pour le dendrogramme (pip install scipy)")

    if (
        not isinstance(features, pd.DataFrame)
        or not isinstance(meta, pd.DataFrame)
        or len(features) < 3
        or features.shape[1] < 2
    ):
        return _empty("Données insuffisantes pour le dendrogramme")

    std = features.std(ddof=0).replace(0, 1)
    standardized = (features - features.mean()) / std

    selected = meta["score_global"].nlargest(top).index

    labels = list(meta.loc[selected, "entreprise"])

    fig = ff.create_dendrogram(
        standardized.loc[selected].values,
        orientation="left",
        labels=labels,
        linkagefun=lambda data: hierarchy.linkage(data, method="ward")
    )

    fig.update_layout(
        title=f"Dendrogramme des {len(labels)} entreprises les mieux classées",
        template=TEMPLATE,
        height=max(480, 18 * len(labels))
    )

    return fig


# ------------------------------------------------------------
# Calendrier
# ------------------------------------------------------------

def fig_calendrier(offers: pd.DataFrame) -> go.Figure:
    """Calendar heatmap : nombre d'offres par jour de semaine et par semaine."""

    if not _has(offers, ["date_pub"]):
        return _empty("Aucune date de publication disponible")

    dates = pd.to_datetime(offers["date_pub"], errors="coerce").dropna()

    if dates.empty:
        return _empty("Aucune date de publication exploitable")

    days = dates.dt.normalize()
    weekday = days.dt.weekday
    week_start = days - pd.to_timedelta(weekday, unit="D")

    counts = (
        pd.DataFrame({"semaine": week_start, "jour": weekday})
        .groupby(["jour", "semaine"])
        .size()
        .unstack(fill_value=0)
        .reindex(range(7), fill_value=0)
    )

    fig = go.Figure(
        go.Heatmap(
            z=counts.values,
            x=counts.columns,
            y=["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
            colorscale="Greens",
            xgap=3,
            ygap=3,
            colorbar={"title": "Offres"},
            hovertemplate=(
                "Semaine du %{x|%d/%m/%Y}<br>%{y} : %{z} offre(s)"
                "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title="Calendrier des publications d'offres",
        template=TEMPLATE,
        height=380,
        yaxis={"autorange": "reversed"},
        xaxis={"title": "Semaine"}
    )

    return fig


# ============================================================
# 13. EXPORT DES GRAPHIQUES EN HTML
# ============================================================

def save_dashboard(
    figures: dict[str, go.Figure | None],
    out_dir: Path,
    insights: list[str] | None = None
) -> Path:
    """
    Enregistre :
        - Un fichier HTML par graphique
        - Un dashboard.html regroupant les graphiques
    """

    out_dir = Path(out_dir)

    out_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    parts = []
    first = True

    for name, fig in figures.items():

        if fig is None:
            continue

        # Export individuel
        fig.write_html(
            out_dir / f"{name}.html",
            include_plotlyjs="cdn"
        )

        # Intégration dans le dashboard
        parts.append(
            fig.to_html(
                full_html=False,
                include_plotlyjs="cdn" if first else False
            )
        )

        first = False

    # Préparation des observations
    bullets = "".join(
        f"<li>{escape(str(message))}</li>"
        for message in (insights or [])
    )

    html = (
        "<html>"
        "<head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Marrakech OpportunityHub</title>"
        "</head>"
        "<body style='font-family:Arial,sans-serif;"
        "max-width:1200px;margin:30px auto;padding:20px'>"
        "<h1>Marrakech OpportunityHub</h1>"
        "<h2>Tableau de bord analytique</h2>"
        "<h3>À retenir</h3>"
        f"<ul>{bullets}</ul>"
        + "".join(parts)
        + "</body></html>"
    )

    path = out_dir / "dashboard.html"

    path.write_text(
        html,
        encoding="utf-8"
    )

    return path