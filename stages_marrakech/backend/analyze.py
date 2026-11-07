
import math
import re
import unicodedata
import pandas as pd
from . import config
# ============================================================
# CONSTANTES
# ============================================================

SECTEURS_CIBLES = {"ia","intelligence artificielle","data","data science","data analyst","data analyste","machine learning","deep learning","big data",
    "informatique","developpement logiciel","developpement web","cybersecurite","digital","technologie","it","logiciel",
}

COLONNES_ENTREPRISES = ["id_entreprise","nom","nom_affiche", "secteur","ville", "statut_email","email_principal", "note","nombre_avis",
]
COLONNES_OFFRES = ["source","titre", "entreprise","ville","contrat","niveau_etudes","experience","salaire","date_publication",
    "date_limite","description","lien","date_collecte",
]
# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def safe_text(value):
    """Convertit une valeur en texte de manière sécurisée."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()
def normalize_text(value):
    """Normalise un texte pour faciliter les comparaisons."""
    text = safe_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def safe_number(value, default=0):
    """Convertit une valeur en nombre."""
    try:
        if value is None or pd.isna(value):
            return default
        if isinstance(value, str):
            value = value.replace(",", ".")
            value = re.sub(r"[^0-9.\-]", "", value)
            if not value:
                return default
        return float(value)
    except (ValueError, TypeError):
        return default
def ensure_columns(df, columns):
    """Ajoute les colonnes manquantes sans supprimer les données."""
    df = df.copy()
    for column in columns:
        if column not in df.columns:
            df[column] = None
    return df
def first_existing_column(df, candidates):
    """Retourne la première colonne existante parmi plusieurs noms."""
    for column in candidates:
        if column in df.columns:
            return column
    return None
def short_company_name(name):
    """Nettoie le nom d'une entreprise."""
    name = safe_text(name)
    if not name:
        return "Entreprise inconnue"
    return re.sub(r"\s+", " ", name).strip()
def empty_dataframe(columns):
    """Crée un DataFrame vide avec les colonnes demandées."""
    return pd.DataFrame(columns=columns)
# ============================================================
# ANALYSE DES OFFRES PAR ENTREPRISE
# ============================================================
def offers_by_company(offers, company):
    """Récupère les offres correspondant à une entreprise."""
    if not isinstance(offers, pd.DataFrame) or offers.empty:
        return pd.DataFrame()
    company_name = normalize_text(
        company.get("nom_affiche")
        or company.get("nom"))
    company_id = safe_text(company.get("id_entreprise"))
    # Correspondance par identifiant
    for column in ["id_entreprise", "company_id"]:
        if column not in offers.columns or not company_id:
            continue
        mask = ( offers[column].fillna("") .astype(str).str.strip()== company_id)
        result = offers.loc[mask]
        if not result.empty:
            return result.copy()
    # Correspondance par nom
    for column in [ "entreprise", "company_name", "nom_entreprise", "nom", ]:
        if column not in offers.columns:
            continue
        normalized_names = offers[column].apply(normalize_text)
        mask = normalized_names.apply(
            lambda value: ( bool(value)and bool(company_name) and (value == company_name or company_name in value or value in company_name) ))
        result = offers.loc[mask]
        if not result.empty:
            return result.copy()
    return pd.DataFrame(columns=offers.columns)
# ============================================================
# SCORE DE RÉPUTATION
# ============================================================
def _reputation(row):
    """Calcule un score de réputation sur 100."""
    note = safe_number(
        row.get("note", row.get("Note", 0))
    )
    avis = safe_number(
        row.get(
            "nombre_avis",
            row.get("nb_avis", row.get("Nb Avis", 0))))
    if note <= 0:
        return 40
    note_score = min(max(note, 0), 5) * 20
    if avis >= 100:avis_bonus = 10
    elif avis >= 50:avis_bonus = 7
    elif avis >= 10:avis_bonus = 4
    elif avis > 0:avis_bonus = 2
    else:avis_bonus = 0
    return min(100, note_score + avis_bonus)
# ============================================================
# SCORE D'ADÉQUATION SECTORIELLE
# ============================================================
def sector_score(sector):
    """Calcule le score d'adéquation avec les secteurs ciblés."""
    sector_normalized = normalize_text(sector)
    if not sector_normalized:
        return 30
    configured_scores = getattr(
        config,
        "SECTOR_SCORES",
        {})
    for configured_sector, score in configured_scores.items():
        configured_normalized = normalize_text( configured_sector )
        if configured_normalized and (configured_normalized in sector_normalized or sector_normalized in configured_normalized):
            return min(100,max(0, safe_number(score, 30)))
    for target in SECTEURS_CIBLES:
        if target in sector_normalized:
            return 100
    return 35
