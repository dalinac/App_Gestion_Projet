"""
Couche d'accès aux données (CRUD) au-dessus de SQLAlchemy.

Le SQL est portable entre SQLite (local) et PostgreSQL/Supabase (cloud) :
paramètres nommés (:nom), ``RETURNING id`` pour récupérer la clé créée et
``ON CONFLICT DO NOTHING`` pour les insertions idempotentes. Les fonctions
retournent des dictionnaires Python pour rester indépendantes de l'interface.
"""

from sqlalchemy import text

from database.db import db_session, rows_to_dicts, row_to_dict


def _build_set_clause(fields, allowed):
    """
    Construit la clause ``SET col=:col`` pour une mise à jour dynamique.
    Retourne (clause_sql, dict_paramètres) ou (None, None) si rien à mettre à jour.
    """
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return None, None
    clause = ", ".join(f"{k}=:{k}" for k in sets)
    return clause, sets


# ===========================================================================
# PROJETS
# ===========================================================================

def get_projects():
    with db_session() as conn:
        res = conn.execute(text("SELECT * FROM projects ORDER BY created_at DESC, id DESC"))
        return rows_to_dicts(res)


def get_project(project_id):
    with db_session() as conn:
        res = conn.execute(text("SELECT * FROM projects WHERE id=:id"), {"id": project_id})
        return row_to_dict(res)


def create_project(name, description, start_date, end_date):
    with db_session() as conn:
        return conn.execute(
            text("""INSERT INTO projects (name, description, start_date, end_date)
                    VALUES (:name, :description, :start_date, :end_date) RETURNING id"""),
            {"name": name, "description": description,
             "start_date": start_date, "end_date": end_date},
        ).scalar()


def update_project(project_id, name, description, start_date, end_date):
    with db_session() as conn:
        conn.execute(
            text("""UPDATE projects
                    SET name=:name, description=:description,
                        start_date=:start_date, end_date=:end_date
                    WHERE id=:id"""),
            {"name": name, "description": description, "start_date": start_date,
             "end_date": end_date, "id": project_id},
        )


def delete_project(project_id):
    with db_session() as conn:
        conn.execute(text("DELETE FROM projects WHERE id=:id"), {"id": project_id})


# ===========================================================================
# PHASES
# ===========================================================================

def get_phases(project_id):
    with db_session() as conn:
        res = conn.execute(
            text("SELECT * FROM phases WHERE project_id=:p ORDER BY order_index, id"),
            {"p": project_id},
        )
        return rows_to_dicts(res)


def get_phase(phase_id):
    with db_session() as conn:
        res = conn.execute(text("SELECT * FROM phases WHERE id=:id"), {"id": phase_id})
        return row_to_dict(res)


def create_phase(project_id, name, description, start_date, end_date,
                 status="À faire", progress=0, version="V1", color="#C9A66B",
                 order_index=0, comments=""):
    with db_session() as conn:
        return conn.execute(
            text("""INSERT INTO phases
                    (project_id, name, description, start_date, end_date, status,
                     progress, version, color, order_index, comments)
                    VALUES (:project_id, :name, :description, :start_date, :end_date,
                            :status, :progress, :version, :color, :order_index, :comments)
                    RETURNING id"""),
            {"project_id": project_id, "name": name, "description": description,
             "start_date": start_date, "end_date": end_date, "status": status,
             "progress": progress, "version": version, "color": color,
             "order_index": order_index, "comments": comments},
        ).scalar()


def update_phase(phase_id, **fields):
    """Met à jour dynamiquement les champs fournis d'une phase."""
    allowed = {"name", "description", "start_date", "end_date", "status",
               "progress", "version", "color", "order_index", "comments"}
    clause, params = _build_set_clause(fields, allowed)
    if not clause:
        return
    params["id"] = phase_id
    with db_session() as conn:
        conn.execute(text(f"UPDATE phases SET {clause} WHERE id=:id"), params)


def update_phase_progress(phase_id, progress):
    """Raccourci pour mettre à jour uniquement l'avancement d'une phase."""
    with db_session() as conn:
        conn.execute(
            text("UPDATE phases SET progress=:pr WHERE id=:id"),
            {"pr": progress, "id": phase_id},
        )


def delete_phase(phase_id):
    with db_session() as conn:
        conn.execute(text("DELETE FROM phases WHERE id=:id"), {"id": phase_id})


# ===========================================================================
# TÂCHES
# ===========================================================================

def get_tasks(phase_id=None, project_id=None):
    """
    Récupère les tâches, filtrables par phase ou par projet entier
    (jointure phases pour récupérer toutes les tâches d'un projet).
    """
    with db_session() as conn:
        if phase_id is not None:
            res = conn.execute(
                text("SELECT * FROM tasks WHERE phase_id=:p ORDER BY start_date, id"),
                {"p": phase_id},
            )
        elif project_id is not None:
            res = conn.execute(
                text("""SELECT t.*, p.name AS phase_name, p.color AS phase_color
                        FROM tasks t
                        JOIN phases p ON t.phase_id = p.id
                        WHERE p.project_id=:p
                        ORDER BY t.start_date, t.id"""),
                {"p": project_id},
            )
        else:
            res = conn.execute(text("SELECT * FROM tasks ORDER BY start_date, id"))
        return rows_to_dicts(res)


def get_task(task_id):
    with db_session() as conn:
        res = conn.execute(text("SELECT * FROM tasks WHERE id=:id"), {"id": task_id})
        return row_to_dict(res)


