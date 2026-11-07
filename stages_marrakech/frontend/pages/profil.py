from __future__ import annotations
import base64
import html
import json
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import streamlit as st


# ============================================================
# 1. RÉGLAGES DE LA PAGE (textes du design, modifiables)
# ============================================================

EDITION_AUTORISEE = True        # False : masque les formulaires de modification (page publique)
MESSAGES_MAX_PAR_SESSION = 3    # limite d'e-mails envoyés par visiteur (anti-spam)

NOM_PROJET = "MarrakechOpportunityHub"
ACCROCHE_PROJET = (
    "Plateforme automatisée de collecte, d'analyse et de recommandation "
    "d'opportunités Tech & IA dans la région Marrakech-Safi."
)
BADGE_ROLE = "Créateur & Leader"
META_LIGNE = ["Ingénierie IA & Analyse des données", "Pipelines ETL & Agents LLM"]

POINTS_FORTS = [
    "Collecte multi-sources & normalisation ETL.",
    "Assistant IA (Groq LLM) qui interroge les données du projet.",
]

ARCHITECTURE = [
    {"icone": "cloud", "titre": "1. Collecte & Pipeline ETL",
     "description": "Collecte des offres et des entreprises, nettoyage et contrôle qualité avec Python et Pandas.",
     "tags": "Python • Pandas • ETL"},
    {"icone": "cpu", "titre": "2. Agent IA & LLM",
     "description": "Assistant intégré (API Groq) qui interroge les données et répond aux questions du projet.",
     "tags": "Groq API • LLM • Function calling"},
    {"icone": "grid", "titre": "3. Interface Streamlit",
     "description": "Tableaux de bord interactifs, filtres dynamiques, graphiques et outils de CV.",
     "tags": "Streamlit • Plotly • CSS"},
    {"icone": "database", "titre": "4. Données & Analyse",
     "description": "Fichiers CSV nettoyés, scores des entreprises, ACP et groupes d'entreprises.",
     "tags": "CSV • Pandas • ACP"},
]

# ============================================================
# 2. CHEMINS ET DONNÉES PAR DÉFAUT
# ============================================================

DOSSIER_DATA = Path(__file__).resolve().parents[2] / "data"
DOSSIER_PROFIL = DOSSIER_DATA / "profil"
FICHIER_PROFIL = DOSSIER_PROFIL / "profil.json"

PROFIL_PAR_DEFAUT = {
    "nom": "Kodji Koffi",
    "titre": "Développeur & Data Analyst — Chef de projet MarrakechOpportunityHub",
    "ville": "Marrakech, Maroc",
    "email": "",
    "telephone": "",
    "linkedin": "",
    "github": "",
    "bio": (
        "MarrakechOpportunityHub (nom de code : tracker_marrakech) est une solution "
        "intelligente conçue pour centraliser, nettoyer et analyser les offres d'emploi, "
        "de stages et les entreprises en Data Science, IA et Développement logiciel dans "
        "la région de Marrakech-Safi."
    ),
    "competences": [
        "Python", "Pandas", "Scikit-Learn", "Streamlit",
        "PostgreSQL", "Groq API", "ETL Pipelines", "Git & GitHub",
    ],
    "photo": None,
}

# ============================================================
# 3. OUTILS : HTML, ICÔNES, FICHIERS
# ============================================================

def esc(valeur) -> str:
    return html.escape(str(valeur or ""), quote=True)


def compact(texte: str) -> str:
    return "".join(ligne.strip() for ligne in texte.splitlines())


def lien_valide(url) -> bool:
    return str(url or "").startswith(("http://", "https://"))


def formater_nombre(valeur) -> str:
    return "—" if valeur is None else f"{valeur:,}".replace(",", " ")


_ICONES = {
    "mail": '<path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><polyline points="22,6 12,13 2,6"/>',
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "github": '<path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "grid": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    "cloud": '<polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/>',
    "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "terminal": '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    "sparkle": '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.7 1.8L21.5 17.5l-1.8.7L19 20l-.7-1.8-1.8-.7 1.8-.7z"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
}


def icone(nom: str, taille: int = 18, couleur: str = "#34d399") -> str:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
           f'stroke="{couleur}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{_ICONES[nom]}</svg>')
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return f'<img class="pf-ico" src="{uri}" width="{taille}" height="{taille}" alt="">'