# ============================================================
# SCORE DE RECRUTEMENT
# ============================================================
def recruitment_score(row, offers=None):
    """Évalue les opportunités de recrutement réellement disponibles."""
    if isinstance(offers, pd.DataFrame) and not offers.empty:
        matching_offers = offers_by_company(offers, row)
        if not matching_offers.empty:
            return min(100, 70 + len(matching_offers) * 5 )
    return 20
# ============================================================
# SCORE DE CONTACT
# ============================================================
def contact_score(row):
    """Évalue la disponibilité des informations de contact."""
    score = 0
    email = safe_text(
        row.get("email_principal",row.get("email", "") )
    )
    statut_email = normalize_text(
        row.get("statut_email", ""))
    telephone = safe_text(
        row.get(
            "telephone",
            row.get("téléphone", "")))
    site_web = safe_text(
        row.get(
            "site_web",
            row.get("website", "")))
    if email and "@" in email:
        score += 50
        if statut_email in {"valide","verifie","verified","confirme",}: score += 15
    if telephone:score += 20
    if site_web:score += 15
    return min(100, score)
# ============================================================
# SCORE DE LOCALISATION
# ============================================================
def location_score(row):
    """Évalue la présence de l'entreprise à Marrakech."""
    city = normalize_text(
        row.get("ville", ""))
    if not city:
        return 20
    target_city = normalize_text(
        getattr(config, "VILLE_CIBLE", "Marrakech"))
    if target_city and target_city in city:
        return 100
    return 30
# ============================================================
# CALCUL DES SCORES
# ============================================================
def compute_scores(companies, offers=None):
    """Calcule les scores de pertinence des entreprises."""

    if not isinstance(companies, pd.DataFrame):
        return pd.DataFrame()
    if companies.empty:
        return companies.copy()
    df = ensure_columns(
        companies,
        COLONNES_ENTREPRISES
    )
    # Évite de dupliquer les colonnes si le scoring est relancé.
    score_columns = [ "score_adequation","score_recrutement","score_reputation","score_localisation","score_contact","score_global","pertinence","priorite",]
    df = df.drop(
        columns=[column for column in score_columns
            if column in df.columns
        ], errors="ignore"
    )
    default_weights = {"adequation": 35,"recrutement": 20,"reputation": 15,"localisation": 10,"contact": 20, }
    weights = dict(getattr(config, "SCORE_WEIGHTS", default_weights))
    for key, value in default_weights.items():
        weights.setdefault(key, value)
    total_weight = sum( safe_number(value) for value in weights.values())
    if total_weight <= 0:
        weights = default_weights.copy()
        total_weight = 100
    scores = []
    for _, row in df.iterrows():
        adequation = sector_score(
            row.get("secteur") )
        recrutement = recruitment_score( row, offers )
        reputation = _reputation(row)
        localisation = location_score(row)
        contact = contact_score(row)
        global_score = (
            adequation * safe_number(weights["adequation"])
            + recrutement * safe_number(weights["recrutement"])
            + reputation * safe_number(weights["reputation"])
            + localisation * safe_number(weights["localisation"])
            + contact * safe_number(weights["contact"])
        ) / total_weight

        scores.append({
            "score_adequation": round(adequation, 2),
            "score_recrutement": round(recrutement, 2),
            "score_reputation": round(reputation, 2),
            "score_localisation": round(localisation, 2),
            "score_contact": round(contact, 2),
            "score_global": round(global_score, 2),
        })

    scores_df = pd.DataFrame(
        scores,
        index=df.index
    )

    df = pd.concat(
        [df, scores_df],
        axis=1
    )

    df["pertinence"] = df["secteur"].apply(
        lambda sector: (
            "Cible IA/Tech"
            if any(
                target in normalize_text(sector)
                for target in SECTEURS_CIBLES
            )
            else "Autre secteur"
        )
    )

    seuil_haut = getattr(
        config,
        "PRIORITE_HAUTE",
        70
    )

    seuil_moyen = getattr(
        config,
        "PRIORITE_MOYENNE",
        50
    )

    df["priorite"] = df["score_global"].apply(
        lambda score: (
            "Haute"
            if score >= seuil_haut
            else (
                "Moyenne"
                if score >= seuil_moyen
                else "Faible"
            )
        )
    )

    return df.sort_values(
        by="score_global",
        ascending=False
    ).reset_index(drop=True)


# ============================================================
# CLASSEMENT DES ENTREPRISES PRIORITAIRES
# ============================================================

