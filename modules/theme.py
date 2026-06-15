"""
Habillage visuel de l'application (thème pastel et ludique).

Ce module centralise l'injection de CSS personnalisé : polices arrondies,
fonds dégradés pastel, coins arrondis, ombres douces. Tout est regroupé ici
pour garder les modules fonctionnels propres et faciliter la personnalisation
des couleurs à un seul endroit.
"""

import streamlit as st

# Palette pastel partagée (réutilisée pour les graphiques si besoin)
PALETTE = {
    "rose": "#F7B7D7",
    "lavande": "#C9A7F0",
    "menthe": "#A8E6CF",
    "peche": "#FFD3B6",
    "ciel": "#A9D6F5",
    "texte": "#6B5876",
    "fond": "#FFF6FB",
    "carte": "#FFFFFF",
}

# Feuille de style complète. Les polices « Baloo 2 » (titres, très rondes) et
# « Quicksand » (texte) sont chargées depuis Google Fonts.
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700&family=Quicksand:wght@400;500;600;700&display=swap');

/* ---- Fond général en dégradé pastel ---- */
.stApp {
    background: linear-gradient(135deg, #FFF1F8 0%, #F4ECFF 55%, #EAF6FF 100%);
    background-attachment: fixed;
}

/* ---- Polices ---- */
html, body, [class*="css"], .stMarkdown, p, label, input, textarea, select, button {
    font-family: 'Quicksand', 'Segoe UI', sans-serif !important;
}
h1, h2, h3, h4, h5,
[data-testid="stHeader"] h1, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Baloo 2', 'Quicksand', sans-serif !important;
    color: #8E5FA8 !important;
    letter-spacing: .3px;
}

/* ---- Barre latérale : carte lavande arrondie ---- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F6ECFF 0%, #FCE9F3 100%);
    border-right: 0;
}
section[data-testid="stSidebar"] > div {
    padding-top: 1rem;
}

/* ---- Cartes d'indicateurs (metrics) ---- */
[data-testid="stMetric"] {
    background: #FFFFFFCC;
    border-radius: 20px;
    padding: 16px 18px;
    box-shadow: 0 6px 18px rgba(180, 140, 200, 0.18);
    border: 1px solid #F2E2F4;
}
[data-testid="stMetricValue"] {
    color: #B5519A !important;
    font-family: 'Baloo 2', sans-serif !important;
}

/* ---- Boutons : dégradé pastel, bien arrondis ---- */
.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button {
    background: linear-gradient(135deg, #F8B4D9 0%, #C9A7F0 100%);
    color: #5A3D6B !important;
    border: 0;
    border-radius: 16px;
    padding: 0.5rem 1.1rem;
    font-weight: 600;
    box-shadow: 0 4px 12px rgba(201, 167, 240, 0.35);
    transition: transform .12s ease, box-shadow .12s ease;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
.stFormSubmitButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 7px 18px rgba(201, 167, 240, 0.5);
    color: #4A2F5C !important;
}

/* ---- Champs de saisie arrondis ----
   On utilise box-shadow (inset) plutôt que `border` pour dessiner le contour :
   `border` modifierait la taille mesurée des text_area auto-redimensionnables,
   ce qui déclenche une boucle ResizeObserver (erreur React « Maximum update
   depth exceeded »). box-shadow n'affecte pas la mise en page : pas de boucle. */
.stTextInput input, .stTextArea textarea, .stDateInput input,
.stNumberInput input, .stTimeInput input {
    border-radius: 14px !important;
    box-shadow: inset 0 0 0 1.5px #ECD9F2 !important;
}

/* ---- Expanders : cartes blanches arrondies ---- */
[data-testid="stExpander"] {
    border-radius: 18px !important;
    border: 1px solid #F0E2F6 !important;
    background: #FFFFFFCC;
    box-shadow: 0 4px 14px rgba(190, 160, 210, 0.14);
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    font-weight: 600;
    color: #7E5A93;
}

/* ---- Onglets ---- */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    background: #FBEFF8;
    border-radius: 14px 14px 0 0;
    padding: 8px 16px;
    color: #8A6AA0;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #F8B4D9, #C9A7F0);
    color: #4A2F5C !important;
}

/* ---- Barre de progression pastel ---- */
[data-testid="stProgress"] > div > div > div > div {
    background: linear-gradient(90deg, #F8B4D9, #C9A7F0, #A9D6F5);
    border-radius: 10px;
}
[data-testid="stProgress"] > div > div > div {
    background-color: #F1E5F7;
    border-radius: 10px;
}

/* ---- Tableaux (dataframe) ---- */
[data-testid="stDataFrame"] {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid #F0E2F6;
}

/* ---- Messages (info/success/warning/error) arrondis ---- */
[data-testid="stAlert"], .stAlert {
    border-radius: 16px !important;
}

/* ---- Blocs de code (récapitulatif) ---- */
.stCode, pre {
    border-radius: 16px !important;
    background: #FBF1FA !important;
}

/* ---- Sliders aux teintes pastel ---- */
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background: #E58BBB !important;
}

/* ---- Séparateurs plus doux ---- */
hr { border-color: #EFDDF0 !important; }

/* ---- Radio de navigation : pastilles arrondies ---- */
section[data-testid="stSidebar"] .stRadio label {
    background: #FFFFFFB3;
    border-radius: 12px;
    padding: 6px 10px;
    margin-bottom: 4px;
    transition: background .15s ease;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: #F8DCEF;
}
</style>
"""


# Séquence de couleurs pastel pour les graphiques (camemberts, etc.)
PASTEL_SEQUENCE = [
    "#F7B7D7", "#C9A7F0", "#A8E6CF", "#FFD3B6",
    "#A9D6F5", "#FFC8DD", "#BDB2FF", "#CAFFBF",
]


def inject_css():
    """Injecte la feuille de style pastel dans la page courante."""
    st.markdown(_CSS, unsafe_allow_html=True)


def style_fig(fig):
    """
    Applique un habillage pastel cohérent à une figure Plotly :
    fond transparent (pour épouser le dégradé de la page), police arrondie
    et couleur de texte douce. Retourne la figure pour permettre le chaînage.
    """
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Quicksand, sans-serif", color="#6B5876"),
        title_font=dict(family="Baloo 2, sans-serif", color="#8E5FA8"),
        legend=dict(bgcolor="rgba(255,255,255,0.5)"),
    )
    return fig


def banner(title, subtitle=""):
    """
    Affiche une jolie bannière d'entête arrondie en dégradé pastel.

    Utilisée en haut des pages pour remplacer un simple `st.header`.
    """
    sub = f"<div style='font-size:0.95rem;opacity:.85;margin-top:4px;'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #F8B4D9 0%, #C9A7F0 60%, #A9D6F5 100%);
            padding: 22px 26px;
            border-radius: 22px;
            box-shadow: 0 8px 22px rgba(201, 167, 240, 0.30);
            margin-bottom: 18px;">
            <div style="
                font-family:'Baloo 2', sans-serif;
                font-size: 1.7rem;
                font-weight: 700;
                color: #ffffff;
                text-shadow: 0 2px 6px rgba(140, 90, 150, 0.25);">
                {title}
            </div>
            <div style="color:#fff;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
