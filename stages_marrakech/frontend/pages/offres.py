import html
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote_plus
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Marrakech Opportunity Hub - Offres", layout="wide")

# --------------------------------------------------------------------------- #
# Réglages (chemins élargis pour éviter les erreurs de localisation du CSV)
# --------------------------------------------------------------------------- #
DOSSIERS_DONNEES = [
    Path("data"), 
    Path("data/raw"), 
    Path("stages_marrakech/data"), 
    Path("stages_marrakech/data/raw"), 
    Path(".")
]
MOTIF_FICHIER = "offres_*.csv"
OFFRES_PAR_PAGE = 10
QUARTIER_INCONNU = "Non précisé"

COLONNES_CSV = [
    "source", "titre", "entreprise", "ville", "contrat", "niveau_etudes", "experience",
    "salaire", "date_publication", "date_limite", "description", "lien", "date_collecte",
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
DATE_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

# --------------------------------------------------------------------------- #
# Style (design d'origine conservé)
# --------------------------------------------------------------------------- #
st.markdown("""
<style>
    /* --- REMONTE LE CONTENU EN HAUT DE LA PAGE --- */
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
    }

    /* --- CARTES D'OFFRES --- */
    .job-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .company-header { display: flex; align-items: center; margin-bottom: 16px; }
    .company-logo {
        width: 50px; height: 50px; background-color: #eff6ff; color: #2563eb;
        font-weight: 700; font-size: 22px; display: flex; align-items: center;
        justify-content: center; border-radius: 10px; margin-right: 16px; flex-shrink: 0;
    }
    .company-info h3 { margin: 0; font-size: 18px; color: #111827; font-weight: 600; }
    .company-info p { margin: 4px 0 0 0; font-size: 14px; color: #6b7280; }
    .badge-container { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
    .badge {
        background-color: #f3f4f6; padding: 6px 12px; border-radius: 20px;
        font-size: 13px; color: #4b5563; font-weight: 500;
    }
    .badge-limite { background-color: #fef3c7; color: #92400e; }
    .job-snippet { font-size: 15px; color: #374151; margin-bottom: 20px; line-height: 1.6; }
    .job-full { font-size: 15px; line-height: 1.7; }

    /* --- STYLE DES BOUTONS --- */
    .btn-postuler a {
        background-color: #2563eb !important; color: #ffffff !important; border: none !important;
        border-radius: 8px !important; font-weight: 600 !important; padding: 10px 20px !important;
        text-align: center; display: block; text-decoration: none;
    }
    .btn-postuler a:hover { background-color: #1d4ed8 !important; color: white !important; }

    .btn-contacter a {
        background-color: #f3f4f6 !important; color: #374151 !important;
        border: 1px solid #e5e7eb !important; border-radius: 8px !important;
        font-weight: 600 !important; padding: 10px 20px !important; text-align: center;
        display: block; text-decoration: none;
    }
    .btn-contacter a:hover { background-color: #e5e7eb !important; color: #111827 !important; }

    .btn-localisation a {
        background-color: #eff6ff !important; color: #2563eb !important; border: none !important;
        border-radius: 8px !important; font-weight: 600 !important; padding: 10px 20px !important;
        text-align: center; display: block; text-decoration: none;
    }
    .btn-localisation a:hover { background-color: #dbeafe !important; }

    .bouton-retour-container { margin-bottom: 20px; }
    .bouton-retour-container button {
        background-color: #1e3a8a !important; color: #ffffff !important; border: none !important;
        border-radius: 8px !important; font-weight: 600 !important; padding: 10px 24px !important;
        transition: all 0.2s ease;
    }
    .bouton-retour-container button:hover { background-color: #172554 !important; }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def esc(valeur):
    """Échappe le texte venant du scraping avant de l'injecter dans du HTML."""
    return html.escape(str(valeur or ""), quote=True)


def normaliser(texte):
    t = unicodedata.normalize("NFKD", str(texte or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def separer_ville(valeur):
    """'Guéliz, Marrakech' -> ('Guéliz', 'Marrakech') ; 'Marrakech' -> ('Non précisé', 'Marrakech')."""
    parties = [p.strip() for p in str(valeur or "").split(",") if p.strip()]
    if len(parties) >= 2:
        return parties[0], parties[-1]
    return QUARTIER_INCONNU, (parties[0] if parties else "")


def formater_date(valeur):
    """2026-10-01T11:45:12 -> 01/10/2026 ; les autres formats restent tels quels."""
    v = str(valeur or "").strip()
    m = DATE_ISO_RE.match(v)
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else v


def extraire_email(description):
    m = EMAIL_RE.search(str(description or ""))
    return m.group(0) if m else ""


def lien_valide(url):
    return str(url or "").startswith(("http://", "https://"))


def lien_carte(row):
    requete = ", ".join(
        p for p in [row["Entreprise"],
                    row["Quartier"] if row["Quartier"] != QUARTIER_INCONNU else "",
                    row["Ville"] or "Marrakech", "Morocco"] if p)
    return requete, f"https://www.google.com/maps/search/?api=1&query={quote_plus(requete)}"


# --------------------------------------------------------------------------- #
# Chargement et préparation des données
# --------------------------------------------------------------------------- #
def preparer(brut):
    """CSV du scraper -> DataFrame au format de la page (Titre, Entreprise, Quartier, ...)."""
    df = brut.copy()
    for col in COLONNES_CSV:
        if col not in df.columns:
            df[col] = ""
    df = df[COLONNES_CSV].fillna("").astype(str)
    df = df[df["titre"].str.strip() != ""]
    avec_lien = df["lien"].str.strip() != ""
    df = pd.concat([df[avec_lien].drop_duplicates(subset="lien"), df[~avec_lien]]).sort_index()
    df = df.reset_index(drop=True)

    quartiers, villes = zip(*df["ville"].map(separer_ville)) if len(df) else ((), ())
    publie = df["date_publication"].str.strip() != ""
    date_aff = [
        (f"Publiée : {formater_date(p)}" if a else f"Collectée : {c[:10]}")
        for p, c, a in zip(df["date_publication"], df["date_collecte"], publie)
    ]
    return pd.DataFrame({
        "id": range(len(df)),
        "Titre": df["titre"].str.strip(),
        "Entreprise": df["entreprise"].str.strip(),
        "Ville": list(villes),
        "Quartier": list(quartiers),
        "Source": df["source"].str.strip(),
        "Contrat": df["contrat"].str.strip(),
        "Niveau": df["niveau_etudes"].str.strip(),
        "Experience": df["experience"].str.strip(),
        "Salaire": df["salaire"].str.strip(),
        "Date": date_aff,
        "DateLimite": df["date_limite"].map(formater_date),
        "DateCollecte": df["date_collecte"].str.strip(),
        "Description": df["description"].str.strip(),
        "Email": df["description"].map(extraire_email),
        "Lien": df["lien"].str.strip(),
    })


def dernier_csv():
    candidats = []
    for dossier in DOSSIERS_DONNEES:
        if dossier.is_dir():
            candidats += list(dossier.glob(MOTIF_FICHIER))
    return max(candidats, key=lambda p: p.stat().st_mtime) if candidats else None


def stocker(df, etiquette, signature):
    st.session_state.offres_df = df
    st.session_state.offres_label = etiquette
    st.session_state.offres_sig = signature
    st.session_state.selected_job_id = None
    st.session_state.page_offres = 1


def assurer_donnees():
    """Garantit qu'un DataFrame est en session en chargeant le dernier CSV du dossier."""
    if "offres_df" not in st.session_state:
        chemin = dernier_csv()
        if chemin is None:
            st.title("Marrakech Opportunity Hub - Offres & Stages")
            st.info("Aucun fichier `offres_*.csv` trouvé dans les dossiers de données. "
                    "Veuillez placer le CSV du scraper dans `data/raw/`.")
            st.stop()
        brut = pd.read_csv(chemin, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        stocker(preparer(brut), chemin.name, ("disque", str(chemin), chemin.stat().st_mtime))

    if "offres_df" not in st.session_state:
        st.stop()
    return st.session_state.offres_df


# --------------------------------------------------------------------------- #
# Vue détail
# --------------------------------------------------------------------------- #
def vue_detail(df, job_id):
    sel = df[df["id"] == job_id]
    if sel.empty:
        st.session_state.selected_job_id = None
        st.rerun()
    row = sel.iloc[0]

    st.markdown('<div class="bouton-retour-container">', unsafe_allow_html=True)
    if st.button("Retour aux offres"):
        st.session_state.selected_job_id = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    lieu = ", ".join(p for p in [row["Quartier"] if row["Quartier"] != QUARTIER_INCONNU else "",
                                row["Ville"]] if p)
    st.title(row["Titre"])
    st.subheader(" — ".join(p for p in [row["Entreprise"] or "Entreprise non précisée", lieu] if p))
    st.markdown("---")

    st.markdown("### Description de l'offre")
    if row["Description"]:
        st.markdown(f'<div class="job-full">{esc(row["Description"])}</div>', unsafe_allow_html=True)
    else:
        st.write("Aucune description n'a pu être extraite. Consulte l'annonce d'origine.")
    st.markdown("---")

    st.markdown("### Informations complémentaires")
    infos = [
        ("Source", row["Source"]),
        ("Publication", row["Date"]),
        ("Date limite", row["DateLimite"]),
        ("Contrat", row["Contrat"]),
        ("Niveau d'études", row["Niveau"]),
        ("Expérience", row["Experience"]),
        ("Salaire", row["Salaire"]),
        ("Collectée le", row["DateCollecte"]),
        ("Contact", f"`{row['Email']}`" if row["Email"] else ""),
    ]
    infos = [(k, v) for k, v in infos if v]
    for debut in range(0, len(infos), 3):
        for col, (cle, valeur) in zip(st.columns(3), infos[debut:debut + 3]):
            col.markdown(f"**{cle} :** {valeur}" if cle == "Contact" else f"**{cle} :** {esc(valeur)}",
                         unsafe_allow_html=cle != "Contact")

    if lien_valide(row["Lien"]):
        st.markdown(f'<div class="btn-postuler"><a href="{esc(row["Lien"])}" target="_blank" rel="noopener">'
                    f'Postuler sur le site d\'origine</a></div>', unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("### Localisation de l'entreprise (Google Maps)")
    requete, url_carte = lien_carte(row)
    st.markdown(f'<div class="btn-localisation"><a href="{esc(url_carte)}" target="_blank" rel="noopener">'
                f' Ouvrir dans Google Maps</a></div>', unsafe_allow_html=True)
    iframe_src = f"https://maps.google.com/maps?q={quote_plus(requete)}&t=&z=15&ie=UTF8&iwloc=&output=embed"
    if hasattr(st, "iframe"):
        st.iframe(iframe_src, height=450)
    else:
        st.components.v1.iframe(iframe_src, height=450, scrolling=True)


# --------------------------------------------------------------------------- #
# Vue liste
# --------------------------------------------------------------------------- #
def carte_offre(row):
    nom = row["Entreprise"] or "Entreprise non précisée"
    initiale = (row["Entreprise"][:1] or "?").upper()
    lieu = ", ".join(p for p in [row["Quartier"] if row["Quartier"] != QUARTIER_INCONNU else "",
                                row["Ville"]] if p)
    badges = []
    if row["Quartier"] != QUARTIER_INCONNU:
        badges.append(f'<div class="badge"> {esc(row["Quartier"])}</div>')
    badges.append(f'<div class="badge">{esc(row["Source"])}</div>')
    if row["Contrat"]:
        badges.append(f'<div class="badge">{esc(row["Contrat"])}</div>')
    if row["Experience"]:
        badges.append(f'<div class="badge">{esc(row["Experience"])}</div>')
    badges.append(f'<div class="badge"> {esc(row["Date"])}</div>')
    if row["DateLimite"]:
        badges.append(f'<div class="badge badge-limite"> Limite : {esc(row["DateLimite"])}</div>')

    extrait = row["Description"][:230] + ("..." if len(row["Description"]) > 230 else "")
    st.markdown(f"""
    <div class="job-card">
        <div class="company-header">
            <div class="company-logo">{esc(initiale)}</div>
            <div class="company-info">
                <h3>{esc(row['Titre'])}</h3>
                <p>{esc(nom)}{' • ' + esc(lieu) if lieu else ''}</p>
            </div>
        </div>
        <div class="badge-container">{''.join(badges)}</div>
        <div class="job-snippet">{esc(extrait)}</div>
    </div>
    """, unsafe_allow_html=True)

    _, url_carte = lien_carte(row)
    b1, b2, b3, b4 = st.columns([1.2, 1.2, 1.2, 1])
    with b1:
        if lien_valide(row["Lien"]):
            st.markdown(f'<div class="btn-postuler"><a href="{esc(row["Lien"])}" target="_blank" '
                        f'rel="noopener">Postuler</a></div>', unsafe_allow_html=True)
    with b2:
        if row["Email"]:
            st.markdown(f'<div class="btn-contacter"><a href="mailto:{esc(row["Email"])}">Contacter</a></div>',
                        unsafe_allow_html=True)
    with b3:
        st.markdown(f'<div class="btn-localisation"><a href="{esc(url_carte)}" target="_blank" '
                    f'rel="noopener">Localisation</a></div>', unsafe_allow_html=True)
    with b4:
        if st.button("Détails", key=f"btn_details_{row['id']}", use_container_width=True):
            st.session_state.selected_job_id = row["id"]
            st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)


def vue_liste(df):
    st.title("Marrakech Opportunity Hub - Offres & Stages")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        recherche = st.text_input("Rechercher un poste ou mot-clé", "")
    with c2:
        quartier_filtre = st.selectbox("Quartier", ["Tous"] + sorted(df["Quartier"].unique()))
    with c3:
        source_filtre = st.selectbox("Source", ["Toutes"] + sorted(s for s in df["Source"].unique() if s))
    with c4:
        contrat_filtre = st.selectbox("Contrat", ["Tous"] + sorted(c for c in df["Contrat"].unique() if c))
    
    # value=False pour ne pas filtrer par défaut sur Marrakech
    seulement_marrakech = st.checkbox("Marrakech uniquement", value=False)

    filtre = df
    if seulement_marrakech:
        meule = (filtre["Ville"] + " " + filtre["Titre"] + " " + filtre["Description"]).map(normaliser)
        filtre = filtre[meule.str.contains("marrakech", na=False)]
    if recherche:
        filtre = filtre[filtre["Titre"].str.contains(recherche, case=False, na=False, regex=False) |
                        filtre["Description"].str.contains(recherche, case=False, na=False, regex=False) |
                        filtre["Entreprise"].str.contains(recherche, case=False, na=False, regex=False)]
    if quartier_filtre != "Tous":
        filtre = filtre[filtre["Quartier"] == quartier_filtre]
    if source_filtre != "Toutes":
        filtre = filtre[filtre["Source"] == source_filtre]
    if contrat_filtre != "Tous":
        filtre = filtre[filtre["Contrat"] == contrat_filtre]

    # retour à la page 1 quand un filtre change
    signature = (recherche, quartier_filtre, source_filtre, contrat_filtre, seulement_marrakech)
    if st.session_state.get("filtres_sig") != signature:
        st.session_state.filtres_sig = signature
        st.session_state.page_offres = 1

    m1, m2, m3 = st.columns(3)
    m1.metric("Offres", len(filtre))
    m2.metric("Entreprises", filtre["Entreprise"].replace("", pd.NA).nunique())
    m3.metric("Sources", filtre["Source"].nunique())
    st.markdown("---")

    if filtre.empty:
        st.info("Aucune offre ne correspond à ces filtres.")
        return

    nb_pages = max(1, -(-len(filtre) // OFFRES_PAR_PAGE))
    page = min(max(1, st.session_state.get("page_offres", 1)), nb_pages)
    st.session_state.page_offres = page
    
    debut = (page - 1) * OFFRES_PAR_PAGE
    
    for _, row in filtre.iloc[debut:debut + OFFRES_PAR_PAGE].iterrows():
        carte_offre(row)

    p1, p2, p3 = st.columns([1, 2, 1])
    with p1:
        if st.button("← Précédent", disabled=page <= 1, use_container_width=True):
            st.session_state.page_offres = page - 1
            st.rerun()
    with p2:
        st.markdown(f"<div style='text-align:center;padding-top:8px'>Page {page} / {nb_pages}</div>",
                    unsafe_allow_html=True)
    with p3:
        if st.button("Suivant →", disabled=page >= nb_pages, use_container_width=True):
            st.session_state.page_offres = page + 1
            st.rerun()


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #
selection = st.session_state.get("selected_job_id")
if selection is not None and "offres_df" in st.session_state:
    vue_detail(assurer_donnees(), selection)
else:
    vue_liste(assurer_donnees())