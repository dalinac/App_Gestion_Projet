"""
Fonctions utilitaires transverses : calculs d'avancement, formats de dates,
constantes partagées (statuts, couleurs).
"""

from datetime import datetime, date, timedelta

# Statuts possibles pour tâches / phases / livrables
STATUSES = ["À faire", "En cours", "En attente", "Terminé"]

# Couleurs (tons naturels) associées aux statuts
STATUS_COLORS = {
    "À faire": "#C9C0B2",
    "En cours": "#D4B483",
    "En attente": "#C8967E",
    "Terminé": "#A9B388",
}

# Palette élégante par défaut pour les phases (crème, ocre, taupe, brun, sauge)
PHASE_PALETTE = [
    "#C9A66B", "#B5A081", "#A9B388", "#CBA890", "#9C8B7A",
    "#D8C3A5", "#B08968", "#C4B7A6", "#D4B483", "#A98B6F",
]


def parse_date(value):
    """Parse une date ISO. Retourne None si vide/invalide."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def format_date_fr(value):
    """Formate une date ISO au format français JJ/MM/AAAA."""
    d = parse_date(value)
    return d.strftime("%d/%m/%Y") if d else "—"


def phase_progress_from_tasks(tasks):
    """
    Calcule l'avancement d'une phase à partir de la moyenne pondérée
    (par durée) de l'avancement de ses tâches. Si aucune tâche, retourne None.
    """
    if not tasks:
        return None
    total_weight = 0
    weighted = 0
    for t in tasks:
        start = parse_date(t.get("start_date"))
        end = parse_date(t.get("end_date"))
        weight = max((end - start).days, 1) if (start and end) else 1
        weighted += (t.get("progress") or 0) * weight
        total_weight += weight
    return round(weighted / total_weight) if total_weight else 0


def global_progress(phases):
    """
    Avancement global du projet : moyenne pondérée (par durée) de l'avancement
    des phases.
    """
    if not phases:
        return 0
    total_weight = 0
    weighted = 0
    for p in phases:
        start = parse_date(p.get("start_date"))
        end = parse_date(p.get("end_date"))
        weight = max((end - start).days, 1) if (start and end) else 1
        weighted += (p.get("progress") or 0) * weight
        total_weight += weight
    return round(weighted / total_weight) if total_weight else 0


def phase_duration_share(phases):
    """
    Calcule la part (en %) de chaque phase dans la durée totale du projet.
    Retourne une liste de tuples (nom_phase, jours, pourcentage).
    """
    durations = []
    for p in phases:
        start = parse_date(p.get("start_date"))
        end = parse_date(p.get("end_date"))
        days = max((end - start).days, 1) if (start and end) else 0
        durations.append((p["name"], days))
    total = sum(d for _, d in durations)
    result = []
    for name, days in durations:
        pct = round(days / total * 100, 1) if total else 0
        result.append((name, days, pct))
    return result


def is_this_week(value, reference=None):
    """
    Indique si une date tombe dans la semaine courante (lundi -> dimanche).
    `reference` permet de fixer la date de référence (par défaut aujourd'hui).
    """
    d = parse_date(value)
    if not d:
        return False
    ref = reference or date.today()
    start_week = ref - timedelta(days=ref.weekday())   # lundi
    end_week = start_week + timedelta(days=6)           # dimanche
    return start_week <= d <= end_week


def task_is_active_this_week(task, reference=None):
    """
    Une tâche est 'à faire cette semaine' si sa période (début->fin) chevauche
    la semaine courante et qu'elle n'est pas terminée.
    """
    if task.get("status") == "Terminé":
        return False
    ref = reference or date.today()
    start_week = ref - timedelta(days=ref.weekday())
    end_week = start_week + timedelta(days=6)
    start = parse_date(task.get("start_date")) or start_week
    end = parse_date(task.get("end_date")) or start
    # Chevauchement d'intervalles [start, end] et [start_week, end_week]
    return start <= end_week and end >= start_week
