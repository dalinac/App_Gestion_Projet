"""
Module Tableau de bord : vue d'ensemble du projet.

Regroupe :
  - les indicateurs clés (avancement global, nb de tâches, livrables, retards) ;
  - le Gantt interactif avec chemin critique ;
  - le diagramme en camembert de la part de chaque phase ;
  - l'avancement détaillé par phase.
"""

import streamlit as st
import plotly.express as px

from database import models
from utils.helpers import (
    global_progress, phase_duration_share, parse_date, format_date_fr,
)
from modules.gantt import build_gantt_figure, build_phase_gantt
from modules import theme
from datetime import date


def render(project_id):
    """Affiche le tableau de bord complet d'un projet."""
    project = models.get_project(project_id)
    phases = models.get_phases(project_id)
    tasks = models.get_tasks(project_id=project_id)
    dependencies = models.get_dependencies(project_id)
    deliverables = models.get_deliverables(project_id)

    theme.banner(f"Tableau de bord — {project['name']}", project.get("description") or "")

    # ---- Indicateurs clés (KPI) ----
    g_progress = global_progress(phases)
    nb_tasks = len(tasks)
    nb_done = sum(1 for t in tasks if t.get("status") == "Terminé")
    nb_late = _count_late(tasks)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avancement global", f"{g_progress}%")
    col2.metric("Tâches", f"{nb_done}/{nb_tasks}", help="Tâches terminées / total")
    col3.metric("Livrables", len(deliverables))
    col4.metric("Tâches en retard", nb_late, delta_color="inverse")

    # Barre d'avancement global
    st.progress(g_progress / 100, text=f"Avancement global du projet : {g_progress}%")

    st.divider()

    # ---- Diagramme de Gantt + chemin critique ----
    st.subheader("Diagramme de Gantt")
    highlight = st.checkbox("Mettre en évidence le chemin critique", value=True)
    fig, cp = build_gantt_figure(tasks, dependencies, highlight_critical=highlight)
    if fig:
        st.plotly_chart(fig, width='stretch')
        if cp["critical_ids"]:
            critical_names = [t["name"] for t in tasks if t["id"] in cp["critical_ids"]]
            st.warning(
                "**Chemin critique** (tout retard décale la fin du projet) : "
                + ", ".join(critical_names)
            )
    else:
        st.info("Aucune tâche datée à afficher. Ajoutez des tâches avec des dates.")

    st.divider()

    # ---- Deux colonnes : camembert + avancement par phase ----
    left, right = st.columns(2)

    with left:
        st.subheader("Part de chaque phase")
        _render_phase_pie(phases)

    with right:
        st.subheader("Avancement par phase")
        _render_phase_progress(phases)

    st.divider()

    # ---- Vue macro des phases ----
    st.subheader("Vue macro des phases")
    macro = build_phase_gantt(phases)
    if macro:
        st.plotly_chart(macro, width='stretch')
    else:
        st.info("Aucune phase datée à afficher.")


def _render_phase_pie(phases):
    """Camembert de la part (en durée) de chaque phase sur le projet."""
    shares = phase_duration_share(phases)
    shares = [(name, days, pct) for name, days, pct in shares if days > 0]
    if not shares:
        st.info("Renseignez les dates des phases pour visualiser leur répartition.")
        return
    names = [s[0] for s in shares]
    days = [s[1] for s in shares]
    colors = [p.get("color", "#4C78A8") for p in phases if parse_date(p.get("start_date")) and parse_date(p.get("end_date"))]
    fig = px.pie(
        names=names,
        values=days,
        title="Répartition de la durée du projet",
        color_discrete_sequence=colors or theme.PASTEL_SEQUENCE,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=380)
    theme.style_fig(fig)
    st.plotly_chart(fig, width='stretch')


def _render_phase_progress(phases):
    """Affiche l'avancement de chaque phase sous forme de barres de progression."""
    if not phases:
        st.info("Aucune phase définie.")
        return
    for p in phases:
        prog = p.get("progress", 0) or 0
        label = f"{p['name']} · {p.get('version', '')} · {p.get('status', '')}"
        st.write(f"**{label}**")
        st.progress(prog / 100, text=f"{prog}%")


def _count_late(tasks, reference=None):
    """Compte les tâches dont la date de fin est dépassée et non terminées."""
    ref = reference or date.today()
    count = 0
    for t in tasks:
        end = parse_date(t.get("end_date"))
        if end and end < ref and t.get("status") != "Terminé":
            count += 1
    return count
