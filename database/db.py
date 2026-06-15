"""
Couche d'accès à la base de données (SQLAlchemy — double moteur).

Cette couche fonctionne avec deux moteurs, sans changer le reste du code :

  * PostgreSQL (ex. Supabase) si une URL de connexion est fournie via le secret
    Streamlit ``DATABASE_URL`` (ou la variable d'environnement du même nom).
    => stockage **persistant**, indispensable sur Streamlit Community Cloud dont
       le système de fichiers est éphémère.

  * SQLite local (fichier ``data/gestion_projet.db``) sinon.
    => pratique pour développer en local sans aucune configuration.

Le SQL utilisé est compatible avec les deux moteurs (SQLAlchemy + clé
``RETURNING``, ``ON CONFLICT DO NOTHING``, ``CURRENT_TIMESTAMP``). Seule la
définition de la clé primaire auto-incrémentée diffère selon le moteur.
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text, event

# Emplacement du fichier SQLite local (utilisé seulement en l'absence d'URL)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "gestion_projet.db")

# Moteur SQLAlchemy mis en cache + indicateur du dialecte
_ENGINE = None
IS_POSTGRES = False


def _database_url():
    """
    Retourne l'URL de connexion à une base distante si elle est configurée.

    Ordre de priorité :
      1. variable d'environnement ``DATABASE_URL`` ;
      2. secret Streamlit ``DATABASE_URL`` (st.secrets).
    Retourne ``None`` si rien n'est configuré (=> SQLite local).
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            # .get évite une exception si la clé est absente
            url = st.secrets.get("DATABASE_URL")
        except Exception:
            url = None
    return url or None


