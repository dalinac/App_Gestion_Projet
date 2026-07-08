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


def phase_segments(phase):
    """
    Périodes d'une phase, sous forme de liste de couples (début, fin) de dates.

    Une phase peut se dérouler en plusieurs temps (alternance, creux d'un mois,
    etc.) : ces périodes sont stockées dans le champ ``segments`` (liste de
    dicts {"start_date", "end_date"}). En l'absence de segments, on retombe sur
    la période unique décrite par ``start_date`` / ``end_date``.

    Les couples renvoyés sont triés et ne contiennent que des dates valides.
    """
    result = []
    for seg in (phase.get("segments") or []):
        a = parse_date(seg.get("start_date"))
        b = parse_date(seg.get("end_date"))
        if a and b and b >= a:
            result.append((a, b))
    if not result:
        a = parse_date(phase.get("start_date"))
        b = parse_date(phase.get("end_date"))
        if a and b and b >= a:
            result.append((a, b))
    return sorted(result)


def phase_active_days(phase):
    """
    Nombre de jours réellement travaillés d'une phase = somme de la durée de
    ses périodes (les creux entre périodes ne sont donc pas comptés).
    """
    return sum(max((b - a).days, 1) for a, b in phase_segments(phase))


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
        weight = phase_active_days(p) or 1
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
        durations.append((p["name"], phase_active_days(p)))
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
    Retourne (date_debut, date_fin) du projet en prenant l'amplitude la PLUS
    LARGE entre les dates saisies sur le projet et l'étendue réelle des phases.

    Motivation : le formulaire de création met par défaut début = fin =
    aujourd'hui. Si l'utilisateur ne corrige que partiellement ces dates, se
    fier aux seules dates du projet fausserait le calcul du temps écoulé (100 %
    dès aujourd'hui) alors que les phases décrivent un planning bien plus long.
    On combine donc les deux sources.
    """
    starts = [parse_date(p.get("start_date")) for p in phases]
    ends = [parse_date(p.get("end_date")) for p in phases]
    starts = [d for d in starts if d]
    ends = [d for d in ends if d]

    if project:
        ps = parse_date(project.get("start_date"))
        pe = parse_date(project.get("end_date"))
        if ps:
            starts.append(ps)
        if pe:
            ends.append(pe)

    start = min(starts) if starts else None
    end = max(ends) if ends else None
    return start, end


def project_health(project, phases, reference=None):
    """
    Indicateur de santé du projet : compare l'avancement réel (avancement global
    pondéré par la durée des phases) au temps écoulé entre le début et la
    deadline.

    On utilise l'avancement global (le même indicateur que le KPI « Avancement
    global ») plutôt qu'un simple décompte des phases « Terminé » : une phase à
    60 % compte pour 60 %, ce qui évite de paraître injustement en retard tant
    qu'aucune phase n'est totalement bouclée.

    Retourne un dict :
        {
          "progress_pct": float,  # % d'avancement réel (pondéré)
          "time_pct": float,      # % de temps écoulé
          "delta": float,         # progress_pct - time_pct (positif = en avance)
          "status": str,          # 'En avance' / 'Dans les temps' / 'En retard'
          "color": str,           # couleur associée au statut
          "available": bool,      # False si dates manquantes
        }
    """
    ref = reference or date.today()
    start, end = project_bounds(project, phases)

    result = {"progress_pct": 0.0, "time_pct": 0.0, "delta": 0.0,
              "status": "Indéterminé", "color": "#C9C0B2", "available": False}

    if not phases or not start or not end or end <= start:
        return result

    progress_pct = float(global_progress(phases))

    total_days = (end - start).days
    elapsed = (ref - start).days
    time_pct = max(0.0, min(100.0, elapsed / total_days * 100)) if total_days else 0.0

    delta = progress_pct - time_pct
    # Tolérance de +/- 7 points pour considérer le projet "dans les temps"
    if delta >= 7:
        status, color = "En avance", "#7FA86B"      # vert sauge
    elif delta <= -7:
        status, color = "En retard", "#B5654A"       # terracotta/brique
    else:
        status, color = "Dans les temps", "#C9A66B"  # ocre

    result.update({
        "progress_pct": round(progress_pct, 1),
        "time_pct": round(time_pct, 1),
        "delta": round(delta, 1),
        "status": status,
        "color": color,
        "available": True,
    })
    return result