def top_priorities(companies, n=10, tech_only=False):
    """
    Retourne les entreprises prioritaires selon leur score.

    Paramètres :
        companies : DataFrame des entreprises
        n : nombre maximum de résultats
        tech_only : privilégier les entreprises technologiques

    Retour :
        DataFrame des meilleures entreprises
    """

    if companies is None or companies.empty:
        return pd.DataFrame()

    df = companies.copy()

    # Identifier la colonne du score.
    # NB : "score_global" doit passer en premier. La colonne "pertinence"
    # produite par compute_scores() est un texte ("Cible IA/Tech" ...) :
    # elle ne doit surtout pas servir de score numérique.
    score_col = next(
        (
            col for col in [
                "score_global",
                "score_pertinence",
                "score",
                "relevance_score"
            ]
            if col in df.columns
        ),
        None
    )

    if score_col is None:
        return df.head(n)

    df[score_col] = pd.to_numeric(
        df[score_col],
        errors="coerce"
    ).fillna(0)

    # Filtrer les entreprises technologiques si demandé
    if tech_only:
        possible_columns = [
            "domaine",
            "secteur",
            "type_principal",
            "activite"
        ]

        sector_col = next(
            (col for col in possible_columns if col in df.columns),
            None
        )

        if sector_col:
            keywords = (
                "informatique|technologie|tech|"
                "data|intelligence artificielle|"
                "ia|digital|développement|"
                "machine learning|big data"
            )

            df = df[
                df[sector_col]
                .astype(str)
                .str.contains(keywords, case=False, na=False)
            ]

    # Trier par score décroissant
    df = df.sort_values(
        by=score_col,
        ascending=False
    )

    return df.head(n).reset_index(drop=True)

# ============================================================
# GÉNÉRATION DES INSIGHTS
# ============================================================

def insights(scored, priorities=None, due=None):
    """Génère des observations analytiques."""

    messages = []

    if not isinstance(scored, pd.DataFrame) or scored.empty:
        return [
            "Aucune entreprise disponible pour l'analyse."
        ]

    messages.append(
        f"Nombre total d'entreprises analysées : {len(scored)}."
    )

    if "secteur" in scored.columns:

        distribution = (
            scored["secteur"]
            .fillna("Non renseigné")
            .astype(str)
            .value_counts()
        )

        if not distribution.empty:
            messages.append(
                f"Secteur le plus représenté : "
                f"{distribution.index[0]} "
                f"({distribution.iloc[0]} entreprises)."
            )

    if "score_global" in scored.columns:

        scores = pd.to_numeric(
            scored["score_global"],
            errors="coerce"
        )

        if scores.notna().any():
            messages.append(
                f"Score moyen de pertinence : "
                f"{scores.mean():.1f}/100."
            )

    if isinstance(priorities, pd.DataFrame):

        messages.append(
            f"Nombre d'entreprises prioritaires : "
            f"{len(priorities)}."
        )

    elif "priorite" in scored.columns:

        high_priority = (
            scored["priorite"] == "Haute"
        ).sum()

        messages.append(
            f"Entreprises à priorité haute : "
            f"{high_priority}."
        )

    if "pertinence" in scored.columns:

        target_count = (
            scored["pertinence"] == "Cible IA/Tech"
        ).sum()

        messages.append(
            f"Entreprises correspondant aux secteurs "
            f"IA / Data / Tech : {target_count}."
        )

    if due is not None:

        if isinstance(due, pd.DataFrame):
            due_count = len(due)
        elif isinstance(due, (list, tuple, set)):
            due_count = len(due)
        else:
            due_count = 0

        messages.append(
            f"Nombre d'éléments nécessitant une relance : "
            f"{due_count}."
        )

    return messages


# ============================================================
# DISTRIBUTION DES NOTES
# ============================================================

def distribution_notes(companies):
    """Construit la distribution des notes des entreprises."""

    result_columns = [
        "tranche",
        "entreprises",
    ]

    if not isinstance(companies, pd.DataFrame) or companies.empty:
        return empty_dataframe(result_columns)

    note_column = first_existing_column(
        companies,
        ["note", "Note", "rating"]
    )

    if note_column is None:
        return empty_dataframe(result_columns)

    notes = pd.to_numeric(
        companies[note_column]
        .astype(str)
        .str.replace(",", ".", regex=False),
        errors="coerce"
    ).dropna()

    notes = notes[
        (notes >= 0) & (notes <= 5)
    ]

    if notes.empty:
        return empty_dataframe(result_columns)

    bins = [0, 1, 2, 3, 4, 5]
    labels = [
        "0-1",
        "1-2",
        "2-3",
        "3-4",
        "4-5",
    ]

    categories = pd.cut(
        notes,
        bins=bins,
        labels=labels,
        include_lowest=True,
        right=True
    )

    result = (
        categories
        .value_counts(sort=False)
        .rename_axis("tranche")
        .reset_index(name="entreprises")
    )

    return result


# ============================================================
# ANALYSE DES OFFRES PAR CONTRAT
# ============================================================

