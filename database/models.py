"""
Couche d'accès aux données (CRUD) au-dessus de SQLite.

Chaque entité (projet, phase, tâche, dépendance, livrable, réunion) dispose de
fonctions de lecture / création / mise à jour / suppression. Les fonctions
retournent des dictionnaires Python pour rester indépendantes de l'UI.
"""

from database.db import db_session


def _rows_to_dicts(rows):
    """Convertit une liste de sqlite3.Row en liste de dict."""
    return [dict(r) for r in rows]


# ===========================================================================
# PROJETS
# ===========================================================================

def get_projects():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return _rows_to_dicts(rows)


def get_project(project_id):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return dict(row) if row else None


def create_project(name, description, start_date, end_date):
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, description, start_date, end_date) VALUES (?,?,?,?)",
            (name, description, start_date, end_date),
        )
        return cur.lastrowid


def update_project(project_id, name, description, start_date, end_date):
    with db_session() as conn:
        conn.execute(
            "UPDATE projects SET name=?, description=?, start_date=?, end_date=? WHERE id=?",
            (name, description, start_date, end_date, project_id),
        )


def delete_project(project_id):
    with db_session() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))


# ===========================================================================
# PHASES
# ===========================================================================

def get_phases(project_id):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM phases WHERE project_id=? ORDER BY order_index, id",
            (project_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


def get_phase(phase_id):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM phases WHERE id=?", (phase_id,)).fetchone()
        return dict(row) if row else None


def create_phase(project_id, name, description, start_date, end_date,
                 status="À faire", progress=0, version="V1", color="#4C78A8",
                 order_index=0, comments=""):
    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO phases
               (project_id, name, description, start_date, end_date, status,
                progress, version, color, order_index, comments)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (project_id, name, description, start_date, end_date, status,
             progress, version, color, order_index, comments),
        )
        return cur.lastrowid


def update_phase(phase_id, **fields):
    """Met à jour dynamiquement les champs fournis d'une phase."""
    if not fields:
        return
    allowed = {"name", "description", "start_date", "end_date", "status",
               "progress", "version", "color", "order_index", "comments"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    clause = ", ".join(f"{k}=?" for k in sets)
    values = list(sets.values()) + [phase_id]
    with db_session() as conn:
        conn.execute(f"UPDATE phases SET {clause} WHERE id=?", values)


def update_phase_progress(phase_id, progress):
    """Raccourci pour mettre à jour uniquement l'avancement d'une phase."""
    with db_session() as conn:
        conn.execute("UPDATE phases SET progress=? WHERE id=?", (progress, phase_id))


def delete_phase(phase_id):
    with db_session() as conn:
        conn.execute("DELETE FROM phases WHERE id=?", (phase_id,))


# ===========================================================================
# TÂCHES
# ===========================================================================

def get_tasks(phase_id=None, project_id=None):
    """
    Récupère les tâches. Filtrable par phase ou par projet entier
    (jointure phases pour récupérer toutes les tâches d'un projet).
    """
    with db_session() as conn:
        if phase_id is not None:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE phase_id=? ORDER BY start_date, id",
                (phase_id,),
            ).fetchall()
        elif project_id is not None:
            rows = conn.execute(
                """SELECT t.*, p.name AS phase_name, p.color AS phase_color
                   FROM tasks t
                   JOIN phases p ON t.phase_id = p.id
                   WHERE p.project_id=?
                   ORDER BY t.start_date, t.id""",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks ORDER BY start_date, id").fetchall()
        return _rows_to_dicts(rows)


def get_task(task_id):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None


def create_task(phase_id, name, description, start_date, end_date,
                status="À faire", progress=0, assignee="", comments=""):
    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO tasks
               (phase_id, name, description, start_date, end_date, status,
                progress, assignee, comments)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (phase_id, name, description, start_date, end_date, status,
             progress, assignee, comments),
        )
        return cur.lastrowid


