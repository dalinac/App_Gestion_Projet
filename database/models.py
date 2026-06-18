"""
Couche d'accès aux données (CRUD) au-dessus du document JSON (``database.db``).

L'API publique est strictement identique à la version SQL précédente : les
modules de l'application n'ont pas à changer. Les fonctions renvoient des copies
des enregistrements (dictionnaires) afin que l'état interne ne soit jamais muté
par accident, et reproduisent les enrichissements attendus (``phase_name``,
``phase_color``) ainsi que les tris.

Portée par utilisateur : les projets sont rattachés à un ``username`` et ne sont
lisibles/modifiables que par leur propriétaire. La hiérarchie est centrée sur les
phases (qui portent les dates et les dépendances) ; les tâches sont de simples
éléments cochables appartenant à une phase.
"""

from database import db


def _clone(row):
    return dict(row) if row else None


def _phase_index(data):
    """Index id -> phase (pour les enrichissements)."""
    return {p["id"]: p for p in data["phases"]}


# ===========================================================================
# PROJETS (rattachés à un username)
# ===========================================================================

def get_projects(username):
    data = db.get_data()
    rows = [p for p in data["projects"] if p.get("username") == username]
    rows.sort(key=lambda p: p["id"], reverse=True)
    return [_clone(p) for p in rows]


def get_project(project_id):
    data = db.get_data()
    for p in data["projects"]:
        if p["id"] == project_id:
            return _clone(p)
    return None


def create_project(username, name, description, start_date, end_date):
    new_id = db.next_id()
    with db.transaction() as data:
        data["projects"].append({
            "id": new_id, "username": username, "name": name,
            "description": description, "start_date": start_date, "end_date": end_date,
        })
    return new_id


def update_project(project_id, name, description, start_date, end_date):
    with db.transaction() as data:
        for p in data["projects"]:
            if p["id"] == project_id:
                p.update(name=name, description=description,
                         start_date=start_date, end_date=end_date)
                break


def delete_project(project_id):
    with db.transaction() as data:
        phase_ids = {ph["id"] for ph in data["phases"] if ph["project_id"] == project_id}
        data["projects"] = [p for p in data["projects"] if p["id"] != project_id]
        data["phases"] = [ph for ph in data["phases"] if ph["project_id"] != project_id]
        data["tasks"] = [t for t in data["tasks"] if t["phase_id"] not in phase_ids]
        data["deliverables"] = [d for d in data["deliverables"] if d["phase_id"] not in phase_ids]
        data["phase_dependencies"] = [
            d for d in data["phase_dependencies"]
            if d["phase_id"] not in phase_ids and d["depends_on_phase_id"] not in phase_ids
        ]
        data["meetings"] = [m for m in data["meetings"] if m["project_id"] != project_id]


# ===========================================================================
# PHASES (coeur du système : dates obligatoires, avancement, dépendances)
# ===========================================================================

def get_phases(project_id):
    data = db.get_data()
    rows = [p for p in data["phases"] if p["project_id"] == project_id]
    rows.sort(key=lambda p: (p.get("order_index", 0), p["id"]))
    return [_clone(p) for p in rows]


def get_phase(phase_id):
    data = db.get_data()
    for p in data["phases"]:
        if p["id"] == phase_id:
            return _clone(p)
    return None


def create_phase(project_id, name, description, start_date, end_date,
                 status="À faire", progress=0, version="V1", color="#C9A66B",
                 order_index=0, comments=""):
    new_id = db.next_id()
    with db.transaction() as data:
        data["phases"].append({
            "id": new_id, "project_id": project_id, "name": name,
            "description": description, "start_date": start_date, "end_date": end_date,
            "status": status, "progress": progress, "version": version, "color": color,
            "order_index": order_index, "comments": comments,
        })
    return new_id


def update_phase(phase_id, **fields):
    allowed = {"name", "description", "start_date", "end_date", "status",
               "progress", "version", "color", "order_index", "comments"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    with db.transaction() as data:
        for p in data["phases"]:
            if p["id"] == phase_id:
                p.update(updates)
                break


def update_phase_progress(phase_id, progress):
    with db.transaction() as data:
        for p in data["phases"]:
            if p["id"] == phase_id:
                p["progress"] = progress
                break


def delete_phase(phase_id):
    with db.transaction() as data:
        data["phases"] = [p for p in data["phases"] if p["id"] != phase_id]
        data["tasks"] = [t for t in data["tasks"] if t["phase_id"] != phase_id]
        data["deliverables"] = [d for d in data["deliverables"] if d["phase_id"] != phase_id]
        data["phase_dependencies"] = [
            d for d in data["phase_dependencies"]
            if d["phase_id"] != phase_id and d["depends_on_phase_id"] != phase_id
        ]
        for m in data["meetings"]:
            if m.get("phase_id") == phase_id:
                m["phase_id"] = None


# ===========================================================================
# TÂCHES (simples éléments cochables d'une phase)
# ===========================================================================

def get_tasks(phase_id=None, project_id=None):
    data = db.get_data()
    if phase_id is not None:
        rows = [t for t in data["tasks"] if t["phase_id"] == phase_id]
        rows.sort(key=lambda t: (t.get("order_index", 0), t["id"]))
        return [_clone(t) for t in rows]
    if project_id is not None:
        phases = _phase_index(data)
        project_phase_ids = {p["id"] for p in data["phases"] if p["project_id"] == project_id}
        rows = [t for t in data["tasks"] if t["phase_id"] in project_phase_ids]
        rows.sort(key=lambda t: (t.get("order_index", 0), t["id"]))
        enriched = []
        for t in rows:
            ph = phases.get(t["phase_id"], {})
            item = _clone(t)
            item["phase_name"] = ph.get("name")
            item["phase_color"] = ph.get("color")
            enriched.append(item)
        return enriched
    rows = sorted(data["tasks"], key=lambda t: (t.get("order_index", 0), t["id"]))
    return [_clone(t) for t in rows]


def create_task(phase_id, name, status="À faire", order_index=0):
    new_id = db.next_id()
    with db.transaction() as data:
        data["tasks"].append({
            "id": new_id, "phase_id": phase_id, "name": name,
            "status": status, "order_index": order_index,
        })
    return new_id


def set_task_status(task_id, status):
    with db.transaction() as data:
        for t in data["tasks"]:
            if t["id"] == task_id:
                t["status"] = status
                break


def rename_task(task_id, name):
    with db.transaction() as data:
        for t in data["tasks"]:
            if t["id"] == task_id:
                t["name"] = name
                break


def delete_task(task_id):
    with db.transaction() as data:
        data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]


