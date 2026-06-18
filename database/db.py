"""
Couche de stockage des données (document JSON, sans base SQL).

Deux backends, choisis automatiquement :

  * GitHub Gist (persistant) si un secret ``[github]`` (token + gist_id) est
    fourni. Les données sont stockées dans un gist privé au format JSON.
    => convient à Streamlit Community Cloud, dont le disque est éphémère.

  * Fichier JSON local (``data/gestion_projet.json``) sinon.
    => pratique pour développer en local sans aucune configuration.

Le module expose un petit nombre de primitives utilisées par ``models.py`` :
``get_data()`` (lecture), ``transaction()`` (mutation + sauvegarde) et
``next_id()`` (identifiants auto-incrémentés). Aucune dépendance SQL ; seule la
bibliothèque ``requests`` (déjà fournie avec Streamlit) sert pour le gist.
"""

import os
import json
import threading
from contextlib import contextmanager

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
JSON_PATH = os.path.join(DATA_DIR, "gestion_projet.json")

# Nom du fichier à l'intérieur du gist
GIST_FILE = "gestion_projet.json"
GITHUB_API = "https://api.github.com"

# Tables du document
TABLES = ["projects", "phases", "tasks", "phase_dependencies",
          "deliverables", "meetings"]

_DATA = None                 # document en mémoire (partagé par le process)
_LOADED_GIST_FILE = None     # nom réel du fichier chargé depuis le gist
_LOCK = threading.RLock()    # sérialise les mutations (Streamlit est multi-thread)


def _empty_document():
    doc = {t: [] for t in TABLES}
    doc["_seq"] = 0
    return doc


# ---------------------------------------------------------------------------
# Configuration du backend
# ---------------------------------------------------------------------------

def _gist_config():
    """Retourne (token, gist_id) si un stockage GitHub Gist est configuré."""
    token = os.environ.get("GITHUB_TOKEN")
    gist_id = os.environ.get("GIST_ID")
    if not (token and gist_id):
        try:
            import streamlit as st
            if "github" in st.secrets:
                gh = st.secrets["github"]
                token = token or gh.get("token")
                gist_id = gist_id or gh.get("gist_id")
        except Exception:
            pass
    if token and gist_id:
        return token, gist_id
    return None


def is_persistent():
    """Vrai si le stockage actif est persistant (GitHub Gist)."""
    return _gist_config() is not None


def backend_label():
    return "GitHub Gist (persistant)" if is_persistent() else "Fichier local (non persistant)"


# ---------------------------------------------------------------------------
# Lecture / écriture du document
# ---------------------------------------------------------------------------

def _gist_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _load_from_gist(token, gist_id):
    """Télécharge le document depuis le gist. Retourne un dict (vide si absent)."""
    global _LOADED_GIST_FILE
    resp = requests.get(f"{GITHUB_API}/gists/{gist_id}",
                        headers=_gist_headers(token), timeout=20)
    resp.raise_for_status()
    files = resp.json().get("files") or {}
    # On privilégie notre fichier ; sinon on prend le premier fichier du gist
    f = files.get(GIST_FILE) or (next(iter(files.values())) if files else None)
    if not f:
        _LOADED_GIST_FILE = GIST_FILE
        return _empty_document()
    _LOADED_GIST_FILE = f.get("filename", GIST_FILE)
    content = f.get("content") or ""
    if f.get("truncated") and f.get("raw_url"):
        content = requests.get(f["raw_url"], timeout=20).text
    content = content.strip()
    if not content:
        return _empty_document()
    return json.loads(content)


def _save_to_gist(token, gist_id, data):
    """Envoie le document vers le gist."""
    filename = _LOADED_GIST_FILE or GIST_FILE
    payload = {"files": {filename: {"content": json.dumps(data, ensure_ascii=False, indent=2)}}}
    resp = requests.patch(f"{GITHUB_API}/gists/{gist_id}",
                          headers=_gist_headers(token), json=payload, timeout=20)
    resp.raise_for_status()


def _load_from_file():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding="utf-8") as fh:
            content = fh.read().strip()
        if content:
            return json.loads(content)
    return _empty_document()


