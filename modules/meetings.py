"""
Module Réunions & Communication.

Permet de :
  - planifier des réunions (date, heure, participants, sujet/phase) ;
  - rédiger le Compte Rendu (CR) directement dans l'application ;
  - mettre à jour le taux d'avancement de la phase concernée depuis la vue CR ;
  - générer automatiquement un récapitulatif textuel (avancements + ordre du jour)
    prêt à être copié/collé pour les parties prenantes.
"""

import streamlit as st
from datetime import date, datetime, time as dtime

from database import models
from modules import theme
from utils.helpers import global_progress, parse_date, format_date_fr

# Heure par défaut fixe pour les nouveaux créneaux. On évite volontairement
# datetime.now().time() comme valeur par défaut d'un time_input : sa valeur
# changeant à chaque rerun pourrait perturber le widget côté navigateur.
DEFAULT_TIME = dtime(9, 0)


def render(project_id):
    theme.banner("Réunions & Communication", "Planifiez, consignez et partagez vos avancées.")

    tab_meet, tab_recap = st.tabs(["Réunions & CR", "Récapitulatif automatique"])
    with tab_meet:
        _render_meetings(project_id)
    with tab_recap:
        _render_auto_recap(project_id)


# ---------------------------------------------------------------------------
# RÉUNIONS & COMPTES RENDUS
# ---------------------------------------------------------------------------

def _render_meetings(project_id):
    phases = models.get_phases(project_id)
    phase_map = {"— Aucune —": None}
    phase_map.update({p["name"]: p["id"] for p in phases})

    # --- Planifier une réunion ---
    with st.expander("Planifier une réunion", expanded=True):
        with st.form("add_meeting", clear_on_submit=True):
            c1, c2 = st.columns(2)
            mdate = c1.date_input("Date", value=date.today())
            mtime = c2.time_input("Heure", value=DEFAULT_TIME)
            subject = st.text_input("Sujet *")
            phase_name = st.selectbox("Phase concernée", list(phase_map.keys()))
            participants = st.text_input("Participants (séparés par des virgules)")
            report = st.text_area("Compte rendu (optionnel à ce stade)", height=120)
            submitted = st.form_submit_button("Créer la réunion")
            if submitted:
                if not subject.strip():
                    st.error("Le sujet est obligatoire.")
                else:
                    models.create_meeting(
                        project_id, phase_map[phase_name], mdate.isoformat(),
                        mtime.strftime("%H:%M"), participants, subject.strip(), report,
                    )
                    st.success("Réunion créée.")
                    st.rerun()

    meetings = models.get_meetings(project_id)
    if not meetings:
        st.info("Aucune réunion planifiée.")
        return

    st.divider()
    st.subheader("Historique des réunions")

    for m in meetings:
        header = f"{format_date_fr(m.get('date'))} {m.get('time', '')} — {m.get('subject', '')}"
        with st.expander(header):
            _render_meeting_editor(m, phase_map, phases)


def _render_meeting_editor(meeting, phase_map, phases):
    """Édition d'une réunion + rédaction du CR + maj avancement de la phase."""
    with st.form(f"edit_meeting_{meeting['id']}"):
        c1, c2 = st.columns(2)
        mdate = c1.date_input(
            "Date", value=parse_date(meeting.get("date")) or date.today(),
            key=f"md_{meeting['id']}",
        )
        mtime_str = meeting.get("time") or "09:00"
        try:
            t_default = datetime.strptime(mtime_str, "%H:%M").time()
        except ValueError:
            t_default = DEFAULT_TIME
        mtime = c2.time_input("Heure", value=t_default, key=f"mt_{meeting['id']}")

        subject = st.text_input("Sujet", value=meeting.get("subject") or "", key=f"ms_{meeting['id']}")

        phase_names = list(phase_map.keys())
        current_phase = next(
            (n for n, pid in phase_map.items() if pid == meeting.get("phase_id")),
            phase_names[0],
        )
        phase_name = st.selectbox(
            "Phase concernée", phase_names,
            index=phase_names.index(current_phase), key=f"mp_{meeting['id']}",
        )
        participants = st.text_input(
            "Participants", value=meeting.get("participants") or "", key=f"mpa_{meeting['id']}"
        )

        # --- Zone de saisie du Compte Rendu ---
        st.markdown("**Compte Rendu**")
        report = st.text_area(
            "Rédigez le CR ici", value=meeting.get("report") or "",
            height=200, key=f"mr_{meeting['id']}", label_visibility="collapsed",
        )

        # --- Mise à jour de l'avancement de la phase concernée ---
        phase_id = phase_map[phase_name]
        new_progress = None
        if phase_id is not None:
            current_phase_obj = next((p for p in phases if p["id"] == phase_id), None)
            if current_phase_obj:
                st.markdown(f"**Avancement de la phase « {current_phase_obj['name']} »**")
                new_progress = st.slider(
                    "Mettre à jour l'avancement (%)", 0, 100,
                    current_phase_obj.get("progress", 0),
                    key=f"mprog_{meeting['id']}",
                )

        col_save, col_del = st.columns(2)
        save = col_save.form_submit_button("Enregistrer le CR")
        delete = col_del.form_submit_button("Supprimer la réunion")

        if save:
            models.update_meeting(
                meeting["id"], date=mdate.isoformat(),
                time=mtime.strftime("%H:%M"), subject=subject,
                phase_id=phase_id, participants=participants, report=report,
            )
            # Met à jour l'avancement de la phase si modifié
            if phase_id is not None and new_progress is not None:
                models.update_phase_progress(phase_id, new_progress)
            st.success("Réunion et CR enregistrés.")
            st.rerun()
        if delete:
            models.delete_meeting(meeting["id"])
            st.warning("Réunion supprimée.")
            st.rerun()