# ===========================================================================
# DÉPENDANCES ENTRE PHASES (la phase B nécessite la phase A)
# ===========================================================================

def get_phase_dependencies(project_id):
    """Toutes les dépendances entre phases d'un projet."""
    data = db.get_data()
    project_phase_ids = {p["id"] for p in data["phases"] if p["project_id"] == project_id}
    return [_clone(d) for d in data["phase_dependencies"]
            if d["phase_id"] in project_phase_ids]


def get_phase_deps_for(phase_id):
    """Ids des phases dont dépend la phase donnée."""
    data = db.get_data()
    return [d["depends_on_phase_id"] for d in data["phase_dependencies"]
            if d["phase_id"] == phase_id]


def add_phase_dependency(phase_id, depends_on_phase_id):
    if phase_id == depends_on_phase_id:
        return
    with db.transaction() as data:
        for d in data["phase_dependencies"]:
            if d["phase_id"] == phase_id and d["depends_on_phase_id"] == depends_on_phase_id:
                return  # déjà présent (équivalent ON CONFLICT DO NOTHING)
        data["phase_dependencies"].append({
            "id": db.next_id(), "phase_id": phase_id,
            "depends_on_phase_id": depends_on_phase_id,
        })


def remove_phase_dependency(phase_id, depends_on_phase_id):
    with db.transaction() as data:
        data["phase_dependencies"] = [
            d for d in data["phase_dependencies"]
            if not (d["phase_id"] == phase_id and d["depends_on_phase_id"] == depends_on_phase_id)
        ]


# ===========================================================================
# LIVRABLES
# ===========================================================================

def get_deliverables(project_id):
    data = db.get_data()
    phases = _phase_index(data)
    project_phase_ids = {p["id"] for p in data["phases"] if p["project_id"] == project_id}
    rows = [d for d in data["deliverables"] if d["phase_id"] in project_phase_ids]
    rows.sort(key=lambda d: (d.get("due_date") or ""))
    enriched = []
    for d in rows:
        item = _clone(d)
        item["phase_name"] = phases.get(d["phase_id"], {}).get("name")
        enriched.append(item)
    return enriched


def create_deliverable(phase_id, name, nature, due_date, recipient, status="À faire"):
    new_id = db.next_id()
    with db.transaction() as data:
        data["deliverables"].append({
            "id": new_id, "phase_id": phase_id, "name": name, "nature": nature,
            "due_date": due_date, "recipient": recipient, "status": status,
        })
    return new_id


def update_deliverable(deliverable_id, **fields):
    allowed = {"name", "nature", "due_date", "recipient", "status", "phase_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    with db.transaction() as data:
        for d in data["deliverables"]:
            if d["id"] == deliverable_id:
                d.update(updates)
                break


def delete_deliverable(deliverable_id):
    with db.transaction() as data:
        data["deliverables"] = [d for d in data["deliverables"] if d["id"] != deliverable_id]


# ===========================================================================
# RÉUNIONS
# ===========================================================================

def get_meetings(project_id):
    data = db.get_data()
    phases = _phase_index(data)
    rows = [m for m in data["meetings"] if m["project_id"] == project_id]
    rows.sort(key=lambda m: (m.get("date") or "", m.get("time") or ""), reverse=True)
    enriched = []
    for m in rows:
        item = _clone(m)
        ph = phases.get(m.get("phase_id"))
        item["phase_name"] = ph.get("name") if ph else None
        enriched.append(item)
    return enriched


def get_meeting(meeting_id):
    data = db.get_data()
    for m in data["meetings"]:
        if m["id"] == meeting_id:
            return _clone(m)
    return None


def create_meeting(project_id, phase_id, date, time, participants, subject, report=""):
    new_id = db.next_id()
    with db.transaction() as data:
        data["meetings"].append({
            "id": new_id, "project_id": project_id, "phase_id": phase_id,
            "date": date, "time": time, "participants": participants,
            "subject": subject, "report": report,
        })
    return new_id


def update_meeting(meeting_id, **fields):
    allowed = {"phase_id", "date", "time", "participants", "subject", "report"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    with db.transaction() as data:
        for m in data["meetings"]:
            if m["id"] == meeting_id:
                m.update(updates)
                break


def delete_meeting(meeting_id):
    with db.transaction() as data:
        data["meetings"] = [m for m in data["meetings"] if m["id"] != meeting_id]