def _save_to_file(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _normalize(data):
    """Garantit la présence de toutes les tables et recalcule le compteur d'id."""
    for t in TABLES:
        data.setdefault(t, [])
    max_id = 0
    for t in TABLES:
        for row in data[t]:
            max_id = max(max_id, int(row.get("id", 0)))
    data["_seq"] = max(int(data.get("_seq", 0)), max_id)
    return data


def _load():
    cfg = _gist_config()
    data = _load_from_gist(*cfg) if cfg else _load_from_file()
    return _normalize(data)


def _persist(data):
    cfg = _gist_config()
    if cfg:
        _save_to_gist(*cfg, data)
    else:
        _save_to_file(data)


def get_data():
    """Retourne le document en mémoire (chargé paresseusement une fois)."""
    global _DATA
    if _DATA is None:
        with _LOCK:
            if _DATA is None:
                _DATA = _load()
    return _DATA


def commit():
    """Sauvegarde le document courant vers le backend actif."""
    _persist(get_data())


def next_id():
    """Identifiant entier unique, croissant, à travers toutes les tables."""
    data = get_data()
    data["_seq"] = int(data.get("_seq", 0)) + 1
    return data["_seq"]


@contextmanager
def transaction():
    """
    Contexte de mutation : fournit le document, puis sauvegarde automatiquement
    en sortie (et garde le verrou pour sérialiser les écritures concurrentes).
    """
    with _LOCK:
        data = get_data()
        yield data
        commit()


# ---------------------------------------------------------------------------
# Initialisation / démonstration
# ---------------------------------------------------------------------------

def init_db(seed: bool = True):
    """Charge le document et insère la démo si la base est vide."""
    data = get_data()
    if seed and not data["projects"]:
        with transaction() as d:
            _seed_demo(d)


def _seed_demo(data):
    """Projet de démonstration (rattaché au username 'demo')."""
    from datetime import date, timedelta

    today = date.today()

    def d(offset):
        return (today + timedelta(days=offset)).isoformat()

    project_id = next_id()
    data["projects"].append({
        "id": project_id, "username": "demo",
        "name": "Projet Démo — Application connectée",
        "description": "Projet d'exemple illustrant le phasage, les livrables et les réunions.",
        "start_date": d(-10), "end_date": d(60),
    })

    phases = [
        ("Cadrage & Besoins", d(-10), d(0), "Terminé", 100, "V1", "#C9A66B"),
        ("Conception", d(0), d(15), "En cours", 60, "V1", "#CBA890"),
        ("Développement", d(12), d(40), "En cours", 25, "V2", "#A9B388"),
        ("Tests & Validation", d(38), d(52), "À faire", 0, "V1", "#B5A081"),
        ("Déploiement", d(50), d(60), "À faire", 0, "V1", "#9C8B7A"),
    ]
    phase_ids = []
    for i, (name, s, e, status, prog, ver, color) in enumerate(phases):
        pid = next_id()
        data["phases"].append({
            "id": pid, "project_id": project_id, "name": name, "description": "",
            "start_date": s, "end_date": e, "status": status, "progress": prog,
            "version": ver, "color": color, "order_index": i, "comments": "",
        })
        phase_ids.append(pid)

    for (b, a) in [(1, 0), (2, 1), (3, 2), (4, 3)]:
        data["phase_dependencies"].append({
            "id": next_id(), "phase_id": phase_ids[b], "depends_on_phase_id": phase_ids[a],
        })

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
        data["tasks"].append({
            "id": next_id(), "phase_id": phase_ids[pi], "name": name,
            "status": status, "order_index": i,
        })

    deliverables = [
        (0, "Cahier des charges", "Document", d(0), "Direction"),
        (1, "Dossier de conception", "Document", d(15), "Équipe technique"),
        (2, "Version bêta", "Code / Logiciel", d(40), "Client"),
        (3, "Rapport de tests", "Rapport", d(52), "Qualité"),
    ]
    for (pi, name, nature, due, recipient) in deliverables:
        data["deliverables"].append({
            "id": next_id(), "phase_id": phase_ids[pi], "name": name, "nature": nature,
            "due_date": due, "recipient": recipient, "status": "À faire",
        })

    data["meetings"].append({
        "id": next_id(), "project_id": project_id, "phase_id": phase_ids[1],
        "date": d(-2), "time": "10:00", "participants": "Alice, Bob, Claire",
        "subject": "Lancement de la phase de conception",
        "report": "Validation de l'architecture. Prochaines étapes : maquettes UI.",
    })