def offers_by_contract(offers):
    """Compte les offres selon leur type de contrat."""

    columns = [
        "contrat",
        "offres",
    ]

    if not isinstance(offers, pd.DataFrame) or offers.empty:
        return empty_dataframe(columns)

    contract_column = first_existing_column(
        offers,
        ["contrat", "type_contrat", "employment_type"]
    )

    if contract_column is None:
        return empty_dataframe(columns)

    df = offers.copy()

    df[contract_column] = (
        df[contract_column]
        .fillna("Non renseigné")
        .astype(str)
        .str.strip()
        .replace("", "Non renseigné")
    )

    return (
        df[contract_column]
        .value_counts()
        .rename_axis("contrat")
        .reset_index(name="offres")
    )


# ============================================================
# ÉVOLUTION DES OFFRES DANS LE TEMPS
# ============================================================

def offers_over_time(offers):
    """Compte les offres publiées par semaine."""

    columns = [
        "semaine",
        "offres",
    ]

    if not isinstance(offers, pd.DataFrame) or offers.empty:
        return empty_dataframe(columns)

    date_column = first_existing_column(
        offers,
        [
            "date_publication",
            "date_publication_offre",
            "published_at",
        ]
    )

    if date_column is None:
        return empty_dataframe(columns)

    dates = pd.to_datetime(
        offers[date_column],
        errors="coerce",
        dayfirst=True,
        utc=True
    )

    valid_dates = dates.dropna()

    if valid_dates.empty:
        return empty_dataframe(columns)

    # Conversion en dates sans fuseau pour le regroupement hebdomadaire.
    valid_dates = valid_dates.dt.tz_convert(None)

    weeks = (
        valid_dates
        .dt.to_period("W")
        .astype(str)
    )

    return (
        weeks
        .value_counts()
        .sort_index()
        .rename_axis("semaine")
        .reset_index(name="offres")
    )


# ============================================================
# ANALYSE MULTIVARIÉE (CORRÉLATIONS, ACP, GROUPES K-MEANS)
# ============================================================

# Variables actives : nom technique -> libellé affiché.
# "score_global" n'en fait pas partie : c'est une combinaison linéaire des
# 5 sous-scores, il fausserait l'ACP. Il sert de variable illustrative
# (matrice de corrélations, classement des groupes).
MULTIVAR_FEATURES = {
    "score_adequation": "Adéquation sectorielle",
    "score_recrutement": "Recrutement",
    "score_reputation": "Réputation",
    "score_localisation": "Localisation",
    "score_contact": "Contact",
    "note": "Note",
    "nombre_avis": "Avis (log)",
    "nb_offres": "Offres",
}

# Mot-clé utilisé pour nommer automatiquement un groupe selon sa
# variable la plus marquée.
CLUSTER_PHRASES = {
    "Adéquation sectorielle": "secteur très ciblé",
    "Recrutement": "recrutement actif",
    "Réputation": "bonne réputation",
    "Localisation": "bien localisées",
    "Contact": "bien joignables",
    "Note": "bien notées",
    "Avis (log)": "très commentées",
    "Offres": "offres disponibles",
}


def _empty_multivariate(reason=""):
    """Résultat vide de l'analyse multivariée (avec une remarque éventuelle)."""

    if reason:
        resume = pd.DataFrame({
            "Indicateur": ["Remarque"],
            "Valeur": [reason],
        })
    else:
        resume = empty_dataframe(["Indicateur", "Valeur"])

    return {
        "Correlations": pd.DataFrame(),
        "ACP_coordonnees": empty_dataframe([
            "entreprise", "secteur", "priorite",
            "score_global", "PC1", "PC2", "groupe",
        ]),
        "ACP_variance": empty_dataframe([
            "composante", "variance_expliquee", "variance_cumulee",
        ]),
        "ACP_variables": empty_dataframe([
            "variable", "PC1", "PC2",
        ]),
        "Clusters": empty_dataframe([
            "entreprise", "secteur", "priorite",
            "score_global", "groupe",
        ]),
        "Profils_clusters": empty_dataframe([
            "groupe", "entreprises",
            "score_global_moyen", "pct_cible_ia_tech",
        ]),
        "Multivarie_resume": resume,
    }


