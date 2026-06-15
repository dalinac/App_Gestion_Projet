"""
Module "Action Rapide".

Vue opérationnelle filtrée : les phases actives cette semaine (et celles en
retard), avec leurs tâches sous forme de to-do list à cocher.
"""

import streamlit as st
from datetime import date, timedelta

from database import models
from modules import theme
from utils.helpers import phase_is_active_this_week, parse_date, format_date_fr, STATUSES


def render(project_id):
    theme.banner("Action Rapide", "Vos phases de la semaine et leurs tâches, en un coup d'œil.")

    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)
    st.caption(
        f"Semaine du {start_week.strftime('%d/%m/%Y')} au {end_week.strftime('%d/%m/%Y')}"
    )

    phases = models.get_phases(project_id)
    week_phases = [p for p in phases if phase_is_active_this_week(p)]
    late_phases = [
        p for p in phases
        if parse_date(p.get("end_date")) and parse_date(p["end_date"]) < today
        and p.get("status") != "Terminé"
    ]

    col1, col2 = st.columns(2)
    col1.metric("Phases actives cette semaine", len(week_phases))
    col2.metric("Phases en retard", len(late_phases), delta_color="inverse")

    st.divider()

    if late_phases:
        st.subheader("Phases en retard")
        for p in late_phases:
            _render_phase_block(p, late=True)
        st.divider()

    st.subheader("Phases de la semaine")
    if not week_phases:
        st.success("Aucune phase active cette semaine.")
        return
    for p in week_phases:
        _render_phase_block(p)


def _render_phase_block(phase, late=False):
    """Affiche une phase (statut rapide) et ses tâches cochables."""
    suffix = "  ·  en retard" if late else ""
    header = (
        f"**{phase['name']}**  ·  {phase.get('version', '')}  ·  "
        f"échéance {format_date_fr(phase.get('end_date'))}{suffix}"
    )
    st.markdown(header)

    # Changement de statut rapide de la phase
    current = phase.get("status", "À faire")
    new_status = st.selectbox(
        "Statut de la phase", STATUSES,
        index=STATUSES.index(current) if current in STATUSES else 0,
        key=f"ar_status_{phase['id']}",
    )
    if new_status != current:
        models.update_phase(phase["id"], status=new_status)
        st.rerun()

    # Tâches de la phase (to-do list)
    tasks = models.get_tasks(phase_id=phase["id"])
    if not tasks:
        st.caption("Aucune tâche dans cette phase.")
    for t in tasks:
        done = t.get("status") == "Terminé"
        checked = st.checkbox(t["name"], value=done, key=f"ar_task_{t['id']}")
        if checked != done:
            models.set_task_status(t["id"], "Terminé" if checked else "À faire")
            st.rerun()
    st.divider()
