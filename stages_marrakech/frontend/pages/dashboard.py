from __future__ import annotations
import re
import unicodedata
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
from stages_marrakech.backend import analyze, tracking, visualize
from stages_marrakech.frontend import services, ui
from stages_marrakech.frontend.safe import require_data, safe_section



try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

# ----------------------------------------------------------------------------
# KPI : calcul robuste + affichage moderne sur une seule ligne
# ----------------------------------------------------------------------------
_TRUE_VALUES = {"true", "1", "oui", "yes", "vrai", "y", "valide", "validé"}


def _fmt(value: int) -> str:
    """Formate un entier avec séparateur de milliers (espace)."""
    return f"{int(value):,}".replace(",", " ")


def _kpi_lookup(tables: dict, *labels: str) -> int | None:
    df = tables.get("KPIs") if isinstance(tables, dict) else None
    if not isinstance(df, pd.DataFrame) or df.shape[1] < 2 or df.empty:
        return None
    mapping = dict(zip(df.iloc[:, 0].astype(str).str.strip(), df.iloc[:, 1]))
    for label in labels:
        if label in mapping:
            try:
                return int(float(mapping[label]))
            except (TypeError, ValueError):
                return None
    return None


def _tech_from_insights(lines: list[str]) -> int | None:
    for line in lines:
        text = str(line)
        if "secteurs" in text.lower() and "tech" in text.lower():
            m = re.search(r":\s*([\d\s\u202f\u00a0]+)\s*\.?\s*$", text)
            if m:
                digits = re.sub(r"\D", "", m.group(1))
                if digits:
                    return int(digits)
    return None


def _count_tech_targets(companies: pd.DataFrame) -> int | None:
    for col in companies.columns:
        name = str(col).lower()
        if "cible" in name and ("ia" in name or "tech" in name):
            s = companies[col]
            if s.dtype == bool:
                return int(s.sum())
            return int(s.astype(str).str.strip().str.lower().isin(_TRUE_VALUES).sum())
    for col in companies.columns:
        if "secteur" in str(col).lower():
            pattern = r"\b(?:ia|ai|data|tech|informatique|digital)\b"
            return int(
                companies[col].astype(str).str.lower().str.contains(pattern, regex=True, na=False).sum()
            )
    return None


def compute_kpis(
    companies: pd.DataFrame,
    offres: pd.DataFrame,
    due: pd.DataFrame,
    tables: dict,
    insight_lines: list[str],
) -> list[tuple[str, str, int]]:
    n_companies = _kpi_lookup(tables, "Entreprises")
    if n_companies is None:
        n_companies = len(companies)

    n_tech = _kpi_lookup(tables, "Entreprises cibles IA/Tech")
    if n_tech is None:
        n_tech = _count_tech_targets(companies) or 0

    n_sectors = _tech_from_insights(insight_lines)
    if n_sectors is None:
        n_sectors = _count_tech_targets(companies) or 0

    return [
        ("", "Entreprises", n_companies),
        ("", "Cibles IA/Tech", n_tech),
        ("", "Secteurs IA / Data / Tech", n_sectors),
        ("", "Offres totales", len(offres)),
        ("", "Postuler", len(due)),
    ]


KPI_CSS = """
<style>
.kpi-row {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 14px;
    margin: 0.5rem 0 1.5rem 0;
}
.kpi-card {
    position: relative;
    overflow: hidden;
    padding: 16px 18px 14px 18px;
    border-radius: 16px;
    background: var(--secondary-background-color, #f6f7fb);
    border: 1px solid rgba(128, 128, 128, 0.18);
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.kpi-card::before {
    content: "";
    position: absolute;
    left: 0; top: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--kpi-a), var(--kpi-b));
}
.kpi-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.12);
}
.kpi-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
}
.kpi-label {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    opacity: 0.65;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.kpi-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px; height: 34px;
    flex: 0 0 34px;
    border-radius: 10px;
    font-size: 1.05rem;
    background: linear-gradient(135deg, var(--kpi-a), var(--kpi-b));
    box-shadow: 0 3px 8px rgba(0, 0, 0, 0.18);
}
.kpi-value {
    font-size: 2.1rem;
    font-weight: 800;
    line-height: 1.1;
    background: linear-gradient(135deg, var(--kpi-a), var(--kpi-b));
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}
@media (max-width: 1100px) {
    .kpi-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
    .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
"""

KPI_COLORS = [
    ("#6366f1", "#8b5cf6"),
    ("#06b6d4", "#3b82f6"),
    ("#10b981", "#34d399"),
    ("#f59e0b", "#f97316"),
    ("#ec4899", "#f43f5e"),
]


