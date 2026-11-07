"""Assistant IA du projet Marrakech OpportunityHub (Groq + appel d'outils).

L'assistant ne reçoit plus un extrait de tous les CSV dans son prompt. Il dispose
d'outils pour interroger les données (recherche, comptage, statistiques) et pour
lire le code du projet, ce qui lui permet de répondre à toute question sur le
projet sans dépasser les limites de taille de l'API.
"""
import base64
import inspect
import json
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from groq import Groq
except ImportError:  # le message d'erreur s'affichera dans le chat
    Groq = None

# =====================================================
# RÉGLAGES
# =====================================================

RACINE = Path(__file__).resolve().parents[2]          # racine du projet
DOSSIER_FRONTEND = Path(__file__).resolve().parent

# Modèles essayés dans cet ordre (seuls ceux réellement disponibles sur ton compte sont utilisés).
# Les modèles llama-3.3-70b-versatile et llama-3.1-8b-instant ont été retirés par Groq le 16/08/2026.
# Pour imposer un modèle : ajoute GROQ_MODEL=nom_du_modele dans le fichier .env.
MODELES_PREFERES = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]
MODELES_NON_CHAT = ("whisper", "guard", "tts", "orpheus", "playai", "embed", "safeguard", "compound")
MAX_TOURS_OUTILS = 5            # nombre maximum d'appels d'outils par question
HISTORIQUE_MAX = 12             # messages de la conversation envoyés au modèle
RESULTAT_MAX_CARACTERES = 4500  # taille maximale du résultat d'un outil
AUTORISER_LECTURE_CODE = True   # False : l'assistant ne peut pas lire les fichiers du projet

DOSSIERS_EXCLUS = {
    ".venv", "venv", "env", "node_modules", "__pycache__", "site-packages",
    ".git", ".pytest_cache", ".idea", ".vscode", ".streamlit",
}
EXTENSIONS_LISIBLES = {".py", ".md", ".txt", ".cfg", ".ini", ".toml", ".yml", ".yaml"}

DOCUMENTATION_PROJET = """
Marrakech OpportunityHub est une application Streamlit (Python) qui centralise la recherche de
stages et d'emplois à Marrakech, surtout dans l'IA, la data et la tech.

PAGES (menu de gauche) :
1. Tableau de bord : 5 indicateurs (Entreprises, Cibles IA/Tech, Secteurs IA/Data/Tech, Offres
   totales, Postuler = relances à faire), la date et l'heure, puis des graphiques : secteurs, top
   priorités, scores et notes, analyses multivariées (bulles, nuage 3D, barres empilées, boîtes à
   moustaches, violons, radar, treemap, sunburst, Sankey, mosaïque, dendrogramme), ACP et groupes
   d'entreprises, qualité des données (complétude).
2. Entreprises : répertoire des entreprises cibles (IA, Tech, ESN, agences web). Filtres Pertinence
   et Secteur, métriques (entreprises affichées, note moyenne sur 5, emails valides). Chaque carte
   montre la note, la pertinence, l'adresse, le téléphone, le site web et l'email, avec les boutons
   Postuler (page carrière), Contacter par email (candidature spontanée) et Localisation (Google
   Maps). Pagination par 10.
3. Offres d'emploi : offres collectées (fichiers offres_*.csv, par exemple offres_reelles_marrakech.csv).
   Recherche par mot-clé, filtres Quartier, Source, Contrat, case « Marrakech uniquement ». Cartes avec
   badges et page Détails (description, informations complémentaires, carte Google Maps). Pagination.
4. Suivi des candidatures : suivi des candidatures envoyées et des relances à faire
   (données dans data/tracking, code dans pages/tracker.py).
5. Créer mon CV : formulaire (informations personnelles, photo, profil, compétences, expériences,
   projets, formation, certifications, langues, centres d'intérêt). On peut cibler une offre pour
   pré-remplir le poste et le profil. Génère un CV au format PDF (reportlab).
6. Évaluation du CV : import d'un CV PDF. Score indicatif sur 100 (coordonnées 15, profil 10,
   formation 15, compétences 20, expériences et projets 15, structure 10, langues 5), détection des
   compétences, puis adéquation avec les offres : compétences 60 %, expérience 25 %, intitulé du
   poste 15 %. Verdict : « Correspond bien » à partir de 70/100, « Correspond partiellement » à
   partir de 45, sinon « Ne correspond pas ». Un rapport texte est téléchargeable.
Assistant : le bouton flottant en bas à droite (c'est toi).

ARCHITECTURE : stages_marrakech/backend (collect, clean, explore, quality, analyze, visualize,
tracking, pipeline, export, config, utils, errors), stages_marrakech/frontend (app.py, pages/,
services.py, ui.py, safe.py, agent_chat.py, errors_ui.py, assets/), stages_marrakech/data
(raw, clean, tracking). Technologies : Streamlit, pandas, plotly, reportlab, PyMuPDF, Groq.
Pour les détails de calcul (scores, priorités, pipeline), lis le code avec lire_fichier_projet.
"""

