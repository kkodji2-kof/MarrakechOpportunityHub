from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from . import config
from .errors import DataSourceError, ValidationError
TRACK_COLUMNS = ["id_suivi", "id_entreprise", "entreprise", "opportunite", "statut", "date_candidature",
                 "date_relance", "email_contact", "canal", "remarque"]
TRACK_FILE = config.TRACK_DIR / "suivi.csv"
FINAL_STATUS = {"Acceptée", "Refusée", "Sans réponse"}

def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=TRACK_COLUMNS)
def load_tracking(path: Path = TRACK_FILE) -> pd.DataFrame:
    """Charge le fichier de suivi. Renvoie un tableau vide s'il n'existe pas ou s'il est corrompu."""
    if not Path(path).exists():
        return _empty()
    
    # --- CORRECTION ICI : Vérifier si le fichier est vide (0 octet) ---
    if Path(path).stat().st_size == 0:
        return _empty()
    # -----------------------------------------------------------------

    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
        
        # Sécurité supplémentaire si le fichier n'a pas de colonnes
        if df.empty and len(df.columns) == 0:
            return _empty()
            
    except pd.errors.EmptyDataError:
        return _empty()
    except Exception as exc: 
        raise DataSourceError(f"Impossible de lire le fichier de suivi : {exc}") from exc
        
    # On s'assure que toutes les colonnes attendues sont présentes
    for col in TRACK_COLUMNS:
        if col not in df.columns:
            df[col] = None

    for col in ("date_candidature", "date_relance"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            
    return df


def save_tracking(df: pd.DataFrame, path: Path = TRACK_FILE) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    
    # On s'assure que toutes les colonnes existent avant de sauvegarder
    for col in TRACK_COLUMNS:
        if col not in out.columns:
            out[col] = None
            
    for col in ("date_candidature", "date_relance"):
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")  
    out.to_csv(path, index=False, encoding="utf-8-sig")

def init_tracking(priorities: pd.DataFrame, n: int = config.TOP_N_SUIVI, path: Path = TRACK_FILE) -> pd.DataFrame:
    """Crée le fichier de suivi à partir des meilleures priorités (sans écraser un suivi existant)."""
    if Path(path).exists() and Path(path).stat().st_size > 0:
        return load_tracking(path)
        
    rows = []
    for i, r in enumerate(priorities.head(n).itertuples(index=False), start=1):
        rows.append({"id_suivi": f"S{i:03d}", "id_entreprise": r.id_entreprise, "entreprise": r.nom_affiche,
                     "opportunite": "Candidature spontanée", "statut": "À contacter",
                     "date_candidature": pd.NaT, "date_relance": pd.NaT, "email_contact": r.email_principal,
                     "canal": "Email", "remarque": None})
                     
    df = pd.DataFrame(rows, columns=TRACK_COLUMNS) if rows else _empty()
    save_tracking(df, path)
    return df


def update_status(df: pd.DataFrame, id_suivi: str, statut: str, remarque: str | None = None,
                  when: date | None = None, delai: int = config.RELANCE_DELAI_JOURS) -> pd.DataFrame:
    """Change le statut d'une ligne. « Candidature envoyée » enregistre la date et programme la relance."""
    if statut not in config.STATUTS:
        raise ValidationError(f"Statut inconnu : « {statut} ». Choix possibles : {', '.join(config.STATUTS)}")
    mask = df["id_suivi"] == id_suivi
    if not mask.any():
        raise ValidationError(f"Ligne de suivi introuvable : {id_suivi}")
    df = df.copy()
    df.loc[mask, "statut"] = statut
    if statut == "Candidature envoyée":
        day = pd.Timestamp(when or config.TODAY)
        df.loc[mask, "date_candidature"] = day
        df.loc[mask, "date_relance"] = day + timedelta(days=delai)
    if remarque is not None:
        df.loc[mask, "remarque"] = remarque
    return df


def add_application(df: pd.DataFrame, entreprise: str, opportunite: str, email_contact: str | None = None,
                    canal: str = "Email", id_entreprise: str | None = None, remarque: str | None = None) -> pd.DataFrame:
    if not entreprise or not opportunite:
        raise ValidationError("L'entreprise et l'opportunité sont obligatoires.")
    next_id = f"S{len(df) + 1:03d}"
    row = {"id_suivi": next_id, "id_entreprise": id_entreprise, "entreprise": entreprise,
           "opportunite": opportunite, "statut": "À contacter", "date_candidature": pd.NaT,
           "date_relance": pd.NaT, "email_contact": email_contact, "canal": canal, "remarque": remarque}
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def relances_a_faire(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Candidatures envoyées sans réponse dont la date de relance est arrivée."""
    if df.empty or "date_relance" not in df.columns:
        return _empty()
        
    today = pd.Timestamp(today or config.TODAY)
    waiting = df["statut"].isin(["Candidature envoyée", "Relance à faire"])
    due = df["date_relance"].notna() & (df["date_relance"] <= today)
    return df[waiting & due].reset_index(drop=True)


def summary(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Répartition utilisée par le cercle (donut) « relances et candidatures à traiter »."""
    if df.empty:
        return pd.DataFrame(columns=["categorie", "nombre"])
        
    due = len(relances_a_faire(df, today))
    sent = int((df["statut"] == "Candidature envoyée").sum())
    rows = [
        ("À contacter", int((df["statut"] == "À contacter").sum())),
        ("Relances à faire", due),
        ("En attente de réponse", max(sent - due, 0)),
        ("Réponses / entretiens", int(df["statut"].isin(["Réponse reçue", "Entretien"]).sum())),
        ("Clôturées", int(df["statut"].isin(FINAL_STATUS).sum())),
    ]
    return pd.DataFrame(rows, columns=["categorie", "nombre"])
