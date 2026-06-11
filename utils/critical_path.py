"""
Calcul du chemin critique (Critical Path Method - CPM).

Le chemin critique est la plus longue chaîne de tâches dépendantes : tout retard
sur une de ces tâches décale la date de fin globale du projet. On l'identifie via
un double passage :
  - passe avant (forward pass)  : calcule les dates au plus tôt (ES/EF) ;
  - passe arrière (backward pass): calcule les dates au plus tard (LS/LF).
Une tâche est critique si sa marge totale (slack = LS - ES) est nulle.

L'implémentation s'appuie sur les durées réelles (dates de début/fin) et le
graphe de dépendances. Elle est volontairement autonome (aucune dépendance
externe) et tolère les données partielles.
"""

from datetime import datetime


def _parse_date(value):
    """Parse une date ISO 'YYYY-MM-DD'. Retourne None si invalide/absente."""
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _duration_days(task):
    """Durée d'une tâche en jours (>= 1) déduite de ses dates."""
    start = _parse_date(task.get("start_date"))
    end = _parse_date(task.get("end_date"))
    if start and end:
        return max((end - start).days, 1)
    return 1


def compute_critical_path(tasks, dependencies):
    """
    Calcule le chemin critique d'un ensemble de tâches.

    Paramètres
    ----------
    tasks : list[dict]
        Tâches avec au moins les clés id, start_date, end_date.
    dependencies : list[dict]
        Dépendances {task_id, depends_on_task_id} : task_id dépend de depends_on.

    Retour
    ------
    dict :
        {
          "critical_ids": set(...),   # ids des tâches critiques
          "slack": {id: marge_jours}, # marge totale par tâche
          "project_duration": int,    # durée totale (jours) du chemin le plus long
        }
    """
    if not tasks:
        return {"critical_ids": set(), "slack": {}, "project_duration": 0}

    # Index des tâches et de leurs durées
    durations = {t["id"]: _duration_days(t) for t in tasks}
    ids = set(durations.keys())

    # Construction du graphe : prédécesseurs et successeurs
    # predecessors[B] = [A] signifie B dépend de A (A doit finir avant B)
    predecessors = {tid: [] for tid in ids}
    successors = {tid: [] for tid in ids}
    for dep in dependencies:
        a = dep["depends_on_task_id"]   # prédécesseur
        b = dep["task_id"]              # successeur
        if a in ids and b in ids:
            predecessors[b].append(a)
            successors[a].append(b)

    # Tri topologique (algorithme de Kahn) pour ordonner les passages
    order = _topological_sort(ids, predecessors, successors)
    if order is None:
        # Cycle détecté : pas de chemin critique exploitable
        return {"critical_ids": set(), "slack": {tid: 0 for tid in ids},
                "project_duration": 0}

    # --- Passe avant : Earliest Start (ES) / Earliest Finish (EF) ---
    es, ef = {}, {}
    for tid in order:
        if predecessors[tid]:
            es[tid] = max(ef[p] for p in predecessors[tid])
        else:
            es[tid] = 0
        ef[tid] = es[tid] + durations[tid]

    project_duration = max(ef.values()) if ef else 0

    # --- Passe arrière : Latest Finish (LF) / Latest Start (LS) ---
    lf, ls = {}, {}
    for tid in reversed(order):
        if successors[tid]:
            lf[tid] = min(ls[s] for s in successors[tid])
        else:
            lf[tid] = project_duration
        ls[tid] = lf[tid] - durations[tid]

    # --- Marge (slack) et identification des tâches critiques ---
    slack = {tid: ls[tid] - es[tid] for tid in ids}
    critical_ids = {tid for tid in ids if slack[tid] == 0}

    return {
        "critical_ids": critical_ids,
        "slack": slack,
        "project_duration": project_duration,
    }


def _topological_sort(ids, predecessors, successors):
    """
    Tri topologique (Kahn). Retourne une liste ordonnée ou None si cycle.
    """
    indegree = {tid: len(predecessors[tid]) for tid in ids}
    queue = [tid for tid in ids if indegree[tid] == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for succ in successors[node]:
            indegree[succ] -= 1
            if indegree[succ] == 0:
                queue.append(succ)
    if len(order) != len(ids):
        return None  # cycle présent
    return order
