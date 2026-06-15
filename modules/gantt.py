"""
Module Gantt : génération du diagramme de Gantt interactif avec Plotly,
mise en évidence du chemin critique et affichage de l'avancement par phase.

Le Gantt regroupe les tâches par phase. Les tâches du chemin critique sont
bordées en rouge afin d'identifier visuellement les goulets d'étranglement.
"""

import plotly.express as px
import plotly.graph_objects as go

from utils.helpers import parse_date
from utils.critical_path import compute_critical_path
from modules import theme


def build_gantt_figure(tasks, dependencies, highlight_critical=True):
    """
    Construit la figure Plotly du diagramme de Gantt.

    Paramètres
    ----------
    tasks : list[dict]
        Tâches du projet (avec phase_name, phase_color via jointure).
    dependencies : list[dict]
        Dépendances entre tâches pour le calcul du chemin critique.
    highlight_critical : bool
        Active la mise en évidence (bordure rouge) des tâches critiques.

    Retour
    ------
    (figure Plotly, dict résultat du chemin critique)
    """
    # Filtre les tâches possédant des dates exploitables
    valid = [t for t in tasks if parse_date(t.get("start_date")) and parse_date(t.get("end_date"))]
    if not valid:
        return None, {"critical_ids": set(), "slack": {}, "project_duration": 0}

    cp = compute_critical_path(tasks, dependencies)
    critical_ids = cp["critical_ids"] if highlight_critical else set()

    # Préparation des données pour px.timeline
    rows = []
    for t in valid:
        rows.append({
            "Tâche": t["name"],
            "Début": parse_date(t["start_date"]),
            "Fin": parse_date(t["end_date"]),
            "Phase": t.get("phase_name", "—"),
            "Avancement": t.get("progress", 0),
            "Responsable": t.get("assignee") or "—",
            "Statut": t.get("status", ""),
            "Critique": "Oui" if t["id"] in critical_ids else "Non",
            "_id": t["id"],
            "_color": t.get("phase_color", "#A9D6F5"),
        })

    # Associe chaque phase à sa couleur (pastel) définie par l'utilisateur,
    # sinon px.timeline appliquerait sa palette par défaut (couleurs vives).
    color_map = {r["Phase"]: r["_color"] for r in rows}

    fig = px.timeline(
        rows,
        x_start="Début",
        x_end="Fin",
        y="Tâche",
        color="Phase",
        color_discrete_map=color_map,
        hover_data=["Responsable", "Statut", "Avancement", "Critique"],
    )
    # Les tâches sont affichées de haut en bas dans l'ordre chronologique
    fig.update_yaxes(autorange="reversed")

    # Mise en évidence du chemin critique : bordure rouge épaisse
    if highlight_critical and critical_ids:
        for trace in fig.data:
            line_widths = []
            line_colors = []
            # Récupère les tâches de cette trace (par nom)
            for y_val in trace.y:
                task = next((r for r in rows if r["Tâche"] == y_val), None)
                if task and task["_id"] in critical_ids:
                    line_widths.append(3)
                    line_colors.append("#A8443A")  # rouge brique (chemin critique)
                else:
                    line_widths.append(0)
                    line_colors.append("rgba(0,0,0,0)")
            trace.marker.line.width = line_widths
            trace.marker.line.color = line_colors

    fig.update_layout(
        title="Diagramme de Gantt — Tâches par phase (chemin critique en rouge)",
        xaxis_title="Temporalité",
        yaxis_title="Tâches",
        height=max(400, 40 * len(rows) + 150),
        legend_title="Phases",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    theme.style_fig(fig)
    return fig, cp


def build_phase_gantt(phases):
    """
    Construit un Gantt synthétique au niveau des phases (vue macro),
    coloré selon l'avancement.
    """
    valid = [p for p in phases if parse_date(p.get("start_date")) and parse_date(p.get("end_date"))]
    if not valid:
        return None

    fig = go.Figure()
    for p in reversed(valid):  # reversed pour affichage du haut vers le bas
        start = parse_date(p["start_date"])
        end = parse_date(p["end_date"])
        fig.add_trace(go.Bar(
            x=[(end - start).days or 1],
            base=[start],
            y=[f"{p['name']} ({p.get('version', '')})"],
            orientation="h",
            marker_color=p.get("color", "#4C78A8"),
            text=f"{p.get('progress', 0)}%",
            textposition="inside",
            hovertemplate=(
                f"<b>{p['name']}</b><br>"
                f"Début : {start}<br>Fin : {end}<br>"
                f"Avancement : {p.get('progress', 0)}%<br>"
                f"Statut : {p.get('status', '')}<extra></extra>"
            ),
            showlegend=False,
        ))
    fig.update_layout(
        title="Vue macro — Phases du projet",
        barmode="stack",
        xaxis=dict(type="date", title="Temporalité"),
        height=max(300, 50 * len(valid) + 120),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    theme.style_fig(fig)
    return fig
