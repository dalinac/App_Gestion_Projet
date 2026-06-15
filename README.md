# Application de Gestion et de Phasage de Projet

### 🔗 Application en ligne : **[gestion-suivi-projet.streamlit.app](https://gestion-suivi-projet.streamlit.app)**

Application web complète pour **piloter l'avancement d'un projet**, **anticiper les blocages**
(chemin critique) et **centraliser la communication** autour des livrables et des réunions.

Construite avec **Python · Streamlit · Plotly · SQLAlchemy** (SQLite en local, **PostgreSQL/Supabase** en ligne).

---

## Fonctionnalités

### 1. Visualisation, planification & tableau de bord
- **Diagramme de Gantt interactif** (Plotly) affichant les tâches par phase et dans le temps.
- **Identification du chemin critique** (méthode CPM) : les tâches goulets d'étranglement
  sont **bordées en rouge** ; tout retard sur ces tâches décale la date de fin du projet.
- **Avancement global et par phase** (barres de progression + pourcentages).
- **Diagramme en camembert** de la part (en durée) de chaque phase sur le projet.
- **Vue « Action Rapide » (To-Do)** : extraction des tâches *à faire cette semaine* et
  des tâches *en retard*, avec complétion en un clic.

### 2. Gestion des tâches, itérations & livrables
- Phases et tâches avec **délais, statut, avancement, responsable et commentaires**.
- **Dépendances** entre tâches (« la tâche B nécessite la tâche A »).
- **Suivi des itérations / versions** : taguer une phase `V1`, `V2`, … (boucles de tests,
  prototypage, validations successives).
- **Module Livrables** : lier un livrable à une phase avec sa **nature**, sa **date limite**
  et son **destinataire**.

### 3. Réunions & communication
- Planification de **réunions** : date, heure, participants, sujet/phase concernée.
- **Compte rendu (CR)** rédigeable directement dans l'application, avec **mise à jour du
  taux d'avancement de la phase** depuis cette vue.
- **Génération automatique** d'un récapitulatif textuel (avancements + ordre du jour),
  prêt à copier/coller pour les parties prenantes.

### 4. Export & sauvegarde
- Export des données en **CSV** (par entité ou archive **ZIP** complète).
- Export du Gantt et des vues analytiques en **PNG**, **PDF** et **HTML interactif**.

---

## Installation & lancement

```bash
# 1. (Recommandé) créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application
streamlit run app.py
```

L'application s'ouvre dans le navigateur (par défaut http://localhost:8501).
Au premier lancement, un **projet de démonstration** est créé automatiquement
pour illustrer toutes les fonctionnalités.

---

## Architecture du code

Le code est **modulaire** : chaque responsabilité est isolée dans son propre fichier.

```
App_Gestion_Projet/
├── app.py                    # Point d'entrée Streamlit + navigation
├── requirements.txt
├── README.md
├── .streamlit/config.toml    # Thème & configuration serveur
├── database/
│   ├── db.py                 # Moteur SQLAlchemy (SQLite local / PostgreSQL), schéma, démo
│   └── models.py             # CRUD (projets, phases, tâches, livrables, réunions)
├── modules/
│   ├── dashboard.py          # Tableau de bord (Gantt, camembert, KPI)
│   ├── gantt.py              # Construction des figures Gantt + chemin critique
│   ├── todo.py               # Vue Action Rapide (semaine)
│   ├── tasks.py              # Gestion phases / tâches / dépendances / versions
│   ├── deliverables.py       # Module Livrables
│   ├── meetings.py           # Réunions, CR, récapitulatif automatique
│   ├── theme.py              # Habillage (couleurs, polices, bannières)
│   └── export.py             # Export CSV / PNG / PDF / HTML / ZIP
├── utils/
│   ├── critical_path.py      # Calcul du chemin critique (CPM)
│   └── helpers.py            # Avancements, dates, constantes
└── data/                     # Base SQLite (générée au lancement, non versionnée)
```

---

## À propos du chemin critique

Le chemin critique est calculé via la **méthode CPM** (`utils/critical_path.py`) :
1. **tri topologique** du graphe de dépendances ;
2. **passe avant** (dates au plus tôt) puis **passe arrière** (dates au plus tard) ;
3. une tâche dont la **marge totale est nulle** est *critique*.

Aucune dépendance externe n'est requise pour ce calcul.

---

## Stockage des données (local & persistant en ligne)

L'application utilise **deux moteurs de base de données**, choisis automatiquement :

| Contexte | Moteur utilisé | Persistance |
|----------|----------------|-------------|
| En local (aucune configuration) | **SQLite** (`data/gestion_projet.db`) | fichier local |
| Avec un secret `DATABASE_URL` | **PostgreSQL** (ex. Supabase) | **permanente** ✅ |

> ⚠️ **Important pour Streamlit Community Cloud** : le système de fichiers y est
> *éphémère*. Sans base externe, un fichier SQLite serait **effacé à chaque
> redémarrage** du serveur. Il faut donc brancher une base PostgreSQL gratuite
> (Supabase) — voir la section suivante.

Le code détecte la présence du secret `DATABASE_URL` : s'il existe, il se
connecte à PostgreSQL ; sinon il retombe sur SQLite. Aucun changement de code
n'est nécessaire pour passer de l'un à l'autre.

---

## 🚀 Déploiement persistant : Streamlit Cloud + Supabase (pas à pas)

### Étape 1 — Créer une base PostgreSQL gratuite sur Supabase
1. Créez un compte sur **https://supabase.com** (gratuit) puis cliquez sur **New project**.
2. Donnez un **nom**, choisissez une **région** proche, et définissez un
   **Database Password** (notez-le, il sert à l'étape 2).
3. Attendez ~1 minute que la base soit prête.

### Étape 2 — Récupérer l'URL de connexion (« Session pooler »)
1. Dans le projet Supabase : bouton **Connect** (en haut) → onglet **Connection string**.
2. Choisissez **Session pooler** (important : compatible avec Streamlit Cloud
   qui ne supporte que l'IPv4) et copiez l'URI. Elle ressemble à :
   ```
   postgresql://postgres.abcdefgh:[email protected]:5432/postgres
   ```
3. Remplacez `[YOUR-PASSWORD]` par le mot de passe défini à l'étape 1.

### Étape 3 — Déclarer le secret sur Streamlit Community Cloud
1. Déployez l'app depuis **https://share.streamlit.io** (connecté à ce dépôt GitHub,
   fichier principal `app.py`).
2. Ouvrez **⋮ → Settings → Secrets** (ou « Manage app » → onglet **Secrets**).
3. Collez **exactement** cette ligne (avec votre URL), puis **Save** :
   ```toml
   DATABASE_URL = "postgresql://postgres.abcdefgh:[email protected]:5432/postgres"
   ```
4. L'application redémarre seule : elle crée les tables automatiquement et passe
   en mode **persistant**. La barre latérale affiche alors « Stockage :
   PostgreSQL (persistant) ».

> 💡 **Test en local de la base en ligne** (facultatif) : copiez
> `.streamlit/secrets.toml.example` en `.streamlit/secrets.toml` et collez-y la
> même ligne `DATABASE_URL`. Ce fichier est ignoré par Git (jamais publié).
> Sans ce fichier, l'app reste sur SQLite local.

---

## Note sur l'export d'images

L'export PNG/PDF s'appuie sur **Kaleido**. La version `0.2.1` (épinglée dans
`requirements.txt`) embarque Chromium et fonctionne sans navigateur externe.
Si l'export image est indisponible, l'application propose automatiquement un
export **HTML interactif** en repli.
