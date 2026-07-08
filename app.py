"""
Application de gestion et de phasage de projet.

Point d'entrée Streamlit. Gère :
  - l'identification par Username (stocké en session) ;
  - la navigation entre les modules ;
  - le filtrage de tous les projets par utilisateur connecté.

Lancement : `streamlit run app.py`
"""

import streamlit as st
from datetime import date

from database.db import init_db
from database import db, models
from modules import dashboard, todo, tasks, deliverables, meetings, export, theme


st.set_page_config(
    page_title="Gestion de Projet",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Injection du thème (couleurs, polices, coins arrondis)
theme.inject_css()


def ensure_db():
    """
    Initialise le stockage une seule fois par session. En cas d'échec d'accès au
    gist GitHub (token invalide, gist introuvable, réseau), affiche un message
    clair et actionnable plutôt que de laisser remonter une erreur technique.
    """
    if st.session_state.get("_db_ready"):
        return
    try:
        init_db(seed=True)
        st.session_state["_db_ready"] = True
    except Exception as exc:
        st.error(
            "Impossible d'accéder au stockage GitHub Gist.\n\n"
            "Causes les plus fréquentes (Streamlit Cloud + GitHub Gist) :\n"
            "- un **token GitHub invalide ou expiré**, ou sans la portée `gist` ;\n"
            "- un **`gist_id` erroné** (l'identifiant est la partie finale de "
            "l'URL du gist) ;\n"
            "- des secrets mal renseignés : il faut un bloc `[github]` avec "
            "`token` et `gist_id` (voir le README, section « Déploiement persistant »)."
        )
        with st.expander("Détail technique de l'erreur"):
            st.code(f"{type(exc).__name__}: {exc}")
        st.stop()


def storage_is_persistent():
    """Vrai si le stockage actif est persistant (GitHub Gist)."""
    return db.is_persistent()


def render_storage_status():
    """
    Affiche l'état du stockage dans la barre latérale (toujours visible) :
    succès si persistant, avertissement appuyé sinon.
    """
    if storage_is_persistent():
        st.sidebar.success("Stockage : GitHub Gist (persistant)")
    else:
        st.sidebar.warning(
            "Stockage : fichier local (NON persistant).\n\n"
            "En ligne (Streamlit Cloud), les données sont effacées à chaque "
            "redémarrage du serveur. Configurez les secrets `[github]` "
            "(token + gist_id) pour les conserver durablement."
        )


def login_screen():
    """
    Écran d'accueil : saisie du Username. Tant qu'aucun nom n'est saisi, le
    contenu de l'application reste inaccessible. Le nom est conservé en session.
    """
    theme.banner(
        "Bienvenue",
        "Saisissez votre nom d'utilisateur pour accéder à vos projets.",
    )

    # Avertissement bien visible si le stockage n'est pas persistant
    if not storage_is_persistent():
        st.warning(
            "**Stockage non persistant.** Vos données sont actuellement dans un "
            "fichier JSON local qui, sur Streamlit Cloud, est effacé à chaque "
            "redémarrage du serveur. Pour conserver durablement vos projets, "
            "configurez un gist GitHub via les secrets `[github]` (token + gist_id, "
            "voir le README, section « Déploiement persistant »)."
        )

    with st.form("login", clear_on_submit=False):
        username = st.text_input("Nom d'utilisateur")
        submitted = st.form_submit_button("Se connecter")
        if submitted:
            if username.strip():
                st.session_state["username"] = username.strip()
                st.session_state.pop("current_project", None)
                st.rerun()
            else:
                st.error("Veuillez saisir un nom d'utilisateur.")
    st.caption(
        "Chaque utilisateur ne voit et ne modifie que ses propres projets. "
        "Saisissez le même nom (mêmes majuscules) pour retrouver vos projets."
    )


def select_project(username):
    """
    Sélecteur de projet (limité aux projets de l'utilisateur connecté) dans la
    barre latérale. Permet d'en créer ou d'en supprimer. Retourne l'id choisi.
    """
    st.sidebar.markdown(
        f"""
        <div style="
            font-family:'Playfair Display', Georgia, serif;
            font-size:1.6rem; font-weight:700;
            text-align:center; color:#8A6D45;
            padding:8px 0 2px 0;">
            Mes Projets
        </div>
        <div style="text-align:center; color:#9C8466; font-size:0.85rem;
                    margin-bottom:8px;">
            Connecté : <b>{username}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Changer d'utilisateur"):
        st.session_state.pop("username", None)
        st.session_state.pop("current_project", None)
        st.rerun()

    projects = models.get_projects(username)

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
                        username, name.strip(), description,
                        start.isoformat(), end.isoformat(),
                    )
                    st.session_state["current_project"] = new_id
                    st.rerun()

    if not projects:
        st.sidebar.info("Aucun projet. Créez-en un pour commencer.")
        return None

    project_ids = [p["id"] for p in projects]
    labels = {p["id"]: p["name"] for p in projects}
    default = st.session_state.get("current_project", project_ids[0])
    if default not in project_ids:
        default = project_ids[0]

    selected = st.sidebar.selectbox(
        "Projet actif", project_ids,
        index=project_ids.index(default),
        format_func=lambda i: labels[i],
    )
    st.session_state["current_project"] = selected

    with st.sidebar.expander("Gérer ce projet"):
        # --- Renommer le projet ---
        with st.form("rename_project", clear_on_submit=False):
            new_name = st.text_input("Renommer ce projet", value=labels[selected])
            if st.form_submit_button("Renommer"):
                if new_name.strip():
                    current = models.get_project(selected)
                    models.update_project(
                        selected, new_name.strip(),
                        current.get("description"),
                        current.get("start_date"), current.get("end_date"),
                    )
                    st.rerun()
                else:
                    st.error("Le nom ne peut pas être vide.")

        st.divider()

        # --- Supprimer le projet (avec confirmation, action définitive) ---
        del_key = f"_confirm_delete_{selected}"
        if not st.session_state.get(del_key):
            if st.button("Supprimer le projet", type="secondary"):
                st.session_state[del_key] = True
                st.rerun()
        else:
            st.warning(
                f"Supprimer définitivement le projet « {labels[selected]} » ? "
                "Cette action est irréversible : toutes ses phases, tâches, "
                "livrables et réunions seront perdus."
            )
            c1, c2 = st.columns(2)
            if c1.button("Oui, supprimer"):
                models.delete_project(selected)
                st.session_state.pop(del_key, None)
                st.session_state.pop("current_project", None)
                st.rerun()
            if c2.button("Annuler"):
                st.session_state.pop(del_key, None)
                st.rerun()

    return selected


def main():
    ensure_db()

    # État du stockage toujours visible (avertit si non persistant)
    render_storage_status()

    # Étape 1 : identification obligatoire
    username = st.session_state.get("username")
    if not username:
        login_screen()
        return

    # Étape 2 : sélection d'un projet de l'utilisateur
    project_id = select_project(username)
    if project_id is None:
        theme.banner(
            "Aucun projet",
            "Créez votre premier projet depuis la barre latérale pour commencer.",
        )
        return

    # Sécurité : on ne charge un projet que s'il appartient à l'utilisateur
    project = models.get_project(project_id)
    if not project or project.get("username") != username:
        st.session_state.pop("current_project", None)
        st.rerun()

    st.sidebar.divider()
    page = st.sidebar.radio(
        "Navigation",
        ["Tableau de bord", "Action Rapide", "Phases & Tâches",
         "Livrables", "Réunions", "Export"],
    )

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


if __name__ == "__main__":
    main()
