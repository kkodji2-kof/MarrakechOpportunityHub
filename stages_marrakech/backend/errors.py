"""Liste des erreurs métier du backend (affichables telles quelles dans le frontend)."""
class OpportunityHubError(Exception):
    """Erreur de base : le message est destiné à l'utilisateur."""
class DataSourceError(OpportunityHubError):
    """Fichier de données introuvable, vide ou illisible."""
class GooglePlacesError(OpportunityHubError):
    """Clé absente, quota dépassé ou réponse invalide de l'API Google Places."""
class ValidationError(OpportunityHubError):
    """Donnée saisie invalide (statut inconnu, date mal formée, entreprise introuvable)."""
