from __future__ import annotations
from pathlib import Path
import re
import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
# ============================================================
# CONVERSION DES DONNÉES EN DATAFRAME
# ============================================================
def to_dataframe(data):
    """Convertit différents types de données en DataFrame."""
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if data is None:
        return pd.DataFrame({
            "Information": ["Aucune donnée disponible"]
        })
    if isinstance(data, pd.Series):
        return data.to_frame().reset_index()
    if isinstance(data, dict):
        if not data:
            return pd.DataFrame()
        # Dictionnaire contenant des valeurs simples
        if all(
            not isinstance(value, (dict, pd.DataFrame, pd.Series))
            for value in data.values()
        ):
            try:
                return pd.DataFrame(data)
            except (ValueError, TypeError):
                return pd.DataFrame(
                    list(data.items()),
                    columns=["Indicateur", "Valeur"]
                )
        # Dictionnaire contenant des DataFrames ou listes
        rows = []

        for key, value in data.items():

            if isinstance(value, pd.DataFrame):
                rows.append({
                    "Indicateur": key,
                    "Valeur": f"{len(value)} lignes"
                })

            elif isinstance(value, (list, tuple)):
                rows.append({
                    "Indicateur": key,
                    "Valeur": "; ".join(map(str, value))
                })

            else:
                rows.append({
                    "Indicateur": key,
                    "Valeur": str(value)
                })

        return pd.DataFrame(rows)
    if isinstance(data, (list, tuple)):
        if not data:
            return pd.DataFrame()
        # Liste de dictionnaires
        if all(isinstance(item, dict) for item in data):
            return pd.DataFrame(data)
        # Liste de DataFrames
        if all(isinstance(item, pd.DataFrame) for item in data):
            return pd.concat(
                data,
                ignore_index=True
            )

        # Liste de valeurs simples, par exemple les insights
        return pd.DataFrame({
            "Valeur": [str(item) for item in data]
        })

    # Valeur simple : texte, nombre, booléen...
    return pd.DataFrame({
        "Valeur": [str(data)]
    })
# ============================================================
# NETTOYAGE DES DATES
# ============================================================

def prepare_dataframe_for_excel(data):
    """
    Convertit les données en DataFrame et retire
    les fuseaux horaires des dates.
    """
    result = to_dataframe(data)
    for column in result.columns:
        # Dates pandas avec fuseau horaire
        if isinstance(
            result[column].dtype,
            pd.DatetimeTZDtype
        ):
            result[column] = (
                result[column].dt.tz_localize(None)
            )
            continue
        # Dates stockées comme objets Python
        if result[column].dtype == "object":
            def remove_timezone(value):
                if isinstance(value, pd.Timestamp):
                    if value.tzinfo is not None:
                        return value.tz_localize(None)
                return value
            result[column] = (
                result[column].apply(remove_timezone)
            )
    return result
# ============================================================
# NOM DES FEUILLES EXCEL
# ============================================================
def safe_sheet_name(name, used_names):
    """Génère un nom de feuille Excel valide et unique."""
    name = re.sub(
        r'[\\/*?:\[\]]',
        "_",
        str(name)
    )
    name = name.strip("'").strip()
    if not name:
        name = "Feuille"
    original = name[:31]
    name = original
    counter = 1
    while name.lower() in used_names:
        suffix = f"_{counter}"
        name = (
            original[:31 - len(suffix)]
            + suffix
        )
        counter += 1
    used_names.add(name.lower())
    return name
# ============================================================
# MISE EN FORME EXCEL
# ============================================================
def _format_sheet(ws):
    """Applique une mise en forme professionnelle."""
    header_fill = PatternFill(
        "solid",
        fgColor="1F3864"
    )
    # En-têtes
    for cell in ws[1]:
        cell.font = Font(
            name="Arial",
            bold=True,
            color="FFFFFF",
            size=10
        )
        cell.fill = header_fill
        cell.alignment = Alignment(
            vertical="center",
            horizontal="center",
            wrap_text=True
        )
    # Largeur des colonnes
    for col_idx, column in enumerate(
        ws.columns,
        start=1
    ):
        longest = max(
            (
                len(str(cell.value))
                for cell in column
                if cell.value is not None
            ),
            default=8
        )
        ws.column_dimensions[
            get_column_letter(col_idx)
        ].width = min(
            max(longest + 2, 10),
            60
        )
    ws.row_dimensions[1].height = 30
    # Figer la première ligne
    ws.freeze_panes = "A2"
   # Filtres
    if ws.max_row > 1 and ws.max_column > 0:
        ws.auto_filter.ref = ws.dimensions
# ============================================================
# EXPORT EXCEL
# ============================================================

def write_excel(path: Path, sheets: dict) -> Path:
    """
    Exporte plusieurs types de données dans un classeur Excel.

    Chaque entrée du dictionnaire devient une feuille.
    """
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    if not isinstance(sheets, dict):
        raise TypeError(
            "Le paramètre sheets doit être un dictionnaire."
        )
    used_names = set()
    with pd.ExcelWriter(
        path,
        engine="openpyxl",
        datetime_format="DD/MM/YYYY",
        date_format="DD/MM/YYYY"
    ) as writer:
        if not sheets:
            df = pd.DataFrame({
                "Information": [
                    "Aucune donnée disponible"
                ]
            })
            df.to_excel(
                writer,
                sheet_name="Informations",
                index=False
            )
            _format_sheet(
                writer.sheets["Informations"]
            )

        for name, data in sheets.items():

            sheet_name = safe_sheet_name(
                name,
                used_names
            )

            try:
                clean_df = prepare_dataframe_for_excel(data)

                clean_df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )
                _format_sheet(
                    writer.sheets[sheet_name]
                )
                print(
                    f"[EXPORT] Feuille créée : {sheet_name}"
                )
            except Exception as error:
                raise RuntimeError(
                    f"Erreur pendant l'export de la feuille "
                    f"'{name}' : {error}"
                ) from error
    print(
        f"[EXPORT] Fichier Excel créé : {path}"
    )
    return path
