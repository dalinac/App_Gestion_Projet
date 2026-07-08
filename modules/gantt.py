"""
Module Gantt : diagramme de Gantt interactif construit à partir des PHASES
et de leurs dépendances, avec mise en évidence du chemin critique.

Les phases sont le coeur du planning : chacune porte ses dates et peut dépendre
d'autres phases. Les phases du chemin critique (tout retard décale la fin du
projet) sont bordées en rouge.
"""

from datetime import date

import pandas as pd
import plotly.express as px

from utils.helpers import parse_date, phase_segments
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
    # Une phase est affichable dès qu'elle a au moins une période valide
    # (période unique OU plusieurs segments).
    valid = [p for p in phases if phase_segments(p)]
    if not valid:
        return None, {"critical_ids": set(), "slack": {}, "project_duration": 0}

    cp = compute_critical_path(phases, _phase_deps_as_items(phase_deps))
    critical_ids = cp["critical_ids"] if highlight_critical else set()

    # Une ligne par PÉRIODE : une phase découpée en plusieurs temps produit
    # plusieurs barres sur la même ligne (même nom, même couleur). Le nom n'est
    # écrit que sur la période la plus large pour éviter les répétitions.
    rows = []
    for p in valid:
        segs = phase_segments(p)
        widest = max(range(len(segs)), key=lambda i: (segs[i][1] - segs[i][0]).days)
        for i, (s, e) in enumerate(segs):
            rows.append({
                "Phase": p["name"],
                "Début": s,
                "Fin": e,
                "Label": p["name"] if i == widest else "",
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
        text="Label",
        hover_data=["Version", "Statut", "Avancement", "Critique"],
    )
    fig.update_yaxes(autorange="reversed")

    # Nom de la phase écrit sur la barre (masqué automatiquement si la barre est
    # trop petite pour l'accueillir — voir uniformtext plus bas).
    fig.update_traces(
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="#3E3325", size=12, family="Mulish, sans-serif"),
        cliponaxis=False,
    )

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
        height=max(360, 46 * len({r["Phase"] for r in rows}) + 150),
        showlegend=False,
        margin=dict(l=10, r=10, t=60, b=10),
        # Survol unifié par date : une étiquette flottante affiche la date exacte
        # à la position du curseur (en plus des infos de chaque phase).
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(255,253,249,0.96)",
            bordercolor="#C7B393",
            font=dict(color="#5C4A38", family="Mulish, sans-serif"),
        ),
        # Uniformise la taille du texte et masque celui qui ne tient pas dans sa
        # barre : les noms n'apparaissent donc que « si la place le permet ».
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )
    theme.style_fig(fig)

    # Grille + curseur vertical qui suit la souris (spike). L'en-tête du survol
    # affiche la date pointée au format JJ/MM/AAAA.
    fig.update_xaxes(
        showgrid=True, gridcolor="#E0D4BF", gridwidth=1,
        showline=True, linecolor="#C7B393", linewidth=1, mirror=True,
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikecolor="#9E7D52", spikethickness=1.2, spikedash="solid",
        hoverformat="%d/%m/%Y",
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#E0D4BF", gridwidth=1,
        showline=True, linecolor="#C7B393", linewidth=1, mirror=True,
    )

    # Repère FIXE « Aujourd'hui » : couleur voyante mais douce (terracotta),
    # indique la date du jour (et donc où l'on est censé être dans le planning).
    today = date.today()
    starts = [r["Début"] for r in rows]
    ends = [r["Fin"] for r in rows]
    if starts and ends and min(starts) <= today <= max(ends):
        fig.add_vline(
            x=pd.Timestamp(today),
            line_width=2,
            line_dash="dash",
            line_color="rgba(200, 90, 70, 0.65)",
            annotation_text="Aujourd'hui",
            annotation_position="top",
            annotation_font_color="#B5654A",
            annotation_font_size=12,
        )
    return fig, cp
