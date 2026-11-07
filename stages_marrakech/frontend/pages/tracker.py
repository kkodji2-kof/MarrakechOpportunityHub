import streamlit as st
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import sqlite3

# ==========================================
# GESTION AUTONOME DE LA BASE DE DONNÉES (SQLITE)
# ==========================================
DB_NAME = "candidatures.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre_offre TEXT NOT NULL,
            nom_entreprise TEXT NOT NULL,
            email_candidat TEXT NOT NULL,
            date_postulation DATE NOT NULL,
            statut TEXT DEFAULT 'En attente'
        )
    """)
    conn.commit()
    conn.close()

def obtenir_candidatures(email_candidat):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, titre_offre, nom_entreprise, date_postulation, statut 
        FROM candidatures 
        WHERE email_candidat = ? 
        ORDER BY date_postulation DESC
    """, (email_candidat,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def supprimer_candidature(candidature_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM candidatures WHERE id = ?", (candidature_id,))
    conn.commit()
    conn.close()

# Initialisation de la base au lancement
init_db()

# Identifiant du candidat connecté (à adapter selon votre système d'authentification)
EMAIL_UTILISATEUR = "candidat@example.com"

# --- FONCTION D'ENVOI D'EMAIL DE RELANCE ---
def envoyer_email_relance(destinataire, titre_offre, nom_entreprise, date_postulation):
    expediteur = st.secrets.get("smtp", {}).get("user", "votre_email@gmail.com")
    mot_de_passe = st.secrets.get("smtp", {}).get("password", "votre_mot_de_passe_app")
    
    sujet = f"🔔 Rappel de relance : Candidature chez {nom_entreprise}"
    corps = f"""Bonjour,

Vous avez postulé à l'offre '{titre_offre}' chez {nom_entreprise} le {date_postulation} (il y a plus de 14 jours).

C'est le moment idéal pour envoyer un message de relance aux recruteurs pour réaffirmer votre motivation !

Cordialement,
L'équipe Marrakech OpportunityHub
"""
    msg = MIMEText(corps)
    msg['Subject'] = sujet
    msg['From'] = expediteur
    msg['To'] = destinataire

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(expediteur, mot_de_passe)
            server.sendmail(expediteur, destinataire, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi d'email : {e}")
        return False

# --- INTERFACE DE LA PAGE DE SUIVI ---
st.title(" Historique & Suivi ")

candidatures = obtenir_candidatures(EMAIL_UTILISATEUR)

if not candidatures:
    st.info("Vous n'avez encore postulé à aucune offre.")
else:
    for cand in candidatures:
        cand_id, titre, entreprise, date_str, statut = cand
        date_post = datetime.strptime(date_str, "%Y-%m-%d")
        jours_ecoules = (datetime.now() - date_post).days
        
        col1, col2, col3, col4 = st.columns([1, 4, 3, 2])
        
        with col1:
            # Cercle / Badge d'alerte (> 14 jours = Rouge, <= 14 jours = Vert)
            if jours_ecoules >= 14:
                st.markdown("🔴 **Relance !**")
            else:
                st.markdown("🟢 **Récent**")
        
        with col2:
            st.markdown(f"**{titre}**")
            st.caption(f"Entreprise : {entreprise}")
        
        with col3:
            st.write(f"Postulé le : `{date_str}` ({jours_ecoules} j)")
        
        with col4:
            # Option de suppression
            if st.button("🗑️ Supprimer", key=f"del_{cand_id}"):
                supprimer_candidature(cand_id)
                st.rerun()
        
        # Alerte et option de relance automatique après 14 jours (2 semaines)
        if jours_ecoules >= 14:
            st.warning(f"**Attention :** Plus de 2 semaines écoulées sans réponse pour cette offre.")
            
            if st.button(f" Envoyer un rappel de relance automatique", key=f"email_{cand_id}"):
                succes = envoyer_email_relance(EMAIL_UTILISATEUR, titre, entreprise, date_str)
                if succes:
                    st.success("Un e-mail de rappel avec les détails de l'offre vous a été envoyé !")
        
        st.divider()