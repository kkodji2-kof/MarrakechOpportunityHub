from __future__ import annotations
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, quote_plus
import pandas as pd
import streamlit as st


PER_PAGE = 10
CLEAN_DIR = Path("stages_marrakech/data/clean")
COMPANIES_FILE = CLEAN_DIR / "entreprises_nettoyees.csv"
TRACKING_DIR = Path("stages_marrakech/data/tracking")
APPLIED_FILE = TRACKING_DIR / "entreprises_postulees.csv"
CAREER_COLUMNS = ["lien_carriere", "url_carriere", "page_carriere", "lien_postuler", "url_offre", "Lien_Annonce"]
EMPTY_STRINGS = {"", "nan", "none", "n/a", "na", "null", "nat", "-", "aucun", "non renseigné"}
NOTE_MIN, NOTE_MAX = 0.0, 5.0  # une note Google valide est comprise entre 0 et 5

CSS = """
<style>
/* Remonte le contenu de la page */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 1rem;
}
header[data-testid="stHeader"] {
    background: transparent;
    height: 2.5rem;
}
.block-container h1 {
    padding-top: 0 !important;
    margin-top: 0 !important;
    font-size: 2.2rem;
    line-height: 1.2;
}
/* Citation en haut à droite */
.motto-right {
    text-align: right;
    font-style: italic;
    font-weight: 700;
    font-size: 1.1rem;
    padding-top: 0.5rem;
    background: linear-gradient(135deg, #6366f1, #ec4899);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}

.ent-nom    { font-size: 1.3rem; font-weight: 800; line-height: 1.25; margin: 0; }
.ent-sect   { color: #6b7280; font-size: 1rem; margin-top: .15rem; }
.ent-avatar {
    width: 64px; height: 64px; border-radius: 16px;
    background: linear-gradient(135deg, #dbe7ff, #c7d8ff);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 1.6rem; color: #1e40af;
}
.ent-chips { display: flex; flex-wrap: wrap; gap: .5rem; margin: .7rem 0 .2rem 0; }
.ent-chip  {
    background: rgba(128,128,128,.13); border-radius: 999px;
    padding: .4rem .9rem; font-size: .95rem; font-weight: 600;
}
.ent-note  { background: #fef3c7; color: #92400e; }
.ent-ok    { background: #dcfce7; color: #166534; }
a.ent-btn {
    display: block; text-align: center; text-decoration: none !important;
    font-weight: 700; font-size: .98rem; padding: .55rem .9rem;
    border-radius: 12px; transition: filter .15s ease; white-space: nowrap;
}
a.ent-btn:hover { filter: brightness(.93); }
a.ent-postuler { background: #2563eb; color: #ffffff !important; box-shadow: 0 3px 8px rgba(37,99,235,.3); }
a.ent-email    { background: rgba(220,38,38,.09); color: #dc2626 !important; border: 1px solid rgba(220,38,38,.3); }
a.ent-loc      { color: #2563eb !important; background: transparent; }
</style>
"""


def has_val(value) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() not in EMPTY_STRINGS


def get_val(row, col):
    value = row.get(col)
    return str(value).strip() if has_val(value) else None


def esc(text) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_safe(text: str) -> str:
    """Échappe les caractères qui casseraient le texte d'un lien Markdown."""
    return str(text).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def md_url(url: str) -> str:
    """Nettoie une URL pour la mettre entre parenthèses dans un lien Markdown."""
    return str(url).strip().replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def ensure_http(url: str) -> str:
    return url if url.lower().startswith(("http://", "https://")) else f"https://{url}"


def get_career_url(row) -> str | None:
    for col in CAREER_COLUMNS:
        value = get_val(row, col)
        if value:
            return ensure_http(value)
    site = get_val(row, "site_web")
    return ensure_http(site) if site else None


def get_maps_url(row) -> str:
    maps = get_val(row, "google_maps")
    if maps and maps.lower().startswith("http"):
        return maps
    query = " ".join(filter(None, [get_val(row, "nom"), get_val(row, "adresse"), "Marrakech"]))
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def phone_href(phone: str) -> str:
    return "tel:" + "".join(ch for ch in phone if ch.isdigit() or ch == "+")


