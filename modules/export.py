"""
Module Export / Import & graphiques.

Export/Import des DONNÉES d'un projet au format CSV (archive ZIP), pensés pour
être le miroir l'un de l'autre : ce que l'on exporte peut être réimporté tel
quel, ou préparé dans un tableur puis importé.

Les fichiers sont reliés entre eux par le NOM de la phase (colonne
``phase_name``) plutôt que par des identifiants internes, ce qui permet de
préparer les données à la main « en les classant comme il faut ».

Fichiers de l'archive :
  - phases.csv     : name, version, status, progress, color, order_index,
                     description, comments, start_date, end_date, segments
                     (segments = périodes multiples, encodées en JSON)
  - taches.csv     : phase_name, name, status, order_index
  - livrables.csv  : phase_name, name, nature, due_date, recipient, status
  - reunions.csv   : phase_name, date, time, participants, subject, report
  - dependances.csv: phase_name, depends_on_phase_name

Ce module fournit aussi ``render_graphics_export`` : l'export d'images (PNG /
PDF / HTML) du Gantt et du camembert, affiché sous le tableau de bord.
"""

import io
import csv
import json
import zipfile

import streamlit as st
import plotly.express as px

from database import models
from modules import theme
from modules.gantt import build_phase_gantt_figure
from utils.helpers import phase_duration_share


# Ordre des colonnes de chaque fichier (sert à l'export)
SCHEMA = {
    "phases": ["name", "version", "status", "progress", "color", "order_index",
               "description", "comments", "start_date", "end_date", "segments"],
    "taches": ["phase_name", "name", "status", "order_index"],
    "livrables": ["phase_name", "name", "nature", "due_date", "recipient", "status"],
    "reunions": ["phase_name", "date", "time", "participants", "subject", "report"],
    "dependances": ["phase_name", "depends_on_phase_name"],
}


# ===========================================================================
# EXPORT (données -> ZIP de CSV)
# ===========================================================================

