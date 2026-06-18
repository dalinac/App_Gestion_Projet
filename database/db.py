"""
Couche d'accès à la base de données (SQLAlchemy — double moteur).

Deux moteurs, sans changer le reste du code :

  * PostgreSQL (ex. Supabase) si une URL est fournie via le secret Streamlit
    ``DATABASE_URL`` (ou la variable d'environnement) -> stockage persistant,
    indispensable sur Streamlit Community Cloud (système de fichiers éphémère).
  * SQLite local (fichier ``data/gestion_projet.db``) sinon.

Modèle de données (hiérarchie centrée sur les Phases) :
  projects (rattachés à un username)
    -> phases (portent les dates et l'avancement ; dépendances entre phases)
       -> tasks (simples éléments textuels cochables, sans dates)
       -> deliverables
    -> meetings

Le SQL est portable entre les deux moteurs (paramètres nommés, ``RETURNING id``,
``ON CONFLICT DO NOTHING``, ``CURRENT_TIMESTAMP``).
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import URL

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "gestion_projet.db")

_ENGINE = None
IS_POSTGRES = False


def _structured_pg_url():
    """
    Construit une URL PostgreSQL à partir d'un secret structuré ``[postgres]``
    (champs séparés). Cette forme évite tout problème d'encodage de mot de passe
    contenant des caractères spéciaux (@ : / # ? ...).

    Format attendu dans les secrets Streamlit :
        [postgres]
        host = "aws-0-....pooler.supabase.com"
        port = 5432
        user = "postgres.xxxxxxxx"
        password = "votre_mot_de_passe"
        dbname = "postgres"
    """
    try:
        import streamlit as st
        if "postgres" not in st.secrets:
            return None
        s = st.secrets["postgres"]
        return URL.create(
            "postgresql+psycopg2",
            username=s.get("user", "postgres"),
            password=s.get("password"),
            host=s["host"],
            port=int(s.get("port", 5432)),
            database=s.get("dbname", "postgres"),
            query={"sslmode": s.get("sslmode", "require")},
        )
    except Exception:
        return None


def _database_url():
    """URL de connexion fournie sous forme de chaîne (env var puis st.secrets)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL")
        except Exception:
            url = None
    return url or None


def get_engine():
    """Crée (une seule fois) et retourne le moteur SQLAlchemy approprié."""
    global _ENGINE, IS_POSTGRES
    if _ENGINE is not None:
        return _ENGINE

    structured = _structured_pg_url()
    raw_url = _database_url()

    if structured is not None:
        # Secret structuré [postgres] : URL déjà construite proprement (ssl inclus)
        IS_POSTGRES = True
        _ENGINE = create_engine(structured, pool_pre_ping=True, pool_recycle=300)
    elif raw_url:
        # Chaîne DATABASE_URL : on normalise le préfixe et on impose le SSL
        url = raw_url
        if url.startswith("postgres://"):
            url = "postgresql+psycopg2://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        connect_args = {}
        if "sslmode" not in url:
            connect_args["sslmode"] = "require"
        IS_POSTGRES = True
        _ENGINE = create_engine(
            url, pool_pre_ping=True, pool_recycle=300, connect_args=connect_args,
        )
    else:
        os.makedirs(DATA_DIR, exist_ok=True)
        IS_POSTGRES = False
        _ENGINE = create_engine(
            f"sqlite:///{DB_PATH}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(_ENGINE, "connect")
        def _enable_sqlite_fk(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return _ENGINE


@contextmanager
def db_session():
    """Connexion transactionnelle (commit auto en sortie, rollback sur exception)."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def rows_to_dicts(result):
    return [dict(r) for r in result.mappings().all()]


def row_to_dict(result):
    row = result.mappings().first()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Schéma
# ---------------------------------------------------------------------------

def _pk():
    return "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _schema_statements():
    pk = _pk()
    return [
        f"""
        CREATE TABLE IF NOT EXISTS projects (
            id          {pk},
            username    TEXT,
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
        # Tâches : simples éléments textuels appartenant à une phase (sans dates)
        f"""
        CREATE TABLE IF NOT EXISTS tasks (
            id          {pk},
            phase_id    INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            status      TEXT DEFAULT 'À faire',
            order_index INTEGER DEFAULT 0
        )""",
        # Dépendances entre PHASES (la phase B nécessite la phase A)
        f"""
        CREATE TABLE IF NOT EXISTS phase_dependencies (
            id                   {pk},
            phase_id             INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
            depends_on_phase_id  INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
            UNIQUE (phase_id, depends_on_phase_id)
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


def _column_exists(conn, table, column):
    if IS_POSTGRES:
        res = conn.execute(
            text("""SELECT 1 FROM information_schema.columns
                    WHERE table_name=:t AND column_name=:c"""),
            {"t": table, "c": column},
        )
        return res.first() is not None
    res = conn.execute(text(f"PRAGMA table_info({table})"))
    return any(r["name"] == column for r in res.mappings().all())


def _migrate():
    """
    Migrations idempotentes pour les bases déjà créées avec une version
    antérieure du schéma (chaque opération dans sa propre transaction afin de
    ne pas invalider les suivantes en cas d'erreur).
    """
    # Ajout de la colonne username sur projects (anciennes bases)
    with db_session() as conn:
        if not _column_exists(conn, "projects", "username"):
            conn.execute(text("ALTER TABLE projects ADD COLUMN username TEXT"))
            # Rattache les anciens projets à un compte de démonstration
            conn.execute(text("UPDATE projects SET username='demo' WHERE username IS NULL"))


def init_db(seed: bool = True):
    """Crée le schéma, applique les migrations, et insère la démo si base vide."""
    get_engine()
    with db_session() as conn:
        for statement in _schema_statements():
            conn.execute(text(statement))
    _migrate()

    if seed:
        with db_session() as conn:
            count = conn.execute(text("SELECT COUNT(*) AS c FROM projects")).scalar()
            if count == 0:
                _seed_demo(conn)


def _seed_demo(conn):
    """Projet de démonstration (rattaché au username 'demo')."""
    from datetime import date, timedelta

    today = date.today()

    def d(offset):
        return (today + timedelta(days=offset)).isoformat()

    project_id = conn.execute(
        text("""INSERT INTO projects (username, name, description, start_date, end_date)
                VALUES (:u, :n, :de, :s, :e) RETURNING id"""),
        {"u": "demo", "n": "Projet Démo — Application connectée",
         "de": "Projet d'exemple illustrant le phasage, les livrables et les réunions.",
         "s": d(-10), "e": d(60)},
    ).scalar()

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

    # Dépendances entre phases (chaîne formant un chemin critique)
    phase_deps = [(1, 0), (2, 1), (3, 2), (4, 3)]
    for (b, a) in phase_deps:
        conn.execute(
            text("""INSERT INTO phase_dependencies (phase_id, depends_on_phase_id)
                    VALUES (:b, :a) ON CONFLICT DO NOTHING"""),
            {"b": phase_ids[b], "a": phase_ids[a]},
        )

    # Tâches (simples éléments cochables) par phase
    tasks = [
        (0, "Recueil des besoins", "Terminé"),
        (0, "Rédaction du cahier des charges", "Terminé"),
        (1, "Architecture technique", "Terminé"),
        (1, "Maquettes UI", "À faire"),
        (2, "Backend API", "À faire"),
        (2, "Interface utilisateur", "À faire"),
        (3, "Tests d'intégration", "À faire"),
        (4, "Mise en production", "À faire"),
    ]
    for i, (pi, name, status) in enumerate(tasks):
        conn.execute(
            text("""INSERT INTO tasks (phase_id, name, status, order_index)
                    VALUES (:p, :n, :st, :o)"""),
            {"p": phase_ids[pi], "n": name, "st": status, "o": i},
        )

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
    get_engine()
    return "PostgreSQL (persistant)" if IS_POSTGRES else "SQLite local"
