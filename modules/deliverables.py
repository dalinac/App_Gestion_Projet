"""
Module Livrables.

Permet de lier un livrable à une phase en précisant :
  - sa nature (document, prototype, code, etc.) ;
  - sa date limite ;
  - son destinataire (à qui le rendre) ;
  - son statut.
Inclut une alerte sur les livrables dont l'échéance approche ou est dépassée.
"""

import streamlit as st
from datetime import date

from database import models
from utils.helpers import STATUSES, parse_date, format_date_fr

# Natures de livrables proposées
NATURES = ["Document", "Prototype", "Code / Logiciel", "Maquette",
           "Rapport", "Présentation", "Autre"]


def render(project_id):
    st.header("Livrables")

    phases = models.get_phases(project_id)
    if not phases:
        st.info("Créez d'abord au moins une phase pour y associer des livrables.")
        return

    phase_map = {p["name"]: p["id"] for p in phases}

    # --- Formulaire de création ---
    with st.expander("Ajouter un livrable", expanded=True):
        with st.form("add_deliverable", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nom du livrable *")
            phase_name = c2.selectbox("Phase liée *", list(phase_map.keys()))
            c3, c4 = st.columns(2)
            nature = c3.selectbox("Nature", NATURES)
            due = c4.date_input("Date limite", value=date.today())
            c5, c6 = st.columns(2)
            recipient = c5.text_input("Destinataire (à qui le rendre)")
            status = c6.selectbox("Statut", STATUSES)
            submitted = st.form_submit_button("Créer le livrable")
            if submitted:
                if not name.strip():
                    st.error("Le nom du livrable est obligatoire.")
                else:
                    models.create_deliverable(
                        phase_map[phase_name], name.strip(), nature,
                        due.isoformat(), recipient, status,
                    )
                    st.success(f"Livrable « {name} » créé.")
                    st.rerun()

    deliverables = models.get_deliverables(project_id)
    if not deliverables:
        st.info("Aucun livrable pour le moment.")
        return

    # --- Alertes d'échéance ---
    today = date.today()
    overdue = [
        dl for dl in deliverables
        if parse_date(dl.get("due_date")) and parse_date(dl["due_date"]) < today
        and dl.get("status") != "Terminé"
    ]
    if overdue:
        st.error(
            f"{len(overdue)} livrable·s en retard : "
            + ", ".join(dl["name"] for dl in overdue)
        )

    st.divider()

    # --- Tableau récapitulatif ---
    st.subheader("Liste des livrables")
    table_rows = []
    for dl in deliverables:
        table_rows.append({
            "Livrable": dl["name"],
            "Phase": dl.get("phase_name", ""),
            "Nature": dl.get("nature", ""),
            "Date limite": format_date_fr(dl.get("due_date")),
            "Destinataire": dl.get("recipient", ""),
            "Statut": dl.get("status", ""),
        })
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    st.divider()

    # --- Édition détaillée ---
    st.subheader("Modifier / supprimer")
    for dl in deliverables:
        with st.expander(f"{dl['name']} · {dl.get('status', '')}"):
            with st.form(f"edit_dl_{dl['id']}"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Nom *", value=dl["name"], key=f"dln_{dl['id']}")
                phase_names = list(phase_map.keys())
                current_phase = next(
                    (n for n, pid in phase_map.items() if pid == dl["phase_id"]),
                    phase_names[0],
                )
                phase_name = c2.selectbox(
                    "Phase", phase_names,
                    index=phase_names.index(current_phase), key=f"dlp_{dl['id']}",
                )
                c3, c4 = st.columns(2)
                nature = c3.selectbox(
                    "Nature", NATURES,
                    index=NATURES.index(dl["nature"]) if dl.get("nature") in NATURES else 0,
                    key=f"dlnat_{dl['id']}",
                )
                due = c4.date_input(
                    "Date limite", value=parse_date(dl.get("due_date")) or date.today(),
                    key=f"dld_{dl['id']}",
                )
                c5, c6 = st.columns(2)
                recipient = c5.text_input(
                    "Destinataire", value=dl.get("recipient") or "", key=f"dlr_{dl['id']}"
                )
                status = c6.selectbox(
                    "Statut", STATUSES,
                    index=STATUSES.index(dl["status"]) if dl.get("status") in STATUSES else 0,
                    key=f"dls_{dl['id']}",
                )
                col_save, col_del = st.columns(2)
                save = col_save.form_submit_button("Enregistrer")
                delete = col_del.form_submit_button("Supprimer")
                if save:
                    models.update_deliverable(
                        dl["id"], name=name, phase_id=phase_map[phase_name],
                        nature=nature, due_date=due.isoformat(),
                        recipient=recipient, status=status,
                    )
                    st.success("Livrable mis à jour.")
                    st.rerun()
                if delete:
                    models.delete_deliverable(dl["id"])
                    st.warning("Livrable supprimé.")
                    st.rerun()
