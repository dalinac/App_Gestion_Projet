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
    Avancement déduit des tâches d'une phase : pourcentage de tâches terminées.
    Retourne None si la phase ne contient aucune tâche.
    """
    if not tasks:
        return None
    done = sum(1 for t in tasks if t.get("status") == "Terminé")
    return round(done / len(tasks) * 100)


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


def phase_is_active_this_week(phase, reference=None):
    """
    Une phase est 'active cette semaine' si sa période (début->fin) chevauche
    la semaine courante et qu'elle n'est pas terminée.
    """
    if phase.get("status") == "Terminé":
        return False
    ref = reference or date.today()
    start_week = ref - timedelta(days=ref.weekday())
    end_week = start_week + timedelta(days=6)
    start = parse_date(phase.get("start_date")) or start_week
    end = parse_date(phase.get("end_date")) or start
    return start <= end_week and end >= start_week


def project_bounds(project, phases):
    """
    Retourne (date_debut, date_fin) du projet : on privilégie les dates du
    projet, avec repli sur l'amplitude des phases.
    """
    start = parse_date(project.get("start_date")) if project else None
    end = parse_date(project.get("end_date")) if project else None
    starts = [parse_date(p.get("start_date")) for p in phases]
    ends = [parse_date(p.get("end_date")) for p in phases]
    starts = [d for d in starts if d]
    ends = [d for d in ends if d]
    if not start and starts:
        start = min(starts)
    if not end and ends:
        end = max(ends)
    return start, end


def project_health(project, phases, reference=None):
    """
    Indicateur de santé du projet : compare l'avancement (part de phases
    terminées) au temps écoulé entre la date de début et la deadline.

    Retourne un dict :
        {
          "done_pct": float,      # % de phases terminées
          "time_pct": float,      # % de temps écoulé
          "delta": float,         # done_pct - time_pct (positif = en avance)
          "status": str,          # 'En avance' / 'Dans les temps' / 'En retard'
          "color": str,           # couleur associée au statut
          "available": bool,      # False si dates manquantes
        }
    """
    ref = reference or date.today()
    start, end = project_bounds(project, phases)

    result = {"done_pct": 0.0, "time_pct": 0.0, "delta": 0.0,
              "status": "Indéterminé", "color": "#C9C0B2", "available": False}

    if not phases or not start or not end or end <= start:
        return result

    done = sum(1 for p in phases if p.get("status") == "Terminé")
    done_pct = done / len(phases) * 100

    total_days = (end - start).days
    elapsed = (ref - start).days
    time_pct = max(0.0, min(100.0, elapsed / total_days * 100)) if total_days else 0.0

    delta = done_pct - time_pct
    # Tolérance de +/- 7 points pour considérer le projet "dans les temps"
    if delta >= 7:
        status, color = "En avance", "#7FA86B"      # vert sauge
    elif delta <= -7:
        status, color = "En retard", "#B5654A"       # terracotta/brique
    else:
        status, color = "Dans les temps", "#C9A66B"  # ocre

    result.update({
        "done_pct": round(done_pct, 1),
        "time_pct": round(time_pct, 1),
        "delta": round(delta, 1),
        "status": status,
        "color": color,
        "available": True,
    })
    return result
