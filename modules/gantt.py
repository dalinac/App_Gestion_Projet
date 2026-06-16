"""
Module Gantt : diagramme de Gantt interactif construit à partir des PHASES
et de leurs dépendances, avec mise en évidence du chemin critique.

Les phases sont le coeur du planning : chacune porte ses dates et peut dépendre
d'autres phases. Les phases du chemin critique (tout retard décale la fin du
projet) sont bordées en rouge.
"""

import plotly.express as px

from utils.helpers import parse_date
from utils.critical_path import compute_critical_path
from modules import theme


def _phase_deps_as_items(phase_deps):
    """
    Adapte les dépendances de phases au format attendu par compute_critical_path
    (clés 'task_id' / 'depends_on_task_id', génériques côté algorithme CPM).
    """
    return [
        {"task_id": d["phase_id"], "depends_on_task_id": d["depends_on_phase_id"]}
        for d in phase_deps
    ]


def build_phase_gantt_figure(phases, phase_deps, highlight_critical=True):
    """
    Construit la figure Gantt des phases.

    Retour : (figure Plotly, dict résultat du chemin critique).
    """
    valid = [
        p for p in phases
        if parse_date(p.get("start_date")) and parse_date(p.get("end_date"))
    ]
    if not valid:
        return None, {"critical_ids": set(), "slack": {}, "project_duration": 0}

    cp = compute_critical_path(phases, _phase_deps_as_items(phase_deps))
    critical_ids = cp["critical_ids"] if highlight_critical else set()

    rows = []
    for p in valid:
        rows.append({
            "Phase": p["name"],
            "Début": parse_date(p["start_date"]),
            "Fin": parse_date(p["end_date"]),
            "Version": p.get("version", ""),
            "Avancement": p.get("progress", 0),
            "Statut": p.get("status", ""),
            "Critique": "Oui" if p["id"] in critical_ids else "Non",
            "_id": p["id"],
            "_color": p.get("color", "#C9A66B"),
        })

    color_map = {r["Phase"]: r["_color"] for r in rows}

    fig = px.timeline(
        rows,
        x_start="Début",
        x_end="Fin",
        y="Phase",
        color="Phase",
        color_discrete_map=color_map,
        hover_data=["Version", "Statut", "Avancement", "Critique"],
    )
    fig.update_yaxes(autorange="reversed")

    # Bordure rouge brique pour les phases du chemin critique
    if highlight_critical and critical_ids:
        for trace in fig.data:
            widths, colors = [], []
            for y_val in trace.y:
                ph = next((r for r in rows if r["Phase"] == y_val), None)
                if ph and ph["_id"] in critical_ids:
                    widths.append(3)
                    colors.append("#A8443A")
                else:
                    widths.append(0)
                    colors.append("rgba(0,0,0,0)")
            trace.marker.line.width = widths
            trace.marker.line.color = colors

    fig.update_layout(
        title="Diagramme de Gantt — Phases (chemin critique en rouge)",
        xaxis_title="Temporalité",
        yaxis_title="Phases",
        height=max(360, 46 * len(rows) + 150),
        showlegend=False,
        margin=dict(l=10, r=10, t=60, b=10),
    )
    theme.style_fig(fig)

    # Grille : contour (mirror) + lignes intérieures, en tons doux
    fig.update_xaxes(
        showgrid=True, gridcolor="#E0D4BF", gridwidth=1,
        showline=True, linecolor="#C7B393", linewidth=1, mirror=True,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#E0D4BF", gridwidth=1,
        showline=True, linecolor="#C7B393", linewidth=1, mirror=True,
    )
    return fig, cp
