"""
Module de gestion des phases (coeur du système) et de leurs tâches.

  - Les phases portent obligatoirement des dates (début / fin), un statut, une
    version (itération) et un avancement.
  - Les dépendances se font entre phases (la phase B nécessite la phase A).
  - Les tâches sont de simples éléments cochables (to-do list) à l'intérieur
    d'une phase ; elles n'ont pas de dates.
"""

import streamlit as st
import pandas as pd
from datetime import date

from database import models
from modules import theme
from utils.helpers import (
    STATUSES, PHASE_PALETTE, parse_date, phase_progress_from_tasks,
    phase_segments,
)


def render(project_id):
    """Interface de gestion des phases, de leurs tâches et de leurs dépendances."""
    theme.banner("Phases & Tâches", "Organisez vos phases, leurs tâches et leurs dépendances.")

    tab_phases, tab_deps = st.tabs(["Phases", "Dépendances"])
    with tab_phases:
        _render_phases(project_id)
    with tab_deps:
        _render_phase_dependencies(project_id)


# ---------------------------------------------------------------------------
# PHASES
# ---------------------------------------------------------------------------

def _render_phases(project_id):
    phases = models.get_phases(project_id)

    # --- Création d'une phase ---
    with st.expander("Ajouter une phase", expanded=not phases):
        with st.form("add_phase", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nom de la phase *")
            version = c2.text_input("Version / Itération", value="V1")
            c3, c4 = st.columns(2)
            start = c3.date_input("Date de début *", value=date.today())
            end = c4.date_input("Date de fin *", value=date.today())
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
                elif end < start:
                    st.error("La date de fin doit être postérieure ou égale à la date de début.")
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

    for p in phases:
        title = f"{p['name']} · {p.get('version', '')} · {p.get('progress', 0)}% · {p.get('status', '')}"
        with st.expander(title):
            _render_phase_editor(p)
            st.markdown("**Tâches (to-do list)**")
            _render_task_todo(p)


def _render_phase_editor(p):
    """Formulaire d'édition d'une phase (métadonnées) + éditeur de périodes."""
    with st.form(f"edit_phase_{p['id']}"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nom *", value=p["name"])
        version = c2.text_input("Version", value=p.get("version", "V1"))
        c5, c6 = st.columns(2)
        status = c5.selectbox(
            "Statut", STATUSES,
            index=STATUSES.index(p["status"]) if p.get("status") in STATUSES else 0,
            key=f"pst_{p['id']}",
        )
        progress = c6.slider(
            "Avancement (%)", 0, 100, p.get("progress", 0), key=f"ppr_{p['id']}"
        )
        color = st.color_picker("Couleur", p.get("color", "#C9A66B"), key=f"pc_{p['id']}")
        description = st.text_area(
            "Description", value=p.get("description") or "", key=f"pd_{p['id']}"
        )
        comments = st.text_area(
            "Commentaires", value=p.get("comments") or "", key=f"pcm_{p['id']}"
        )

        # Avancement calculé d'après les tâches cochées
        phase_tasks = models.get_tasks(phase_id=p["id"])
        auto = phase_progress_from_tasks(phase_tasks)
        if auto is not None:
            st.caption(f"Avancement calculé d'après les tâches cochées : {auto}%")

        col_save, col_auto, col_del = st.columns(3)
        save = col_save.form_submit_button("Enregistrer")
        use_auto = col_auto.form_submit_button("Utiliser l'avancement calculé")
        delete = col_del.form_submit_button("Supprimer la phase")

        if save:
            models.update_phase(
                p["id"], name=name, description=description,
                status=status, progress=progress, version=version,
                color=color, comments=comments,
            )
            st.success("Phase mise à jour.")
            st.rerun()
        if use_auto and auto is not None:
            models.update_phase_progress(p["id"], auto)
            st.success(f"Avancement défini à {auto}%.")
            st.rerun()
        if delete:
            models.delete_phase(p["id"])
            st.warning("Phase supprimée.")
            st.rerun()

    _render_phase_periods(p)


def _render_phase_periods(p):
    """
    Éditeur des périodes d'une phase (hors formulaire principal).

    Une phase peut se dérouler en plusieurs temps (alternance, creux d'un mois,
    etc.). Le tableau accepte autant de lignes « du… au… » que nécessaire ; les
    dates de la phase (enveloppe) sont recalculées à partir de ces périodes.
    """
    st.markdown("**Périodes de la phase**")
    st.caption(
        "Ajoutez plusieurs lignes pour découper la phase en plusieurs temps "
        "(les creux entre périodes ne comptent pas dans la durée travaillée). "
        "Une seule ligne = phase continue."
    )

    periods = phase_segments(p)
    rows = [{"Début": s, "Fin": e} for s, e in periods] or [{"Début": None, "Fin": None}]
    df = pd.DataFrame(rows, columns=["Début", "Fin"])

    edited = st.data_editor(
        df, num_rows="dynamic", width='stretch', key=f"periods_{p['id']}",
        column_config={
            "Début": st.column_config.DateColumn("Début", format="DD/MM/YYYY"),
            "Fin": st.column_config.DateColumn("Fin", format="DD/MM/YYYY"),
        },
    )

    if st.button("Enregistrer les périodes", key=f"savep_{p['id']}"):
        segs, err = _read_periods(edited)
        if err:
            st.error(err)
        else:
            start = min(s for s, _ in segs).isoformat()
            end = max(e for _, e in segs).isoformat()
            # Une seule période => phase continue (pas de segments à stocker).
            segments = [] if len(segs) == 1 else [
                {"start_date": s.isoformat(), "end_date": e.isoformat()} for s, e in segs
            ]
            models.update_phase(p["id"], start_date=start, end_date=end, segments=segments)
            st.success("Périodes enregistrées.")
            st.rerun()


def _coerce_date(value):
    """Convertit une cellule du tableau (Timestamp/date/texte/NaT) en date ou None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except (TypeError, ValueError):
            pass
    return parse_date(str(value))


def _read_periods(edited):
    """Valide et trie les périodes saisies. Retourne (liste[(début,fin)], erreur)."""
    result = []
    for _, r in edited.iterrows():
        s = _coerce_date(r.get("Début"))
        e = _coerce_date(r.get("Fin"))
        if s is None and e is None:
            continue
        if s is None or e is None:
            return None, "Chaque période doit avoir une date de début ET une date de fin."
        if e < s:
            return None, "La date de fin doit être postérieure ou égale à la date de début."
        result.append((s, e))
    if not result:
        return None, "Renseignez au moins une période (début et fin)."
    return sorted(result), None


def _render_task_todo(p):
    """To-do list des tâches d'une phase : cases à cocher + ajout + suppression."""
    tasks = models.get_tasks(phase_id=p["id"])
    if not tasks:
        st.caption("Aucune tâche. Ajoutez-en ci-dessous.")
    for t in tasks:
        done = t.get("status") == "Terminé"
        cols = st.columns([0.85, 0.15])
        checked = cols[0].checkbox(t["name"], value=done, key=f"task_chk_{t['id']}")
        if checked != done:
            models.set_task_status(t["id"], "Terminé" if checked else "À faire")
            st.rerun()
        if cols[1].button("Supprimer", key=f"task_del_{t['id']}"):
            models.delete_task(t["id"])
            st.rerun()

    # Ajout d'une tâche
    with st.form(f"add_task_{p['id']}", clear_on_submit=True):
        new_name = st.text_input("Nouvelle tâche", key=f"newtask_{p['id']}",
                                  label_visibility="collapsed",
                                  placeholder="Intitulé de la tâche…")
        if st.form_submit_button("Ajouter la tâche"):
            if new_name.strip():
                models.create_task(p["id"], new_name.strip(),
                                   order_index=len(tasks))
                st.rerun()


# ---------------------------------------------------------------------------
# DÉPENDANCES ENTRE PHASES
# ---------------------------------------------------------------------------

def _render_phase_dependencies(project_id):
    st.markdown(
        "Définissez les dépendances entre phases. "
        "**La phase B nécessite la phase A** signifie que A doit être terminée avant B."
    )
    phases = models.get_phases(project_id)
    if len(phases) < 2:
        st.info("Ajoutez au moins deux phases pour créer des dépendances.")
        return

    label = {p["id"]: p["name"] for p in phases}
    ids = list(label.keys())

    with st.form("add_phase_dep", clear_on_submit=True):
        c1, c2 = st.columns(2)
        b = c1.selectbox("Phase B (dépendante)", ids, format_func=lambda i: label[i])
        a = c2.selectbox("nécessite la Phase A (prérequis)", ids,
                         format_func=lambda i: label[i])
        if st.form_submit_button("Ajouter la dépendance"):
            if a == b:
                st.error("Une phase ne peut pas dépendre d'elle-même.")
            else:
                models.add_phase_dependency(b, a)
                st.success("Dépendance ajoutée.")
                st.rerun()

    st.divider()
    deps = models.get_phase_dependencies(project_id)
    if not deps:
        st.caption("Aucune dépendance définie.")
        return
    st.subheader("Dépendances existantes")
    for d in deps:
        b_label = label.get(d["phase_id"], "?")
        a_label = label.get(d["depends_on_phase_id"], "?")
        col1, col2 = st.columns([0.85, 0.15])
        col1.write(f"**{b_label}** nécessite **{a_label}**")
        if col2.button("Supprimer", key=f"del_phdep_{d['id']}"):
            models.remove_phase_dependency(d["phase_id"], d["depends_on_phase_id"])
            st.rerun()
