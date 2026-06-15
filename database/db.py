"""
Couche d'accès à la base de données SQLite.

Ce module centralise :
  - la connexion à la base SQLite (stockage local) ;
  - la création / migration du schéma (tables) ;
  - l'insertion de données de démonstration au premier lancement.

Le choix de SQLite permet un stockage local sans serveur, idéal pour une
application de bureau légère basée sur Streamlit.
"""

import os
import sqlite3
from contextlib import contextmanager

# Emplacement du fichier base de données (dossier `data/` à la racine du projet)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "gestion_projet.db")


def get_connection():
    """Retourne une connexion SQLite avec accès par nom de colonne (Row)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # accès colonne via row["nom"]
    conn.execute("PRAGMA foreign_keys = ON")  # active les clés étrangères
    return conn


@contextmanager
def db_session():
    """
    Gestionnaire de contexte simplifiant l'usage de la base.

    Exemple :
        with db_session() as conn:
            conn.execute(...)

    Le commit est automatique en sortie, le rollback en cas d'exception,
    et la connexion est toujours fermée.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Définition du schéma
# ---------------------------------------------------------------------------

SCHEMA = """
-- Projets : conteneur racine
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    start_date  TEXT,                       -- format ISO 'YYYY-MM-DD'
    end_date    TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Phases d'un projet (regroupent les tâches, portent l'avancement et la version)
CREATE TABLE IF NOT EXISTS phases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    start_date  TEXT,
    end_date    TEXT,
    status      TEXT DEFAULT 'À faire',     -- À faire / En cours / Terminé / En attente
    progress    INTEGER DEFAULT 0,          -- pourcentage 0..100
    version     TEXT DEFAULT 'V1',          -- suivi d'itérations (V1, V2, ...)
    color       TEXT DEFAULT '#A9D6F5',
    order_index INTEGER DEFAULT 0,
    comments    TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Tâches rattachées à une phase
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id    INTEGER NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    start_date  TEXT,
    end_date    TEXT,
    status      TEXT DEFAULT 'À faire',
    progress    INTEGER DEFAULT 0,
    assignee    TEXT,                        -- personne responsable
    comments    TEXT,
    FOREIGN KEY (phase_id) REFERENCES phases(id) ON DELETE CASCADE
);

-- Dépendances entre tâches : `task_id` dépend de `depends_on_task_id`
-- (la tâche B nécessite la tâche A => task_id=B, depends_on_task_id=A)
CREATE TABLE IF NOT EXISTS dependencies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id             INTEGER NOT NULL,
    depends_on_task_id  INTEGER NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    UNIQUE (task_id, depends_on_task_id)
);

-- Livrables liés à une phase
CREATE TABLE IF NOT EXISTS deliverables (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id    INTEGER NOT NULL,
    name        TEXT NOT NULL,
    nature      TEXT,                        -- document, prototype, code, etc.
    due_date    TEXT,
    recipient   TEXT,                        -- destinataire (à qui le rendre)
    status      TEXT DEFAULT 'À faire',
    FOREIGN KEY (phase_id) REFERENCES phases(id) ON DELETE CASCADE
);

-- Réunions et comptes rendus
CREATE TABLE IF NOT EXISTS meetings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL,
    phase_id        INTEGER,                 -- phase concernée (optionnel)
    date            TEXT,
    time            TEXT,
    participants    TEXT,
    subject         TEXT,
    report          TEXT,                    -- compte rendu (CR)
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (phase_id) REFERENCES phases(id) ON DELETE SET NULL
);
"""


def init_db(seed: bool = True):
    """
    Crée le schéma s'il n'existe pas et insère un jeu de données de démonstration
    lors du tout premier lancement (si la base est vide et `seed=True`).
    """
    with db_session() as conn:
        conn.executescript(SCHEMA)
        # Insère les données de démo seulement si aucun projet n'existe encore
        if seed:
            count = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
            if count == 0:
                _seed_demo(conn)