# ---------------------------------------------------------------------------
# RÉCAPITULATIF AUTOMATIQUE
# ---------------------------------------------------------------------------

def _render_auto_recap(project_id):
    st.markdown(
        "Génère un **récapitulatif textuel** compilant les avancements des phases "
        "et l'ordre du jour, prêt à être copié/collé pour les parties prenantes."
    )

    project = models.get_project(project_id)
    phases = models.get_phases(project_id)
    meetings = models.get_meetings(project_id)

    # Sélection optionnelle d'une réunion pour intégrer son sujet / CR
    meeting_options = {"— Aucune réunion —": None}
    for m in meetings:
        label = f"{format_date_fr(m.get('date'))} — {m.get('subject', '')}"
        meeting_options[label] = m["id"]
    selected = st.selectbox("Réunion associée (optionnel)", list(meeting_options.keys()))
    meeting_id = meeting_options[selected]
    meeting = models.get_meeting(meeting_id) if meeting_id else None

    agenda = st.text_area(
        "Points à l'ordre du jour (un par ligne)",
        value=(meeting.get("subject") if meeting else ""),
        height=120,
    )

    recap = generate_recap(project, phases, agenda, meeting)

    st.divider()
    st.subheader("Récapitulatif généré")
    # Zone de texte en lecture : sélectionnable pour un copier/coller facile.
    # On évite st.code ici : son rendu (highlighter) boucle dans un onglet
    # initialement masqué et déclenche l'erreur React « Maximum update depth ».
    st.text_area(
        "Récapitulatif (sélectionnez puis copiez)",
        value=recap,
        height=320,
    )
    st.download_button(
        "Télécharger le récapitulatif (.txt)",
        data=recap,
        file_name=f"recap_{project['name'].replace(' ', '_')}.txt",
        mime="text/plain",
    )
    st.caption("Astuce : utilisez l'icône de copie en haut à droite du bloc ci-dessus.")


def generate_recap(project, phases, agenda, meeting=None):
    """
    Compile un récapitulatif textuel : entête, avancement global, détail par
    phase, ordre du jour et éventuel CR de réunion.
    """
    lines = []
    lines.append(f"# RÉCAPITULATIF — {project['name']}")
    lines.append(f"Date d'édition : {date.today().strftime('%d/%m/%Y')}")
    lines.append("")

    # Avancement global
    g = global_progress(phases)
    lines.append(f"## Avancement global du projet : {g}%")
    lines.append("")

    # Détail par phase
    lines.append("## Avancement par phase")
    if phases:
        for p in phases:
            lines.append(
                f"- {p['name']} ({p.get('version', '')}) : "
                f"{p.get('progress', 0)}% — {p.get('status', '')}"
            )
    else:
        lines.append("- Aucune phase définie.")
    lines.append("")

    # Réunion associée
    if meeting:
        lines.append("## Réunion")
        lines.append(f"Date : {format_date_fr(meeting.get('date'))} {meeting.get('time', '')}")
        lines.append(f"Sujet : {meeting.get('subject', '')}")
        if meeting.get("participants"):
            lines.append(f"Participants : {meeting['participants']}")
        lines.append("")

    # Ordre du jour
    if agenda and agenda.strip():
        lines.append("## Ordre du jour / Points clés")
        for item in agenda.strip().splitlines():
            if item.strip():
                lines.append(f"- {item.strip()}")
        lines.append("")

    # Compte rendu éventuel
    if meeting and meeting.get("report"):
        lines.append("## Compte rendu")
        lines.append(meeting["report"])
        lines.append("")

    return "\n".join(lines)