def render_kpi_row(kpis: list[tuple[str, str, int]]) -> None:
    cards = []
    for i, (icon, label, value) in enumerate(kpis):
        a, b = KPI_COLORS[i % len(KPI_COLORS)]
        cards.append(
            f'<div class="kpi-card" style="--kpi-a:{a};--kpi-b:{b};">'
            f'<div class="kpi-top"><span class="kpi-label">{label}</span>'
            f'<span class="kpi-icon">{icon}</span></div>'
            f'<div class="kpi-value">{_fmt(value)}</div>'
            f"</div>"
        )
    html = KPI_CSS + '<div class="kpi-row">' + "".join(cards) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# En-tête : remonte le contenu + date/heure à droite
# ----------------------------------------------------------------------------
HEADER_CSS = """
<style>
/* Réduit l'espace vide en haut de la page */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 1rem;
}
header[data-testid="stHeader"] {
    background: transparent;
    height: 2.5rem;
}
/* Le titre ne rajoute pas d'espace au-dessus */
.block-container h1 {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
.datetime-right {
    text-align: right;
    font-weight: 600;
    font-size: 1.05rem;
    padding-top: 0.8rem;
    white-space: nowrap;
}
</style>
"""


def _now() -> datetime:
    """Heure de Marrakech si disponible, sinon heure locale de la machine."""
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("Africa/Casablanca"))
        except Exception:  # tzdata absent (Windows)
            pass
    return datetime.now()


def _datetime_html() -> str:
    now = _now()
    return f'<div class="datetime-right">{now.strftime("%d/%m/%Y à %H:%M")}</div>'


# Rafraîchissement automatique toutes les 30 s (Streamlit >= 1.37)
if hasattr(st, "fragment"):

    @st.fragment(run_every=30)
    def afficher_date() -> None:
        st.markdown(_datetime_html(), unsafe_allow_html=True)

else:

    def afficher_date() -> None:
        st.markdown(_datetime_html(), unsafe_allow_html=True)


NOM_CSV_OFFRES = "offres_reelles_marrakech.csv"

ALIAS_COLONNES = {
    "niveau_etude": "niveau_etudes",
    "niveau_d_etudes": "niveau_etudes",
    "niveau_d_etude": "niveau_etudes",
    "niveau_detudes": "niveau_etudes",
    "experience_requise": "experience",
    "annees_experience": "experience",
    "salaire_propose": "salaire",
    "salaire_mensuel": "salaire",
    "remuneration": "salaire",
    "societe": "entreprise",
    "company": "entreprise",
    "company_name": "entreprise",
    "nom_entreprise": "entreprise",
}


def _trouver_csv_offres():
    ici = Path(__file__).resolve().parent
    bases = [Path.cwd(), ici, *list(ici.parents)[:4]]
    sous_dossiers = ["", "data", "data/clean", "data/raw", "data/processed", "data/offres"]

    for base in bases:
        for sous_dossier in sous_dossiers:
            candidat = base / sous_dossier / NOM_CSV_OFFRES
            if candidat.is_file():
                return candidat
    return None


@st.cache_data(show_spinner=False)
def _lire_csv_offres(chemin: str, modifie: float) -> pd.DataFrame:
    df = None
    for encodage in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(chemin, sep=None, engine="python", encoding=encodage)
            break
        except UnicodeDecodeError:
            continue

    if df is None:
        return pd.DataFrame()

    renommer = {}
    for colonne in df.columns:
        texte = unicodedata.normalize("NFKD", str(colonne).strip().lower())
        texte = "".join(c for c in texte if not unicodedata.combining(c))
        cle = re.sub(r"[^a-z0-9]+", "_", texte).strip("_")
        cible = ALIAS_COLONNES.get(cle)
        if cible and cible not in df.columns:
            renommer[colonne] = cible

    return df.rename(columns=renommer)


CHART_H = 480


def _show(label, builder, key, height=CHART_H):
    with safe_section(label):
        fig = builder()
        if fig is not None:
            fig.update_layout(height=height)
        ui.show_figure(fig, key)


# ----------------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------------
st.markdown(HEADER_CSS, unsafe_allow_html=True)

col_titre, col_date = st.columns([4, 1])
with col_titre:
    st.title("Tableau de bord")
    st.caption("Exploration, qualité, visualisation et analytique des opportunités à Marrakech.")
with col_date:
    afficher_date()

data = require_data()
companies: pd.DataFrame = data["entreprises"]
offres: pd.DataFrame = data.get("offres", data.get("offres_fiables", pd.DataFrame()))
if offres is None:
    offres = pd.DataFrame()

tables = services.get_tables(companies, offres)
track = services.get_tracking()
due = tracking.relances_a_faire(track) if (track is not None and not track.empty) else pd.DataFrame()
scored_companies = analyze.compute_scores(companies, offres)
priorities = analyze.top_priorities(scored_companies, n=10, tech_only=False)
insight_lines = [str(x) for x in analyze.insights(scored_companies, priorities, due)]

# --- KPI --------------------------------------------------------------------
with safe_section("Chiffres clés"):
    render_kpi_row(compute_kpis(companies, offres, due, tables, insight_lines))