def _feature_matrix(scored, offers=None):
    """
    Construit la matrice des variables actives.

    Retour :
        features : DataFrame numérique (colonnes = libellés affichés)
        meta     : DataFrame descriptif (entreprise, secteur, priorité...)
    """

    df = ensure_columns(
        scored,
        COLONNES_ENTREPRISES + ["score_global", "pertinence", "priorite"]
    ).reset_index(drop=True)

    # Nombre d'offres rattachées à chaque entreprise
    if isinstance(offers, pd.DataFrame) and not offers.empty:
        df["nb_offres"] = [
            len(offers_by_company(offers, row))
            for _, row in df.iterrows()
        ]
    else:
        df["nb_offres"] = 0

    nan = float("nan")
    features = pd.DataFrame(index=df.index)

    for column in MULTIVAR_FEATURES:
        if column in df.columns:
            features[column] = df[column].apply(
                lambda value: safe_number(value, nan)
            )

    # Une note <= 0 signifie « non renseignée » : valeur manquante
    if "note" in features.columns:
        features["note"] = features["note"].where(features["note"] > 0)

    # Le nombre d'avis est très asymétrique : transformation log(1 + x)
    if "nombre_avis" in features.columns:
        features["nombre_avis"] = (
            features["nombre_avis"]
            .fillna(0)
            .clip(lower=0)
            .apply(math.log1p)
        )

    # Imputation par la médiane, puis suppression des variables constantes
    # (une variable sans variance n'apporte rien à l'ACP).
    features = features.fillna(features.median()).fillna(0)
    features = features.loc[:, features.std(ddof=0) > 1e-9]
    features = features.rename(columns=MULTIVAR_FEATURES)

    names = [
        short_company_name(safe_text(nom_affiche) or safe_text(nom))
        for nom_affiche, nom in zip(df["nom_affiche"], df["nom"])
    ]

    meta = pd.DataFrame(
        {
            "entreprise": names,
            "secteur": df["secteur"].apply(
                lambda value: safe_text(value) or "Non renseigné"
            ),
            "priorite": df["priorite"].apply(safe_text),
            "pertinence": df["pertinence"].apply(safe_text),
            "score_global": pd.to_numeric(
                df["score_global"],
                errors="coerce"
            ).fillna(0),
        },
        index=df.index
    )

    return features, meta


def correlation_matrix(features, meta):
    """Matrice de corrélations (variables actives + score global)."""

    data = features.copy()
    data["Score global"] = meta["score_global"]

    return data.corr().fillna(0).round(2)


def pca_analysis(features, meta):
    """
    ACP normée sur les variables actives.

    Retour :
        coords    : coordonnées des entreprises sur PC1 / PC2
        variance  : variance expliquée par composante
        variables : corrélations variables-composantes (cercle des corrélations)
    """

    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    X = StandardScaler().fit_transform(features)

    pca = PCA(random_state=42).fit(X)
    projected = pca.transform(X)

    coords = meta[
        ["entreprise", "secteur", "priorite", "score_global"]
    ].copy()
    coords["PC1"] = projected[:, 0].round(3)
    coords["PC2"] = projected[:, 1].round(3) if projected.shape[1] > 1 else 0.0

    ratios = pca.explained_variance_ratio_ * 100

    variance = pd.DataFrame({
        "composante": [f"PC{i + 1}" for i in range(len(ratios))],
        "variance_expliquee": ratios.round(1),
        "variance_cumulee": ratios.cumsum().round(1),
    })

    # Corrélation de chaque variable avec chaque composante
    loadings = pca.components_.T * (pca.explained_variance_ ** 0.5)

    variables = pd.DataFrame(
        {
            "variable": list(features.columns),
            "PC1": loadings[:, 0].round(3),
            "PC2": loadings[:, 1].round(3) if loadings.shape[1] > 1 else 0.0,
        }
    )

    return coords, variance, variables


def cluster_companies(features, meta, k=None, max_k=6):
    """
    Regroupe les entreprises par K-means.

    Si k est None, le nombre de groupes (2 à max_k) est choisi
    automatiquement avec le meilleur coefficient de silhouette.

    Les groupes sont numérotés par score global moyen décroissant
    (Groupe 1 = le plus pertinent) et nommés selon leur variable dominante.

    Retour : (groupes, profils, silhouette, k_final)
    """

    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    X = StandardScaler().fit_transform(features)
    n = len(features)
    upper = min(max_k, n - 1)

    if upper < 2:
        raise ValueError("pas assez d'entreprises pour former des groupes.")

    def fit(n_clusters):
        model = KMeans(
            n_clusters=n_clusters,
            n_init=10,
            random_state=42
        ).fit(X)

        labels = model.labels_

        if len(set(labels)) > 1:
            silhouette = float(silhouette_score(X, labels))
        else:
            silhouette = -1.0

        return labels, silhouette

    if k is None:
        best = None

        for candidate in range(2, upper + 1):
            labels, silhouette = fit(candidate)

            if best is None or silhouette > best[0]:
                best = (silhouette, candidate, labels)

        silhouette, k_final, raw = best

    else:
        k_final = max(2, min(int(k), upper))
        raw, silhouette = fit(k_final)

    raw = pd.Series(raw, index=features.index)

    # Classement des groupes par score global moyen décroissant
    order = (
        meta["score_global"]
        .groupby(raw)
        .mean()
        .sort_values(ascending=False)
        .index
    )

    # Moyenne standardisée de chaque variable par groupe (pour le nommage)
    z_means = (
        pd.DataFrame(X, index=features.index, columns=features.columns)
        .groupby(raw)
        .mean()
    )

    labels_map = {}

    for position, cluster in enumerate(order, start=1):
        z_row = z_means.loc[cluster]

        if z_row.max() >= 0.3:
            phrase = CLUSTER_PHRASES.get(z_row.idxmax(), z_row.idxmax())
        else:
            phrase = "profil moyen"

        labels_map[cluster] = f"Groupe {position} · {phrase}"

    groups = raw.map(labels_map)

    # Profils moyens par groupe (échelle d'origine)
    profile = features.copy()
    profile["groupe"] = groups
    profile["score_global"] = meta["score_global"]
    profile["cible"] = (meta["pertinence"] == "Cible IA/Tech")

    grouped = profile.groupby("groupe")

    profiles = grouped[list(features.columns)].mean().round(2)
    profiles.insert(0, "entreprises", grouped.size())
    profiles.insert(1, "score_global_moyen", grouped["score_global"].mean().round(1))
    profiles.insert(2, "pct_cible_ia_tech", (grouped["cible"].mean() * 100).round(0))

    profiles = (
        profiles
        .reset_index()
        .sort_values("groupe")
        .reset_index(drop=True)
    )

    return groups, profiles, silhouette, k_final