def valid_note(value) -> float | None:
    """Retourne la note si elle est valide (entre 0 et 5), sinon None."""
    try:
        note = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(note) or not (NOTE_MIN <= note <= NOTE_MAX):
        return None
    return note


@st.cache_data
def load_companies(path):
    return pd.read_csv(path)


def go_page(page: int) -> None:
    st.session_state["entreprises_page"] = page


def page_window(page: int, total: int, size: int = 5) -> list[int]:
    first = max(1, min(page - size // 2, total - size + 1))
    return list(range(first, min(total, first + size - 1) + 1))


st.markdown(CSS, unsafe_allow_html=True)

# ── En-tête : titre à gauche, citation à droite ──
col_titre, col_motto = st.columns([3, 1.2])
with col_titre:
    st.title("Répertoire des Entreprises - Marrakech")
    st.markdown("Explorez le répertoire unifié des entreprises cibles (IA, Tech, ESN, Agences web) à Marrakech.")
with col_motto:
    st.markdown("<div class='motto-right'>« L'effort fait le génie »</div>", unsafe_allow_html=True)

if not COMPANIES_FILE.exists():
    st.warning("Aucun fichier d'entreprises nettoyées trouvé. Veuillez exécuter le pipeline via la barre latérale.")
else:
    try:
        df_companies = load_companies(COMPANIES_FILE)
    except Exception as e:
        st.error(f"Erreur lors du chargement : {e}")
        st.stop()

    if df_companies.empty:
        st.info("Aucune entreprise disponible.")
    else:
        # ── Filtres dans la page (plus dans la barre latérale) ──
        f1, f2 = st.columns(2)
        if "pertinence" in df_companies.columns:
            pertinences = ["Toutes"] + sorted(df_companies["pertinence"].dropna().unique().tolist())
            with f1:
                sel_pert = st.selectbox("Pertinence", pertinences, key="ent_filtre_pertinence")
            if sel_pert != "Toutes":
                df_companies = df_companies[df_companies["pertinence"] == sel_pert]

        if "secteur" in df_companies.columns:
            secteurs = ["Tous"] + sorted(df_companies["secteur"].dropna().unique().tolist())
            with f2:
                sel_secteur = st.selectbox("Secteur", secteurs, key="ent_filtre_secteur")
            if sel_secteur != "Tous":
                df_companies = df_companies[df_companies["secteur"] == sel_secteur]

        # ── Métriques clés : seules les notes valides (0 à 5) sont prises en compte ──
        if "note" in df_companies.columns:
            notes_numeriques = pd.to_numeric(df_companies["note"], errors="coerce")
            notes_numeriques = notes_numeriques[
                (notes_numeriques >= NOTE_MIN) & (notes_numeriques <= NOTE_MAX)
            ].dropna()
            moyenne_notes = notes_numeriques.mean() if not notes_numeriques.empty else float("nan")
        else:
            moyenne_notes = float("nan")

        col1, col2, col3 = st.columns(3)
        col1.metric("Entreprises affichées", len(df_companies))
        col2.metric(
            "Note moyenne",
            f"{moyenne_notes:.2f} ⭐"
            if not pd.isna(moyenne_notes)
            else "N/A",
        )
        col3.metric(
            "Emails valides",
            int((df_companies["statut_email"] == "Validé").sum()) if "statut_email" in df_companies.columns else 0,
        )

        st.markdown("---")
        st.subheader("Liste détaillée")

        if df_companies.empty:
            st.info("Aucune entreprise ne correspond à vos filtres.")
            st.stop()

        # ── Pagination ──
        total_pages = max(1, -(-len(df_companies) // PER_PAGE))
        page = min(max(1, int(st.session_state.get("entreprises_page", 1))), total_pages)
        st.session_state["entreprises_page"] = page
        start = (page - 1) * PER_PAGE
        page_rows = df_companies.iloc[start:start + PER_PAGE]

        # ── Cartes d'entreprises ──
        for pos, (_, row) in enumerate(page_rows.iterrows()):
            nom = get_val(row, "nom") or "Entreprise"
            secteur = get_val(row, "secteur")
            adresse = get_val(row, "adresse")
            telephone = get_val(row, "telephone")
            email = get_val(row, "email_principal")
            site = get_val(row, "site_web")
            career_url = get_career_url(row)

            with st.container(border=True):
                # En-tête : avatar + nom + secteur
                h_av, h_txt = st.columns([1, 7])
                with h_av:
                    st.markdown(f"<div class='ent-avatar'>{esc(nom[:1].upper())}</div>", unsafe_allow_html=True)
                with h_txt:
                    html = f"<p class='ent-nom'>{esc(nom)}</p>"
                    if secteur:
                        html += f"<p class='ent-sect'>{esc(secteur)}</p>"
                    st.markdown(html, unsafe_allow_html=True)

                # Pastilles : note, pertinence, email validé, adresse
                chips = []
                note = valid_note(row.get("note"))
                if note is not None:
                    label = f"⭐ {note:.1f}"
                    avis = row.get("nombre_avis")
                    if has_val(avis):
                        try:
                            label += f" ({int(float(avis))} avis)"
                        except (TypeError, ValueError):
                            pass
                    chips.append(f"<span class='ent-chip ent-note'>{esc(label)}</span>")
                if get_val(row, "pertinence"):
                    chips.append(f"<span class='ent-chip'>{esc(get_val(row, 'pertinence'))}</span>")
                if get_val(row, "statut_email") == "Validé":
                    chips.append("<span class='ent-chip ent-ok'>Email validé</span>")
                if chips:
                    st.markdown(f"<div class='ent-chips'>{''.join(chips)}</div>", unsafe_allow_html=True)
                if adresse:
                    st.markdown(f"<div class='ent-chips'><span class='ent-chip'>{esc(adresse)}</span></div>",
                                unsafe_allow_html=True)

                # Contact : téléphone · site web · e-mail
                parts = []
                if telephone:
                    parts.append(f"📞 [{md_safe(telephone)}]({phone_href(telephone)})")
                if site:
                    parts.append(f"🌐 [Site web]({md_url(ensure_http(site))})")
                if email:
                    parts.append(f"✉️ [{md_safe(email)}](mailto:{md_url(email)})")
                if parts:
                    st.markdown(" · ".join(parts))

                # Boutons d'action
                b1, b2, b3 = st.columns([1, 1.5, 1.1])
                with b1:
                    if career_url:
                        st.markdown(
                            f"<a class='ent-btn ent-postuler' href='{esc(career_url)}' "
                            "target='_blank' rel='noopener noreferrer'>↗ Postuler</a>",
                            unsafe_allow_html=True,
                        )
                with b2:
                    if email:
                        subject = quote("Candidature spontanée - Stage")
                        st.markdown(
                            f"<a class='ent-btn ent-email' href='mailto:{esc(email)}?subject={subject}'>"
                            "✉ Contacter par email</a>",
                            unsafe_allow_html=True,
                        )
                with b3:
                    st.markdown(
                        f"<a class='ent-btn ent-loc' href='{esc(get_maps_url(row))}' "
                        "target='_blank' rel='noopener noreferrer'>🗺 Localisation</a>",
                        unsafe_allow_html=True,
                    )

        # ── Sous-pages : pagination en bas de la liste ──
        if total_pages > 1:
            st.markdown("---")
            window = page_window(page, total_pages)
            nav = st.columns([1.4] + [0.6] * len(window) + [1.4])
            with nav[0]:
                st.button("← Précédent", key="ent_prev", disabled=page <= 1,
                          on_click=go_page, args=(page - 1,), use_container_width=True)
            for col, p in zip(nav[1:-1], window):
                with col:
                    st.button(str(p), key=f"ent_pg_{p}", type="primary" if p == page else "secondary",
                              on_click=go_page, args=(p,), use_container_width=True)
            with nav[-1]:
                st.button("Suivant →", key="ent_next", disabled=page >= total_pages,
                          on_click=go_page, args=(page + 1,), use_container_width=True)
            st.caption(f"Page {page} sur {total_pages}")