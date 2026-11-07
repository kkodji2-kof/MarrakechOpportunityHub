import os
import sys
from io import BytesIO
from xml.sax.saxutils import escape
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image as PDFImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


# --- IMPORT DU FICHIER SERVICES ---
# On ajoute la racine du projet (Marrakech_opportunityhub) au chemin pour que Python trouve 'stages_marrakech'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

try:
    from stages_marrakech.frontend import services
    from stages_marrakech.backend.errors import DataSourceError
except ImportError as e:
    st.error(f"Erreur d'importation du module services : {e}")

# Remonte le contenu en haut de la page
st.markdown(
    """
<style>
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem; }
    header[data-testid="stHeader"] { background: transparent; height: 2.5rem; }
    .block-container h1 { padding-top: 0 !important; margin-top: 0 !important; }
</style>
""",
    unsafe_allow_html=True,
)

BLEU = colors.HexColor("#2563EB")
TURQUOISE = colors.HexColor("#14B8A6")
TEXTE = colors.HexColor("#0F172A")
GRIS = colors.HexColor("#64748B")
GRIS_CLAIR = colors.HexColor("#E2E8F0")

st.title("CV & Lettre ")
st.caption(
    "Sélectionnez "
)

# ==========================================
# FONCTIONS PDF
# ==========================================
def nettoyer(texte):
  texte = str(texte or "").strip()
  return escape(texte).replace("\n", "<br/>")

def ajouter_section(contenu, titre, texte, styles):
  if texte and texte.strip():
    contenu.append(Paragraph(titre.upper(), styles["SectionCV"]))
    contenu.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_CLAIR, spaceAfter=5))
    contenu.append(Paragraph(nettoyer(texte), styles["TexteCV"]))
    contenu.append(Spacer(1, 3))

