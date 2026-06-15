# Application de Gestion et de Phasage de Projet

## Application en ligne : [gestion-suivi-projet.streamlit.app](https://gestion-suivi-projet.streamlit.app)

Application web complète pour **piloter l'avancement d'un projet**, **anticiper les blocages**
(chemin critique) et **centraliser la communication** autour des livrables et des réunions.

Construite avec **Python, Streamlit, Plotly et SQLAlchemy** (SQLite en local, PostgreSQL/Supabase en ligne).

---

## Identification et confidentialité

Au lancement, l'application demande un **nom d'utilisateur** (conservé le temps de la
session). Chaque projet est rattaché à un utilisateur : on ne voit, ne charge et ne
modifie **que ses propres projets**. Le bouton « Changer d'utilisateur » permet de
revenir à l'écran de connexion. Saisir le même nom plus tard redonne accès aux mêmes
projets (les données sont conservées en base).

> Remarque : il s'agit d'un cloisonnement par nom d'utilisateur, sans mot de passe.
> C'est suffisant pour séparer les espaces de travail lors d'un partage de lien, mais
> ce n'est pas une authentification sécurisée.

---

## Fonctionnalités

### 1. Hiérarchie centrée sur les Phases
- Les **Phases** sont le coeur du planning : elles portent obligatoirement des **dates**
  (début et fin), un **statut**, une **version** (itération V1, V2, ...) et un **avancement**.
- Les **dépendances** se font **entre phases** (la phase B nécessite la phase A).
- Les **Tâches** sont de simples éléments cochables (to-do list) à l'intérieur d'une
  phase ; elles n'ont pas de dates. L'avancement d'une phase peut être déduit
  automatiquement du pourcentage de tâches cochées.

### 2. Tableau de bord et planification
- **Diagramme de Gantt interactif** (Plotly) construit à partir des phases et de leurs
  dépendances.
- **Chemin critique** (méthode CPM) : les phases dont tout retard décale la fin du
  projet sont bordées en rouge.
- **Avancement global et par phase**, et **camembert** de la part de chaque phase.
- **Santé du projet** : jauge comparant le pourcentage de phases terminées au temps
  écoulé entre le début et la deadline. Indique si le projet est « En avance »,
  « Dans les temps » ou « En retard ».
- **Vue Action Rapide** : phases actives cette semaine (et en retard) avec leurs tâches
  à cocher.

### 3. Livrables, réunions et communication
- **Livrables** : nature, date limite et destinataire, liés à une phase.
- **Réunions** : date, heure, participants, sujet ; compte rendu rédigeable dans
  l'application avec mise à jour de l'avancement de la phase concernée.
- **Récapitulatif automatique** : génère un texte (avancements et ordre du jour) prêt à
  copier/coller pour les parties prenantes.

### 4. Export et sauvegarde
- Export des données en **CSV** (par entité ou archive **ZIP**).
- Export du Gantt et du camembert en **PNG**, **PDF** et **HTML interactif**.

---

## Installation et lancement en local

```bash
# 1. (Recommandé) créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application
streamlit run app.py
```