# =====================================================
# OUTILS GÉNÉRIQUES
# =====================================================

def _norm(texte):
    """Minuscules sans accents, pour comparer des textes."""
    t = unicodedata.normalize("NFKD", str(texte or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _court(valeur, n=300):
    texte = str(valeur).strip()
    return texte if len(texte) <= n else texte[: n - 1] + "…"


def _json(objet):
    texte = json.dumps(objet, ensure_ascii=False, default=str)
    if len(texte) > RESULTAT_MAX_CARACTERES:
        texte = texte[:RESULTAT_MAX_CARACTERES] + " … [résultat tronqué : affine ta recherche]"
    return texte


def _parcourir():
    """Liste tous les fichiers du projet (sans .venv, .git, .streamlit, etc.)."""
    for dossier, sous_dossiers, fichiers in os.walk(RACINE):
        sous_dossiers[:] = [
            d for d in sous_dossiers if d not in DOSSIERS_EXCLUS and not d.startswith(".")
        ]
        for nom in fichiers:
            yield Path(dossier) / nom


def _liste_arg(valeur):
    """Accepte une liste, ou une chaîne « a, b »."""
    if isinstance(valeur, list):
        return [str(v) for v in valeur]
    if isinstance(valeur, str) and valeur.strip():
        return [v.strip() for v in valeur.split(",") if v.strip()]
    return []


def _dict_arg(valeur):
    """Accepte un dictionnaire, ou une chaîne JSON."""
    if isinstance(valeur, dict):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            resultat = json.loads(valeur)
            return resultat if isinstance(resultat, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


# =====================================================
# DONNÉES (tous les CSV du projet, mis en cache)
# =====================================================

def _lire_csv(chemin):
    for encodage in ("utf-8-sig", "latin-1"):
        for sep in (None, ","):
            try:
                return pd.read_csv(
                    chemin, dtype=str, keep_default_na=False,
                    sep=sep, engine="python", encoding=encodage,
                )
            except UnicodeDecodeError:
                break
            except Exception:
                continue
    return None


def _signature_csv():
    fichiers = []
    for f in _parcourir():
        nom = f.name.lower()
        if f.suffix.lower() == ".csv" and "test" not in nom and "export" not in nom:
            try:
                fichiers.append((str(f), f.stat().st_mtime))
            except OSError:
                pass
    return tuple(sorted(fichiers))


@st.cache_data(show_spinner=False, max_entries=2)
def _charger_tables(signature):
    tables, textes, chemins = {}, {}, {}
    for chemin_str, _ in signature:
        f = Path(chemin_str)
        df = _lire_csv(f)
        if df is None or df.empty:
            continue
        nom = f.stem if f.stem not in tables else f"{f.parent.name}/{f.stem}"
        tables[nom] = df
        chemins[nom] = str(f.relative_to(RACINE))
        textes[nom] = df.astype(str).agg(" ".join, axis=1).map(_norm)
    return tables, textes, chemins


def _donnees():
    return _charger_tables(_signature_csv())


def _trouver_table(tables, nom):
    cible = _norm(nom).replace(".csv", "").strip()
    for n in tables:
        if _norm(n) == cible:
            return n
    for n in tables:
        if cible and cible in _norm(n):
            return n
    return None


def _trouver_colonne(df, nom):
    cible = _norm(nom).strip()
    for c in df.columns:
        if _norm(c).strip() == cible:
            return c
    for c in df.columns:
        if cible and cible in _norm(c):
            return c
    return None


def _selection(table, mots_cles, filtres):
    """Retourne (nom, df, lignes_sélectionnées) ou (None, None, erreur_json)."""
    tables, textes, _ = _donnees()
    nom = _trouver_table(tables, table)
    if nom is None:
        return None, None, _json({"erreur": f"Table inconnue : {table}",
                                  "tables_disponibles": list(tables)})
    df = tables[nom]
    masque = pd.Series(True, index=df.index)
    for mot in _norm(mots_cles).split():
        masque &= textes[nom].str.contains(re.escape(mot), regex=True, na=False)
    for colonne, valeur in _dict_arg(filtres).items():
        c = _trouver_colonne(df, colonne)
        if c is None:
            return None, None, _json({"erreur": f"Colonne inconnue : {colonne}",
                                      "colonnes_disponibles": list(df.columns)})
        masque &= df[c].map(_norm).str.contains(re.escape(_norm(valeur)), regex=True, na=False)
    return nom, df, df[masque]


# =====================================================
# OUTILS EXPOSÉS AU MODÈLE
# =====================================================

def outil_lister_tables():
    tables, _, chemins = _donnees()
    if not tables:
        return _json({"erreur": "Aucun fichier CSV trouvé dans le projet."})
    return _json({"tables": [
        {"nom": n, "fichier": chemins[n], "nb_lignes": len(df), "colonnes": list(df.columns)}
        for n, df in tables.items()
    ]})


def outil_rechercher(table, mots_cles="", filtres=None, colonnes=None, limite=10):
    nom, df, sel = _selection(table, mots_cles, filtres)
    if nom is None:
        return sel
    try:
        limite = max(1, min(int(limite), 20))
    except (TypeError, ValueError):
        limite = 10
    cols = [c for c in (_trouver_colonne(df, c) for c in _liste_arg(colonnes)) if c]
    cols = cols or list(df.columns)
    lignes = [
        {c: _court(ligne[c]) for c in cols if str(ligne[c]).strip()}
        for _, ligne in sel.head(limite)[cols].iterrows()
    ]
    return _json({"table": nom, "total_correspondances": int(len(sel)),
                  "affichees": len(lignes), "lignes": lignes})


def outil_compter_par(table, colonne, top=15, mots_cles="", filtres=None):
    nom, df, sel = _selection(table, mots_cles, filtres)
    if nom is None:
        return sel
    c = _trouver_colonne(df, colonne)
    if c is None:
        return _json({"erreur": f"Colonne inconnue : {colonne}",
                      "colonnes_disponibles": list(df.columns)})
    serie = sel[c].astype(str).str.strip()
    comptes = serie[serie != ""].value_counts()
    try:
        top = max(1, min(int(top), 50))
    except (TypeError, ValueError):
        top = 15
    return _json({
        "table": nom, "colonne": c, "lignes_selectionnees": int(len(sel)),
        "valeurs_distinctes": int(len(comptes)),
        "repartition": [{"valeur": v, "nombre": int(n)} for v, n in comptes.head(top).items()],
    })


def outil_statistiques(table, colonne, mots_cles="", filtres=None, min_valeur=None, max_valeur=None):
    nom, df, sel = _selection(table, mots_cles, filtres)
    if nom is None:
        return sel
    c = _trouver_colonne(df, colonne)
    if c is None:
        return _json({"erreur": f"Colonne inconnue : {colonne}",
                      "colonnes_disponibles": list(df.columns)})
    valeurs = pd.to_numeric(sel[c].astype(str).str.replace(",", ".", regex=False), errors="coerce").dropna()
    try:
        if min_valeur is not None:
            valeurs = valeurs[valeurs >= float(min_valeur)]
        if max_valeur is not None:
            valeurs = valeurs[valeurs <= float(max_valeur)]
    except (TypeError, ValueError):
        pass
    if valeurs.empty:
        return _json({"table": nom, "colonne": c, "erreur": "Aucune valeur numérique."})
    return _json({
        "table": nom, "colonne": c, "valeurs_numeriques": int(len(valeurs)),
        "minimum": round(float(valeurs.min()), 3), "maximum": round(float(valeurs.max()), 3),
        "moyenne": round(float(valeurs.mean()), 3), "mediane": round(float(valeurs.median()), 3),
    })


# --- lecture du code du projet -------------------------------------------------

_MOTIFS_SECRETS = [
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "gsk_***"),
    (re.compile(r"GOCSPX-[A-Za-z0-9_\-]{10,}"), "GOCSPX-***"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "AIza***"),
    (re.compile(
        r"""(?i)(api[_-]?key|secret|password|passwd|mot_de_passe|token|client_secret|cookie_secret)"""
        r"""(\s*[=:]\s*)(['"])[^'"\n]{6,}\3"""
    ), r"\1\2\3***\3"),
]


def _masquer_secrets(texte):
    for motif, remplacement in _MOTIFS_SECRETS:
        texte = motif.sub(remplacement, texte)
    return texte


def _fichier_bloque(chemin):
    nom = chemin.name.lower()
    if nom.startswith(".env") or nom == "secrets.toml" or nom.endswith((".pem", ".key", ".p12")) or nom == "id_rsa":
        return True
    return any(p in DOSSIERS_EXCLUS or p.startswith(".") for p in chemin.relative_to(RACINE).parts[:-1])


def _fichier_lisible(chemin):
    return (not _fichier_bloque(chemin)) and (
        chemin.suffix.lower() in EXTENSIONS_LISIBLES or chemin.name == "Dockerfile"
    )


def outil_lister_fichiers_projet():
    if not AUTORISER_LECTURE_CODE:
        return _json({"erreur": "La lecture des fichiers du projet est désactivée."})
    fichiers = sorted(str(f.relative_to(RACINE)) for f in _parcourir() if _fichier_lisible(f))
    return _json({"racine": RACINE.name, "fichiers": fichiers[:200]})


def outil_lire_fichier_projet(chemin, debut=1, fin=None):
    if not AUTORISER_LECTURE_CODE:
        return _json({"erreur": "La lecture des fichiers du projet est désactivée."})
    racine = RACINE.resolve()
    cible = (RACINE / str(chemin)).resolve()
    if not (cible.is_file() and cible.is_relative_to(racine)):
        # Recherche par nom de fichier (ex. « dashboard.py »)
        nom = Path(str(chemin)).name.lower()
        candidats = [f for f in _parcourir() if f.name.lower() == nom and _fichier_lisible(f)]
        if not candidats:
            return _json({"erreur": f"Fichier introuvable : {chemin}. Utilise lister_fichiers_projet."})
        cible = candidats[0].resolve()
    if not _fichier_lisible(cible):
        return _json({"erreur": "Ce fichier n'est pas lisible (type non autorisé ou fichier sensible)."})
    try:
        lignes = cible.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return _json({"erreur": str(e)})
    try:
        debut = max(1, int(debut or 1))
        fin = min(len(lignes), int(fin)) if fin else min(len(lignes), debut + 199)
    except (TypeError, ValueError):
        debut, fin = 1, min(len(lignes), 200)
    extrait = "\n".join(f"{i}: {l}" for i, l in enumerate(lignes[debut - 1:fin], start=debut))
    return _json({
        "fichier": str(cible.relative_to(racine)), "lignes_totales": len(lignes),
        "debut": debut, "fin": fin, "contenu": _masquer_secrets(extrait),
    })


FONCTIONS_OUTILS = {
    "lister_tables": outil_lister_tables,
    "rechercher": outil_rechercher,
    "compter_par": outil_compter_par,
    "statistiques": outil_statistiques,
    "lister_fichiers_projet": outil_lister_fichiers_projet,
    "lire_fichier_projet": outil_lire_fichier_projet,
}

_FILTRES_DOC = {
    "type": "object",
    "additionalProperties": {"type": "string"},
    "description": "Filtres {colonne: texte contenu}, ex. {\"secteur\": \"IA\", \"ville\": \"Marrakech\"}.",
}

OUTILS = [
    {"type": "function", "function": {
        "name": "lister_tables",
        "description": "Liste les tables de données (fichiers CSV du projet) avec leur nombre de lignes et leurs colonnes. À appeler en premier pour toute question sur les données.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "rechercher",
        "description": "Recherche des lignes dans une table. Tous les mots-clés doivent apparaître dans la ligne (sans tenir compte des accents). Retourne le nombre total de correspondances et les premières lignes.",
        "parameters": {"type": "object", "properties": {
            "table": {"type": "string", "description": "Nom de la table (voir lister_tables)."},
            "mots_cles": {"type": "string", "description": "Mots recherchés, séparés par des espaces. Vide = toutes les lignes."},
            "filtres": _FILTRES_DOC,
            "colonnes": {"type": "array", "items": {"type": "string"}, "description": "Colonnes à afficher (par défaut toutes)."},
            "limite": {"type": "integer", "description": "Nombre de lignes à afficher (max 20)."}},
            "required": ["table"]}}},
    {"type": "function", "function": {
        "name": "compter_par",
        "description": "Répartition (nombre de lignes par valeur) d'une colonne, par exemple le nombre d'entreprises par secteur ou d'offres par contrat.",
        "parameters": {"type": "object", "properties": {
            "table": {"type": "string"}, "colonne": {"type": "string"},
            "top": {"type": "integer", "description": "Nombre de valeurs à afficher (max 50)."},
            "mots_cles": {"type": "string"}, "filtres": _FILTRES_DOC},
            "required": ["table", "colonne"]}}},
    {"type": "function", "function": {
        "name": "statistiques",
        "description": "Statistiques (minimum, maximum, moyenne, médiane) d'une colonne numérique. Pour les notes, utilise min_valeur=0 et max_valeur=5 car certaines valeurs sont aberrantes.",
        "parameters": {"type": "object", "properties": {
            "table": {"type": "string"}, "colonne": {"type": "string"},
            "mots_cles": {"type": "string"}, "filtres": _FILTRES_DOC,
            "min_valeur": {"type": "number"}, "max_valeur": {"type": "number"}},
            "required": ["table", "colonne"]}}},
    {"type": "function", "function": {
        "name": "lister_fichiers_projet",
        "description": "Liste les fichiers de code et de documentation du projet (arborescence).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "lire_fichier_projet",
        "description": "Lit un fichier du projet (code Python, README...) par tranche de 200 lignes. Sert à expliquer le fonctionnement de l'application, les calculs de scores, le pipeline, etc.",
        "parameters": {"type": "object", "properties": {
            "chemin": {"type": "string", "description": "Chemin relatif ou simple nom de fichier, ex. 'analyze.py'."},
            "debut": {"type": "integer"}, "fin": {"type": "integer"}},
            "required": ["chemin"]}}},
]


def executer_outil(nom, arguments_json):
    fonction = FONCTIONS_OUTILS.get(nom)
    if fonction is None:
        return _json({"erreur": f"Outil inconnu : {nom}"})
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    parametres = inspect.signature(fonction).parameters
    arguments = {k: v for k, v in arguments.items() if k in parametres}
    try:
        return fonction(**arguments)
    except TypeError as e:
        return _json({"erreur": f"Arguments invalides : {e}"})
    except Exception as e:  # un outil ne doit jamais faire planter le chat
        return _json({"erreur": f"{type(e).__name__} : {e}"})


# =====================================================
# MODÈLE
# =====================================================

_MOTIF_CLE_FICHIER = re.compile(r"""(?mi)^\s*GROQ_API_KEY\s*[=:]\s*["']?([^"'\s#]+)["']?""")


def _cle_dans_fichier(chemin):
    """Lit GROQ_API_KEY directement dans un fichier texte (.env ou secrets.toml),
    même si le fichier a une erreur de syntaxe ailleurs (ex. section [auth] en double)."""
    try:
        correspondance = _MOTIF_CLE_FICHIER.search(chemin.read_text(encoding="utf-8-sig", errors="replace"))
    except OSError:
        return None
    return correspondance.group(1) if correspondance else None


def _cle_api():
    """Retourne (clé, diagnostic). Sources, dans l'ordre : st.secrets, variable d'environnement,
    fichier .env, lecture directe de .streamlit/secrets.toml."""
    diagnostic = []
    candidates = []

    try:
        cle = st.secrets.get("GROQ_API_KEY")
        if cle:
            candidates.append(("secrets.toml", str(cle)))
        else:
            diagnostic.append("secrets.toml lisible mais sans GROQ_API_KEY à la racine "
                              "(la ligne doit être placée avant toute section [...])")
    except Exception as erreur:
        diagnostic.append(f"secrets.toml illisible ({type(erreur).__name__}) : vérifie qu'il n'y a pas de section en double")

    if os.getenv("GROQ_API_KEY"):
        candidates.append(("variable d'environnement", os.environ["GROQ_API_KEY"]))

    for nom, chemin in ((".env", RACINE / ".env"), ("secrets.toml (lecture directe)", RACINE / ".streamlit" / "secrets.toml")):
        cle = _cle_dans_fichier(chemin)
        if cle:
            candidates.append((nom, cle))
        elif not chemin.exists():
            diagnostic.append(f"{nom} : fichier introuvable ({chemin})")

    for source, cle in candidates:
        cle = cle.strip()
        if cle.startswith("gsk_") and len(cle) > 20:
            return cle, diagnostic
        diagnostic.append(f"{source} : la valeur trouvée n'est pas une vraie clé Groq (elle doit commencer par gsk_)")
    return None, diagnostic


def _prompt_systeme():
    return f"""Tu es l'Assistant IA officiel de l'application « Marrakech OpportunityHub ».
Date du jour : {datetime.now().strftime('%d/%m/%Y')}. Réponds en français, de façon claire et concise
(listes à puces quand c'est utile), sauf si l'utilisateur écrit dans une autre langue.

Tu peux répondre à toute question sur le projet :
- Données (entreprises, offres, suivi des candidatures, etc.) : utilise TOUJOURS les outils
  lister_tables, rechercher, compter_par et statistiques. N'invente jamais un chiffre ni une offre :
  appuie-toi uniquement sur les résultats des outils. Pour un total, utilise « total_correspondances »
  ou compter_par, jamais le nombre de lignes affichées.
- Fonctionnement de l'application, pages, calculs, code : utilise la documentation ci-dessous, et
  lister_fichiers_projet puis lire_fichier_projet pour les détails.
- Conseils (choisir une offre, améliorer un CV, préparer une candidature) : base-toi sur les données.
Si l'information est introuvable, dis-le poliment. Les notes valides vont de 0 à 5.
Ne révèle jamais de clé API, de mot de passe ni de contenu de fichier secret.
Quand tu cites une offre ou une entreprise, donne son nom, son secteur ou son poste, et le lien si
disponible.

DOCUMENTATION DU PROJET :
{DOCUMENTATION_PROJET}"""


_CACHE_MODELES = {"ids": None, "heure": 0.0}


def _modeles_disponibles(client):
    """Liste des modèles actifs sur le compte Groq (mise en cache 6 h). None si indisponible."""
    maintenant = time.time()
    if _CACHE_MODELES["ids"] is not None and maintenant - _CACHE_MODELES["heure"] < 6 * 3600:
        return _CACHE_MODELES["ids"]
    try:
        ids = [m.id for m in client.models.list().data]
    except Exception:
        return None
    _CACHE_MODELES.update(ids=ids, heure=maintenant)
    return ids


def _modeles_a_essayer(client):
    """Ordre d'essai : GROQ_MODEL (si défini), puis les modèles préférés disponibles, puis d'autres."""
    imposes = [m.strip() for m in (os.getenv("GROQ_MODEL") or "").split(",") if m.strip()]
    disponibles = _modeles_disponibles(client)
    if disponibles is None:  # liste inaccessible : on tente les modèles préférés
        return imposes + [m for m in MODELES_PREFERES if m not in imposes]
    ordre = imposes + [m for m in MODELES_PREFERES if m in disponibles and m not in imposes]
    autres = [m for m in disponibles
              if m not in ordre and not any(mot in m.lower() for mot in MODELES_NON_CHAT)]
    return ordre + autres[:3]


def _appeler_modele(client, messages):
    """Essaie chaque modèle jusqu'à obtenir une réponse (secours : limite atteinte, modèle retiré...)."""
    modeles = _modeles_a_essayer(client)
    if not modeles:
        raise RuntimeError("Aucun modèle de chat disponible sur ce compte Groq.")
    erreurs = []
    for modele in modeles:
        try:
            return client.chat.completions.create(
                model=modele, messages=messages, tools=OUTILS,
                tool_choice="auto", temperature=0.2, max_tokens=4096,
            )
        except Exception as erreur:
            erreurs.append(f"{modele} : {str(erreur)[:160]}")
    raise RuntimeError("Aucun modèle n'a répondu. " + " | ".join(erreurs[:3]))


def generer_reponse(historique_messages):
    cle, diagnostic = _cle_api()
    if not cle:
        details = "\n".join(f"- {d}" for d in diagnostic) or "- aucune source de clé trouvée"
        return ("⚠️ La clé API Groq est introuvable ou invalide.\n\n"
                f"{details}\n\n"
                "Ajoute `GROQ_API_KEY=gsk_...` dans un fichier `.env` à la racine du projet, "
                "puis relance Streamlit.")
    if Groq is None:
        return "⚠️ Le module `groq` n'est pas installé. Lance : `pip install groq`."

    client = Groq(api_key=cle)
    messages = [{"role": "system", "content": _prompt_systeme()}]
    for msg in historique_messages[-HISTORIQUE_MAX:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        for _ in range(MAX_TOURS_OUTILS + 1):
            reponse = _appeler_modele(client, messages)
            message = reponse.choices[0].message
            if not message.tool_calls:
                return message.content or "Je n'ai pas de réponse à te proposer."
            messages.append({
                "role": "assistant", "content": message.content or "",
                "tool_calls": [{
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                } for tc in message.tool_calls],
            })
            for tc in message.tool_calls:
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": executer_outil(tc.function.name, tc.function.arguments),
                })
        return "Je n'ai pas réussi à terminer l'analyse. Peux-tu reformuler ou préciser ta question ?"
    except Exception as erreur:
        texte = str(erreur)
        if "429" in texte or "rate" in texte.lower():
            return "⏳ La limite d'utilisation de l'API Groq est atteinte. Réessaie dans une minute."
        return f"Désolé, une erreur s'est produite : {texte[:300]}"


def charger_toutes_les_donnees():
    """Résumé des tables disponibles (conservé pour compatibilité)."""
    return outil_lister_tables()


# =====================================================
# INTERFACE : BOUTON FLOTTANT + POPOVER
# =====================================================

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except (FileNotFoundError, OSError):
        return None


def _icone_chatbot():
    for chemin in (
        DOSSIER_FRONTEND / "chatbot_icon.png",
        DOSSIER_FRONTEND / "assets" / "chatbot_icon.png",
        DOSSIER_FRONTEND / "assets" / "logo_icon.png",
    ):
        img = get_base64_image(chemin)
        if img:
            return img
    return None


CSS_ASSISTANT = """
<style>
/* Le conteneur du popover ne doit plus s'étendre sur toute la largeur : simple bouton rond */
div[data-testid="stPopover"] {
    position: fixed !important; bottom: 30px !important; right: 30px !important;
    left: auto !important; top: auto !important;
    width: 65px !important; min-width: 0 !important; z-index: 999999 !important;
}
div[data-testid="stPopover"] button, button[data-testid="stPopoverButton"] {
    width: 65px !important; height: 65px !important; min-height: 0 !important;
    padding: 0 !important; border-radius: 50% !important; border: 3px solid white !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important; transition: transform 0.2s ease !important;
    __BOUTON__
}
div[data-testid="stPopover"] button:hover { transform: scale(1.1) !important; }
div[data-testid="stPopover"] button > * { display: none !important; }
div[data-testid="stPopoverBody"] {
    width: min(380px, 92vw) !important; max-height: 85vh !important;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2) !important; border-radius: 15px !important;
    margin-bottom: 10px !important;
}
</style>
"""


def afficher_chatbot_flottant():
    img_b64 = _icone_chatbot()
    if img_b64:
        bouton = (f"background-color: #ffffff !important; background-image: url('data:image/png;base64,{img_b64}') !important; "
                  "background-size: cover !important; background-position: center !important;")
    else:
        bouton = ("background-color: #0b57d0 !important; display: flex !important; "
                  "align-items: center !important; justify-content: center !important;")
    css = CSS_ASSISTANT.replace("__BOUTON__", bouton)
    if not img_b64:
        css += ("<style>div[data-testid=\"stPopover\"] button::after "
                "{ content: '💬'; font-size: 28px; color: white; }</style>")
    st.markdown(css, unsafe_allow_html=True)

    message_accueil = {
        "role": "assistant",
        "content": ("Bonjour ! Je suis l'assistant d'OpportunityHub. Je peux chercher dans vos offres et "
                    "entreprises, faire des statistiques, vous conseiller et expliquer le fonctionnement "
                    "du projet. Que voulez-vous savoir ?"),
    }
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [message_accueil]

    with st.popover("Assistant"):
        titre, effacer = st.columns([3, 2])
        with titre:
            st.markdown("### 🤖 Assistant")
        with effacer:
            if st.button("Nouvelle discussion", key="chat_reset", use_container_width=True):
                st.session_state.chat_history = [message_accueil]
                st.rerun()

        chat_container = st.container(height=350)
        with chat_container:
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        prompt = st.chat_input("Posez une question sur le projet...", key="chat_assistant_input")
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    with st.spinner("Analyse en cours..."):
                        reponse = generer_reponse(st.session_state.chat_history)
                    st.markdown(reponse)
            st.session_state.chat_history.append({"role": "assistant", "content": reponse})