# --- Vue d'ensemble ---------------------------------------------------------
st.subheader("Vue d'ensemble")
left, right = st.columns(2)
with left:
    _show("Secteurs", lambda: visualize.fig_secteurs(tables["Par_secteur"]), "fig_secteurs")
with right:
    _show("Top priorités", lambda: visualize.fig_top_priorites(priorities), "fig_top")

# --- Scores et notes --------------------------------------------------------
st.subheader("Scores et notes")
left, right = st.columns(2)
with left:
    _show("Scores", lambda: visualize.fig_scores(companies), "fig_scores")
with right:
    _show("Notes", lambda: visualize.fig_notes(tables["Distribution_notes"]), "fig_notes")

# --- Analyses multivariées (Graphiques fonctionnels uniquement) ------------
st.subheader("Analyses multivariées détaillées")

offers_bulles = pd.DataFrame()
source_bulles = ""

with safe_section("Préparation des analyses multivariées"):
    companies_x = analyze.add_offer_counts(scored_companies, offres)
    offers_x = analyze.enrich_offers(offres, scored_companies)

    chemin_csv = _trouver_csv_offres()
    offres_reelles = (
        _lire_csv_offres(str(chemin_csv), chemin_csv.stat().st_mtime)
        if chemin_csv is not None
        else pd.DataFrame()
    )

    if not offres_reelles.empty:
        offers_bulles = offres_reelles.copy()
        source_bulles = f"Source : {NOM_CSV_OFFRES} ({len(offres_reelles)} offres réelles)."
    else:
        offers_bulles = offers_x
        source_bulles = f"{NOM_CSV_OFFRES} introuvable : offres de la page utilisées."

    try:
        feats, feats_meta = analyze.company_features(scored_companies, offres)
    except Exception:
        feats, feats_meta = pd.DataFrame(), pd.DataFrame()

st.markdown("##### Relations")
left, right = st.columns(2)
with left:
    _show("Bulles : expérience, formation et salaire", lambda: visualize.fig_bulles(offers_bulles), "ov_bulles", height=520)
    if source_bulles:
        st.caption(source_bulles)
with right:
    _show("Nuage 3D", lambda: visualize.fig_scatter3d(offers_x, companies_x), "ov_3d")

st.markdown("##### Comparaisons")
left, right = st.columns(2)
with left:
    _show("Barres empilées", lambda: visualize.fig_barres_empilees(offers_x), "ov_barres")
with right:
    _show("Boîtes à moustaches", lambda: visualize.fig_boxplot(companies_x, offers_x), "ov_box")

left, right = st.columns(2)
with left:
    _show("Violons", lambda: visualize.fig_violin(offers_x, companies_x), "ov_violin")
with right:
    _show("Radar", lambda: visualize.fig_radar(priorities), "ov_radar")

st.markdown("##### Structure et flux")
left, right = st.columns(2)
with left:
    _show("Treemap", lambda: visualize.fig_treemap(offers_x), "ov_treemap")
with right:
    _show("Sunburst", lambda: visualize.fig_sunburst(offers_x), "ov_sunburst")

left, right = st.columns(2)
with left:
    _show("Sankey", lambda: visualize.fig_sankey(offers_x, track), "ov_sankey")
with right:
    mosaic_var = st.selectbox(
        "Croiser le secteur avec",
        ["contrat", "niveau_etudes", "ville"],
        key="ov_mosaic_var",
    )
    _show("Mosaïque", lambda: visualize.fig_mosaique(offers_x, "secteur", mosaic_var), "ov_mosaic")

_show(
    "Dendrogramme",
    lambda: visualize.fig_dendrogramme(feats, feats_meta),
    "ov_dendro",
    height=max(CHART_H, 600),
)

# --- ACP et groupes ---------------------------------------------------------
st.subheader("ACP et groupes d'entreprises")

with safe_section("ACP et groupes"):
    multi = analyze.multivariate_analysis(
        scored_companies,
        offres,
        k=3,
    )

    if not multi["ACP_coordonnees"].empty:
        left, right = st.columns(2)
        with left:
            _show(
                "ACP",
                lambda: visualize.fig_acp_individus(multi["ACP_coordonnees"], multi["ACP_variance"]),
                "fig_multi_acp",
            )
        with right:
            _show(
                "Cercle des corrélations",
                lambda: visualize.fig_acp_cercle(multi["ACP_variables"], multi["ACP_variance"]),
                "fig_multi_cercle",
            )

        left, right = st.columns(2)
        with left:
            _show(
                "Matrice de corrélations",
                lambda: visualize.fig_correlations(multi["Correlations"]),
                "fig_multi_corr",
            )

# --- Qualité des données ----------------------------------------------------
st.subheader("Qualité des données")
with safe_section("Qualité des données"):
    quality_tables = data["qualite"]
    _show(
        "Complétude",
        lambda: visualize.fig_qualite(quality_tables["Completude_entreprises"]),
        "fig_qualite",
    )