def _seed_demo(conn):
    """Insère un projet exemple pour illustrer l'ensemble des fonctionnalités."""
    from datetime import date, timedelta

    today = date.today()

    def d(offset):
        return (today + timedelta(days=offset)).isoformat()

    # --- Projet ---
    cur = conn.execute(
        "INSERT INTO projects (name, description, start_date, end_date) VALUES (?,?,?,?)",
        (
            "Projet Démo — Application connectée",
            "Projet d'exemple illustrant le phasage, les livrables et les réunions.",
            d(-10),
            d(60),
        ),
    )
    project_id = cur.lastrowid

    # --- Phases (avec couleurs, versions et avancement) ---
    phases = [
        ("Cadrage & Besoins", d(-10), d(0), "Terminé", 100, "V1", "#A9D6F5"),
        ("Conception", d(0), d(15), "En cours", 60, "V1", "#FFD3B6"),
        ("Développement", d(12), d(40), "En cours", 25, "V2", "#A8E6CF"),
        ("Tests & Validation", d(38), d(52), "À faire", 0, "V1", "#F7B7D7"),
        ("Déploiement", d(50), d(60), "À faire", 0, "V1", "#C9A7F0"),
    ]
    phase_ids = []
    for i, (name, s, e, status, prog, ver, color) in enumerate(phases):
        c = conn.execute(
            """INSERT INTO phases
               (project_id, name, start_date, end_date, status, progress, version, color, order_index)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (project_id, name, s, e, status, prog, ver, color, i),
        )
        phase_ids.append(c.lastrowid)

    # --- Tâches par phase (avec dépendances pour le chemin critique) ---
    tasks = [
        # (phase_index, name, start, end, status, progress, assignee)
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
        c = conn.execute(
            """INSERT INTO tasks
               (phase_id, name, start_date, end_date, status, progress, assignee)
               VALUES (?,?,?,?,?,?,?)""",
            (phase_ids[pi], name, s, e, status, prog, assignee),
        )
        task_ids.append(c.lastrowid)

    # Dépendances : chaîne logique formant un chemin critique
    deps = [
        (1, 0),  # cahier des charges nécessite recueil des besoins
        (2, 1),  # architecture nécessite cahier des charges
        (3, 1),  # maquettes nécessitent cahier des charges
        (4, 2),  # backend nécessite architecture
        (5, 3),  # UI nécessite maquettes
        (6, 4),  # tests nécessitent backend
        (6, 5),  # tests nécessitent UI
        (7, 6),  # mise en prod nécessite tests
    ]
    for (b, a) in deps:
        conn.execute(
            "INSERT OR IGNORE INTO dependencies (task_id, depends_on_task_id) VALUES (?,?)",
            (task_ids[b], task_ids[a]),
        )

    # --- Livrables ---
    deliverables = [
        (0, "Cahier des charges", "Document PDF", d(0), "Direction"),
        (1, "Dossier de conception", "Document", d(15), "Équipe technique"),
        (2, "Version bêta", "Logiciel", d(40), "Client"),
        (3, "Rapport de tests", "Document", d(52), "Qualité"),
    ]
    for (pi, name, nature, due, recipient) in deliverables:
        conn.execute(
            """INSERT INTO deliverables (phase_id, name, nature, due_date, recipient)
               VALUES (?,?,?,?,?)""",
            (phase_ids[pi], name, nature, due, recipient),
        )

    # --- Réunions ---
    conn.execute(
        """INSERT INTO meetings (project_id, phase_id, date, time, participants, subject, report)
           VALUES (?,?,?,?,?,?,?)""",
        (
            project_id,
            phase_ids[1],
            d(-2),
            "10:00",
            "Alice, Bob, Claire",
            "Lancement de la phase de conception",
            "Validation de l'architecture. Prochaines étapes : maquettes UI.",
        ),
    )
