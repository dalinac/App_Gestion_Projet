"""
Module Tableau de bord : vue d'ensemble du projet.

Regroupe :
  - les indicateurs clés (avancement global, phases, livrables, santé) ;
  - le Gantt interactif des phases avec chemin critique ;
  - le diagramme en camembert de la part de chaque phase ;
  - l'avancement détaillé par phase ;
  - l'indicateur de Santé du Projet (avancement vs temps écoulé).
"""

import html

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from database import models
from utils.helpers import (
    global_progress, phase_duration_share, parse_date, project_health,
    format_date_fr,
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

    st.divider()

    # ---- Tâches du projet (code couleur terminé / à faire) ----
    st.subheader("Tâches du projet")
    _render_tasks_overview(project_id)

    st.divider()

    # ---- Livrables à rendre (rendu et validé ou non) ----
    st.subheader("Livrables à rendre")
    _render_deliverables_overview(deliverables)

    st.divider()

    # ---- Réunions (cliquer pour afficher le compte rendu) ----
    st.subheader("Réunions")
    _render_meetings_overview(project_id)


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
            value=health["progress_pct"],
            number={"suffix": "%"},
            delta={
                "reference": health["time_pct"],
                "increasing": {"color": "#7FA86B"},
                "decreasing": {"color": "#B5654A"},
            },
            title={"text": "Avancement réel vs temps écoulé"},
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
            f"Avancement réel : {health['progress_pct']}%  ·  "
            f"Temps écoulé : {health['time_pct']}%"
        )
        st.caption(
            "Le repère sombre sur la jauge indique le temps écoulé. "
            "Si l'avancement le dépasse, le projet est en avance ; en dessous, "
            "il est en retard."
        )


def _render_tasks_overview(project_id):
    """
    Tâches du projet groupées par phase, avec code couleur :
    vert = terminée, ocre/brun = à faire.
    """
    tasks = models.get_tasks(project_id=project_id)
    if not tasks:
        st.info("Aucune tâche pour le moment. Ajoutez-en depuis « Phases & Tâches ».")
        return

    st.markdown(
        "<span style='background:#7FA86B;color:#fff;border-radius:8px;"
        "padding:2px 9px;font-size:0.8rem;'>Terminée</span>&nbsp;&nbsp;"
        "<span style='background:#C08457;color:#fff;border-radius:8px;"
        "padding:2px 9px;font-size:0.8rem;'>À faire</span>",
        unsafe_allow_html=True,
    )

    by_phase = {}
    for t in tasks:
        by_phase.setdefault(t.get("phase_name", "—"), []).append(t)

    for phase_name, items in by_phase.items():
        chips = ""
        for t in items:
            done = t.get("status") == "Terminé"
            color = "#7FA86B" if done else "#C08457"
            chips += (
                f"<span style='background:{color};color:#fff;border-radius:10px;"
                f"padding:4px 12px;margin:3px;display:inline-block;font-size:0.9rem;'>"
                f"{html.escape(t['name'])}</span>"
            )
        st.markdown(f"**{html.escape(phase_name)}**")
        st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)


def _render_deliverables_overview(deliverables):
    """Livrables : date limite, destinataire et état (rendu et validé ou non)."""
    if not deliverables:
        st.info("Aucun livrable défini. Ajoutez-en depuis « Livrables ».")
        return

    today = date.today()
    rows = []
    for dl in deliverables:
        status = dl.get("status", "À faire")
        overdue = (
            parse_date(dl.get("due_date")) and parse_date(dl["due_date"]) < today
            and status != "Terminé"
        )
        if status == "Terminé":
            label, color = "Rendu et validé", "#7FA86B"
        elif overdue:
            label, color = "En retard", "#B5654A"
        elif status in ("En cours", "En attente"):
            label, color = status, "#C9A66B"
        else:
            label, color = "À rendre", "#B9A48B"
        badge = (
            f"<span style='background:{color};color:#fff;border-radius:10px;"
            f"padding:3px 10px;font-size:0.85rem;'>{label}</span>"
        )
        rows.append(
            "<tr>"
            f"<td style='padding:6px 10px;'>{html.escape(dl['name'])}</td>"
            f"<td style='padding:6px 10px;color:#8A7355;'>{html.escape(dl.get('phase_name') or '')}</td>"
            f"<td style='padding:6px 10px;'>{format_date_fr(dl.get('due_date'))}</td>"
            f"<td style='padding:6px 10px;color:#8A7355;'>{html.escape(dl.get('recipient') or '—')}</td>"
            f"<td style='padding:6px 10px;'>{badge}</td>"
            "</tr>"
        )

    table = (
        "<table style='width:100%;border-collapse:collapse;'>"
        "<thead><tr style='text-align:left;color:#5C4A38;border-bottom:1px solid #E0D4BF;'>"
        "<th style='padding:6px 10px;'>Livrable</th>"
        "<th style='padding:6px 10px;'>Phase</th>"
        "<th style='padding:6px 10px;'>Date limite</th>"
        "<th style='padding:6px 10px;'>Destinataire</th>"
        "<th style='padding:6px 10px;'>État</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )
    st.markdown(table, unsafe_allow_html=True)


def _render_meetings_overview(project_id):
    """Réunions cliquables : ouvrir une réunion affiche son compte rendu."""
    meetings = models.get_meetings(project_id)
    if not meetings:
        st.info("Aucune réunion planifiée. Ajoutez-en depuis « Réunions ».")
        return
    for m in meetings:
        title = (
            f"{format_date_fr(m.get('date'))}  {m.get('time', '')}  —  "
            f"{m.get('subject', '')}"
        )
        with st.expander(title):
            if m.get("phase_name"):
                st.caption(f"Phase concernée : {m['phase_name']}")
            if m.get("participants"):
                st.caption(f"Participants : {m['participants']}")
            report = m.get("report")
            if report and report.strip():
                st.markdown("**Compte rendu**")
                st.write(report)
            else:
                st.caption("Aucun compte rendu saisi pour cette réunion.")
