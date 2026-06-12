"""
Module Export & Sauvegarde.

Permet d'exporter :
  - les données du projet (phases, tâches, livrables, réunions) au format CSV ;
  - le diagramme de Gantt et les vues analytiques au format image (PNG) et PDF.

L'export image/PDF repose sur Plotly + Kaleido. Si Kaleido n'est pas installé,
une alternative HTML interactive est proposée pour ne jamais bloquer l'utilisateur.
"""

import io
import csv
import zipfile

import streamlit as st

from database import models
from modules.gantt import build_gantt_figure, build_phase_gantt
from utils.helpers import phase_duration_share
import plotly.express as px


def render(project_id):
    st.header("Export & Sauvegarde")

    project = models.get_project(project_id)

    st.subheader("Export des données (CSV)")
    st.caption("Exportez chaque entité du projet ou l'ensemble dans une archive ZIP.")

    phases = models.get_phases(project_id)
    tasks = models.get_tasks(project_id=project_id)
    deliverables = models.get_deliverables(project_id)
    meetings = models.get_meetings(project_id)

    datasets = {
        "phases": phases,
        "taches": tasks,
        "livrables": deliverables,
        "reunions": meetings,
    }

    col1, col2, col3, col4 = st.columns(4)
    cols = [col1, col2, col3, col4]
    for col, (name, data) in zip(cols, datasets.items()):
        csv_bytes = _to_csv_bytes(data)
        col.download_button(
            f"{name}.csv",
            data=csv_bytes,
            file_name=f"{name}.csv",
            mime="text/csv",
            disabled=not data,
            use_container_width=True,
        )

    # Archive ZIP complète
    zip_bytes = _build_zip(datasets)
    st.download_button(
        "Télécharger toutes les données (ZIP)",
        data=zip_bytes,
        file_name=f"export_{_safe(project['name'])}.zip",
        mime="application/zip",
        use_container_width=True,
    )

    st.divider()

    # ---- Export graphiques ----
    st.subheader("Export des vues analytiques (image / PDF)")

    dependencies = models.get_dependencies(project_id)
    gantt_fig, _ = build_gantt_figure(tasks, dependencies, highlight_critical=True)
    pie_fig = _build_pie(phases)
    macro_fig = build_phase_gantt(phases)

    figures = {
        "Diagramme de Gantt": gantt_fig,
        "Répartition des phases (camembert)": pie_fig,
        "Vue macro des phases": macro_fig,
    }

    available = {k: v for k, v in figures.items() if v is not None}
    if not available:
        st.info("Ajoutez des phases et des tâches datées pour générer les graphiques.")
        return

    choice = st.selectbox("Choisir la vue à exporter", list(available.keys()))
    fig = available[choice]
    st.plotly_chart(fig, use_container_width=True)

    kaleido_ok = _kaleido_available()
    c1, c2, c3 = st.columns(3)

    if kaleido_ok:
        png_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
        c1.download_button(
            "PNG", data=png_bytes,
            file_name=f"{_safe(choice)}.png", mime="image/png",
            use_container_width=True,
        )
        pdf_bytes = fig.to_image(format="pdf", width=1200, height=600, scale=2)
        c2.download_button(
            "PDF", data=pdf_bytes,
            file_name=f"{_safe(choice)}.pdf", mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.warning(
            "Export PNG/PDF indisponible : le moteur **Kaleido** n'est pas installé. "
            "Installez-le avec `pip install kaleido`. "
            "En attendant, exportez la version HTML interactive ci-dessous."
        )

    # HTML interactif (toujours disponible)
    html_bytes = fig.to_html(include_plotlyjs="cdn").encode("utf-8")
    c3.download_button(
        "HTML interactif", data=html_bytes,
        file_name=f"{_safe(choice)}.html", mime="text/html",
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_csv_bytes(rows):
    """Convertit une liste de dicts en CSV (bytes UTF-8 avec BOM pour Excel)."""
    if not rows:
        return b""
    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    # BOM utf-8-sig pour une ouverture correcte des accents dans Excel
    return output.getvalue().encode("utf-8-sig")


def _build_zip(datasets):
    """Assemble tous les CSV dans une archive ZIP en mémoire."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in datasets.items():
            if data:
                zf.writestr(f"{name}.csv", _to_csv_bytes(data))
    buffer.seek(0)
    return buffer.getvalue()


def _build_pie(phases):
    """Reconstruit le camembert de répartition des phases pour l'export."""
    shares = [(n, d) for n, d, _ in phase_duration_share(phases) if d > 0]
    if not shares:
        return None
    fig = px.pie(
        names=[s[0] for s in shares],
        values=[s[1] for s in shares],
        title="Répartition de la durée du projet par phase",
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


# Cache du résultat du test Kaleido (évite de re-rendre une image à chaque page)
_KALEIDO_STATUS = None


def _kaleido_available():
    """
    Vérifie que l'export d'images fonctionne réellement.

    On effectue un mini rendu de test : selon la version, Kaleido peut être
    importable mais échouer au rendu (ex. Kaleido >=1.0 sans Google Chrome).
    Le résultat est mis en cache pour ne pas pénaliser les affichages suivants.
    """
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
