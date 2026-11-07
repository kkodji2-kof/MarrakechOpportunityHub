from __future__ import annotations
import argparse
import logging
import sys
import pandas as pd
from stages_marrakech.backend import analytics, clean, collect, explore, quality, tracking, visualize
from stages_marrakech.backend import config
from stages_marrakech.backend.errors import OpportunityHubError
from stages_marrakech.backend.export import write_excel
log = logging.getLogger("backend")
def run(use_google: bool = False, top_n: int = 20) -> dict:
    errors: list[str] = []  # « liste des erreurs » remontée au frontend
    for folder in (config.CLEAN_DIR, config.REPORT_DIR, config.TRACK_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    # ---- 1. DATA COLLECTION ---------------------------------------------------
    log.info("1/6 Collecte des données")
    frames, load_errors = collect.load_sources()
    errors += load_errors
    raw_companies = collect.harmonize_companies(frames)
    raw_offers = collect.harmonize_offers(frames)
    if use_google:
        google_df, google_errors = collect.google_places_collect()
        errors += google_errors
        if not google_df.empty:
            raw_companies = pd.concat([raw_companies, google_df], ignore_index=True)
    if raw_companies.empty:
        raise OpportunityHubError("Aucune donnée d'entreprise : dépose tes fichiers dans data/raw.")
    raw_companies.to_csv(config.RAW_DIR / "entreprises_brut_unifie.csv", index=False, encoding="utf-8-sig")

    # ---- 2. DATA CLEANING -----------------------------------------------------
    log.info("2/6 Nettoyage")
    companies, rejected_c, clean_report = clean.clean_companies(raw_companies)
    offers, rejected_o = clean.clean_offers(raw_offers) if len(raw_offers) else (pd.DataFrame(), pd.DataFrame())
    rejected = pd.concat([rejected_c, rejected_o], ignore_index=True)
    comparison = clean.cleaning_comparison(raw_companies, companies, rejected_c)
    companies.to_csv(config.CLEAN_DIR / "entreprises_nettoyees.csv", index=False, encoding="utf-8-sig")
    offers.to_csv(config.CLEAN_DIR / "offres_nettoyees.csv", index=False, encoding="utf-8-sig")

    # ---- 4. DATA QUALITY (avant l'analyse, pour exclure les offres douteuses) --
    log.info("4/6 Contrôle qualité")
    q = quality.quality_report(companies, offers)
    offers_ok = quality.reliable_offers(offers, q["Qualite_offres"])

    # ---- 3. DATA EXPLORING ----------------------------------------------------
    log.info("3/6 Exploration")
    tables = explore.explore(companies, offers_ok)

    # ---- 6. APPLICATION ANALYTICS (scores, priorités, suivi) -------------------
    log.info("6/6 Analytique et suivi")
    scored = analytics.compute_scores(companies, offers_ok)
    priorities = analytics.top_priorities(scored, n=top_n)
    track = tracking.init_tracking(analytics.top_priorities(scored, n=config.TOP_N_SUIVI))
    due = tracking.relances_a_faire(track)
    notes = analytics.insights(scored, priorities, due)
    scored.to_csv(config.CLEAN_DIR / "entreprises_scorees.csv", index=False, encoding="utf-8-sig")

    # ---- 5. DATA VISUALIZATION ------------------------------------------------
    log.info("5/6 Visualisation")
    figs = {
        "secteurs": visualize.fig_secteurs(tables["Par_secteur"]),
        "scores": visualize.fig_scores(scored),
        "notes": visualize.fig_notes(tables["Distribution_notes"]),
        "top_priorites": visualize.fig_top_priorites(priorities),
        "offres_temps": visualize.fig_offres_temps(tables["Offres_par_semaine"]),
        "offres_contrat": visualize.fig_offres_contrat(tables["Offres_par_contrat"]),
        "relances": visualize.fig_relances(tracking.summary(track)),
        "entonnoir": visualize.fig_entonnoir(track),
        "qualite": visualize.fig_qualite(q["Completude_entreprises"]),
        "carte": visualize.fig_carte(scored),
    }
    dashboard = visualize.save_dashboard(figs, config.REPORT_DIR, notes)

    # ---- Exports Excel --------------------------------------------------------
    write_excel(config.REPORT_DIR / "donnees_avant_nettoyage.xlsx", {"Avant_nettoyage": raw_companies,
                                                                    "Offres_brutes": raw_offers})
    write_excel(config.REPORT_DIR / "donnees_apres_nettoyage.xlsx", {
        "Apres_nettoyage": companies, "Offres_nettoyees": offers, "Comparaison": comparison,
        "Emails_rejetes": rejected})
    analysis_sheets = {**tables, **q, "Priorites": priorities, "Scores": scored, "Suivi": track}
    write_excel(config.REPORT_DIR / "analyse_et_suivi.xlsx", analysis_sheets)

    summary = {"entreprises": len(companies), "offres_fiables": len(offers_ok), "priorites": len(priorities),
               "relances_dues": len(due), "dashboard": str(dashboard), "erreurs": errors, "insights": notes}
    log.info("Terminé : %s", {k: v for k, v in summary.items() if k not in {"insights", "erreurs"}})
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backend Marrakech OpportunityHub")
    parser.add_argument("--google", action="store_true", help="collecte aussi via Google Places API")
    parser.add_argument("--top", type=int, default=20, help="nombre d'entreprises dans la liste de priorités")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        result = run(use_google=args.google, top_n=args.top)
    except OpportunityHubError as exc:
        log.error("Erreur : %s", exc)
        return 1
    for line in result["insights"]:
        print("•", line)
    for err in result["erreurs"]:
        print("⚠", err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
