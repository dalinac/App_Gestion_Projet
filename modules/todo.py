"""
Module "Action Rapide" (To-Do List).

Tableau de bord filtré extrayant les tâches "à faire cette semaine" pour la
gestion opérationnelle au quotidien. Permet de cocher rapidement les tâches
terminées et de visualiser les retards.
"""

import streamlit as st
from datetime import date, timedelta

from database import models
from utils.helpers import (
    task_is_active_this_week, parse_date, format_date_fr, STATUSES,
)


def render(project_id):
    """Affiche la vue Action Rapide pour le projet courant."""
    st.header("⚡ Action Rapide — À faire cette semaine")

    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)
    st.caption(
        f"Semaine du {start_week.strftime('%d/%m/%Y')} au {end_week.strftime('%d/%m/%Y')}"
    )

    tasks = models.get_tasks(project_id=project_id)

    # Tâches de la semaine (chevauchant la semaine courante, non terminées)
    week_tasks = [t for t in tasks if task_is_active_this_week(t)]
    # Tâches en retard (fin dépassée, non terminées)
    late_tasks = [
        t for t in tasks
        if parse_date(t.get("end_date")) and parse_date(t["end_date"]) < today
        and t.get("status") != "Terminé"
    ]

    col1, col2 = st.columns(2)
    col1.metric("À faire cette semaine", len(week_tasks))
    col2.metric("En retard", len(late_tasks), delta_color="inverse")

    st.divider()

    # ---- Tâches en retard (prioritaires) ----
    if late_tasks:
        st.subheader("🔴 Tâches en retard")
        for t in late_tasks:
            _render_task_row(t, overdue=True)
        st.divider()

    # ---- Tâches de la semaine ----
    st.subheader("📌 Tâches de la semaine")
    if not week_tasks:
        st.success("Aucune tâche à traiter cette semaine. 🎉")
        return

    for t in week_tasks:
        _render_task_row(t)


def _render_task_row(task, overdue=False):
    """Affiche une ligne de tâche avec case de complétion et changement de statut."""
    cols = st.columns([0.06, 0.44, 0.2, 0.3])

    # Case à cocher : marque la tâche comme terminée
    done = task.get("status") == "Terminé"
    checked = cols[0].checkbox(
        "Terminé",
        value=done,
        key=f"todo_done_{task['id']}",
        label_visibility="collapsed",
    )
    if checked and not done:
        models.update_task(task["id"], status="Terminé", progress=100)
        st.rerun()
    elif not checked and done:
        models.update_task(task["id"], status="En cours")
        st.rerun()

    # Nom + phase
    phase = task.get("phase_name", "")
    icon = "🔴 " if overdue else ""
    cols[1].markdown(f"{icon}**{task['name']}**  \n_{phase}_")

    # Échéance + responsable
    cols[2].write(f"📅 {format_date_fr(task.get('end_date'))}")
    cols[2].caption(f"👤 {task.get('assignee') or '—'}")

    # Statut rapide
    current = task.get("status", "À faire")
    new_status = cols[3].selectbox(
        "Statut",
        STATUSES,
        index=STATUSES.index(current) if current in STATUSES else 0,
        key=f"todo_status_{task['id']}",
        label_visibility="collapsed",
    )
    if new_status != current:
        progress = 100 if new_status == "Terminé" else task.get("progress", 0)
        models.update_task(task["id"], status=new_status, progress=progress)
        st.rerun()