def update_task(task_id, **fields):
    allowed = {"name", "description", "start_date", "end_date", "status",
               "progress", "assignee", "comments", "phase_id"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    clause = ", ".join(f"{k}=?" for k in sets)
    values = list(sets.values()) + [task_id]
    with db_session() as conn:
        conn.execute(f"UPDATE tasks SET {clause} WHERE id=?", values)


def delete_task(task_id):
    with db_session() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))


# ===========================================================================
# DÉPENDANCES
# ===========================================================================

def get_dependencies(project_id):
    """Retourne toutes les dépendances des tâches d'un projet."""
    with db_session() as conn:
        rows = conn.execute(
            """SELECT d.* FROM dependencies d
               JOIN tasks t ON d.task_id = t.id
               JOIN phases p ON t.phase_id = p.id
               WHERE p.project_id=?""",
            (project_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


def get_task_dependencies(task_id):
    """Retourne les tâches dont dépend la tâche donnée."""
    with db_session() as conn:
        rows = conn.execute(
            "SELECT depends_on_task_id FROM dependencies WHERE task_id=?",
            (task_id,),
        ).fetchall()
        return [r["depends_on_task_id"] for r in rows]


def add_dependency(task_id, depends_on_task_id):
    if task_id == depends_on_task_id:
        return  # une tâche ne peut dépendre d'elle-même
    with db_session() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO dependencies (task_id, depends_on_task_id) VALUES (?,?)",
            (task_id, depends_on_task_id),
        )


def remove_dependency(task_id, depends_on_task_id):
    with db_session() as conn:
        conn.execute(
            "DELETE FROM dependencies WHERE task_id=? AND depends_on_task_id=?",
            (task_id, depends_on_task_id),
        )


# ===========================================================================
# LIVRABLES
# ===========================================================================

def get_deliverables(project_id):
    with db_session() as conn:
        rows = conn.execute(
            """SELECT dl.*, p.name AS phase_name
               FROM deliverables dl
               JOIN phases p ON dl.phase_id = p.id
               WHERE p.project_id=?
               ORDER BY dl.due_date""",
            (project_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


def create_deliverable(phase_id, name, nature, due_date, recipient, status="À faire"):
    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO deliverables (phase_id, name, nature, due_date, recipient, status)
               VALUES (?,?,?,?,?,?)""",
            (phase_id, name, nature, due_date, recipient, status),
        )
        return cur.lastrowid


def update_deliverable(deliverable_id, **fields):
    allowed = {"name", "nature", "due_date", "recipient", "status", "phase_id"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    clause = ", ".join(f"{k}=?" for k in sets)
    values = list(sets.values()) + [deliverable_id]
    with db_session() as conn:
        conn.execute(f"UPDATE deliverables SET {clause} WHERE id=?", values)


def delete_deliverable(deliverable_id):
    with db_session() as conn:
        conn.execute("DELETE FROM deliverables WHERE id=?", (deliverable_id,))


# ===========================================================================
# RÉUNIONS
# ===========================================================================

def get_meetings(project_id):
    with db_session() as conn:
        rows = conn.execute(
            """SELECT m.*, p.name AS phase_name
               FROM meetings m
               LEFT JOIN phases p ON m.phase_id = p.id
               WHERE m.project_id=?
               ORDER BY m.date DESC, m.time DESC""",
            (project_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


def get_meeting(meeting_id):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        return dict(row) if row else None


def create_meeting(project_id, phase_id, date, time, participants, subject, report=""):
    with db_session() as conn:
        cur = conn.execute(
            """INSERT INTO meetings
               (project_id, phase_id, date, time, participants, subject, report)
               VALUES (?,?,?,?,?,?,?)""",
            (project_id, phase_id, date, time, participants, subject, report),
        )
        return cur.lastrowid


def update_meeting(meeting_id, **fields):
    allowed = {"phase_id", "date", "time", "participants", "subject", "report"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    clause = ", ".join(f"{k}=?" for k in sets)
    values = list(sets.values()) + [meeting_id]
    with db_session() as conn:
        conn.execute(f"UPDATE meetings SET {clause} WHERE id=?", values)


def delete_meeting(meeting_id):
    with db_session() as conn:
        conn.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))