def conteneur(cle: str):
    try:
        return st.container(key=cle)
    except TypeError:
        return st.container()


def avec_icone(fonction, libelle: str, icon: str, **options):
    try:
        return fonction(libelle, icon=icon, **options)
    except TypeError:
        return fonction(libelle, **options)


# ============================================================
# 4. PROFIL : CHARGEMENT, ENREGISTREMENT, PHOTO
# ============================================================

def charger_profil_disque() -> dict:
    try:
        donnees = json.loads(FICHIER_PROFIL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return donnees if isinstance(donnees, dict) else {}


def sauvegarder_profil(profil: dict) -> bool:
    try:
        DOSSIER_PROFIL.mkdir(parents=True, exist_ok=True)
        contenu = {cle: profil.get(cle) for cle in PROFIL_PAR_DEFAUT}
        FICHIER_PROFIL.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def get_profile_data() -> dict:
    if "profile_data" not in st.session_state:
        profil = {cle: (list(v) if isinstance(v, list) else v) for cle, v in PROFIL_PAR_DEFAUT.items()}
        for cle, valeur in charger_profil_disque().items():
            if cle not in profil:
                continue
            if cle == "photo":
                valide = isinstance(valeur, str) or valeur is None
            else:
                valide = isinstance(valeur, type(PROFIL_PAR_DEFAUT[cle]))
            if valide:
                profil[cle] = valeur
        st.session_state.profile_data = profil
    return st.session_state.profile_data


def lire_photo(profil: dict) -> bytes | None:
    nom = Path(str(profil.get("photo") or "")).name
    if not nom:
        return None
    try:
        return (DOSSIER_PROFIL / nom).read_bytes()
    except OSError:
        return None


def photo_data_uri(profil: dict) -> str | None:
    octets = lire_photo(profil)
    return "data:image/jpeg;base64," + base64.b64encode(octets).decode() if octets else None


def enregistrer_photo(fichier, profil: dict) -> tuple[bool, str]:
    try:
        from PIL import Image, ImageOps
        if fichier.size > 5 * 1024 * 1024:
            return False, "La photo dépasse 5 Mo."
        image = ImageOps.exif_transpose(Image.open(fichier)).convert("RGB")
        image = ImageOps.fit(image, (600, 600), method=Image.LANCZOS)
        DOSSIER_PROFIL.mkdir(parents=True, exist_ok=True)
        image.save(DOSSIER_PROFIL / "photo.jpg", "JPEG", quality=90)
    except Exception as erreur:
        return False, f"Image illisible ({type(erreur).__name__})."
    profil["photo"] = "photo.jpg"
    sauvegarder_profil(profil)
    return True, "Photo enregistrée."


# ============================================================
# 5. MÉTRIQUES RÉELLES DU PROJET
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def metriques_du_tracker() -> dict:
    chiffres = {"Offres collectées": None, "Entreprises indexées": None,
                "Cibles IA/Tech": None, "Candidatures suivies": None}

    fichier = DOSSIER_DATA / "clean" / "entreprises_nettoyees.csv"
    if fichier.is_file():
        try:
            df = pd.read_csv(fichier, dtype=str, keep_default_na=False)
            chiffres["Entreprises indexées"] = len(df)
            if "pertinence" in df.columns:
                chiffres["Cibles IA/Tech"] = int(df["pertinence"].str.lower().str.contains("cible").sum())
        except Exception:
            pass

    offres = sorted(DOSSIER_DATA.rglob("offres_*.csv"), key=lambda p: p.stat().st_mtime) if DOSSIER_DATA.is_dir() else []
    if offres:
        try:
            df = pd.read_csv(offres[-1], dtype=str, keep_default_na=False, encoding="utf-8-sig")
            if "titre" in df.columns:
                df = df[df["titre"].str.strip() != ""]
            if "lien" in df.columns:
                avec_lien = df["lien"].str.strip() != ""
                chiffres["Offres collectées"] = int(df[avec_lien]["lien"].nunique() + (~avec_lien).sum())
            else:
                chiffres["Offres collectées"] = len(df)
        except Exception:
            pass

    suivi = DOSSIER_DATA / "tracking" / "entreprises_postulees.csv"
    if suivi.is_file():
        try:
            chiffres["Candidatures suivies"] = len(pd.read_csv(suivi))
        except Exception:
            chiffres["Candidatures suivies"] = 0
    return chiffres


# ============================================================
# 6. ENVOI D'E-MAIL (formulaire de contact)
# ============================================================

EMAIL_VALIDE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
VALEURS_EXEMPLE_SMTP = {"votre.adresse@gmail.com", "mot_de_passe_application_16_caracteres", ""}


def config_smtp() -> dict | None:
    try:
        section = st.secrets.get("app")
        reglages = {
            "hote": str(section.get("SMTP_HOST", "")),
            "port": int(section.get("SMTP_PORT", 587)),
            "utilisateur": str(section.get("SMTP_USER", "")),
            "mot_de_passe": str(section.get("SMTP_PASSWORD", "")),
        }
    except Exception:
        return None
    if (not reglages["hote"] or reglages["utilisateur"] in VALEURS_EXEMPLE_SMTP
            or reglages["mot_de_passe"] in VALEURS_EXEMPLE_SMTP):
        return None
    return reglages


def envoyer_email(smtp: dict, destinataire: str, nom: str, email_visiteur: str, message: str) -> None:
    nom_propre = re.sub(r"[\r\n]+", " ", nom)[:80]
    courriel = EmailMessage()
    courriel["Subject"] = f"[{NOM_PROJET}] Message de {nom_propre}"
    courriel["From"] = smtp["utilisateur"]
    courriel["To"] = destinataire
    courriel["Reply-To"] = email_visiteur
    courriel.set_content(f"Nom : {nom_propre}\nEmail : {email_visiteur}\n\nMessage :\n{message}")
    if smtp["port"] == 465:
        with smtplib.SMTP_SSL(smtp["hote"], 465, timeout=15, context=ssl.create_default_context()) as serveur:
            serveur.login(smtp["utilisateur"], smtp["mot_de_passe"])
            serveur.send_message(courriel)
    else:
        with smtplib.SMTP(smtp["hote"], smtp["port"], timeout=15) as serveur:
            serveur.starttls(context=ssl.create_default_context())
            serveur.login(smtp["utilisateur"], smtp["mot_de_passe"])
            serveur.send_message(courriel)


def verifier_message(nom: str, email: str, message: str) -> str | None:
    if not nom.strip():
        return "Veuillez saisir votre nom."
    if not EMAIL_VALIDE.match(email.strip()):
        return "Veuillez saisir une adresse e-mail valide."
    if not message.strip():
        return "Veuillez saisir votre message."
    if len(message) > 3000:
        return "Le message est trop long (3000 caractères maximum)."
    return None


# ============================================================
# 7. STYLE CSS GLOBAL (Grille 2x2 pour l'architecture & Texte noir pur)
# ============================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #030712 !important;
}
.stApp { color: #f3f4f6 !important; font-family: 'Plus Jakarta Sans', sans-serif; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #f3f4f6 !important; font-family: 'Plus Jakarta Sans', sans-serif; }
[data-testid="stCaptionContainer"] { color: #94a3b8 !important; }
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p, label { color: #e2e8f0 !important; }
hr { border-color: #1e293b !important; }

.block-container, [data-testid="stMainBlockContainer"], [data-testid="stAppViewBlockContainer"] {
    padding-top: 1rem !important; padding-bottom: 2.1rem !important;
}
[data-testid="stHeader"] { background: transparent !important; height: 2.5rem !important; }

.pf-hero { position: relative; height: 296px; }
.pf-banner {
    position: absolute; top: 0; left: 0; right: 0; height: 170px; border-radius: 20px; overflow: hidden;
    background: linear-gradient(120deg, #0b3b3a 0%, #0e2f3d 45%, #0b1220 100%);
    border: 1px solid #1e293b;
}
.pf-banner::before {
    content: ""; position: absolute; inset: 0;
    background-image: radial-gradient(rgba(255,255,255,.12) 1px, transparent 1px); background-size: 20px 20px;
}
.pf-banner::after {
    content: ""; position: absolute; right: -80px; top: -120px; width: 380px; height: 380px; border-radius: 50%;
    background: radial-gradient(circle, rgba(34,211,238,.22), transparent 65%);
}
.pf-banner-text { position: absolute; left: 260px; top: 34px; right: 24px; z-index: 1; }
.pf-projet { font-size: 2rem; font-weight: 800; color: #ffffff; line-height: 1.15; }
.pf-accroche { color: #34d399; font-size: .95rem; margin-top: .5rem; max-width: 620px; line-height: 1.5; }
.pf-photo {
    position: absolute; left: 24px; top: 96px; width: 200px; height: 200px; z-index: 2;
    border-radius: 20px; border: 4px solid #0b1220; box-shadow: 0 12px 30px rgba(0,0,0,.55);
    background: linear-gradient(135deg, #064e3b, #10b981); overflow: hidden;
    display: flex; align-items: center; justify-content: center;
    color: #ffffff; font-size: 3.4rem; font-weight: 800;
}
.pf-photo img.pf-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.pf-photo-badge {
    position: absolute; right: 10px; bottom: 10px; width: 44px; height: 44px; border-radius: 14px;
    background: #10b981; border: 4px solid #0b1220; display: flex; align-items: center; justify-content: center;
}

.st-key-pf_actions { margin-top: -60px; padding-left: 248px; position: relative; z-index: 3; }

.pf-identite { padding-top: 26px; }
.pf-ligne-nom { display: flex; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: .35rem; }
.pf-nom { font-size: 2.8rem; font-weight: 800; color: #f9fafb; line-height: 1.1; }
.badge-emerald {
    display: inline-flex; align-items: center; gap: .4rem; background: rgba(16,185,129,.12); color: #34d399;
    padding: .35rem .9rem; border-radius: 9999px; font-size: .85rem; border: 1px solid rgba(16,185,129,.35); font-weight: 600;
}
.pf-titre { color: #34d399; font-weight: 600; font-size: 1.2rem; margin-bottom: .8rem; }
.pf-meta { display: flex; flex-wrap: wrap; gap: .6rem 1.6rem; color: #94a3b8; font-size: .95rem; margin-bottom: 1.5rem; }
.pf-meta span { display: inline-flex; align-items: center; gap: .5rem; }
.pf-ico { display: inline-block; vertical-align: middle; flex-shrink: 0; }

.pf-card { background: #090d16; border: 1px solid #1e293b; border-radius: 1.2rem; padding: 1.6rem; }
.pf-card-titre { display: flex; align-items: center; gap: .7rem; font-size: 1.5rem; font-weight: 800; color: #f9fafb; margin-bottom: .9rem; }
.pf-card-texte { color: #cbd5e1; font-size: 1rem; line-height: 1.7; }
.pf-code { background: #1e293b; color: #34d399; padding: .1rem .45rem; border-radius: 6px; font-family: ui-monospace, Consolas, monospace; font-size: .85em; }
.pf-points { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: .8rem; margin-top: 1.2rem; }
.pf-point {
    display: flex; align-items: center; gap: .6rem; background: #0b1220; border: 1px solid #1e293b;
    border-radius: .8rem; padding: .8rem 1rem; color: #cbd5e1; font-size: .9rem;
}
.pf-section-titre { display: flex; align-items: center; gap: .6rem; font-size: 1.5rem; font-weight: 800; color: #f9fafb; margin: 1.6rem 0 .9rem 0; }

/* ---- GRILLE 2 COLONNES ET 2 LIGNES POUR L'ARCHITECTURE ---- */
.pf-archi { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
.pf-archi-carte { background: #090d16; border: 1px solid #1e293b; border-radius: 1rem; padding: 1.2rem 1.3rem; }
.pf-archi-titre { display: flex; align-items: center; gap: .6rem; font-weight: 800; font-size: 1.1rem; color: #f9fafb; }
.pf-archi-desc { color: #94a3b8; font-size: .9rem; line-height: 1.5; margin: .6rem 0 .8rem 0; }
.pf-archi-tags { display: inline-block; background: #1e293b; color: #34d399; font-family: ui-monospace, Consolas, monospace; font-size: .75rem; padding: .25rem .5rem; border-radius: 6px; }

.pf-metriques-titre { color: #94a3b8; font-size: .85rem; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 1rem; }
.pf-metriques { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .9rem; }
.pf-metrique { background: #0f172a; border: 1px solid #1e293b; border-radius: 1rem; padding: 1.1rem .8rem; text-align: center; }
.pf-valeur { color: #34d399; font-size: 2.1rem; font-weight: 800; line-height: 1.1; }
.pf-libelle { color: #94a3b8; font-size: .85rem; margin-top: .3rem; }

.st-key-pf_collab {
    background: linear-gradient(to bottom right, rgba(6,78,59,.45), rgba(15,23,42,.85));
    border: 1px solid rgba(16,185,129,.3); border-radius: 1.2rem; padding: 1.3rem 1.4rem;
}
.pf-collab-titre { display: flex; align-items: center; gap: .6rem; font-weight: 800; font-size: 1.3rem; color: #f9fafb; margin-bottom: .4rem; }
.pf-collab-texte { color: #cbd5e1; font-size: .95rem; line-height: 1.6; margin-bottom: .6rem; }

.pf-skills { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: .7rem; margin-bottom: .8rem; }
.skill-tag {
    background: #090d16; color: #34d399; padding: 10px 14px; border-radius: 10px; border: 1px solid #1e293b;
    text-align: center; font-size: 13px; font-weight: 600;
}

[data-testid="stButton"] button, [data-testid="stLinkButton"] a, [data-testid="stDownloadButton"] button,
[data-testid="stFormSubmitButton"] button, div.stButton > button, div.stLinkButton > a {
    background-color: #10b981 !important; color: #030712 !important; border-radius: 12px !important;
    font-weight: 700 !important; min-height: 48px; border: none !important; width: 100%;
    display: flex; align-items: center; justify-content: center; text-decoration: none !important;
    box-shadow: 0 6px 18px rgba(16,185,129,.25);
}
[data-testid="stButton"] button:hover, [data-testid="stLinkButton"] a:hover,
[data-testid="stDownloadButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover {
    background-color: #34d399 !important; color: #030712 !important;
}
[data-testid="stButton"] button p, [data-testid="stLinkButton"] a p, [data-testid="stDownloadButton"] button p,
[data-testid="stFormSubmitButton"] button p { color: inherit !important; }

.st-key-pf_annuler button {
    background-color: #1e293b !important; color: #e2e8f0 !important; border: 1px solid #334155 !important; box-shadow: none !important;
}
.st-key-pf_annuler button:hover {
    background-color: #334155 !important; color: #ffffff !important;
}

div[data-baseweb="input"] input, 
div[data-baseweb="textarea"] textarea,
input, textarea {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    font-weight: 600 !important;
}

[data-testid="stExpander"] { background: #090d16; border: 1px solid #1e293b !important; border-radius: 12px; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p { color: #e2e8f0 !important; }
[data-testid="stForm"] { background: #090d16; border: 1px solid #1e293b !important; border-radius: 12px; }

div[role="dialog"] { background: #111a2e !important; border: 1px solid #1e293b; border-radius: 1.2rem !important; }
div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3 { color: #f9fafb !important; }

@media (max-width: 900px) {
    .pf-hero { height: 360px; }
    .pf-banner { height: 210px; }
    .pf-banner-text { left: 24px; top: 20px; }
    .pf-projet { font-size: 1.5rem; }
    .pf-photo { top: 160px; }
    .st-key-pf_actions { margin-top: 0; padding-left: 0; }
    .pf-nom { font-size: 2.1rem; }
    .pf-archi { grid-template-columns: 1fr; }
}
</style>
"""

# ============================================================
# 8. FENÊTRE MODALE DE CONTACT (1 SEUL CLIC)
# ============================================================

def ouvrir_contact(profil: dict) -> None:
    @st.dialog(f"Contacter {profil['nom']}", width="large")
    def _fenetre():
        st.caption(f"Au sujet du projet {NOM_PROJET} ou pour une opportunité.")
        destinataire = profil["email"].strip()
        smtp = config_smtp()

        nom_contact = st.text_input("Votre Nom", placeholder="Ex : Sarah Amrani", key="contact_nom_saisi")
        email_contact = st.text_input("Votre Email", placeholder="sarah@exemple.ma", key="contact_email_saisi")
        message_contact = st.text_area(
            "Message", height=140,
            placeholder=f"Bonjour {profil['nom'].split()[0]}, j'ai vu votre projet {NOM_PROJET} et j'aimerais...",
            key="contact_msg_saisi"
        )

        col_annuler, col_envoyer = st.columns(2)
        
        with col_annuler:
            if st.button("Annuler", key="btn_fermer_modal", use_container_width=True):
                st.rerun()

        with col_envoyer:
            if st.button("Envoyer", type="primary", key="btn_valider_contact", use_container_width=True):
                erreur = verifier_message(nom_contact, email_contact, message_contact)
                if erreur:
                    st.error(erreur)
                elif not destinataire:
                    st.warning("L'adresse de contact n'est pas encore renseignée sur cette page.")
                else:
                    if smtp:
                        try:
                            envoyer_email(smtp, destinataire, nom_contact.strip(), email_contact.strip(), message_contact.strip())
                            st.session_state["pf_flash"] = "Votre message a bien été envoyé."
                            st.rerun()
                        except Exception as erreur_envoi:
                            st.error(f"L'envoi a échoué ({type(erreur_envoi).__name__}).")
                    else:
                        sujet = quote(f"Message de {nom_contact.strip()} - {NOM_PROJET}")
                        corps = quote(f"Nom : {nom_contact.strip()}\nEmail : {email_contact.strip()}\n\nMessage :\n{message_contact.strip()}")
                        mailto_url = f"mailto:{destinataire}?subject={sujet}&body={corps}"
                        
                        st.markdown(
                            f'''
                            <div style="margin-top: 1rem;">
                                <a href="{mailto_url}" target="_blank" style="
                                    background-color: #10b981; 
                                    color: #030712; 
                                    padding: 0.75rem 1.5rem; 
                                    border-radius: 12px; 
                                    font-weight: 700; 
                                    text-decoration: none; 
                                    display: flex; 
                                    align-items: center; 
                                    justify-content: center; 
                                    box-shadow: 0 6px 18px rgba(16,185,129,.25);">
                                     Cliquer ici pour envoyer le message via votre application e-mail
                                </a>
                            </div>
                            ''',
                            unsafe_allow_html=True
                        )

    _fenetre()


# ============================================================
# 9. EN-TÊTE : BANNIÈRE, PHOTO CARRÉE, BOUTONS, IDENTITÉ
# ============================================================

def hero_html(profil: dict) -> str:
    photo = photo_data_uri(profil)
    initiales = "".join(mot[0] for mot in profil["nom"].split()[:2]).upper() or "?"
    contenu_photo = f'<img class="pf-img" src="{photo}" alt="{esc(profil["nom"])}">' if photo else esc(initiales)
    return compact(f"""
        <div class="pf-hero">
            <div class="pf-banner">
                <div class="pf-banner-text">
                    <div class="pf-projet">{esc(NOM_PROJET)}</div>
                    <div class="pf-accroche">{esc(ACCROCHE_PROJET)}</div>
                </div>
            </div>
            <div class="pf-photo">{contenu_photo}
                <div class="pf-photo-badge">{icone("code", 22, "#030712")}</div>
            </div>
        </div>
    """)


def identite_html(profil: dict) -> str:
    meta = [("pin", profil["ville"]), ("cpu", META_LIGNE[0]), ("database", META_LIGNE[1])]
    if profil["telephone"]:
        meta.append(("phone", profil["telephone"]))
    meta_html = "".join(f"<span>{icone(cle, 18)}{esc(texte)}</span>" for cle, texte in meta if texte)
    return compact(f"""
        <div class="pf-identite">
            <div class="pf-ligne-nom">
                <div class="pf-nom">{esc(profil["nom"])}</div>
                <span class="badge-emerald">{icone("terminal", 16)}{esc(BADGE_ROLE)}</span>
            </div>
            <div class="pf-titre">{esc(profil["titre"])}</div>
            <div class="pf-meta">{meta_html}</div>
        </div>
    """)


def display_profile_header(profil: dict) -> None:
    st.markdown(hero_html(profil), unsafe_allow_html=True)

    with conteneur("pf_actions"):
        col_contact, col_gh, col_li = st.columns([1.5, 1.1, 1.1], gap="small")
        
        with col_contact:
            if avec_icone(st.button, "Contacter le Développeur", ":material/mail:", key="pf_btn_contact",
                          use_container_width=True):
                ouvrir_contact(profil)

        with col_gh:
            url_github = profil.get("github", "https://github.com")
            if not lien_valide(url_github):
                url_github = "https://github.com"
            avec_icone(st.link_button, "Mon GitHub", ":material/code:", url=url_github,
                       key="pf_link_github", use_container_width=True)

        with col_li:
            url_linkedin = profil.get("linkedin", "https://linkedin.com")
            if not lien_valide(url_linkedin):
                url_linkedin = "https://linkedin.com"
            avec_icone(st.link_button, "Mon LinkedIn", ":material/work:", url=url_linkedin,
                       key="pf_link_linkedin", use_container_width=True)
    st.markdown(identite_html(profil), unsafe_allow_html=True)


# ============================================================
# 10. PROJET : À PROPOS, ARCHITECTURE, MÉTRIQUES, COLLABORATION
# ============================================================

def a_propos_html(profil: dict) -> str:
    points = "".join(f'<div class="pf-point">{icone("check", 20)}<span>{esc(p)}</span></div>' for p in POINTS_FORTS)
    bio = esc(profil["bio"]).replace("tracker_marrakech", '<span class="pf-code">tracker_marrakech</span>')
    return compact(f"""
        <div class="pf-card">
            <div class="pf-card-titre">{icone("sparkle", 26)}À Propos du Projet : {esc(NOM_PROJET)}</div>
            <div class="pf-card-texte">{bio}</div>
            <div class="pf-points">{points}</div>
        </div>
    """)


def architecture_html() -> str:
    cartes = "".join(
        compact(f"""
            <div class="pf-archi-carte">
                <div class="pf-archi-titre">{icone(carte["icone"], 20)}{esc(carte["titre"])}</div>
                <div class="pf-archi-desc">{esc(carte["description"])}</div>
                <span class="pf-archi-tags">{esc(carte["tags"])}</span>
            </div>
        """)
        for carte in ARCHITECTURE
    )
    return compact(f"""
        <div class="pf-section-titre">{icone("layers", 26)}Architecture &amp; Stack Technique</div>
        <div class="pf-archi">{cartes}</div>
    """)


def metriques_html() -> str:
    tuiles = "".join(
        f'<div class="pf-metrique"><div class="pf-valeur">{formater_nombre(valeur)}</div>'
        f'<div class="pf-libelle">{esc(libelle)}</div></div>'
        for libelle, valeur in metriques_du_tracker().items()
    )
    return compact(f"""
        <div class="pf-card">
            <div class="pf-metriques-titre">Métriques du Tracker</div>
            <div class="pf-metriques">{tuiles}</div>
        </div>
    """)


def display_project_architecture_and_metrics(profil: dict) -> None:
    st.markdown("<br>", unsafe_allow_html=True)
    col_arch, col_metrics = st.columns([1.5, 1], gap="large")

    with col_arch:
        st.markdown(a_propos_html(profil), unsafe_allow_html=True)
        st.markdown(architecture_html(), unsafe_allow_html=True)

    with col_metrics:
        st.markdown(metriques_html(), unsafe_allow_html=True)
        st.write("")
        with conteneur("pf_collab"):
            st.markdown(compact(f"""
                <div class="pf-collab-titre">{icone("zap", 24)}Collaboration</div>
                <div class="pf-collab-texte">Vous êtes recruteur, entreprise ou développeur à Marrakech ?
                Rejoignez ou intégrez {esc(NOM_PROJET)} dans vos workflows.</div>
            """), unsafe_allow_html=True)
            if st.button("Démarrer un échange", key="pf_btn_echange", use_container_width=True):
                ouvrir_contact(profil)


# ============================================================
# 11. INFORMATIONS PERSONNELLES (Mode Bascule / Toggle)
# ============================================================

def display_personal_information(profil: dict) -> None:
    if "mode_edition_profil" not in st.session_state:
        st.session_state.mode_edition_profil = False

    if not st.session_state.mode_edition_profil:
        col_btn, _ = st.columns([1.5, 2.5])
        with col_btn:
            if avec_icone(st.button, "Modifier les informations", ":material/edit:", key="btn_ouvrir_edition", use_container_width=True):
                st.session_state.mode_edition_profil = True
                st.rerun()
        return

    st.markdown("## Modifier les informations personnelles")

    with st.form("form_profile"):
        col1, col2 = st.columns(2)
        with col1:
            nom = st.text_input("Nom complet", value=profil["nom"])
            titre = st.text_input("Titre professionnel", value=profil["titre"])
            email = st.text_input("Adresse e-mail (destinataire des messages)", value=profil["email"])
            telephone = st.text_input("Téléphone", value=profil["telephone"])
        with col2:
            ville = st.text_input("Ville", value=profil["ville"])
            linkedin = st.text_input("LinkedIn (https://...)", value=profil["linkedin"])
            github = st.text_input("GitHub (https://...)", value=profil["github"])

        bio = st.text_area("Présentation du projet", value=profil["bio"], height=120)
        
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            sauvegarder = st.form_submit_button("Enregistrer les modifications", use_container_width=True)
        with col_cancel:
            annuler = st.form_submit_button("Annuler", use_container_width=True)

    if annuler:
        st.session_state.mode_edition_profil = False
        st.rerun()

    if sauvegarder:
        if email.strip() and not EMAIL_VALIDE.match(email.strip()):
            st.error("Adresse e-mail invalide.")
        elif any(lien.strip() and not lien_valide(lien.strip()) for lien in (linkedin, github)):
            st.error("Les liens LinkedIn et GitHub doivent commencer par https://")
        else:
            profil.update({
                "nom": nom.strip() or profil["nom"], "titre": titre.strip(), "email": email.strip(),
                "telephone": telephone.strip(), "ville": ville.strip(), "linkedin": linkedin.strip(),
                "github": github.strip(), "bio": bio.strip(),
            })
            st.session_state.profile_data = profil
            if not sauvegarder_profil(profil):
                st.warning("Profil mis à jour, mais impossible de l'enregistrer sur le disque.")
            
            st.session_state.mode_edition_profil = False
            st.session_state["pf_flash"] = "Profil mis à jour avec succès."
            st.rerun()

    with st.expander(" Modifier la photo"):
        fichier = st.file_uploader("Importer une image (recadrée automatiquement en carré)",
                                   type=["png", "jpg", "jpeg"], key="uploader_photo")
        if fichier is not None and st.button("Enregistrer la photo", key="pf_btn_photo"):
            ok, message = enregistrer_photo(fichier, profil)
            if ok:
                st.session_state["pf_flash"] = message
                st.rerun()
            st.error(message)


# ============================================================
# 12. COMPÉTENCES
# ============================================================

def display_skills(profil: dict) -> None:
    st.markdown("## Compétences Techniques")
    competences = profil["competences"]

    if competences:
        tags = "".join(f'<div class="skill-tag">{esc(c)}</div>' for c in competences)
        st.markdown(f'<div class="pf-skills">{tags}</div>', unsafe_allow_html=True)
    else:
        st.info("Aucune compétence enregistrée.")

    if EDITION_AUTORISEE:
        with st.expander("Modifier mes compétences"):
            nouvelles = st.text_area("Séparez les compétences par des virgules", value=", ".join(competences))
            if st.button("Mettre à jour les compétences", key="pf_btn_competences"):
                liste = [item.strip()[:40] for item in nouvelles.split(",") if item.strip()]
                profil["competences"] = list(dict.fromkeys(liste))[:30]
                st.session_state.profile_data = profil
                sauvegarder_profil(profil)
                st.session_state["pf_flash"] = "Compétences mises à jour."
                st.rerun()


# ============================================================
# 13. PAGE PRINCIPALE
# ============================================================

def show_profile() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    message = st.session_state.pop("pf_flash", None)
    if message:
        st.toast(message)

    profil = get_profile_data()
    display_profile_header(profil)
    display_project_architecture_and_metrics(profil)
    st.divider()
    display_skills(profil)

    if EDITION_AUTORISEE:
        st.divider()
        display_personal_information(profil)

    st.markdown(
        f'<div style="text-align:center; color:#64748b; font-size:12px; padding:25px;">'
        f'© 2026 {esc(profil["nom"])} • {esc(NOM_PROJET)} (tracker_marrakech) • {esc(profil["ville"])}</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# 14. EXÉCUTION
# ============================================================

if __name__ == "__main__":
    show_profile()