L'application s'ouvre dans le navigateur (par défaut http://localhost:8501). En local,
sans configuration, elle utilise une base SQLite et crée un projet de démonstration
(accessible avec le nom d'utilisateur `demo`).

---

## Architecture du code

Le code est modulaire : chaque responsabilité est isolée dans son propre fichier.

```
App_Gestion_Projet/
├── app.py                    # Point d'entrée : identification, navigation
├── requirements.txt
├── README.md
├── .streamlit/
│   ├── config.toml           # Thème et configuration serveur
│   └── secrets.toml.example  # Modèle de secret DATABASE_URL (jamais versionné)
├── database/
│   ├── db.py                 # Moteur SQLAlchemy (SQLite/PostgreSQL), schéma, démo
│   └── models.py             # CRUD (projets, phases, tâches, dépendances, livrables, réunions)
├── modules/
│   ├── dashboard.py          # Tableau de bord (Gantt, camembert, santé du projet)
│   ├── gantt.py              # Gantt des phases + chemin critique
│   ├── todo.py               # Action Rapide (phases de la semaine)
│   ├── tasks.py              # Phases, tâches (to-do) et dépendances entre phases
│   ├── deliverables.py       # Livrables
│   ├── meetings.py           # Réunions, CR, récapitulatif automatique
│   ├── theme.py              # Habillage (couleurs, polices, bannières)
│   └── export.py             # Export CSV / PNG / PDF / HTML / ZIP
├── utils/
│   ├── critical_path.py      # Calcul du chemin critique (CPM)
│   └── helpers.py            # Avancements, dates, santé du projet, constantes
└── data/                     # Base SQLite locale (générée au lancement, non versionnée)
```

---

## À propos du chemin critique

Le chemin critique est calculé via la méthode CPM (`utils/critical_path.py`), appliquée
aux **phases** et à leurs dépendances :
1. tri topologique du graphe de dépendances ;
2. passe avant (dates au plus tôt) puis passe arrière (dates au plus tard) ;
3. une phase dont la marge totale est nulle est critique.

Aucune dépendance externe n'est requise pour ce calcul.

---

## Stockage des données (local et persistant en ligne)

L'application utilise deux moteurs de base de données, choisis automatiquement :

| Contexte | Moteur utilisé | Persistance |
|----------|----------------|-------------|
| En local (aucune configuration) | SQLite (`data/gestion_projet.db`) | fichier local |
| Avec un secret `DATABASE_URL` | PostgreSQL (ex. Supabase) | permanente |

Important pour Streamlit Community Cloud : le système de fichiers y est éphémère. Sans
base externe, un fichier SQLite serait effacé à chaque redémarrage du serveur. Il faut
donc brancher une base PostgreSQL gratuite (Supabase) ; voir la section suivante.

Le code détecte la présence du secret `DATABASE_URL` : s'il existe, il se connecte à
PostgreSQL ; sinon il retombe sur SQLite. Aucun changement de code n'est nécessaire pour
passer de l'un à l'autre.

---

## Déploiement persistant : Streamlit Cloud et Supabase (pas à pas)

### Étape 1 - Créer une base PostgreSQL gratuite sur Supabase
1. Créez un compte sur https://supabase.com (gratuit) puis cliquez sur New project.
2. Donnez un nom, choisissez une région proche, et définissez un Database Password
   (notez-le, il sert à l'étape 2).
3. Attendez environ une minute que la base soit prête.

### Étape 2 - Récupérer l'URL de connexion (Session pooler)
1. Dans le projet Supabase : bouton Connect (en haut) puis onglet Connection string.
2. Choisissez Session pooler (important : compatible avec Streamlit Cloud qui ne
   supporte que l'IPv4) et copiez l'URI. Elle ressemble à :
   ```
   postgresql://postgres.abcdefgh:[email protected]:5432/postgres
   ```
3. Remplacez `[YOUR-PASSWORD]` par le mot de passe défini à l'étape 1.

### Étape 3 - Déclarer le secret sur Streamlit Community Cloud
1. Déployez l'application depuis https://share.streamlit.io (connecté à ce dépôt GitHub,
   fichier principal `app.py`).
2. Ouvrez le menu de l'application (trois points) puis Settings puis Secrets
   (ou « Manage app » puis onglet Secrets).
3. Collez exactement cette ligne (avec votre URL), puis Save :
   ```toml
   DATABASE_URL = "postgresql://postgres.abcdefgh:[email protected]:5432/postgres"
   ```
4. L'application redémarre seule : elle crée les tables automatiquement et passe en mode
   persistant. La barre latérale affiche alors « Stockage : PostgreSQL (persistant) ».

Test en local de la base en ligne (facultatif) : copiez `.streamlit/secrets.toml.example`
en `.streamlit/secrets.toml` et collez-y la même ligne `DATABASE_URL`. Ce fichier est
ignoré par Git (jamais publié). Sans ce fichier, l'application reste sur SQLite local.

---

## Note sur l'export d'images

L'export PNG/PDF s'appuie sur Kaleido. La version `0.2.1` (épinglée dans
`requirements.txt`) embarque Chromium et fonctionne sans navigateur externe. Si l'export
image est indisponible, l'application propose automatiquement un export HTML interactif
en repli.