def get_engine():
    """Crée (une seule fois) et retourne le moteur SQLAlchemy approprié."""
    global _ENGINE, IS_POSTGRES
    if _ENGINE is not None:
        return _ENGINE

    url = _database_url()
    if url:
        # Normalise le préfixe pour utiliser le pilote psycopg2
        if url.startswith("postgres://"):
            url = "postgresql+psycopg2://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]

        connect_args = {}
        # Supabase impose le SSL ; on l'ajoute si l'URL ne le précise pas déjà
        if "sslmode" not in url:
            connect_args["sslmode"] = "require"

        IS_POSTGRES = True
        _ENGINE = create_engine(
            url,
            pool_pre_ping=True,      # vérifie la connexion (utile derrière un pooler)
            pool_recycle=300,        # recycle les connexions inactives
            connect_args=connect_args,
        )
    else:
        os.makedirs(DATA_DIR, exist_ok=True)
        IS_POSTGRES = False
        _ENGINE = create_engine(
            f"sqlite:///{DB_PATH}",
            connect_args={"check_same_thread": False},  # Streamlit est multi-thread
        )

        # Active les clés étrangères pour SQLite (désactivées par défaut)
        @event.listens_for(_ENGINE, "connect")
        def _enable_sqlite_fk(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return _ENGINE


@contextmanager
def db_session():
    """
    Gestionnaire de contexte fournissant une connexion transactionnelle.

        with db_session() as conn:
            conn.execute(text("..."), {...})

    Le commit est automatique en sortie, le rollback en cas d'exception.
    """
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def rows_to_dicts(result):
    """Convertit un Result SQLAlchemy en liste de dictionnaires."""
    return [dict(r) for r in result.mappings().all()]


def row_to_dict(result):
    """Retourne la première ligne d'un Result en dict, ou None."""
    row = result.mappings().first()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Définition du schéma
# ---------------------------------------------------------------------------

def _pk():
    """Type de clé primaire auto-incrémentée selon le moteur."""
    return "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _schema_statements():
    """Liste des instructions CREATE TABLE (compatibles SQLite et PostgreSQL)."""
    pk = _pk()
    return [
        f"""
        CREATE TABLE IF NOT EXISTS projects (
            id          {pk},
            name        TEXT NOT NULL,
            description TEXT,
            start_date  TEXT,
            end_date    TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        f"""
        CREATE TABLE IF NOT EXISTS phases (
            id          {pk},
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            description TEXT,
            start_date  TEXT,
            end_date    TEXT,
            status      TEXT DEFAULT 'À faire',
            progress    INTEGER DEFAULT 0,
            version     TEXT DEFAULT 'V1',
            color       TEXT DEFAULT '#C9A66B',
            order_index INTEGER DEFAULT 0,
            comments    TEXT
        )""",
        f"""
        CREATE TABLE IF NOT EXISTS tasks (
            id          {pk},
            phase_id    INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            description TEXT,
            start_date  TEXT,
            end_date    TEXT,
            status      TEXT DEFAULT 'À faire',
            progress    INTEGER DEFAULT 0,
            assignee    TEXT,
            comments    TEXT
        )""",
        f"""
        CREATE TABLE IF NOT EXISTS dependencies (
            id                  {pk},
            task_id             INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            depends_on_task_id  INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            UNIQUE (task_id, depends_on_task_id)
        )""",
        f"""
        CREATE TABLE IF NOT EXISTS deliverables (
            id          {pk},
            phase_id    INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            nature      TEXT,
            due_date    TEXT,
            recipient   TEXT,
            status      TEXT DEFAULT 'À faire'
        )""",
        f"""
        CREATE TABLE IF NOT EXISTS meetings (
            id              {pk},
            project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            phase_id        INTEGER REFERENCES phases(id) ON DELETE SET NULL,
            date            TEXT,
            time            TEXT,
            participants    TEXT,
            subject         TEXT,
            report          TEXT
        )""",
    ]


def init_db(seed: bool = True):
    """
    Crée le schéma (si absent) et insère un jeu de démonstration au premier
    lancement (uniquement si la base ne contient encore aucun projet).
    """
    get_engine()  # s'assure que IS_POSTGRES est positionné avant de bâtir le schéma
    with db_session() as conn:
        for statement in _schema_statements():
            conn.execute(text(statement))

    if seed:
        with db_session() as conn:
            count = conn.execute(text("SELECT COUNT(*) AS c FROM projects")).scalar()
            if count == 0:
                _seed_demo(conn)


def _seed_demo(conn):
    """Insère un projet exemple illustrant l'ensemble des fonctionnalités."""
    from datetime import date, timedelta

    today = date.today()

    def d(offset):
        return (today + timedelta(days=offset)).isoformat()

    # --- Projet ---
    project_id = conn.execute(
        text("""INSERT INTO projects (name, description, start_date, end_date)
                VALUES (:n, :de, :s, :e) RETURNING id"""),
        {
            "n": "Projet Démo — Application connectée",
            "de": "Projet d'exemple illustrant le phasage, les livrables et les réunions.",
            "s": d(-10), "e": d(60),
        },
    ).scalar()

    # --- Phases ---
    phases = [
        ("Cadrage & Besoins", d(-10), d(0), "Terminé", 100, "V1", "#C9A66B"),
        ("Conception", d(0), d(15), "En cours", 60, "V1", "#CBA890"),
        ("Développement", d(12), d(40), "En cours", 25, "V2", "#A9B388"),
        ("Tests & Validation", d(38), d(52), "À faire", 0, "V1", "#B5A081"),
        ("Déploiement", d(50), d(60), "À faire", 0, "V1", "#9C8B7A"),
    ]
    phase_ids = []
    for i, (name, s, e, status, prog, ver, color) in enumerate(phases):
        pid = conn.execute(
            text("""INSERT INTO phases
                    (project_id, name, start_date, end_date, status, progress,
                     version, color, order_index)
                    VALUES (:p, :n, :s, :e, :st, :pr, :v, :c, :o) RETURNING id"""),
            {"p": project_id, "n": name, "s": s, "e": e, "st": status,
             "pr": prog, "v": ver, "c": color, "o": i},
        ).scalar()
        phase_ids.append(pid)

    # --- Tâches ---
    tasks = [
        (0, "Recueil des besoins", d(-10), d(-5), "Terminé", 100, "Alice"),
        (0, "Rédaction cahier des charges", d(-5), d(0), "Terminé", 100, "Bob"),
        (1, "Architecture technique", d(0), d(7), "En cours", 70, "Claire"),
        (1, "Maquettes UI", d(2), d(12), "En cours", 50, "David"),
        (2, "Backend API", d(12), d(30), "En cours", 30, "Claire"),
        (2, "Interface utilisateur", d(15), d(35), "À faire", 0, "David"),
        (3, "Tests d'intégration", d(38), d(48), "À faire", 0, "Alice"),
        (4, "Mise en production", d(50), d(58), "À faire", 0, "Bob"),
    ]
    task_ids = []
    for (pi, name, s, e, status, prog, assignee) in tasks:
        tid = conn.execute(
            text("""INSERT INTO tasks
                    (phase_id, name, start_date, end_date, status, progress, assignee)
                    VALUES (:p, :n, :s, :e, :st, :pr, :a) RETURNING id"""),
            {"p": phase_ids[pi], "n": name, "s": s, "e": e, "st": status,
             "pr": prog, "a": assignee},
        ).scalar()
        task_ids.append(tid)

    # --- Dépendances (forment un chemin critique) ---
    deps = [(1, 0), (2, 1), (3, 1), (4, 2), (5, 3), (6, 4), (6, 5), (7, 6)]
    for (b, a) in deps:
        conn.execute(
            text("""INSERT INTO dependencies (task_id, depends_on_task_id)
                    VALUES (:b, :a) ON CONFLICT DO NOTHING"""),
            {"b": task_ids[b], "a": task_ids[a]},
        )

    # --- Livrables ---
    deliverables = [
        (0, "Cahier des charges", "Document", d(0), "Direction"),
        (1, "Dossier de conception", "Document", d(15), "Équipe technique"),
        (2, "Version bêta", "Code / Logiciel", d(40), "Client"),
        (3, "Rapport de tests", "Rapport", d(52), "Qualité"),
    ]
    for (pi, name, nature, due, recipient) in deliverables:
        conn.execute(
            text("""INSERT INTO deliverables (phase_id, name, nature, due_date, recipient)
                    VALUES (:p, :n, :na, :du, :r)"""),
            {"p": phase_ids[pi], "n": name, "na": nature, "du": due, "r": recipient},
        )

    # --- Réunion ---
    conn.execute(
        text("""INSERT INTO meetings
                (project_id, phase_id, date, time, participants, subject, report)
                VALUES (:p, :ph, :da, :ti, :pa, :su, :re)"""),
        {"p": project_id, "ph": phase_ids[1], "da": d(-2), "ti": "10:00",
         "pa": "Alice, Bob, Claire",
         "su": "Lancement de la phase de conception",
         "re": "Validation de l'architecture. Prochaines étapes : maquettes UI."},
    )


def backend_label():
    """Petit libellé indiquant le moteur actif (affiché dans l'UI)."""
    get_engine()
    return "PostgreSQL (persistant)" if IS_POSTGRES else "SQLite local"