def build_project_zip(project_id):
    """Construit l'archive ZIP (CSV) des données du projet. Retourne des bytes."""
    datasets = _collect_datasets(project_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, columns in SCHEMA.items():
            zf.writestr(f"{name}.csv", _to_csv_bytes(datasets.get(name, []), columns))
    buffer.seek(0)
    return buffer.getvalue()


def _collect_datasets(project_id):
    """Prépare, à partir du modèle, les lignes name-based de chaque fichier."""
    phases = models.get_phases(project_id)
    id_to_name = {p["id"]: p["name"] for p in phases}

    phase_rows = []
    for p in phases:
        phase_rows.append({
            "name": p.get("name", ""),
            "version": p.get("version", ""),
            "status": p.get("status", ""),
            "progress": p.get("progress", 0),
            "color": p.get("color", ""),
            "order_index": p.get("order_index", 0),
            "description": p.get("description", "") or "",
            "comments": p.get("comments", "") or "",
            "start_date": p.get("start_date", "") or "",
            "end_date": p.get("end_date", "") or "",
            "segments": json.dumps(p.get("segments") or [], ensure_ascii=False),
        })

    task_rows = [{
        "phase_name": t.get("phase_name", ""),
        "name": t.get("name", ""),
        "status": t.get("status", ""),
        "order_index": t.get("order_index", 0),
    } for t in models.get_tasks(project_id=project_id)]

    deliverable_rows = [{
        "phase_name": dl.get("phase_name", ""),
        "name": dl.get("name", ""),
        "nature": dl.get("nature", ""),
        "due_date": dl.get("due_date", "") or "",
        "recipient": dl.get("recipient", "") or "",
        "status": dl.get("status", ""),
    } for dl in models.get_deliverables(project_id)]

    meeting_rows = [{
        "phase_name": m.get("phase_name", "") or "",
        "date": m.get("date", "") or "",
        "time": m.get("time", "") or "",
        "participants": m.get("participants", "") or "",
        "subject": m.get("subject", "") or "",
        "report": m.get("report", "") or "",
    } for m in models.get_meetings(project_id)]

    dep_rows = []
    for d in models.get_phase_dependencies(project_id):
        b = id_to_name.get(d["phase_id"])
        a = id_to_name.get(d["depends_on_phase_id"])
        if a and b:
            dep_rows.append({"phase_name": b, "depends_on_phase_name": a})

    return {
        "phases": phase_rows,
        "taches": task_rows,
        "livrables": deliverable_rows,
        "reunions": meeting_rows,
        "dependances": dep_rows,
    }


def _to_csv_bytes(rows, columns):
    """Écrit des lignes (list de dicts) en CSV. BOM utf-8 pour Excel."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return output.getvalue().encode("utf-8-sig")


# ===========================================================================
# IMPORT (CSV / ZIP -> projet)
# ===========================================================================

def parse_uploads(uploaded_files):
    """
    Lit une liste de fichiers téléversés (ZIP et/ou CSV) et retourne un dict
    {nom_entité: [lignes...]} pour les fichiers reconnus.
    """
    datasets = {}
    for uf in uploaded_files:
        raw = uf.read()
        fname = (uf.name or "").lower()
        if fname.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for member in zf.namelist():
                    key = _match_entity(member)
                    if key:
                        datasets[key] = _read_csv_bytes(zf.read(member))
        elif fname.endswith(".csv"):
            key = _match_entity(fname)
            if key:
                datasets[key] = _read_csv_bytes(raw)
    return datasets


def _match_entity(filename):
    """Associe un nom de fichier à une entité connue (phases, taches, ...)."""
    base = filename.rsplit("/", 1)[-1].lower()
    for key in SCHEMA:
        if base == f"{key}.csv" or base.startswith(f"{key}."):
            return key
    return None


def _read_csv_bytes(raw):
    """Décode des bytes CSV (utf-8-sig) en liste de dicts."""
    text = raw.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def import_data(project_id, datasets):
    """
    Insère/complète les données du projet à partir des fichiers analysés.
    Les entités sont reliées aux phases par leur NOM. Retourne un récapitulatif.
    """
    summary = {"phases": 0, "taches": 0, "livrables": 0,
               "reunions": 0, "dependances": 0, "ignores": []}

    # Index des phases existantes (par nom) dans le projet cible
    name_to_id = {p["name"]: p["id"] for p in models.get_phases(project_id)}

    # --- Phases (upsert par nom) ---
    for i, row in enumerate(datasets.get("phases", [])):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        fields = {
            "description": row.get("description", "") or "",
            "start_date": (row.get("start_date") or "").strip(),
            "end_date": (row.get("end_date") or "").strip(),
            "status": (row.get("status") or "À faire").strip() or "À faire",
            "progress": _to_int(row.get("progress"), 0),
            "version": (row.get("version") or "V1").strip() or "V1",
            "color": (row.get("color") or "#C9A66B").strip() or "#C9A66B",
            "order_index": _to_int(row.get("order_index"), i),
            "comments": row.get("comments", "") or "",
            "segments": _parse_segments(row.get("segments")),
        }
        if name in name_to_id:
            models.update_phase(name_to_id[name], name=name, **fields)
        else:
            new_id = models.create_phase(
                project_id, name, fields["description"], fields["start_date"],
                fields["end_date"], fields["status"], fields["progress"],
                fields["version"], fields["color"], fields["order_index"],
                fields["comments"], fields["segments"],
            )
            name_to_id[name] = new_id
        summary["phases"] += 1

    # --- Tâches (dédup par phase + nom) ---
    existing_tasks = {
        (t.get("phase_name"), t.get("name"))
        for t in models.get_tasks(project_id=project_id)
    }
    for i, row in enumerate(datasets.get("taches", [])):
        pname = (row.get("phase_name") or "").strip()
        tname = (row.get("name") or "").strip()
        if not tname:
            continue
        pid = name_to_id.get(pname)
        if not pid:
            summary["ignores"].append(f"Tâche « {tname} » : phase « {pname} » introuvable")
            continue
        if (pname, tname) in existing_tasks:
            continue
        models.create_task(pid, tname, (row.get("status") or "À faire").strip() or "À faire",
                            _to_int(row.get("order_index"), i))
        existing_tasks.add((pname, tname))
        summary["taches"] += 1

    # --- Livrables (dédup par phase + nom) ---
    existing_dels = {
        (dl.get("phase_name"), dl.get("name"))
        for dl in models.get_deliverables(project_id)
    }
    for row in datasets.get("livrables", []):
        pname = (row.get("phase_name") or "").strip()
        dname = (row.get("name") or "").strip()
        if not dname:
            continue
        pid = name_to_id.get(pname)
        if not pid:
            summary["ignores"].append(f"Livrable « {dname} » : phase « {pname} » introuvable")
            continue
        if (pname, dname) in existing_dels:
            continue
        models.create_deliverable(
            pid, dname, (row.get("nature") or "").strip(),
            (row.get("due_date") or "").strip(), (row.get("recipient") or "").strip(),
            (row.get("status") or "À faire").strip() or "À faire",
        )
        existing_dels.add((pname, dname))
        summary["livrables"] += 1

    # --- Réunions (dédup par date + sujet) ---
    existing_meets = {
        (m.get("date"), m.get("subject"))
        for m in models.get_meetings(project_id)
    }
    for row in datasets.get("reunions", []):
        subject = (row.get("subject") or "").strip()
        mdate = (row.get("date") or "").strip()
        if not subject and not mdate:
            continue
        if (mdate, subject) in existing_meets:
            continue
        pid = name_to_id.get((row.get("phase_name") or "").strip())
        models.create_meeting(
            project_id, pid, mdate, (row.get("time") or "").strip(),
            (row.get("participants") or "").strip(), subject,
            row.get("report", "") or "",
        )
        existing_meets.add((mdate, subject))
        summary["reunions"] += 1

    # --- Dépendances (reliées par nom, idempotentes) ---
    for row in datasets.get("dependances", []):
        b = name_to_id.get((row.get("phase_name") or "").strip())
        a = name_to_id.get((row.get("depends_on_phase_name") or "").strip())
        if a and b and a != b:
            models.add_phase_dependency(b, a)
            summary["dependances"] += 1

    return summary


def _to_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError, AttributeError):
        return default


def _parse_segments(value):
    """Décode la colonne 'segments' (JSON). Retourne une liste (vide si invalide)."""
    if not value:
        return []
    try:
        data = json.loads(value)
    except (ValueError, TypeError):
        return []
    result = []
    for seg in data if isinstance(data, list) else []:
        if isinstance(seg, dict) and seg.get("start_date") and seg.get("end_date"):
            result.append({"start_date": str(seg["start_date"])[:10],
                           "end_date": str(seg["end_date"])[:10]})
    return result


# ===========================================================================
# EXPORT GRAPHIQUE (Gantt / camembert en PNG, PDF, HTML)
# ===========================================================================

def render_graphics_export(project_id):
    """Encart d'export d'images/PDF, destiné à être affiché sous le Gantt."""
    phases = models.get_phases(project_id)
    phase_deps = models.get_phase_dependencies(project_id)
    gantt_fig, _ = build_phase_gantt_figure(phases, phase_deps, highlight_critical=True)
    pie_fig = _build_pie(phases)

    figures = {
        "Diagramme de Gantt des phases": gantt_fig,
        "Répartition des phases (camembert)": pie_fig,
    }
    available = {k: v for k, v in figures.items() if v is not None}
    if not available:
        st.info("Ajoutez des phases avec des dates pour générer les graphiques.")
        return

    choice = st.selectbox("Vue à exporter", list(available.keys()), key="gfx_export_choice")
    fig = available[choice]

    kaleido_ok = _kaleido_available()
    c1, c2, c3 = st.columns(3)

    if kaleido_ok:
        png_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
        c1.download_button("PNG", data=png_bytes, file_name=f"{_safe(choice)}.png",
                           mime="image/png", width='stretch')
        pdf_bytes = fig.to_image(format="pdf", width=1200, height=600, scale=2)
        c2.download_button("PDF", data=pdf_bytes, file_name=f"{_safe(choice)}.pdf",
                           mime="application/pdf", width='stretch')
    else:
        st.caption(
            "Export PNG/PDF indisponible (moteur Kaleido absent) : l'export HTML "
            "interactif ci-dessous reste disponible."
        )

    html_bytes = fig.to_html(include_plotlyjs="cdn").encode("utf-8")
    c3.download_button("HTML interactif", data=html_bytes, file_name=f"{_safe(choice)}.html",
                       mime="text/html", width='stretch')


def _build_pie(phases):
    """Camembert de répartition des phases (pour l'export image)."""
    shares = [(n, d) for n, d, _ in phase_duration_share(phases) if d > 0]
    if not shares:
        return None
    fig = px.pie(
        names=[s[0] for s in shares],
        values=[s[1] for s in shares],
        title="Répartition de la durée du projet par phase",
        color_discrete_sequence=theme.PASTEL_SEQUENCE,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    theme.style_fig(fig)
    return fig


# Cache du résultat du test Kaleido (évite de re-rendre une image à chaque page)
_KALEIDO_STATUS = None


def _kaleido_available():
    """Vérifie que l'export d'images fonctionne réellement (mini rendu de test)."""
    global _KALEIDO_STATUS
    if _KALEIDO_STATUS is not None:
        return _KALEIDO_STATUS
    try:
        import plotly.graph_objects as go
        go.Figure().to_image(format="png", width=10, height=10)
        _KALEIDO_STATUS = True
    except Exception:
        _KALEIDO_STATUS = False
    return _KALEIDO_STATUS


def _safe(name):
    """Nettoie une chaîne pour en faire un nom de fichier sûr."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
