"""
Module Tableau de bord : vue d'ensemble du projet.

Regroupe :
  - les indicateurs clés (avancement global, phases, livrables, santé) ;
  - le Gantt interactif des phases avec chemin critique ;
  - le diagramme en camembert de la part de chaque phase ;
  - l'avancement détaillé par phase ;
  - l'indicateur de Santé du Projet (avancement vs temps écoulé).
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from database import models
from utils.helpers import (
    global_progress, phase_duration_share, parse_date, project_health,
)
from modules.gantt import build_phase_gantt_figure
from modules import theme
from datetime import date


def render(project_id):
    """Affiche le tableau de bord complet d'un projet."""
    project = models.get_project(project_id)
    phases = models.get_phases(project_id)
    phase_deps = models.get_phase_dependencies(project_id)
    deliverables = models.get_deliverables(project_id)

    theme.banner(f"Tableau de bord — {project['name']}", project.get("description") or "")

    # ---- Indicateurs clés (KPI) ----
    g_progress = global_progress(phases)
    nb_phases = len(phases)
    nb_done = sum(1 for p in phases if p.get("status") == "Terminé")
    health = project_health(project, phases)
    today = date.today()
    nb_late = sum(
        1 for p in phases
        if parse_date(p.get("end_date")) and parse_date(p["end_date"]) < today
        and p.get("status") != "Terminé"
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avancement global", f"{g_progress}%")
    col2.metric("Phases terminées", f"{nb_done}/{nb_phases}")
    col3.metric("Livrables", len(deliverables))
    col4.metric("Phases en retard", nb_late, delta_color="inverse")

    st.progress(g_progress / 100, text=f"Avancement global du projet : {g_progress}%")

    st.divider()

    # ---- Diagramme de Gantt des phases + chemin critique ----
    st.subheader("Diagramme de Gantt des phases")
    highlight = st.checkbox("Mettre en évidence le chemin critique", value=True)
    fig, cp = build_phase_gantt_figure(phases, phase_deps, highlight_critical=highlight)
    if fig:
        st.plotly_chart(fig, width='stretch')
        if cp["critical_ids"]:
            names = [p["name"] for p in phases if p["id"] in cp["critical_ids"]]
            st.warning(
                "Chemin critique (tout retard décale la fin du projet) : "
                + ", ".join(names)
            )
    else:
        st.info("Ajoutez des phases avec des dates de début et de fin pour afficher le Gantt.")

    st.divider()

    # ---- Camembert + avancement par phase ----
    left, right = st.columns(2)
    with left:
        st.subheader("Part de chaque phase")
        _render_phase_pie(phases)
    with right:
        st.subheader("Avancement par phase")
        _render_phase_progress(phases)

    st.divider()

    # ---- Santé du projet (remplace l'ancienne vue macro) ----
    st.subheader("Santé du projet")
    _render_health(health)


def _render_phase_pie(phases):
    """Camembert de la part (en durée) de chaque phase sur le projet."""
    shares = [(n, d, p) for n, d, p in phase_duration_share(phases) if d > 0]
    if not shares:
        st.info("Renseignez les dates des phases pour visualiser leur répartition.")
        return
    names = [s[0] for s in shares]
    days = [s[1] for s in shares]
    colors = [
        p.get("color", "#C9A66B") for p in phases
        if parse_date(p.get("start_date")) and parse_date(p.get("end_date"))
    ]
    fig = px.pie(
        names=names, values=days,
        title="Répartition de la durée du projet",
        color_discrete_sequence=colors or theme.PASTEL_SEQUENCE,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=380)
    theme.style_fig(fig)
    st.plotly_chart(fig, width='stretch')


def _render_phase_progress(phases):
    """Avancement de chaque phase sous forme de barres de progression."""
    if not phases:
        st.info("Aucune phase définie.")
        return
    for p in phases:
        prog = p.get("progress", 0) or 0
        label = f"{p['name']} · {p.get('version', '')} · {p.get('status', '')}"
        st.write(f"**{label}**")
        st.progress(prog / 100, text=f"{prog}%")


def _render_health(health):
    """
    Indicateur de Santé du Projet : jauge comparant l'avancement (part de phases
    terminées) au temps écoulé (repère). Couleur = en avance / dans les temps /
    en retard.
    """
    if not health["available"]:
        st.info(
            "Renseignez les dates de début et de fin du projet (et au moins une "
            "phase) pour calculer la santé du projet."
        )
        return

    col_gauge, col_txt = st.columns([0.6, 0.4])

    with col_gauge:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=health["done_pct"],
            number={"suffix": "%"},
            delta={
                "reference": health["time_pct"],
                "increasing": {"color": "#7FA86B"},
                "decreasing": {"color": "#B5654A"},
            },
            title={"text": "Phases terminées vs temps écoulé"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": health["color"]},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, health["time_pct"]], "color": "#EFE6D4"},
                ],
                "threshold": {
                    "line": {"color": "#5C4A38", "width": 3},
                    "thickness": 0.85,
                    "value": health["time_pct"],
                },
            },
        ))
        # Mise en page manuelle (pas de style_fig : éviterait un titre de layout
        # vide que Plotly afficherait comme « undefined » ; la jauge a son propre titre)
        fig.update_layout(
            height=300, margin=dict(l=20, r=20, t=50, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Mulish, sans-serif", color="#5C4A38"),
        )
        st.plotly_chart(fig, width='stretch')

    with col_txt:
        st.markdown(
            f"""
            <div style="
                background:{health['color']};
                color:#FFFBF4; border-radius:14px;
                padding:18px 20px; margin-top:24px;
                font-family:'Playfair Display', serif;
                font-size:1.4rem; font-weight:700; text-align:center;">
                {health['status']}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"Phases terminées : {health['done_pct']}%  ·  "
            f"Temps écoulé : {health['time_pct']}%"
        )
        st.caption(
            "Le repère sombre sur la jauge indique le temps écoulé. "
            "Si l'avancement le dépasse, le projet est en avance ; en dessous, "
            "il est en retard."
        )
