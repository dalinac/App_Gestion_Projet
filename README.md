# Application de Gestion et de Phasage de Projet

## Application en ligne : [gestion-suivi-projet.streamlit.app](https://gestion-suivi-projet.streamlit.app)

Application web complète pour **piloter l'avancement d'un projet**, **anticiper les blocages**
(chemin critique) et **centraliser la communication** autour des livrables et des réunions.

Construite avec **Python, Streamlit et Plotly**. Les données sont stockées dans un
**document JSON** persisté sur un **gist GitHub** en ligne (fichier local en développement).

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
sans configuration, elle utilise un fichier JSON local (`data/gestion_projet.json`) et
crée un projet de démonstration (accessible avec le nom d'utilisateur `demo`).

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
│   └── secrets.toml.example  # Modèle de secret [github] (jamais versionné)
├── database/
│   ├── db.py                 # Stockage document JSON (gist GitHub / fichier local), démo
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
└── data/                     # Document JSON local (généré au lancement, non versionné)
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

L'application utilise deux backends de stockage, choisis automatiquement :

| Contexte | Backend utilisé | Persistance |
|----------|-----------------|-------------|
| En local (aucune configuration) | Fichier JSON (`data/gestion_projet.json`) | fichier local |
| Avec des secrets `[github]` (token + gist_id) | Document JSON dans un gist GitHub | permanente |

Important pour Streamlit Community Cloud : le système de fichiers y est éphémère. Sans
stockage externe, le fichier JSON local serait effacé à chaque redémarrage du serveur. Il
faut donc brancher un **gist GitHub** (gratuit) ; voir la section suivante.

Le code détecte la présence des secrets `[github]` : s'ils existent, il lit/écrit les
données dans le gist ; sinon il retombe sur le fichier JSON local. Aucun changement de
code n'est nécessaire pour passer de l'un à l'autre. Toutes les données (projets, phases,
tâches, dépendances, livrables, réunions) tiennent dans un unique document JSON.

---

## Déploiement persistant : Streamlit Cloud et GitHub Gist (pas à pas)

### Étape 1 - Créer un gist privé
1. Allez sur https://gist.github.com (connecté à votre compte GitHub).
2. Créez un fichier nommé **`gestion_projet.json`** dont le contenu est exactement : `{}`
3. Cliquez sur **Create secret gist** (gist privé, non listé publiquement).
4. L'identifiant du gist (`gist_id`) est la dernière partie de son URL :
   `https://gist.github.com/<votre-user>/<gist_id>`.

### Étape 2 - Créer un token GitHub avec la portée « gist »
- Token classique : https://github.com/settings/tokens > **Generate new token** >
  cochez la case **`gist`**. Copiez le token généré (`ghp_...`).
- Ou token « fine-grained » : autorisez l'accès **Gists** en lecture/écriture.

> Le token ne donne accès qu'aux gists ; il ne permet pas d'agir sur vos dépôts si vous
> ne cochez que la portée `gist`.

### Étape 3 - Déclarer les secrets sur Streamlit Community Cloud
1. Déployez l'application depuis https://share.streamlit.io (connecté à ce dépôt GitHub,
   fichier principal `app.py`).
2. Ouvrez le menu de l'application (trois points) puis Settings puis Secrets
   (ou « Manage app » puis onglet Secrets).
3. Collez ces lignes, puis Save :
   ```toml
   [github]
   token = "ghp_votre_token_personnel"
   gist_id = "abcdef0123456789abcdef0123456789"
   ```
4. L'application redémarre seule : elle écrit la démo dans le gist et passe en mode
   persistant. La barre latérale affiche alors « Stockage : GitHub Gist (persistant) ».

Test en local du stockage gist (facultatif) : copiez `.streamlit/secrets.toml.example`
en `.streamlit/secrets.toml` et renseignez `token` et `gist_id`. Ce fichier est ignoré
par Git (jamais publié). Sans ce fichier, l'application reste sur le fichier JSON local.

---

## Note sur l'export d'images

L'export PNG/PDF s'appuie sur Kaleido. La version `0.2.1` (épinglée dans
`requirements.txt`) embarque Chromium et fonctionne sans navigateur externe. Si l'export
image est indisponible, l'application propose automatiquement un export HTML interactif
en repli.
