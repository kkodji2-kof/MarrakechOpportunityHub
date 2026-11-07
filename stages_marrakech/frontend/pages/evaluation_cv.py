import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import pymupdf
import streamlit as st


# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Agent IA - Évaluation du CV",
    page_icon="",
    layout="wide"
)

# Remonte le contenu en haut de la page
st.markdown("""
<style>
    .block-container,
    [data-testid="stMainBlockContainer"],
    [data-testid="stAppViewBlockContainer"] {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    [data-testid="stHeader"] {
        background: transparent !important;
        height: 2.5rem !important;
    }
    .block-container h1,
    [data-testid="stMainBlockContainer"] h1 {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

BLEU = "#2563EB"
VERT = "#0D9488"

DOSSIERS_DONNEES = [
    Path("data"),
    Path("data/raw"),
    Path("stages_marrakech/data"),
    Path("stages_marrakech/data/raw"),
    Path("."),
]
MOTIF_FICHIER = "offres_*.csv"

# Seuils et pondérations de l'adéquation CV / offre
SEUIL_BON = 70
SEUIL_PARTIEL = 45
POIDS_COMPETENCES = 0.60
POIDS_EXPERIENCE = 0.25
POIDS_TITRE = 0.15

VERDICTS = {
    "bon": ("", "Correspond bien"),
    "partiel": ("", "Correspond partiellement"),
    "faible": ("", "Ne correspond pas"),
}


# =========================================================
# OUTILS DE TEXTE
# =========================================================

def normaliser(texte):
    """Minuscules, sans accents, apostrophes simplifiées."""
    t = unicodedata.normalize("NFKD", str(texte or "").lower().replace("’", "'"))
    return "".join(c for c in t if not unicodedata.combining(c))


def lien_valide(url):
    return str(url or "").startswith(("http://", "https://"))


# =========================================================
# DICTIONNAIRE DES COMPÉTENCES (alias sans accents)
# =========================================================

COMPETENCES = {
    "Python": ["python"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript"],
    "PHP": ["php"],
    "C++": ["c++"],
    "C#": ["c#", "csharp"],
    ".NET": [".net", "dotnet"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "sqlite", "sql server"],
    "MongoDB": ["mongodb", "mongo", "nosql"],
    "Flask": ["flask"],
    "Django": ["django"],
    "FastAPI": ["fastapi"],
    "Streamlit": ["streamlit"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "TensorFlow": ["tensorflow"],
    "Keras": ["keras"],
    "PyTorch": ["pytorch", "torch"],
    "Machine Learning": ["machine learning", "apprentissage automatique"],
    "Deep Learning": ["deep learning", "apprentissage profond"],
    "NLP": ["nlp", "traitement du langage naturel"],
    "Vision par ordinateur": ["computer vision", "vision par ordinateur", "opencv"],
    "Intelligence artificielle": ["intelligence artificielle", "artificial intelligence", "ia"],
    "IA générative": ["ia generative", "genai", "llm", "chatgpt", "openai", "langchain", "prompt engineering"],
    "Data Science": ["data science", "science des donnees", "data scientist"],
    "Analyse de données": ["analyse de donnees", "analyse des donnees", "data analysis",
                           "data analyst", "analyste de donnees", "data analyste"],
    "Visualisation de données": ["data visualisation", "data visualization", "visualisation de donnees",
                                 "dataviz", "matplotlib", "seaborn", "plotly"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau software", "tableau desktop"],
    "Excel": ["excel"],
    "ETL": ["etl", "talend", "pentaho"],
    "Data Warehouse": ["data warehouse", "datawarehouse", "entrepot de donnees"],
    "Big Data": ["big data", "spark", "hadoop"],
    "Git": ["git"],
    "GitHub": ["github"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Linux": ["linux"],
    "Cloud": ["aws", "azure", "gcp", "google cloud", "cloud"],
    "API": ["api", "apis", "api rest", "rest api", "restful"],
    "n8n": ["n8n"],
    "Automatisation": ["automatisation", "automation", "rpa", "zapier"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "React": ["react", "reactjs", "react.js"],
    "Angular": ["angular"],
    "Vue.js": ["vue.js", "vuejs", "vue js"],
    "Laravel": ["laravel"],
    "Spring Boot": ["spring boot", "spring"],
    "Cybersécurité": ["cybersecurite", "securite informatique", "pentest"],
    "Réseaux": ["reseaux", "reseau informatique", "cisco"],
    "Agile / Scrum": ["agile", "scrum", "kanban"],
    "Gestion de projet": ["gestion de projet", "gestion de projets", "project management", "chef de projet"],
    "Communication": ["communication"],
    "Travail d'équipe": ["travail d'equipe", "esprit d'equipe", "teamwork", "travail en equipe"],
    "Marketing digital": ["marketing digital", "seo", "community manager", "reseaux sociaux"],
    "Anglais": ["anglais", "english"],
}


def _motif(alias):
    return re.compile(
        r"(?<![a-z0-9+#])(?:" + "|".join(re.escape(a) for a in alias) + r")(?![a-z0-9+#])"
    )


MOTIFS_COMPETENCES = {nom: _motif(alias) for nom, alias in COMPETENCES.items()}


def extraire_competences(texte):
    """Liste des compétences du dictionnaire présentes dans le texte (ordre du dictionnaire)."""
    t = normaliser(texte)
    return [nom for nom, motif in MOTIFS_COMPETENCES.items() if motif.search(t)]


# Mots ignorés pour la comparaison par mots-clés
MOTS_VIDES = set("""
avec pour dans nous vous notre votre vos nos cette cela sont etre avoir faire plus tout tous tres entre sans sous chez
ainsi comme aussi mais dont leur leurs quand ils elles elle les des une aux par sur que qui quoi est ses son
stage stagiaire poste offre recherche recherchons recherche entreprise equipe missions mission profil candidat
candidature candidats experience experiences contrat cdi cdd marrakech maroc casablanca rabat homme femme
sera serez serait afin ainsi ceci toute toutes meme autres autre bien bonne bonnes bons niveau domaine
rejoindre rejoignez integrer integrez souhaitez souhaite disposez dispose maitrise maitriser connaissance connaissances
capacite capacites esprit sens rigueur autonomie travail travailler travaille
""".split())


def mots_cles(texte, limite=None):
    """Retourne une liste [(racine, mot_original)] triée par fréquence."""
    tokens = re.findall(r"[a-z0-9][a-z0-9+#]{3,}", normaliser(texte))
    compteur, original = Counter(), {}
    for token in tokens:
        if token in MOTS_VIDES or token.isdigit():
            continue
        racine = token.rstrip("s")
        compteur[racine] += 1
        original.setdefault(racine, token)
    resultat = [(racine, original[racine]) for racine, _ in compteur.most_common(limite)]
    return resultat


# =========================================================
# EXTRACTION DU TEXTE DU PDF
# =========================================================

def extraire_texte_pdf(fichier):
    """Extrait le texte d'un CV PDF."""

    texte_pages = []

    with pymupdf.open(
        stream=fichier.getvalue(),
        filetype="pdf"
    ) as document:

        for page in document:
            texte_pages.append(page.get_text("text"))

    return "\n".join(texte_pages).strip()


# =========================================================
# STRUCTURE DU CV : SECTIONS, EXPÉRIENCE
# =========================================================

SECTIONS = {
    "experience": ["experience", "experiences", "experience professionnelle", "experiences professionnelles",
                   "parcours professionnel", "stages", "stage", "emploi", "work experience",
                   "professional experience"],
    "projets": ["projet", "projets", "projets realises", "projets academiques", "realisations", "projects"],
    "formation": ["formation", "formations", "etudes", "parcours academique", "diplomes", "education", "cursus"],
    "competences": ["competences", "competences techniques", "skills", "technologies", "outils"],
    "langues": ["langues", "languages"],
    "certifications": ["certifications", "certification", "certificats"],
    "interets": ["centres d'interet", "interets", "loisirs", "hobbies"],
    "profil": ["profil", "profil professionnel", "a propos", "presentation", "resume",
               "objectif", "objectif professionnel"],
}


def decouper_sections(texte_cv):
    """Découpe le CV par rubriques à partir des titres reconnus (ligne seule)."""
    cle_par_titre = {t: k for k, titres in SECTIONS.items() for t in titres}
    sections = {k: [] for k in SECTIONS}
    courant = None
    for ligne in texte_cv.splitlines():
        propre = re.sub(r"[^a-z' ]", "", normaliser(ligne))
        propre = re.sub(r"\s+", " ", propre).strip()
        if propre and len(propre) <= 40 and propre in cle_par_titre:
            courant = cle_par_titre[propre]
            continue
        if courant:
            sections[courant].append(ligne)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


FIN_ACTUELLE = r"present|aujourd'hui|aujourdhui|actuel|actuellement|en cours|now|current"
MOTIF_PERIODE = re.compile(
    r"(?<!\d)((?:19|20)\d{2})\s*(?:-|–|—|a|au|to)\s*"
    r"(?:\d{1,2}\s*[/.]\s*|[a-z]{3,9}\.?\s+)?((?:19|20)\d{2}|" + FIN_ACTUELLE + r")"
)


def estimer_annees_experience(texte_experience, texte_complet):
    """Estime les années d'expérience à partir des périodes datées de la rubrique expérience."""
    annee_courante = datetime.now().year
    total = 0.0
    for debut, fin in MOTIF_PERIODE.findall(normaliser(texte_experience)):
        debut = int(debut)
        fin = int(fin) if fin.isdigit() else annee_courante
        duree = fin - debut
        if duree < 0 or duree > 40:
            continue
        total += duree if duree > 0 else 0.5
    explicites = re.findall(
        r"(\d{1,2})\s*\+?\s*ans?\s*(?:d'|de\s+)?experience", normaliser(texte_complet)
    )
    if explicites:
        total = max(total, float(max(int(x) for x in explicites)))
    return round(min(total, 30.0), 1)


def analyser_profil_cv(texte_cv):
    """Prépare les informations du CV utilisées pour la comparaison avec les offres."""
    sections = decouper_sections(texte_cv)
    zone_preuve = sections["experience"] + "\n" + sections["projets"]
    norm = normaliser(texte_cv)

    if sections["experience"]:
        a_exp = len(sections["experience"].split()) >= 5
    else:
        a_exp = bool(re.search(r"\b(stagiaire|missions?|responsabilites)\b", norm))
    a_proj = bool(sections["projets"]) or "projet" in norm

    tokens = re.findall(r"[a-z0-9][a-z0-9+#]{3,}", norm)
    return {
        "competences": set(extraire_competences(texte_cv)),
        "preuves": set(extraire_competences(zone_preuve)),
        "annees": estimer_annees_experience(sections["experience"], texte_cv),
        "a_exp": a_exp,
        "a_proj": a_proj,
        "racines": {t.rstrip("s") for t in tokens},
        "sections": sections,
    }


# =========================================================
# OFFRES D'EMPLOI
# =========================================================

def dernier_csv_offres():
    candidats = []
    for dossier in DOSSIERS_DONNEES:
        if dossier.is_dir():
            candidats += list(dossier.glob(MOTIF_FICHIER))
    return max(candidats, key=lambda p: p.stat().st_mtime) if candidats else None


@st.cache_data(show_spinner=False)
def lire_csv(chemin, modifie):
    return pd.read_csv(chemin, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def standardiser_offres(df):
    """Convertit un DataFrame d'offres (colonnes en minuscules ou capitalisées) en liste de dictionnaires."""
    if df is None or df.empty:
        return []
    colonnes = {normaliser(c).strip(): c for c in df.columns}

    def col(*noms):
        return next((colonnes[n] for n in noms if n in colonnes), None)

    champs = {
        "titre": col("titre", "title", "poste"),
        "entreprise": col("entreprise", "company", "societe"),
        "description": col("description"),
        "lien": col("lien", "url", "link"),
        "experience": col("experience", "experience_requise"),
        "contrat": col("contrat", "type_contrat"),
        "ville": col("ville", "lieu", "localisation"),
        "competences": col("competences"),
    }
    if champs["titre"] is None:
        return []

    offres, vus = [], set()
    for _, ligne in df.iterrows():
        offre = {}
        for nom, colonne in champs.items():
            valeur = ligne[colonne] if colonne is not None else ""
            offre[nom] = "" if pd.isna(valeur) else str(valeur).strip()
        if not offre["titre"]:
            continue
        cle = offre["lien"] or (offre["titre"], offre["entreprise"])
        if cle in vus:
            continue
        vus.add(cle)
        offres.append(offre)
    return offres


def charger_offres():
    """Charge les offres : dernier CSV du scraper en priorité, sinon offres déjà en session."""
    chemin = dernier_csv_offres()
    if chemin is not None:
        offres = standardiser_offres(lire_csv(str(chemin), chemin.stat().st_mtime))
        if offres:
            return offres, chemin.name
    df_session = st.session_state.get("offres_df")
    if isinstance(df_session, pd.DataFrame):
        offres = standardiser_offres(df_session)
        if offres:
            return offres, "offres de la session"
    return [], ""


# =========================================================
# ADÉQUATION CV / OFFRE
# =========================================================

def experience_requise(titre, contrat, description, champ_experience):
    """Retourne (années requises ou None, offre de type stage/alternance)."""
    stage = bool(re.search(
        r"\b(stage|stagiaire|pfe|internship|intern|alternance|apprenti)\b",
        normaliser(titre + " " + contrat)
    )) or bool(re.search(
        r"\b(stagiaire|pfe|stage de fin d'etudes)\b", normaliser(description)
    ))

    champ = normaliser(champ_experience)
    if champ:
        if re.search(r"debutant|sans experience|aucune|moins d'un an|moins de 1 an", champ):
            return 0, stage
        m = re.search(r"(\d{1,2})", champ)
        if m and int(m.group(1)) <= 15:
            return int(m.group(1)), stage

    texte = normaliser(titre + " " + description)
    if re.search(r"\b(debutant|sans experience|aucune experience)\b", texte):
        return 0, stage
    motifs = (
        r"(\d{1,2})\s*(?:a|-|to)\s*\d{1,2}\s*ans?\s*(?:d'|de\s+)?experience",
        r"(\d{1,2})\s*\+?\s*ans?\s*(?:d'|de\s+)?(?:experience|exp)",
        r"experience\s*(?:professionnelle\s*)?(?:de|d'|:|minimum|min\.?|of)?\s*(?:de\s+)?(\d{1,2})\s*ans?",
    )
    for motif in motifs:
        m = re.search(motif, texte)
        if m and 0 <= int(m.group(1)) <= 15:
            return int(m.group(1)), stage
    if re.search(r"\bjunior\b", texte):
        return 1, stage
    if re.search(r"\b(senior|confirme)\b", texte):
        return 5, stage
    return None, stage


def evaluer_offre(profil, offre):
    """Compare le CV (compétences + expériences) à une offre et calcule une adéquation sur 100."""
    texte_offre = " ".join([offre["titre"], offre["description"], offre.get("competences", "")])
    requises = extraire_competences(texte_offre)

    ok, preuves, manquantes, points = [], [], [], 0.0
    for comp in requises:
        if comp in profil["preuves"]:
            ok.append(comp)
            preuves.append(comp)
            points += 1.0
        elif comp in profil["competences"]:
            ok.append(comp)
            points += 0.8
        else:
            manquantes.append(comp)

    mots_manquants = []
    if len(requises) >= 2:
        mode = "competences"
        score_comp = round(points / len(requises) * 100)
    else:
        mode = "mots-cles"
        cles = mots_cles(offre["titre"] + " " + offre["description"], limite=15)
        if cles:
            trouves = [r for r, _ in cles if r in profil["racines"]]
            score_comp = round(len(trouves) / len(cles) * 100)
            mots_manquants = [mot for r, mot in cles if r not in profil["racines"]][:8]
        else:
            score_comp = 0

    # Correspondance avec l'intitulé du poste
    racines_titre = {r for r, _ in mots_cles(offre["titre"])}
    if racines_titre:
        score_titre = round(
            len([r for r in racines_titre if r in profil["racines"]]) / len(racines_titre) * 100
        )
    else:
        score_titre = 50

    # Expérience
    exp_req, stage = experience_requise(
        offre["titre"], offre["contrat"], offre["description"], offre["experience"]
    )
    annees_cv, a_exp, a_proj = profil["annees"], profil["a_exp"], profil["a_proj"]
    if stage:
        score_exp = 100 if (a_exp or a_proj) else 55
    elif exp_req is None:
        score_exp = 75 if a_exp else (60 if a_proj else 40)
    elif exp_req == 0:
        score_exp = 100 if (a_exp or a_proj) else 60
    elif annees_cv > 0:
        score_exp = round(min(1.0, annees_cv / exp_req) * 100)
    else:
        score_exp = 45 if a_exp else (25 if a_proj else 10)

    score = round(
        POIDS_COMPETENCES * score_comp
        + POIDS_EXPERIENCE * score_exp
        + POIDS_TITRE * score_titre
    )
    niveau = "bon" if score >= SEUIL_BON else "partiel" if score >= SEUIL_PARTIEL else "faible"

    return {
        "score": score,
        "niveau": niveau,
        "verdict": VERDICTS[niveau][1],
        "score_competences": score_comp,
        "score_experience": score_exp,
        "score_titre": score_titre,
        "competences_offre": requises,
        "competences_ok": ok,
        "competences_preuves": preuves,
        "competences_manquantes": manquantes,
        "mode": mode,
        "mots_manquants": mots_manquants,
        "exp_requise": exp_req,
        "exp_cv": annees_cv,
        "stage": stage,
        "a_exp": a_exp,
        "a_proj": a_proj,
    }


def classer_offres(profil, offres):
    """Évalue toutes les offres et les trie de la meilleure à la moins bonne."""
    resultats = [(evaluer_offre(profil, offre), offre) for offre in offres]
    resultats.sort(key=lambda x: (x[0]["score"], len(x[0]["competences_ok"])), reverse=True)
    return resultats


def _liste(elements):
    return ", ".join(elements)


def rediger_avis(res, offre):
    """Rédige l'avis détaillé (compétences + expériences), que l'offre corresponde ou non."""
    emoji, libelle = VERDICTS[res["niveau"]]
    lignes = []

    if res["niveau"] == "bon":
        lignes.append(f"{emoji} **Votre CV correspond bien à cette offre** (adéquation {res['score']}/100).")
    elif res["niveau"] == "partiel":
        lignes.append(f"{emoji} **Votre CV correspond partiellement à cette offre** (adéquation {res['score']}/100).")
    else:
        lignes.append(f"{emoji} **Votre CV ne correspond pas (ou très peu) à cette offre** "
                      f"(adéquation {res['score']}/100).")

    # --- Compétences ---
    total = len(res["competences_offre"])
    if res["mode"] == "competences":
        txt = (f"**Compétences :** vous couvrez {len(res['competences_ok'])} des {total} compétences "
               f"repérées dans l'offre")
        txt += f" ({_liste(res['competences_ok'])})." if res["competences_ok"] else "."
        lignes.append(txt)
        if res["competences_preuves"]:
            lignes.append(f"Points forts : {_liste(res['competences_preuves'])} apparaissent dans vos "
                          f"expériences ou projets, ce qui prouve que vous les avez réellement utilisées.")
        declarees = [c for c in res["competences_ok"] if c not in res["competences_preuves"]]
        if declarees:
            lignes.append(f"{_liste(declarees)} figure(nt) seulement dans votre liste de compétences : "
                          f"illustrez-les dans une expérience ou un projet pour les rendre crédibles.")
        if res["competences_manquantes"]:
            lignes.append(f"Compétences demandées qui manquent à votre CV : {_liste(res['competences_manquantes'])}.")
    else:
        lignes.append("**Compétences :** l'offre cite peu de technologies précises, l'analyse s'appuie donc "
                      f"sur ses mots-clés (couverture : {res['score_competences']} %).")
        if res["competences_ok"]:
            lignes.append(f"Compétence repérée en commun : {_liste(res['competences_ok'])}.")
        if res["competences_manquantes"]:
            lignes.append(f"Compétence demandée qui manque : {_liste(res['competences_manquantes'])}.")
        if res["mots_manquants"]:
            lignes.append(f"Mots-clés de l'offre absents de votre CV : {_liste(res['mots_manquants'])}.")

    # --- Expériences ---
    annees = f"{res['exp_cv']:g}"
    if res["stage"]:
        if res["a_exp"] or res["a_proj"]:
            lignes.append("**Expérience :** c'est une offre de stage/alternance ; vos expériences et projets "
                          "sont adaptés à ce niveau.")
        else:
            lignes.append("**Expérience :** c'est une offre de stage/alternance ; aucune expérience ni projet "
                          "n'est détecté dans votre CV. Ajoutez vos projets académiques.")
    elif res["exp_requise"] is None:
        base = "**Expérience :** l'offre ne précise pas le niveau demandé. "
        if res["a_exp"]:
            base += "Votre CV présente des expériences professionnelles, c'est un atout."
        elif res["a_proj"]:
            base += "Votre CV présente surtout des projets : détaillez vos missions et résultats."
        else:
            base += "Aucune expérience ni projet n'est détecté : c'est un point faible."
        lignes.append(base)
    elif res["exp_requise"] == 0:
        lignes.append("**Expérience :** l'offre accepte les débutants ; votre profil est adapté.")
    else:
        n = res["exp_requise"]
        if res["exp_cv"] >= n:
            lignes.append(f"**Expérience :** l'offre demande environ {n} an(s) d'expérience et votre CV en "
                          f"laisse apparaître environ {annees} : c'est cohérent.")
        elif res["exp_cv"] > 0:
            lignes.append(f"**Expérience :** l'offre demande environ {n} an(s) d'expérience, votre CV en montre "
                          f"environ {annees}. L'écart est à compenser par vos projets et vos résultats.")
        else:
            lignes.append(f"**Expérience :** l'offre demande environ {n} an(s) d'expérience et aucune durée "
                          f"d'expérience n'est détectée dans votre CV. Indiquez des dates (ex. 2023 – 2024) "
                          f"si vous en avez.")

    # --- Conseil ---
    if res["niveau"] == "bon":
        conseil = ("**Conseil :** vous pouvez postuler. Reprenez les mots-clés de l'offre dans votre profil "
                   "et mettez en avant vos réalisations les plus proches du poste.")
    elif res["niveau"] == "partiel":
        manque = res["competences_manquantes"] or res["mots_manquants"]
        conseil = ("**Conseil :** candidature possible, mais renforcez votre CV"
                   + (f" sur : {_liste(manque[:5])}." if manque else "."))
    else:
        manque = res["competences_manquantes"]
        conseil = ("**Conseil :** cette offre n'est pas alignée avec votre profil actuel. "
                   + (f"Pour la viser, il faudrait acquérir : {_liste(manque[:5])}. " if manque else "")
                   + "Privilégiez les offres mieux classées, ou complétez votre CV si vous avez déjà "
                     "ces compétences.")
    lignes.append(conseil)
    return "\n\n".join(lignes)


# =========================================================
# AFFICHAGE DES OFFRES
# =========================================================

def afficher_carte_offre(res, offre, rang=None):
    emoji, libelle = VERDICTS[res["niveau"]]
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            titre = f"**{rang}. {offre['titre']}**" if rang else f"**{offre['titre']}**"
            details = " · ".join(p for p in [offre["entreprise"], offre["ville"]] if p)
            st.markdown(titre + (f"  \n{details}" if details else ""))
        with c2:
            st.metric("Adéquation", f"{res['score']}%")
        st.progress(res["score"] / 100)
        st.caption(f"{emoji} {libelle}")

        if res["competences_ok"]:
            marques = [
                f"{c} ✔" if c in res["competences_preuves"] else c for c in res["competences_ok"]
            ]
            st.markdown(f"**En commun :** {_liste(marques)}")
        if res["competences_manquantes"]:
            st.markdown(f"**À renforcer :** {_liste(res['competences_manquantes'])}")

        with st.expander("Voir l'avis détaillé"):
            st.markdown(rediger_avis(res, offre))
            if lien_valide(offre["lien"]):
                st.markdown(f"[Voir l'offre d'origine]({offre['lien']})")


def afficher_analyse_detaillee(res, offre):
    emoji, libelle = VERDICTS[res["niveau"]]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Adéquation globale", f"{res['score']}/100")
    c2.metric("Compétences", f"{res['score_competences']}/100")
    c3.metric("Expérience", f"{res['score_experience']}/100")
    c4.metric("Intitulé du poste", f"{res['score_titre']}/100")
    st.progress(res["score"] / 100)

    if res["niveau"] == "bon":
        st.success(f"{emoji} {libelle}")
    elif res["niveau"] == "partiel":
        st.warning(f"{emoji} {libelle}")
    else:
        st.error(f"{emoji} {libelle}")

    st.markdown(rediger_avis(res, offre))

    if res["competences_offre"]:
        lignes = []
        for comp in res["competences_offre"]:
            if comp in res["competences_preuves"]:
                statut = " Présente (prouvée par vos expériences/projets)"
            elif comp in res["competences_ok"]:
                statut = " Présente (liste de compétences uniquement)"
            else:
                statut = " Absente de votre CV"
            lignes.append({"Compétence demandée": comp, "Dans votre CV": statut})
        st.dataframe(lignes, use_container_width=True, hide_index=True)

    if lien_valide(offre.get("lien", "")):
        st.markdown(f"[Voir l'offre d'origine]({offre['lien']})")


def afficher_adequation_offres(profil, offres, source, classement):
    st.divider()
    st.header("Adéquation avec les offres d'emploi")
    st.caption(
        "Comparaison de vos compétences et de vos expériences avec chaque offre. "
        "Les compétences marquées  apparaissent dans vos expériences ou projets."
    )

    modes = ["Meilleures offres pour mon CV", "Une offre de la liste", "Coller une offre"]
    if not offres:
        st.info("Aucun fichier `offres_*.csv` trouvé : collez le texte d'une offre ci-dessous.")
        mode = "Coller une offre"
    else:
        mode = st.radio("Que voulez-vous faire ?", modes, horizontal=True, key="mode_adequation")
        st.caption(f"{len(offres)} offres analysées · source : {source}")

    # --- Classement de toutes les offres ---
    if mode == modes[0]:
        bons = [x for x in classement if x[0]["niveau"] == "bon"]
        partiels = [x for x in classement if x[0]["niveau"] == "partiel"]
        faibles = [x for x in classement if x[0]["niveau"] == "faible"]

        m1, m2, m3 = st.columns(3)
        m1.metric(" Correspondent bien", len(bons))
        m2.metric(" Partielles", len(partiels))
        m3.metric(" Ne correspondent pas", len(faibles))

        compteur = Counter(c for res, _ in classement for c in res["competences_manquantes"])
        if compteur:
            top = [f"{nom} ({n} offres)" for nom, n in compteur.most_common(6)]
            st.info("Compétences demandées qui vous manquent le plus souvent : " + _liste(top) + ".")

        limite = st.slider("Offres affichées par catégorie", 3, 30, 10, key="limite_offres")
        onglets = st.tabs([
            f" Correspondent bien ({len(bons)})",
            f" Partielles ({len(partiels)})",
            f" Ne correspondent pas ({len(faibles)})",
        ])
        for onglet, groupe, message in zip(
            onglets,
            (bons, partiels, faibles),
            (
                "Aucune offre ne correspond bien pour l'instant : consultez les offres partielles.",
                "Aucune offre à correspondance partielle.",
                "Aucune offre n'est en total décalage avec votre CV.",
            ),
        ):
            with onglet:
                if not groupe:
                    st.write(message)
                for rang, (res, offre) in enumerate(groupe[:limite], 1):
                    afficher_carte_offre(res, offre, rang)

    # --- Une offre précise de la liste ---
    elif mode == modes[1]:
        index = st.selectbox(
            "Choisir une offre",
            options=list(range(len(offres))),
            format_func=lambda i: " — ".join(
                p for p in [offres[i]["titre"], offres[i]["entreprise"]] if p
            ),
            key="offre_choisie",
        )
        offre = offres[index]
        afficher_analyse_detaillee(evaluer_offre(profil, offre), offre)

    # --- Offre collée par l'utilisateur ---
    else:
        titre = st.text_input("Intitulé du poste (optionnel)", key="offre_collee_titre")
        description = st.text_area(
            "Texte de l'offre (missions, profil recherché, compétences, expérience)",
            height=220,
            key="offre_collee_description",
        )
        if description.strip() or titre.strip():
            offre = {
                "titre": titre.strip() or "Offre collée",
                "entreprise": "", "description": description.strip(), "lien": "",
                "experience": "", "contrat": "", "ville": "", "competences": "",
            }
            afficher_analyse_detaillee(evaluer_offre(profil, offre), offre)


# =========================================================
# ANALYSE DU CV
# =========================================================

def evaluer_cv(texte_cv):

    texte = texte_cv.lower()
    criteres = []
    points_forts = []
    ameliorations = []

    # -----------------------------------------------------
    # 1. Coordonnées : 15 points
    # -----------------------------------------------------

    email_present = bool(
        re.search(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            texte_cv,
            re.I
        )
    )

    telephone_present = bool(
        re.search(
            r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)",
            texte_cv
        )
    )

    lien_present = any(
        mot in texte
        for mot in ["linkedin", "github.com", "portfolio"]
    )

    score_coordonnees = (
        (8 if email_present else 0)
        + (4 if telephone_present else 0)
        + (3 if lien_present else 0)
    )

    criteres.append({
        "Critère": "Coordonnées",
        "Score": score_coordonnees,
        "Maximum": 15
    })

    if email_present:
        points_forts.append("Adresse e-mail détectée.")
    else:
        ameliorations.append(
            "Ajoutez une adresse e-mail professionnelle."
        )

    if not telephone_present:
        ameliorations.append(
            "Vérifiez la présence d'un numéro de téléphone."
        )

    if not lien_present:
        ameliorations.append(
            "Ajoutez un lien LinkedIn, GitHub ou portfolio pertinent, "
            "si vous en possédez un."
        )

    # -----------------------------------------------------
    # 2. Profil professionnel : 10 points
    # -----------------------------------------------------

    mots_profil = [
        "profil", "objectif professionnel",
        "à propos", "présentation",
        "étudiant", "professionnel"
    ]

    score_profil = (
        10 if any(mot in texte for mot in mots_profil)
        and len(texte.split()) >= 80
        else 5 if len(texte.split()) >= 40
        else 0
    )

    criteres.append({
        "Critère": "Profil professionnel",
        "Score": score_profil,
        "Maximum": 10
    })

    if score_profil >= 10:
        points_forts.append(
            "Une présentation professionnelle semble présente."
        )
    else:
        ameliorations.append(
            "Ajoutez une présentation de quelques lignes indiquant "
            "votre parcours, vos compétences et votre objectif."
        )

    # -----------------------------------------------------
    # 3. Formation : 15 points
    # -----------------------------------------------------

    mots_formation = [
        "formation", "diplôme", "licence", "master",
        "baccalauréat", "université", "école",
        "études", "education"
    ]

    score_formation = (
        15 if any(mot in texte for mot in mots_formation)
        else 0
    )

    criteres.append({
        "Critère": "Formation",
        "Score": score_formation,
        "Maximum": 15
    })

    if score_formation:
        points_forts.append(
            "Une rubrique de formation semble présente."
        )
    else:
        ameliorations.append(
            "Présentez vos diplômes, établissements et années d'études."
        )

    # -----------------------------------------------------
    # 4. Compétences techniques : 20 points
    # -----------------------------------------------------

    competences_trouvees = extraire_competences(texte_cv)

    score_competences = min(
        20,
        len(competences_trouvees) * 2
    )

    criteres.append({
        "Critère": "Compétences",
        "Score": score_competences,
        "Maximum": 20
    })

    if competences_trouvees:
        points_forts.append(
            "Compétences détectées : "
            + ", ".join(competences_trouvees[:12]) + "."
        )
    else:
        ameliorations.append(
            "Ajoutez une rubrique de compétences techniques "
            "et transversales réellement maîtrisées."
        )

    # -----------------------------------------------------
    # 5. Expériences et projets : 15 points
    # -----------------------------------------------------

    mots_experience = [
        "expérience", "stage", "stagiaire", "emploi",
        "entreprise", "mission", "responsabilités"
    ]

    mots_projet = [
        "projet", "réalisation", "développé",
        "conception", "application"
    ]

    experience_presente = any(
        mot in texte for mot in mots_experience
    )

    projet_present = any(
        mot in texte for mot in mots_projet
    )

    if experience_presente:
        score_experience = 15
        points_forts.append(
            "Des expériences professionnelles semblent mentionnées."
        )
    elif projet_present:
        score_experience = 10
        points_forts.append(
            "Des projets ou réalisations semblent mentionnés."
        )
    else:
        score_experience = 0

    criteres.append({
        "Critère": "Expériences et projets",
        "Score": score_experience,
        "Maximum": 15
    })

    if score_experience < 15:
        ameliorations.append(
            "Décrivez vos stages, expériences ou projets avec les "
            "missions, les outils utilisés et les résultats obtenus. "
            "Les projets académiques conviennent aussi aux étudiants."
        )

    # -----------------------------------------------------
    # 6. Structure et contenu : 10 points
    # -----------------------------------------------------

    nombre_mots = len(texte.split())

    score_structure = 0

    if nombre_mots >= 100:
        score_structure += 4

    if nombre_mots >= 180:
        score_structure += 2

    if re.search(r"\b20\d{2}\b", texte):
        score_structure += 2

    if len(re.findall(r"[\n•●▪\-]", texte_cv)) >= 3:
        score_structure += 2

    criteres.append({
        "Critère": "Structure et contenu",
        "Score": score_structure,
        "Maximum": 10
    })

    if nombre_mots < 100:
        ameliorations.append(
            "Le texte extrait est court. Vérifiez que le PDF contient "
            "bien toutes les rubriques de votre CV."
        )

    # -----------------------------------------------------
    # 7. Langues : 5 points
    # -----------------------------------------------------

    mots_langues = [
        "langues", "français", "anglais",
        "arabe", "espagnol", "allemand",
        "courant", "niveau b1", "niveau b2"
    ]

    score_langues = (
        5 if any(mot in texte for mot in mots_langues)
        else 0
    )

    criteres.append({
        "Critère": "Langues",
        "Score": score_langues,
        "Maximum": 5
    })

    if score_langues:
        points_forts.append(
            "Des informations sur les langues semblent présentes."
        )
    else:
        ameliorations.append(
            "Ajoutez les langues que vous maîtrisez et vos niveaux réels."
        )

    # -----------------------------------------------------
    # CALCUL DU SCORE SUR 100
    # -----------------------------------------------------

    score_total = sum(
        critere["Score"] for critere in criteres
    )

    score_maximum = sum(
        critere["Maximum"] for critere in criteres
    )

    score_final = round(
        score_total / score_maximum * 100
    )

    if score_final >= 80:
        diagnostic = "Bonne complétude selon les critères détectés"
    elif score_final >= 60:
        diagnostic = "CV à améliorer sur quelques points"
    elif score_final >= 40:
        diagnostic = "Plusieurs rubriques sont à renforcer"
    else:
        diagnostic = "CV à compléter ou texte extrait insuffisant"

    if not ameliorations:
        ameliorations.append(
            "Relisez votre CV et vérifiez l'exactitude de toutes "
            "les informations avant de postuler."
        )

    return {
        "score": score_final,
        "diagnostic": diagnostic,
        "criteres": criteres,
        "points_forts": points_forts,
        "ameliorations": ameliorations,
        "competences": competences_trouvees,
        "nombre_mots": nombre_mots
    }


# =========================================================
# RAPPORT TÉLÉCHARGEABLE
# =========================================================

def construire_rapport(resultat, classement):
    lignes = [
        "RAPPORT D'EVALUATION DU CV",
        f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        f"Score indicatif : {resultat['score']}/100",
        resultat["diagnostic"],
        "",
        "DETAIL DES CRITERES"
    ]

    for critere in resultat["criteres"]:
        lignes.append(
            f"- {critere['Critère']} : "
            f"{critere['Score']}/{critere['Maximum']}"
        )

    lignes.extend(["", "POINTS FORTS"])

    for point in resultat["points_forts"]:
        lignes.append("- " + point)

    lignes.extend(["", "COMPETENCES DETECTEES"])
    lignes.append(
        ", ".join(resultat["competences"])
        or "Aucune détectée"
    )

    lignes.extend(["", "RECOMMANDATIONS"])

    for conseil in resultat["ameliorations"]:
        lignes.append("- " + conseil)

    if classement:
        nb = {n: sum(1 for r, _ in classement if r["niveau"] == n) for n in VERDICTS}
        lignes.extend([
            "",
            "ADEQUATION AVEC LES OFFRES",
            f"- Correspondent bien : {nb['bon']}",
            f"- Correspondent partiellement : {nb['partiel']}",
            f"- Ne correspondent pas : {nb['faible']}",
            "",
            "MEILLEURES OFFRES"
        ])
        for rang, (res, offre) in enumerate(classement[:10], 1):
            lignes.append(
                f"{rang}. {offre['titre']} ({offre['entreprise'] or 'entreprise non précisée'}) "
                f"- {res['score']}/100 - {res['verdict']}"
            )
            if res["competences_manquantes"]:
                lignes.append("   Compétences manquantes : " + _liste(res["competences_manquantes"]))

    return "\n".join(lignes)


# =========================================================
# RÉSULTATS
# =========================================================

def afficher_rapport(texte_cv):
    resultat = evaluer_cv(texte_cv)
    profil = analyser_profil_cv(texte_cv)
    offres, source = charger_offres()
    classement = classer_offres(profil, offres) if offres else []

    st.divider()
    st.header("Résultats de l'évaluation")
    if st.session_state.get("cv_nom"):
        st.caption(f"CV analysé : {st.session_state['cv_nom']}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Score indicatif",
            f"{resultat['score']}/100"
        )

    with col2:
        st.metric(
            "Mots détectés",
            resultat["nombre_mots"]
        )

    with col3:
        st.metric(
            "Compétences repérées",
            len(resultat["competences"])
        )

    st.progress(resultat["score"] / 100)

    st.info(resultat["diagnostic"])

    # Tableau des critères
    st.subheader("Détail des critères")

    st.dataframe(
        resultat["criteres"],
        use_container_width=True,
        hide_index=True
    )

    # Points forts
    st.subheader("Points forts détectés")

    if resultat["points_forts"]:
        for point in resultat["points_forts"]:
            st.markdown(f"- {point}")
    else:
        st.write(
            "Aucun point fort n'a pu être identifié "
            "automatiquement dans le texte extrait."
        )

    # Compétences
    st.subheader("Compétences détectées")

    if resultat["competences"]:
        st.write(
            ", ".join(resultat["competences"])
        )
    else:
        st.write(
            "Aucune compétence de la liste de détection "
            "n'a été trouvée."
        )

    # Suggestions
    st.subheader(" Recommandations")

    for conseil in resultat["ameliorations"]:
        st.markdown(f"- {conseil}")

    # Adéquation avec les offres
    afficher_adequation_offres(profil, offres, source, classement)

    # Téléchargement du rapport
    st.divider()
    st.download_button(
        label="Télécharger le rapport d'évaluation",
        data=construire_rapport(resultat, classement).encode("utf-8"),
        file_name="rapport_evaluation_cv.txt",
        mime="text/plain",
        type="primary",
        use_container_width=True,
        key="telecharger_rapport"
    )
    with st.expander("Consulter le texte extrait du CV"):
        st.text(texte_cv[:15000])


# =========================================================
# INTERFACE UTILISATEUR
# =========================================================

st.title("Agent d'évaluation de CV")

st.write(
    "Importez votre CV au format PDF. L'agent analyse son contenu, "
    "repère les compétences, les compare aux offres d'emploi et propose des améliorations."
)

st.caption(
    "L'évaluation est indicative : elle mesure des éléments détectables "
    "du document et ne prédit pas les décisions d'un recruteur."
)

with st.form("evaluation_cv"):

    fichier_cv = st.file_uploader(
        "Importer votre CV (PDF)",
        type=["pdf"],
        help="Sélectionnez le CV que vous souhaitez faire évaluer."
    )

    lancer = st.form_submit_button(
        " Évaluer mon CV",
        type="primary",
        use_container_width=True
    )


# =========================================================
# TRAITEMENT
# =========================================================

if lancer:

    if fichier_cv is None:
        st.error("Veuillez importer un CV au format PDF.")

    else:
        try:
            with st.spinner("Analyse du CV en cours..."):
                texte_extrait = extraire_texte_pdf(fichier_cv)

            if not texte_extrait:
                st.session_state.pop("cv_texte", None)
                st.error(
                    "Aucun texte n'a été extrait. "
                    "Votre PDF est peut-être un scan sans texte OCR."
                )
            else:
                # Le CV est gardé en session pour que les choix faits ensuite
                # (offre, onglets, filtres) ne fassent pas disparaître les résultats.
                st.session_state["cv_texte"] = texte_extrait
                st.session_state["cv_nom"] = fichier_cv.name

        except Exception as erreur:
            st.error(
                f"Une erreur est survenue pendant l'analyse : {erreur}"
            )

texte_cv = st.session_state.get("cv_texte")

if texte_cv:
    try:
        afficher_rapport(texte_cv)
    except Exception as erreur:
        st.error(
            f"Une erreur est survenue pendant l'analyse : {erreur}"
        )