def create_task(phase_id, name, description, start_date, end_date,
                status="À faire", progress=0, assignee="", comments=""):
    with db_session() as conn:
        return conn.execute(
            text("""INSERT INTO tasks
                    (phase_id, name, description, start_date, end_date, status,
                     progress, assignee, comments)
                    VALUES (:phase_id, :name, :description, :start_date, :end_date,
                            :status, :progress, :assignee, :comments)
                    RETURNING id"""),
            {"phase_id": phase_id, "name": name, "description": description,
             "start_date": start_date, "end_date": end_date, "status": status,
             "progress": progress, "assignee": assignee, "comments": comments},
        ).scalar()


def update_task(task_id, **fields):
    allowed = {"name", "description", "start_date", "end_date", "status",
               "progress", "assignee", "comments", "phase_id"}
    clause, params = _build_set_clause(fields, allowed)
    if not clause:
        return
    params["id"] = task_id
    with db_session() as conn:
        conn.execute(text(f"UPDATE tasks SET {clause} WHERE id=:id"), params)


def delete_task(task_id):
    with db_session() as conn:
        conn.execute(text("DELETE FROM tasks WHERE id=:id"), {"id": task_id})


# ===========================================================================
# DÉPENDANCES
# ===========================================================================

def get_dependencies(project_id):
    """Retourne toutes les dépendances des tâches d'un projet."""
    with db_session() as conn:
        res = conn.execute(
            text("""SELECT d.* FROM dependencies d
                    JOIN tasks t ON d.task_id = t.id
                    JOIN phases p ON t.phase_id = p.id
                    WHERE p.project_id=:p"""),
            {"p": project_id},
        )
        return rows_to_dicts(res)


def get_task_dependencies(task_id):
    """Retourne les ids des tâches dont dépend la tâche donnée."""
    with db_session() as conn:
        res = conn.execute(
            text("SELECT depends_on_task_id FROM dependencies WHERE task_id=:id"),
            {"id": task_id},
        )
        return [r["depends_on_task_id"] for r in res.mappings().all()]


def add_dependency(task_id, depends_on_task_id):
    if task_id == depends_on_task_id:
        return  # une tâche ne peut pas dépendre d'elle-même
    with db_session() as conn:
        conn.execute(
            text("""INSERT INTO dependencies (task_id, depends_on_task_id)
                    VALUES (:t, :d) ON CONFLICT DO NOTHING"""),
            {"t": task_id, "d": depends_on_task_id},
        )


def remove_dependency(task_id, depends_on_task_id):
    with db_session() as conn:
        conn.execute(
            text("""DELETE FROM dependencies
                    WHERE task_id=:t AND depends_on_task_id=:d"""),
            {"t": task_id, "d": depends_on_task_id},
        )


# ===========================================================================
# LIVRABLES
# ===========================================================================

def get_deliverables(project_id):
    with db_session() as conn:
        res = conn.execute(
            text("""SELECT dl.*, p.name AS phase_name
                    FROM deliverables dl
                    JOIN phases p ON dl.phase_id = p.id
                    WHERE p.project_id=:p
                    ORDER BY dl.due_date"""),
            {"p": project_id},
        )
        return rows_to_dicts(res)


def create_deliverable(phase_id, name, nature, due_date, recipient, status="À faire"):
    with db_session() as conn:
        return conn.execute(
            text("""INSERT INTO deliverables (phase_id, name, nature, due_date, recipient, status)
                    VALUES (:phase_id, :name, :nature, :due_date, :recipient, :status)
                    RETURNING id"""),
            {"phase_id": phase_id, "name": name, "nature": nature,
             "due_date": due_date, "recipient": recipient, "status": status},
        ).scalar()


def update_deliverable(deliverable_id, **fields):
    allowed = {"name", "nature", "due_date", "recipient", "status", "phase_id"}
    clause, params = _build_set_clause(fields, allowed)
    if not clause:
        return
    params["id"] = deliverable_id
    with db_session() as conn:
        conn.execute(text(f"UPDATE deliverables SET {clause} WHERE id=:id"), params)


def delete_deliverable(deliverable_id):
    with db_session() as conn:
        conn.execute(text("DELETE FROM deliverables WHERE id=:id"), {"id": deliverable_id})


# ===========================================================================
# RÉUNIONS
# ===========================================================================

def get_meetings(project_id):
    with db_session() as conn:
        res = conn.execute(
            text("""SELECT m.*, p.name AS phase_name
                    FROM meetings m
                    LEFT JOIN phases p ON m.phase_id = p.id
                    WHERE m.project_id=:p
                    ORDER BY m.date DESC, m.time DESC"""),
            {"p": project_id},
        )
        return rows_to_dicts(res)


def get_meeting(meeting_id):
    with db_session() as conn:
        res = conn.execute(text("SELECT * FROM meetings WHERE id=:id"), {"id": meeting_id})
        return row_to_dict(res)


def create_meeting(project_id, phase_id, date, time, participants, subject, report=""):
    with db_session() as conn:
        return conn.execute(
            text("""INSERT INTO meetings
                    (project_id, phase_id, date, time, participants, subject, report)
                    VALUES (:project_id, :phase_id, :date, :time, :participants, :subject, :report)
                    RETURNING id"""),
            {"project_id": project_id, "phase_id": phase_id, "date": date,
             "time": time, "participants": participants, "subject": subject,
             "report": report},
        ).scalar()


def update_meeting(meeting_id, **fields):
    allowed = {"phase_id", "date", "time", "participants", "subject", "report"}
    clause, params = _build_set_clause(fields, allowed)
    if not clause:
        return
    params["id"] = meeting_id
    with db_session() as conn:
        conn.execute(text(f"UPDATE meetings SET {clause} WHERE id=:id"), params)


def delete_meeting(meeting_id):
    with db_session() as conn:
        conn.execute(text("DELETE FROM meetings WHERE id=:id"), {"id": meeting_id})