def multivariate_analysis(scored, offers=None, k=None):
    """
    Analyse multivariée complète des entreprises.

    Paramètres :
        scored : DataFrame retourné par compute_scores()
        offers : DataFrame des offres (facultatif)
        k      : nombre de groupes (None = choix automatique)

    Clés retournées :
        Correlations, ACP_coordonnees, ACP_variance, ACP_variables,
        Clusters, Profils_clusters, Multivarie_resume

    La fonction ne lève jamais d'exception : en cas de problème
    (données insuffisantes, scikit-learn absent...), elle renvoie des
    tableaux vides et une remarque dans Multivarie_resume.
    """

    if not isinstance(scored, pd.DataFrame) or scored.empty:
        return _empty_multivariate(
            "Aucune entreprise disponible pour l'analyse multivariée."
        )

    try:
        features, meta = _feature_matrix(scored, offers)
    except Exception as exc:
        return _empty_multivariate(f"Préparation impossible : {exc}")

    if features.shape[1] < 2 or len(features) < 4:
        return _empty_multivariate(
            "Données insuffisantes : il faut au moins 4 entreprises "
            "et 2 variables qui varient."
        )

    result = _empty_multivariate()
    result["Correlations"] = correlation_matrix(features, meta)

    try:
        import sklearn  # noqa: F401
    except ImportError:
        result["Multivarie_resume"] = pd.DataFrame({
            "Indicateur": ["Remarque"],
            "Valeur": [
                "scikit-learn n'est pas installé "
                "(pip install scikit-learn) : seules les corrélations "
                "sont disponibles."
            ],
        })
        return result

    try:
        coords, variance, variables = pca_analysis(features, meta)

        groups, profiles, silhouette, k_final = cluster_companies(
            features,
            meta,
            k=k
        )

    except Exception as exc:
        result["Multivarie_resume"] = pd.DataFrame({
            "Indicateur": ["Remarque"],
            "Valeur": [f"Calcul impossible : {exc}"],
        })
        return result

    coords["groupe"] = groups

    clusters = (
        meta[["entreprise", "secteur", "priorite", "score_global"]]
        .assign(groupe=groups)
        .sort_values(
            ["groupe", "score_global"],
            ascending=[True, False]
        )
        .reset_index(drop=True)
    )

    explained = variance["variance_expliquee"].iloc[:2].sum()

    result.update({
        "ACP_coordonnees": coords,
        "ACP_variance": variance,
        "ACP_variables": variables,
        "Clusters": clusters,
        "Profils_clusters": profiles,
        "Multivarie_resume": pd.DataFrame({
            "Indicateur": [
                "Entreprises analysées",
                "Variables actives",
                "Variance expliquée (PC1 + PC2)",
                "Nombre de groupes",
                "Coefficient de silhouette",
            ],
            "Valeur": [
                str(len(features)),
                ", ".join(features.columns),
                f"{explained:.1f} %",
                str(k_final),
                f"{silhouette:.2f}",
            ],
        }),
    })

    return result


# ============================================================
# PRÉPARATION DES DONNÉES POUR LES GRAPHES MULTIVARIÉS
# ============================================================

OFFRES_ENRICHIES_COLONNES = COLONNES_OFFRES + [
    "secteur",
    "score_entreprise",
    "entreprise_nom",
    "offres_entreprise",
    "salaire_num",
    "experience_ans",
    "date_pub",
]