def generer_cv(donnees, photo_bytes=None):
  fichier = BytesIO()
  document = SimpleDocTemplate(fichier, pagesize=A4, rightMargin=1.6*cm, leftMargin=1.6*cm, topMargin=1.4*cm, bottomMargin=1.5*cm, title=f"CV - {donnees['nom']}", author=donnees["nom"])
  styles = getSampleStyleSheet()
  styles.add(ParagraphStyle(name="NomCV", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=BLEU, alignment=TA_LEFT, spaceAfter=5))
  styles.add(ParagraphStyle(name="TitreCV", parent=styles["Normal"], fontSize=10, leading=14, textColor=GRIS, spaceAfter=7))
  styles.add(ParagraphStyle(name="SectionCV", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=BLEU, spaceBefore=9, spaceAfter=5, keepWithNext=True))
  styles.add(ParagraphStyle(name="TexteCV", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=TEXTE, spaceAfter=4))
  styles.add(ParagraphStyle(name="PetitCV", parent=styles["BodyText"], fontSize=7.5, leading=10, textColor=GRIS, spaceAfter=3))

  contenu = []
  identite = [Paragraph(nettoyer(donnees["nom"]), styles["NomCV"])]
  if donnees["poste"].strip():
    identite.append(Paragraph(nettoyer(donnees["poste"]), styles["TitreCV"]))
  coordonnees = []
  for cle in ["email", "telephone", "ville", "linkedin"]:
    valeur = donnees.get(cle, "").strip()
    if valeur: coordonnees.append(nettoyer(valeur))
  for coordonnee in coordonnees:
    identite.append(Paragraph(coordonnee, styles["PetitCV"]))

  if photo_bytes:
    photo_flux = BytesIO(photo_bytes)
    photo_pdf = PDFImage(photo_flux, width=3.2*cm, height=3.8*cm, kind="proportional", hAlign="CENTER")
    cellule_photo = photo_pdf
  else:
    cellule_photo = ""

  entete = Table([[identite, cellule_photo]], colWidths=[13.2*cm, 3.8*cm], hAlign="LEFT")
  entete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
  contenu.append(entete)
  contenu.append(Spacer(1, 8))
  contenu.append(HRFlowable(width="100%", thickness=1.5, color=TURQUOISE, spaceAfter=5))

  ajouter_section(contenu, "Profil professionnel", donnees["profil"], styles)
  ajouter_section(contenu, "Compétences techniques", donnees["competences"], styles)
  ajouter_section(contenu, "Expériences professionnelles", donnees["experiences"], styles)
  ajouter_section(contenu, "Projets réalisés", donnees["projets"], styles)
  ajouter_section(contenu, "Formation", donnees["formation"], styles)
  ajouter_section(contenu, "Certifications", donnees["certifications"], styles)
  ajouter_section(contenu, "Langues", donnees["langues"], styles)
  ajouter_section(contenu, "Centres d'intérêt", donnees["interets"], styles)

  def pied_de_page(canvas, doc):
    canvas.saveState()
    largeur, _ = A4
    canvas.setStrokeColor(GRIS_CLAIR)
    canvas.line(1.6*cm, 1.05*cm, largeur - 1.6*cm, 1.05*cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    canvas.drawString(1.6*cm, 0.7*cm, "MarrakechOpportunityHub")
    canvas.drawRightString(largeur - 1.6*cm, 0.7*cm, f"Page {doc.page}")
    canvas.restoreState()

  document.build(contenu, onFirstPage=pied_de_page, onLaterPages=pied_de_page)
  fichier.seek(0)
  return fichier.getvalue()

def generer_lettre_motivation_pdf(donnees, entreprise, offre_titre, texte_lm):
  fichier = BytesIO()
  document = SimpleDocTemplate(fichier, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm, title=f"Lettre_de_motivation - {donnees['nom']}", author=donnees["nom"])
  styles = getSampleStyleSheet()
  styles.add(ParagraphStyle(name="Expediteur", fontName="Helvetica", fontSize=9, leading=13, textColor=TEXTE))
  styles.add(ParagraphStyle(name="Destinataire", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=BLEU, alignment=2))
  styles.add(ParagraphStyle(name="Objet", fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=BLEU, spaceAfter=15))
  styles.add(ParagraphStyle(name="CorpsLM", fontName="Helvetica", fontSize=10, leading=15, textColor=TEXTE, spaceAfter=10))

  contenu = []
  exp_txt = f"<b>{donnees['nom']}</b><br/>{donnees.get('ville', '')}<br/>{donnees.get('telephone', '')} | {donnees.get('email', '')}"
  contenu.append(Paragraph(exp_txt, styles["Expediteur"]))
  contenu.append(Spacer(1, 15))
  dest_txt = f"À l'attention de l'équipe recrutement<br/><b>{entreprise}</b>"
  contenu.append(Paragraph(dest_txt, styles["Destinataire"]))
  contenu.append(Spacer(1, 20))
  contenu.append(Paragraph(f"Objet : Candidature au poste de {offre_titre}", styles["Objet"]))
  contenu.append(Spacer(1, 10))
  for paragraphe in texte_lm.split("\n"):
    if paragraphe.strip():
      contenu.append(Paragraph(nettoyer(paragraphe), styles["CorpsLM"]))
  document.build(contenu)
  fichier.seek(0)
  return fichier.getvalue()

# ==========================================
# CHARGEMENT DES DONNÉES DEPUIS SERVICES.PY
# ==========================================
def charger_offres_auto():
    # 1. Mémoire Streamlit (si déjà chargé)
    if "offres_df" in st.session_state and isinstance(st.session_state.offres_df, pd.DataFrame) and not st.session_state.offres_df.empty:
        return st.session_state.offres_df.copy()

    # 2. Appel direct à votre fichier services.py
    try:
        # On récupère le dictionnaire de données
        data = services.get_data()
        
        # On privilégie les offres fiables (sans anomalies), sinon on prend toutes les offres
        df_offres = data.get("offres_fiables")
        if df_offres is None or df_offres.empty:
            df_offres = data.get("offres")

        if df_offres is not None and not df_offres.empty:
            st.session_state.offres_df = df_offres
            return df_offres
            
    except DataSourceError as e:
        st.warning(f" Le pipeline de données n'a pas encore été lancé : {e}")
    except Exception as e:
        st.error(f"Erreur lors du chargement des offres : {e}")

    return pd.DataFrame()

# Exécution
df_offres_affichees = charger_offres_auto()

# ==========================================
# FORMULAIRE PRINCIPAL
# ==========================================
with st.form("formulaire_cv"):

  choix_offres = ["-- Créer un CV sans cibler d'offre --"]
  
  if not df_offres_affichees.empty:
      cols = df_offres_affichees.columns
      
      # Détection intelligente des colonnes (basée sur les noms dans OFFER_COLUMNS)
      col_titre = next((c for c in cols if "titre" in str(c).lower() or "poste" in str(c).lower()), None)
      col_entreprise = next((c for c in cols if "entreprise" in str(c).lower() or "societe" in str(c).lower()), None)
      col_desc = next((c for c in cols if "description" in str(c).lower() or "mission" in str(c).lower()), None)
      
      # Si les colonnes spécifiques ne sont pas trouvées, on prend la 1ère et 2ème colonne par défaut
      if not col_titre and len(cols) > 0: col_titre = cols[1] if len(cols) > 1 else cols[0] # id_offre est souvent en 1er
      if not col_entreprise and len(cols) > 2: col_entreprise = cols[2]
      
      if col_titre:
          for _, row in df_offres_affichees.iterrows():
              titre = str(row[col_titre]).strip() if pd.notna(row[col_titre]) else "Poste sans nom"
              entreprise = str(row[col_entreprise]).strip() if col_entreprise and pd.notna(row[col_entreprise]) else "Entreprise inconnue"
              
              if titre != "" and titre.lower() != "nan":
                  choix_offres.append(f"{titre} — {entreprise}")

  # La liste roulante
  offre_selectionnee = st.selectbox(
      "Liste complète des offres disponibles (Titre + Entreprise)", 
      choix_offres,
      help="Tapez pour rechercher une offre spécifique"
  )

  poste_defaut, profil_defaut, entreprise_cible, titre_offre_cible, lettre_defaut = "", "", "", "", ""

  if offre_selectionnee != "-- Créer un CV sans cibler d'offre --":
    index_offre = choix_offres.index(offre_selectionnee) - 1
    row = df_offres_affichees.iloc[index_offre]

    poste_defaut = str(row[col_titre]) if col_titre else ""
    titre_offre_cible = poste_defaut
    entreprise_cible = str(row[col_entreprise]) if col_entreprise else "L'entreprise"
    desc = str(row[col_desc]) if col_desc and pd.notna(row[col_desc]) else "Description non disponible."

    profil_defaut = (
        f"Fort d'une préparation technique en Intelligence Artificielle, je postule pour le poste de {titre_offre_cible} au sein de {entreprise_cible}. "
        f"Mon parcours me permet de répondre aux exigences de votre offre : {desc}"
    )

    lettre_defaut = (
        f"Madame, Monsieur,\n\nC'est avec un vif intérêt que je vous adresse ma candidature pour le poste de {titre_offre_cible} au sein de {entreprise_cible}.\n\n"
        f"Actuellement en formation en Intelligence Artificielle et Data Analyst, je développe des compétences approfondies en Python, SQL, et en conception de solutions analytiques.\n\n"
        f"Votre offre axée sur '{desc}' résonne parfaitement avec mes compétences techniques.\n\n"
        f"Je serais ravi de mettre mon dynamisme au service de vos équipes.\n\n"
        f"Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées."
    )

  st.divider()

  st.subheader("1. Informations personnelles")
  col1, col2 = st.columns(2)
  with col1:
    nom = st.text_input("Nom et prénom *", value="Kodji Koffi", placeholder="Saisissez votre nom")
    poste = st.text_input("Poste recherché", value=poste_defaut, placeholder="Ex. : Développeur Python")
    email = st.text_input("Adresse e-mail", placeholder="Saisissez votre e-mail")
  with col2:
    telephone = st.text_input("Téléphone", placeholder="Saisissez votre numéro")
    ville = st.text_input("Ville", value="Marrakech, Maroc")
    linkedin = st.text_input("LinkedIn ou portfolio", placeholder="https://...")

  st.subheader("2. Photo du candidat")
  photo = st.file_uploader("Importer une photo", type=["jpg", "jpeg", "png"])
  if photo is not None:
    st.image(photo, caption="Aperçu", width=150)

  st.subheader("3. Profil professionnel (Généré par l'Agent IA)")
  profil = st.text_area("Présentation professionnelle adaptée", value=profil_defaut, height=110)

  st.subheader("4. Lettre de motivation (Générée par l'Agent IA)")
  lettre_motivation_texte = st.text_area("Contenu de la lettre de motivation", value=lettre_defaut, height=180)

  st.subheader("5. Compétences")
  competences = st.text_area("Compétences techniques", value="Python, SQL, R, Java\nPandas, NumPy, Scikit-Learn, Streamlit\nPostgreSQL, ETL, Talend Open Studio", height=100)

  st.subheader("6. Expériences professionnelles")
  experiences = st.text_area("Stages, emplois et expériences", placeholder="Entreprise, poste, dates, missions...", height=100)

  st.subheader("7. Projets réalisés")
  projets = st.text_area("Projets académiques et personnels", value="Marrakech OpportunityHub : Plateforme web interactive\nPulmoScan AI : Application d'intelligence artificielle", height=100)

  st.subheader("8. Formation")
  formation = st.text_area("Diplômes et études", value="2ème année en Intelligence Artificielle - Option Data Analyste (OFPPT)", height=90)

  col3, col4 = st.columns(2)
  with col3:
    certifications = st.text_area("Certifications", value="Scikit-Learn Machine Learning", height=80)
  with col4:
    langues = st.text_area("Langues", value="Français (Courant), Anglais (Technique)", height=80)

  interets = st.text_input("Centres d'intérêt", value="Veille technologique, IA")

  st.caption("* Le nom et prénom sont obligatoires.")
  
  # CORRECTION DU TERMINAL : width="stretch" au lieu de use_container_width=True
  generer = st.form_submit_button("Générer mon CV et ma Lettre de motivation PDF", type="primary", width="stretch")

if generer:
  if not nom.strip():
    st.error("Veuillez saisir votre nom et prénom.")
  else:
    donnees = {
        "nom": nom.strip(), "poste": poste, "email": email, "telephone": telephone,
        "ville": ville, "linkedin": linkedin, "profil": profil, "competences": competences,
        "experiences": experiences, "projets": projets, "formation": formation,
        "certifications": certifications, "langues": langues, "interets": interets,
    }
    try:
      photo_bytes = photo.getvalue() if photo else None
      pdf_cv = generer_cv(donnees, photo_bytes=photo_bytes)
      pdf_lm = generer_lettre_motivation_pdf(donnees, entreprise_cible if entreprise_cible else "Entreprise_Partenaire", titre_offre_cible if titre_offre_cible else "Poste_Cible", lettre_motivation_texte)

      st.success("Votre CV et votre lettre de motivation ont été générés avec succès !")
      nom_fichier = "".join(c if c.isalnum() or c in "-_" else "_" for c in nom.strip())

      col_dl1, col_dl2 = st.columns(2)
      with col_dl1:
        st.download_button(label="Télécharger mon CV (PDF)", data=pdf_cv, file_name=f"CV_{nom_fichier}.pdf", mime="application/pdf", type="primary", width="stretch")
      with col_dl2:
        st.download_button(label="Télécharger la Lettre (PDF)", data=pdf_lm, file_name=f"Lettre_Motivation_{nom_fichier}.pdf", mime="application/pdf", type="primary", width="stretch")

    except Exception as erreur:
      st.error(f"Impossible de générer les documents : {erreur}")