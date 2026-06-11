"""
Module de gestion des phases et des tâches.

Permet de :
  - créer / éditer / supprimer des phases (avec délais, statut, version, couleur,
    commentaires et avancement) ;
  - créer / éditer / supprimer des tâches au sein des phases (délais, statut,
    avancement, responsable, commentaires) ;
  - gérer les dépendances entre tâches (la tâche B nécessite la tâche A) ;
  - taguer les itérations/versions (V1, V2, ...).
"""

import streamlit as st
from datetime import date

from database import models
from utils.helpers import (
    STATUSES, PHASE_PALETTE, parse_date, format_date_fr, phase_progress_from_tasks,
)


def render(project_id):
    """Affiche l'interface de gestion des phases et tâches."""
    st.header("🗂️ Gestion des phases & tâches")

    tab_phases, tab_tasks, tab_deps = st.tabs(
        ["📋 Phases", "✅ Tâches", "🔗 Dépendances"]
    )

    with tab_phases:
        _render_phases(project_id)
    with tab_tasks:
        _render_tasks(project_id)
    with tab_deps:
        _render_dependencies(project_id)


# ---------------------------------------------------------------------------
# PHASES
# ---------------------------------------------------------------------------

def _render_phases(project_id):
    phases = models.get_phases(project_id)

    # --- Formulaire de création ---
    with st.expander("➕ Ajouter une phase", expanded=not phases):
        with st.form("add_phase", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nom de la phase *")
            version = c2.text_input("Version / Itération", value="V1")
            c3, c4 = st.columns(2)
            start = c3.date_input("Date de début", value=date.today())
            end = c4.date_input("Date de fin", value=date.today())
            c5, c6 = st.columns(2)
            status = c5.selectbox("Statut", STATUSES)
            progress = c6.slider("Avancement (%)", 0, 100, 0)
            color = st.color_picker(
                "Couleur", PHASE_PALETTE[len(phases) % len(PHASE_PALETTE)]
            )
            description = st.text_area("Description")
            comments = st.text_area("Commentaires")
            submitted = st.form_submit_button("Créer la phase")
            if submitted:
                if not name.strip():
                    st.error("Le nom de la phase est obligatoire.")
                else:
                    models.create_phase(
                        project_id, name.strip(), description,
                        start.isoformat(), end.isoformat(), status, progress,
                        version, color, order_index=len(phases), comments=comments,
                    )
                    st.success(f"Phase « {name} » créée.")
                    st.rerun()

    if not phases:
        st.info("Aucune phase pour le moment. Créez votre première phase ci-dessus.")
        return

    # --- Liste éditable des phases ---
    for p in phases:
        title = f"{p['name']} · {p.get('version', '')} · {p.get('progress', 0)}% · {p.get('status', '')}"
        with st.expander(title):
            with st.form(f"edit_phase_{p['id']}"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Nom *", value=p["name"])
                version = c2.text_input("Version", value=p.get("version", "V1"))
                c3, c4 = st.columns(2)
                start = c3.date_input(
                    "Début", value=parse_date(p.get("start_date")) or date.today(),
                    key=f"ps_{p['id']}",
                )
                end = c4.date_input(
                    "Fin", value=parse_date(p.get("end_date")) or date.today(),
                    key=f"pe_{p['id']}",
                )
                c5, c6 = st.columns(2)
                status = c5.selectbox(
                    "Statut", STATUSES,
                    index=STATUSES.index(p["status"]) if p.get("status") in STATUSES else 0,
                    key=f"pst_{p['id']}",
                )
                progress = c6.slider(
                    "Avancement (%)", 0, 100, p.get("progress", 0), key=f"ppr_{p['id']}"
                )
                color = st.color_picker(
                    "Couleur", p.get("color", "#4C78A8"), key=f"pc_{p['id']}"
                )
                description = st.text_area(
                    "Description", value=p.get("description") or "", key=f"pd_{p['id']}"
                )
                comments = st.text_area(
                    "Commentaires", value=p.get("comments") or "", key=f"pcm_{p['id']}"
                )

                # Avancement calculé à partir des tâches (information)
                phase_tasks = models.get_tasks(phase_id=p["id"])
                auto = phase_progress_from_tasks(phase_tasks)
                if auto is not None:
                    st.caption(
                        f"💡 Avancement calculé depuis les {len(phase_tasks)} tâche(s) : {auto}%"
                    )

                col_save, col_auto, col_del = st.columns(3)
                save = col_save.form_submit_button("💾 Enregistrer")
                use_auto = col_auto.form_submit_button("🔄 Utiliser l'avancement calculé")
                delete = col_del.form_submit_button("🗑️ Supprimer")

                if save:
                    models.update_phase(
                        p["id"], name=name, description=description,
                        start_date=start.isoformat(), end_date=end.isoformat(),
                        status=status, progress=progress, version=version,
                        color=color, comments=comments,
                    )
                    st.success("Phase mise à jour.")
                    st.rerun()
                if use_auto and auto is not None:
                    models.update_phase(p["id"], progress=auto)
                    st.success(f"Avancement défini à {auto}%.")
                    st.rerun()
                if delete:
                    models.delete_phase(p["id"])
                    st.warning("Phase supprimée.")
                    st.rerun()


# ---------------------------------------------------------------------------
# TÂCHES
# ---------------------------------------------------------------------------

def _render_tasks(project_id):
    phases = models.get_phases(project_id)
    if not phases:
        st.info("Créez d'abord au moins une phase pour y ajouter des tâches.")
        return

    phase_map = {p["name"]: p["id"] for p in phases}

    # --- Formulaire de création ---
    with st.expander("➕ Ajouter une tâche", expanded=True):
        with st.form("add_task", clear_on_submit=True):
            phase_name = st.selectbox("Phase *", list(phase_map.keys()))
            c1, c2 = st.columns(2)
            name = c1.text_input("Nom de la tâche *")
            assignee = c2.text_input("Responsable")
            c3, c4 = st.columns(2)
            start = c3.date_input("Date de début", value=date.today())
            end = c4.date_input("Date de fin", value=date.today())
            c5, c6 = st.columns(2)
            status = c5.selectbox("Statut", STATUSES)
            progress = c6.slider("Avancement (%)", 0, 100, 0)
            description = st.text_area("Description")
            comments = st.text_area("Commentaires")
            submitted = st.form_submit_button("Créer la tâche")
            if submitted:
                if not name.strip():
                    st.error("Le nom de la tâche est obligatoire.")
                else:
                    models.create_task(
                        phase_map[phase_name], name.strip(), description,
                        start.isoformat(), end.isoformat(), status, progress,
                        assignee, comments,
                    )
                    st.success(f"Tâche « {name} » créée.")
                    st.rerun()

    # --- Liste des tâches groupées par phase ---
    for p in phases:
        phase_tasks = models.get_tasks(phase_id=p["id"])
        st.subheader(f"📋 {p['name']} ({len(phase_tasks)} tâche·s)")
        if not phase_tasks:
            st.caption("Aucune tâche dans cette phase.")
            continue
        for t in phase_tasks:
            _render_task_editor(t, phase_map)


def _render_task_editor(task, phase_map):
    """Formulaire d'édition d'une tâche."""
    title = f"{task['name']} · {task.get('progress', 0)}% · {task.get('status', '')}"
    with st.expander(title):
        with st.form(f"edit_task_{task['id']}"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nom *", value=task["name"], key=f"tn_{task['id']}")
            assignee = c2.text_input(
                "Responsable", value=task.get("assignee") or "", key=f"ta_{task['id']}"
            )
            # Réaffectation possible à une autre phase
            phase_names = list(phase_map.keys())
            current_phase = next(
                (n for n, pid in phase_map.items() if pid == task["phase_id"]),
                phase_names[0],
            )
            new_phase = st.selectbox(
                "Phase", phase_names,
                index=phase_names.index(current_phase),
                key=f"tp_{task['id']}",
            )
            c3, c4 = st.columns(2)
            start = c3.date_input(
                "Début", value=parse_date(task.get("start_date")) or date.today(),
                key=f"ts_{task['id']}",
            )
            end = c4.date_input(
                "Fin", value=parse_date(task.get("end_date")) or date.today(),
                key=f"te_{task['id']}",
            )
            c5, c6 = st.columns(2)
            status = c5.selectbox(
                "Statut", STATUSES,
                index=STATUSES.index(task["status"]) if task.get("status") in STATUSES else 0,
                key=f"tst_{task['id']}",
            )
            progress = c6.slider(
                "Avancement (%)", 0, 100, task.get("progress", 0), key=f"tpr_{task['id']}"
            )
            description = st.text_area(
                "Description", value=task.get("description") or "", key=f"td_{task['id']}"
            )
            comments = st.text_area(
                "Commentaires", value=task.get("comments") or "", key=f"tcm_{task['id']}"
            )
            col_save, col_del = st.columns(2)
            save = col_save.form_submit_button("💾 Enregistrer")
            delete = col_del.form_submit_button("🗑️ Supprimer")
            if save:
                models.update_task(
                    task["id"], name=name, assignee=assignee,
                    phase_id=phase_map[new_phase],
                    start_date=start.isoformat(), end_date=end.isoformat(),
                    status=status, progress=progress, description=description,
                    comments=comments,
                )
                st.success("Tâche mise à jour.")
                st.rerun()
            if delete:
                models.delete_task(task["id"])
                st.warning("Tâche supprimée.")
                st.rerun()


# ---------------------------------------------------------------------------
# DÉPENDANCES
# ---------------------------------------------------------------------------

def _render_dependencies(project_id):
    st.markdown(
        "Définissez les dépendances entre tâches. "
        "**La tâche B nécessite la tâche A** signifie que A doit être terminée avant B."
    )
    tasks = models.get_tasks(project_id=project_id)
    if len(tasks) < 2:
        st.info("Ajoutez au moins deux tâches pour créer des dépendances.")
        return

    task_label = {t["id"]: f"{t.get('phase_name', '')} › {t['name']}" for t in tasks}
    ids = list(task_label.keys())

    # --- Ajout d'une dépendance ---
    with st.form("add_dep", clear_on_submit=True):
        c1, c2 = st.columns(2)
        b = c1.selectbox(
            "Tâche B (dépendante)", ids, format_func=lambda i: task_label[i]
        )
        a = c2.selectbox(
            "nécessite la Tâche A (prérequis)", ids, format_func=lambda i: task_label[i]
        )
        submitted = st.form_submit_button("🔗 Ajouter la dépendance")
        if submitted:
            if a == b:
                st.error("Une tâche ne peut pas dépendre d'elle-même.")
            else:
                models.add_dependency(b, a)
                st.success("Dépendance ajoutée.")
                st.rerun()

    st.divider()

    # --- Liste des dépendances existantes ---
    deps = models.get_dependencies(project_id)
    if not deps:
        st.caption("Aucune dépendance définie.")
        return
    st.subheader("Dépendances existantes")
    for d in deps:
        b_label = task_label.get(d["task_id"], "?")
        a_label = task_label.get(d["depends_on_task_id"], "?")
        col1, col2 = st.columns([0.85, 0.15])
        col1.write(f"**{b_label}** ⬅ nécessite ⬅ **{a_label}**")
        if col2.button("🗑️", key=f"del_dep_{d['id']}"):
            models.remove_dependency(d["task_id"], d["depends_on_task_id"])
            st.rerun()