def parse_salary(value):
    """
    Extrait un salaire mensuel moyen (MAD) d'un texte libre.

    Exemples : « 4 000 - 6 000 MAD » -> 5000 ; « Selon profil » -> NaN.
    Les nombres inférieurs à 500 sont ignorés (ce ne sont pas des salaires).
    """

    text = safe_text(value)

    if not text:
        return float("nan")

    # « 4 000 » ou « 4.000 » -> 4000
    text = re.sub(r"(?<=\d)[\s\u00a0.](?=\d{3}(?!\d))", "", text)

    numbers = [
        float(number.replace(",", "."))
        for number in re.findall(r"\d+(?:[.,]\d+)?", text)
    ]

    numbers = [number for number in numbers if number >= 500][:2]

    if not numbers:
        return float("nan")

    return sum(numbers) / len(numbers)


def parse_experience(value):
    """
    Extrait l'expérience demandée en années.

    Exemples : « 2 ans » -> 2 ; « 6 mois » -> 0.5 ; « Débutant » -> 0.
    """

    raw = safe_text(value)
    text = normalize_text(raw)

    if not text:
        return float("nan")

    if re.search(r"debutant|sans experience|jeune diplome|aucune", text):
        return 0.0

    numbers = [
        float(number.replace(",", "."))
        for number in re.findall(r"\d+(?:[.,]\d+)?", raw)
    ][:2]

    if not numbers:
        return float("nan")

    average = sum(numbers) / len(numbers)

    if "mois" in text and not re.search(r"\bans?\b", text):
        average = average / 12

    return min(average, 30.0)


def add_offer_counts(scored, offers=None):
    """
    Retourne les entreprises scorées avec une colonne nb_offres
    et des colonnes numériques propres (score_global, note, nombre_avis).
    """

    if not isinstance(scored, pd.DataFrame) or scored.empty:
        return pd.DataFrame()

    df = ensure_columns(
        scored,
        COLONNES_ENTREPRISES + ["score_global"]
    ).reset_index(drop=True)

    if isinstance(offers, pd.DataFrame) and not offers.empty:
        df["nb_offres"] = [
            len(offers_by_company(offers, row))
            for _, row in df.iterrows()
        ]
    else:
        df["nb_offres"] = 0

    df["secteur"] = df["secteur"].apply(
        lambda value: safe_text(value) or "Non renseigné"
    )

    df["nom_affiche"] = [
        short_company_name(safe_text(nom_affiche) or safe_text(nom))
        for nom_affiche, nom in zip(df["nom_affiche"], df["nom"])
    ]

    for column in ["score_global", "note", "nombre_avis"]:
        df[column] = df[column].apply(lambda value: safe_number(value, 0))

    return df


def enrich_offers(offers, scored=None):
    """
    Enrichit les offres :
        - secteur et score de l'entreprise rattachée
        - entreprise_nom, offres_entreprise
        - salaire_num (MAD), experience_ans (années)
        - date_pub (date de publication, ou de collecte à défaut)
        - valeurs vides remplacées par « Non renseigné »
    """

    if not isinstance(offers, pd.DataFrame) or offers.empty:
        return empty_dataframe(OFFRES_ENRICHIES_COLONNES)

    df = ensure_columns(offers, COLONNES_OFFRES).reset_index(drop=True)

    name_column = first_existing_column(
        df,
        ["entreprise", "company_name", "nom_entreprise", "nom"]
    )

    if name_column:
        df["entreprise_nom"] = df[name_column].apply(
            lambda value: short_company_name(safe_text(value))
        )
    else:
        df["entreprise_nom"] = "Entreprise inconnue"

    df["offres_entreprise"] = (
        df.groupby("entreprise_nom")["entreprise_nom"].transform("size")
    )

    for column in ["contrat", "niveau_etudes", "ville"]:
        df[column] = df[column].apply(
            lambda value: safe_text(value) or "Non renseigné"
        )

    # Rattachement aux entreprises scorées (secteur, score)
    df["secteur"] = "Non rattaché"
    df["score_entreprise"] = float("nan")

    if isinstance(scored, pd.DataFrame) and not scored.empty:

        matched = pd.Series(False, index=df.index)

        for _, company in scored.iterrows():

            found = offers_by_company(df, company)

            if found.empty:
                continue

            index = [i for i in found.index if not matched.loc[i]]

            if not index:
                continue

            df.loc[index, "secteur"] = (
                safe_text(company.get("secteur")) or "Non renseigné"
            )

            df.loc[index, "score_entreprise"] = safe_number(
                company.get("score_global"),
                float("nan")
            )

            matched.loc[index] = True

    df["salaire_num"] = df["salaire"].apply(parse_salary)
    df["experience_ans"] = df["experience"].apply(parse_experience)

    published = pd.to_datetime(
        df["date_publication"],
        errors="coerce",
        dayfirst=True,
        utc=True
    )

    collected = pd.to_datetime(
        df["date_collecte"],
        errors="coerce",
        dayfirst=True,
        utc=True
    )

    df["date_pub"] = published.fillna(collected).dt.tz_convert(None)

    return df


