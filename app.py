"""
Application de gestion et de phasage de projet.

Point d'entrée Streamlit. Orchestration de la navigation entre les modules :
  - Tableau de bord (Gantt, chemin critique, avancement, camembert) ;
  - Action Rapide (to-do de la semaine) ;
  - Gestion des phases & tâches (délais, statut, dépendances, versions) ;
  - Livrables ;
  - Réunions & Communication (CR, récapitulatif auto) ;
  - Export & Sauvegarde.

Lancement : `streamlit run app.py`
"""

import streamlit as st
from datetime import date

from database.db import init_db
from database import db, models
from modules import dashboard, todo, tasks, deliverables, meetings, export, theme


# Configuration de la page (doit être le premier appel Streamlit)
st.set_page_config(
    page_title="Gestion de Projet",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Injection du thème pastel (polices, couleurs douces, coins arrondis)
theme.inject_css()


def ensure_db():
    """Initialise la base de données une seule fois par session."""
    if not st.session_state.get("_db_ready"):
        init_db(seed=True)
        st.session_state["_db_ready"] = True


def select_project():
    """
    Affiche le sélecteur de projet dans la barre latérale et permet d'en créer
    ou d'en supprimer. Retourne l'id du projet sélectionné (ou None).
    """
    st.sidebar.markdown(
        """
        <div style="
            font-family:'Playfair Display', Georgia, serif;
            font-size:1.6rem; font-weight:700;
            text-align:center; color:#8A6D45;
            padding:8px 0 4px 0;">
            Mes Projets
        </div>
        <div style="text-align:center; color:#9C8466; font-size:0.85rem;
                    font-style:italic; margin-bottom:8px;">
            Gérez vos phases avec élégance
        </div>
        """,
        unsafe_allow_html=True,
    )
    projects = models.get_projects()

    # Création d'un nouveau projet
    with st.sidebar.expander("Nouveau projet"):
        with st.form("new_project", clear_on_submit=True):
            name = st.text_input("Nom du projet *")
            description = st.text_area("Description")
            c1, c2 = st.columns(2)
            start = c1.date_input("Début", value=date.today())
            end = c2.date_input("Fin", value=date.today())
            if st.form_submit_button("Créer"):
                if not name.strip():
                    st.error("Le nom est obligatoire.")
                else:
                    new_id = models.create_project(
                        name.strip(), description, start.isoformat(), end.isoformat()
                    )
                    st.session_state["current_project"] = new_id
                    st.rerun()

    if not projects:
        st.sidebar.info("Aucun projet. Créez-en un pour commencer.")
        return None

    # Sélection du projet courant
    project_ids = [p["id"] for p in projects]
    labels = {p["id"]: p["name"] for p in projects}
    default = st.session_state.get("current_project", project_ids[0])
    if default not in project_ids:
        default = project_ids[0]

    selected = st.sidebar.selectbox(
        "Projet actif",
        project_ids,
        index=project_ids.index(default),
        format_func=lambda i: labels[i],
    )
    st.session_state["current_project"] = selected

    # Suppression du projet
    with st.sidebar.expander("Gérer ce projet"):
        if st.button("Supprimer le projet", type="secondary"):
            models.delete_project(selected)
            st.session_state.pop("current_project", None)
            st.rerun()

    return selected


def main():
    ensure_db()
    project_id = select_project()

    if project_id is None:
        theme.banner(
            "Bienvenue",
            "Créez votre premier projet depuis la barre latérale pour commencer.",
        )
        return

    # Navigation principale
    st.sidebar.divider()
    page = st.sidebar.radio(
        "Navigation",
        [
            "Tableau de bord",
            "Action Rapide",
            "Phases & Tâches",
            "Livrables",
            "Réunions",
            "Export",
        ],
    )

    # Routage vers le module correspondant
    if page == "Tableau de bord":
        dashboard.render(project_id)
    elif page == "Action Rapide":
        todo.render(project_id)
    elif page == "Phases & Tâches":
        tasks.render(project_id)
    elif page == "Livrables":
        deliverables.render(project_id)
    elif page == "Réunions":
        meetings.render(project_id)
    elif page == "Export":
        export.render(project_id)

    st.sidebar.divider()
    st.sidebar.caption(f"Stockage : {db.backend_label()}")


if __name__ == "__main__":
    main()
