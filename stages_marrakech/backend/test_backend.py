from datetime import date
import pandas as pd
import pytest
from stages_marrakech.backend import analyze, clean, quality, tracking
from stages_marrakech.backend.errors import ValidationError
from stages_marrakech.backend.utils import check_email, extract_emails, normalize_phone, to_float

def test_extract_emails_nettoie_html_et_prefixe():
    raw = "contact<span class='x'>@sggi-maroc.com</span> ; http://info@smartinfluencer.ma"
    valid, invalid = extract_emails(raw)
    assert valid == ["contact@sggi-maroc.com", "info@smartinfluencer.ma"]
    assert invalid == []

def test_extract_emails_rejette_caractere_interdit():
    valid, invalid = extract_emails("contact-rh@sofitelmarrakechlounge&spa.ma")
    assert valid == [] and len(invalid) == 1

@pytest.mark.parametrize("email,site,statut", [
    ("exemple@email.com", None, "Rejeté"),
    ("logo@site.png", None, "Rejeté"),
    ("moi@gmail.com", None, "À vérifier"),
    ("contact@itlabspro.com", "https://www.itlabspro.com/", "Validé"),
    ("contact@autre-domaine.ma", "https://www.itlabspro.com/", "À vérifier"),
])
def test_check_email(email, site, statut):
    assert check_email(email, site)[0] == statut

def test_normalize_phone_et_note():
    assert normalize_phone("06 61 21 22 56") == "+212661212256"
    assert normalize_phone("+212 6 70 70 79 83") == "+212670707983"
    assert normalize_phone("021 721 04 04") == "021 721 04 04" 
    assert to_float("4,9") == 4.9 and to_float("abc") is None

def _raw():
    return pd.DataFrame([
        {"nom": "Agence Web X", "adresse": "Av 1, Marrakech 40000", "telephone": "0661212256",
         "site_web": "https://agencex.ma", "google_maps": None, "note": "4,9", "nombre_avis": 50,
         "categories_google": None, "emails_bruts": "contact@agencex.ma", "place_id": None, "source_dataset": "A"},
        {"nom": "Agence Web X", "adresse": None, "telephone": None, "site_web": "agencex.ma",
         "google_maps": None, "note": None, "nombre_avis": None, "categories_google": None,
         "emails_bruts": "recrute@agencex.ma", "place_id": None, "source_dataset": "B"},
        {"nom": "Riad Soleil", "adresse": "Rue 2, Marrakech", "telephone": None, "site_web": None,
         "google_maps": None, "note": None, "nombre_avis": None, "categories_google": None,
         "emails_bruts": None, "place_id": None, "source_dataset": "A"},
    ])

def test_clean_companies_fusionne_les_doublons_et_choisit_le_bon_email():
    companies, rejected, report = clean.clean_companies(_raw())
    assert len(companies) == 2 and report["doublons_fusionnes"] == 1
    agency = companies[companies["nom"] == "Agence Web X"].iloc[0]
    assert agency["email_principal"] == "recrute@agencex.ma"       
    assert agency["note"] == 4.9 and agency["telephone"] == "+212661212256"
    assert agency["sources"] == "A + B"

def test_secteurs():
    assert clean.classify_sector("VHYNX IA | Agence Web") == "IA / Data"
    assert clean.classify_sector("Riad Soleil") == "Hors cible"
    assert clean.classify_sector("Boutique Zara") == "Hors cible"

def test_recouvrement_titre_description():
    ok = quality.title_description_overlap("Data Scientist Junior", "Nous recrutons un Data Scientist")
    bad = quality.title_description_overlap("Développeur Fullstack Python", "Cabinet comptable cherche comptable confirmé")
    assert ok >= 0.5 and bad == 0.0
    assert quality.title_description_overlap("Stage Intelligence Artificielle", "projets IA") > 0

def test_offre_future_et_simulee_detectees():
    offers = pd.DataFrame([{"id_offre": "O001", "titre": "Data Analyst", "entreprise": "X", "date": pd.Timestamp("2030-01-01"),
                            "email_statut": "Aucun", "description": "Data Analyst pour tableaux de bord", "url": "u",
                            "origine": "simulée"}])
    res = quality.quality_offers(offers, today=date(2026, 10, 22))
    assert "futur" in res.loc[0, "anomalies"] and res.loc[0, "fiabilite"] == "Simulée"

def test_score_entre_0_et_100_et_ordre():
    companies, _, _ = clean.clean_companies(_raw())
    scored = analyze.compute_scores(companies)
    assert scored["score_pertinence"].between(0, 100).all()
    assert scored.iloc[0]["nom"] == "Agence Web X"  

def test_cycle_de_suivi_et_relance():
    track = tracking.add_application(tracking._empty(), "Agence X", "Stage IA", "recrute@agencex.ma")
    track = tracking.update_status(track, "S001", "Candidature envoyée", when=date(2026, 10, 1))
    assert track.loc[0, "date_relance"] == pd.Timestamp("2026-10-08")
    assert len(tracking.relances_a_faire(track, today=date(2026, 10, 7))) == 0
    assert len(tracking.relances_a_faire(track, today=date(2026, 10, 8))) == 1
    track = tracking.update_status(track, "S001", "Réponse reçue")
    assert len(tracking.relances_a_faire(track, today=date(2026, 10, 30))) == 0

def test_statut_inconnu_leve_une_erreur_claire():
    track = tracking.add_application(tracking._empty(), "Agence X", "Stage IA")
    with pytest.raises(ValidationError):
        tracking.update_status(track, "S001", "Statut inventé")