def company_features(scored, offers=None):
    """Matrice des variables actives (features) et description (meta)."""
    return _feature_matrix(scored, offers)


# ============================================================
# EXPLORATION ET ANALYSE DES DONNÉES
# ============================================================

def explore(companies, offers=None):
    """
    Effectue l'exploration complète.

    Les clés retournées sont prévues pour être utilisées
    dans pipeline.py et visualize.py.
    """

    empty_sectors = empty_dataframe([
        "secteur",
        "nombre_entreprises",
        "score_moyen",
    ])

    empty_priorities = empty_dataframe([
        "priorite",
        "nombre_entreprises",
    ])

    empty_notes = empty_dataframe([
        "tranche",
        "entreprises",
    ])

    empty_contracts = empty_dataframe([
        "contrat",
        "offres",
    ])

    empty_weeks = empty_dataframe([
        "semaine",
        "offres",
    ])

    # --------------------------------------------------------
    # Normalisation des entrées
    # --------------------------------------------------------

    if not isinstance(companies, pd.DataFrame):
        companies = pd.DataFrame()

    if not isinstance(offers, pd.DataFrame):
        offers = pd.DataFrame()

    # --------------------------------------------------------
    # Cas sans entreprises
    # --------------------------------------------------------

    if companies.empty:

        return {
            "Entreprises_scorees": pd.DataFrame(),
            "Top_priorites": pd.DataFrame(),
            "Insights": [
                "Aucune entreprise disponible pour l'analyse."
            ],
            "Par_secteur": empty_sectors,
            "Analyse_secteurs": empty_sectors,
            "Repartition_priorites": empty_priorities,
            "Distribution_notes": empty_notes,
            "Offres_par_contrat": empty_contracts,
            "Offres_par_semaine": empty_weeks,
            **_empty_multivariate(
                "Aucune entreprise disponible pour l'analyse multivariée."
            ),
        }

    # --------------------------------------------------------
    # Calcul des scores
    # --------------------------------------------------------

    scored = compute_scores(
        companies,
        offers
    )

    # --------------------------------------------------------
    # Classement des priorités
    # --------------------------------------------------------

    priorities = top_priorities(scored)

    # --------------------------------------------------------
    # Analyse par secteur
    # --------------------------------------------------------

    if "secteur" in scored.columns:

        sector_source = scored.copy()

        sector_source["secteur"] = (
            sector_source["secteur"]
            .fillna("Non renseigné")
            .replace("", "Non renseigné")
        )

        # size() compte toutes les lignes, même si id_entreprise
        # est vide. Cela évite de sous-estimer les effectifs.
        sectors_df = (
            sector_source
            .groupby("secteur", dropna=False)
            .agg(
                nombre_entreprises=("secteur", "size"),
                score_moyen=("score_global", "mean"),
            )
            .reset_index()
        )

        sectors_df["score_moyen"] = (
            sectors_df["score_moyen"].round(2)
        )

        sectors_df = sectors_df.sort_values(
            "nombre_entreprises",
            ascending=False
        ).reset_index(drop=True)

    else:
        sectors_df = empty_sectors.copy()

    # --------------------------------------------------------
    # Répartition des priorités
    # --------------------------------------------------------

    if "priorite" in scored.columns:

        priorities_df = (
            scored["priorite"]
            .fillna("Non renseignée")
            .value_counts()
            .rename_axis("priorite")
            .reset_index(name="nombre_entreprises")
        )

    else:
        priorities_df = empty_priorities.copy()

    # --------------------------------------------------------
    # Distribution des notes
    # --------------------------------------------------------
    notes_df = distribution_notes(companies)
    # --------------------------------------------------------
    # Statistiques des offres
    # --------------------------------------------------------

    contracts_df = offers_by_contract(offers)

    weeks_df = offers_over_time(offers)

    # --------------------------------------------------------
    # Analyse multivariée
    # --------------------------------------------------------
    multivariate = multivariate_analysis(
        scored,
        offers
    )
    # --------------------------------------------------------
    # Insights
    # --------------------------------------------------------
    analysis_insights = insights(
        scored,
        priorities=priorities
    )

    # --------------------------------------------------------
    # Résultat final
    # --------------------------------------------------------

    return {
        "Entreprises_scorees": scored,
        "Top_priorites": priorities,
        "Insights": analysis_insights,

        # Analyse sectorielle
        "Par_secteur": sectors_df,
        "Analyse_secteurs": sectors_df,

        # Répartition des priorités
        "Repartition_priorites": priorities_df,

        # Distribution des notes
        "Distribution_notes": notes_df,

        # Statistiques des offres
        "Offres_par_contrat": contracts_df,
        "Offres_par_semaine": weeks_df,

        # Analyse multivariée
        **multivariate,
    }