"""
Habillage visuel de l'application (thème élégant et chaleureux).

Palette de tons neutres et naturels : crème, beige, taupe, ocre doux et brun.
Tout le style est centralisé ici pour faciliter la personnalisation des couleurs
à un seul endroit.

Note de stabilité : le contour des champs de saisie est dessiné avec
`box-shadow: inset` plutôt qu'avec `border`. En effet, `border` modifie la
taille mesurée des zones de texte auto-redimensionnables, ce qui peut déclencher
une boucle ResizeObserver (erreur React « Maximum update depth exceeded »).
"""

import streamlit as st

# Palette élégante partagée (tons neutres et naturels)
PALETTE = {
    "creme": "#FBF8F2",
    "sable": "#EFE6D6",
    "beige": "#E0D4BF",
    "taupe": "#B5A081",
    "ocre": "#C9A66B",
    "caramel": "#B49063",
    "brun": "#5C4A38",
    "espresso": "#4A3D2E",
    "carte": "#FFFDF9",
}

# Feuille de style. Polices « Playfair Display » (titres, élégante et féminine)
# et « Mulish » (texte courant, sobre et lisible) chargées depuis Google Fonts.
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Mulish:wght@400;500;600;700&display=swap');

/* ---- Fond général : dégradé crème très doux ---- */
.stApp {
    background: linear-gradient(135deg, #FBF8F2 0%, #F5EEE2 60%, #F1E9DA 100%);
    background-attachment: fixed;
}

/* ---- Polices ---- */
html, body, [class*="css"], .stMarkdown, p, label, input, textarea, select, button {
    font-family: 'Mulish', 'Segoe UI', sans-serif !important;
}
h1, h2, h3, h4, h5,
[data-testid="stHeader"] h1, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Playfair Display', Georgia, serif !important;
    color: #5C4A38 !important;
    letter-spacing: .2px;
}

/* ---- Barre latérale : beige chaleureux ---- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F3EBDC 0%, #EFE6D4 100%);
    border-right: 1px solid #E7DCC9;
}
section[data-testid="stSidebar"] > div {
    padding-top: 1rem;
}

/* ---- Cartes d'indicateurs (metrics) ---- */
[data-testid="stMetric"] {
    background: #FFFDF9;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 4px 14px rgba(150, 125, 90, 0.12);
    border: 1px solid #ECE2D0;
}
[data-testid="stMetricValue"] {
    color: #A07A4B !important;
    font-family: 'Playfair Display', serif !important;
}

/* ---- Boutons : caramel sobre, légèrement arrondis ---- */
.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button {
    background: #B49063;
    color: #FFFBF4 !important;
    border: 0;
    border-radius: 10px;
    padding: 0.5rem 1.1rem;
    font-weight: 600;
    letter-spacing: .2px;
    box-shadow: 0 3px 9px rgba(150, 120, 80, 0.22);
    transition: background .15s ease, transform .12s ease;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
.stFormSubmitButton > button:hover {
    background: #9E7D52;
    transform: translateY(-1px);
    color: #FFFBF4 !important;
}

/* ---- Champs de saisie (contour via box-shadow : voir note du module) ---- */
.stTextInput input, .stTextArea textarea, .stDateInput input,
.stNumberInput input, .stTimeInput input {
    border-radius: 10px !important;
    box-shadow: inset 0 0 0 1.5px #E2D7C2 !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    box-shadow: inset 0 0 0 1.5px #C9A66B !important;
}

/* ---- Expanders : cartes ivoire discrètes ---- */
[data-testid="stExpander"] {
    border-radius: 12px !important;
    border: 1px solid #ECE2D0 !important;
    background: #FFFDFA;
    box-shadow: 0 3px 10px rgba(150, 125, 90, 0.08);
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    font-weight: 600;
    color: #6B5844;
}

/* ---- Onglets ---- */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
}
.stTabs [data-baseweb="tab"] {
    background: #F1E9DB;
    border-radius: 10px 10px 0 0;
    padding: 8px 16px;
    color: #80694F;
}
.stTabs [aria-selected="true"] {
    background: #CDBA99;
    color: #4A3D2E !important;
}

/* ---- Barre de progression (tons ocre/taupe) ---- */
[data-testid="stProgress"] > div > div > div > div {
    background: linear-gradient(90deg, #C9A66B, #B5A081);
    border-radius: 8px;
}
[data-testid="stProgress"] > div > div > div {
    background-color: #ECE4D4;
    border-radius: 8px;
}

/* ---- Tableaux (dataframe) ---- */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #ECE2D0;
}

/* ---- Messages (info/success/warning/error) ---- */
[data-testid="stAlert"], .stAlert {
    border-radius: 12px !important;
}

/* ---- Sliders ---- */
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background: #B49063 !important;
}

/* ---- Séparateurs ---- */
hr { border-color: #E7DCC9 !important; }

/* ---- Radio de navigation : pastilles discrètes ---- */
section[data-testid="stSidebar"] .stRadio label {
    background: #FFFFFF99;
    border-radius: 10px;
    padding: 6px 10px;
    margin-bottom: 4px;
    transition: background .15s ease;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: #EFE3CE;
}
</style>
"""


# Séquence de couleurs pour les graphiques : tons naturels et harmonieux
PASTEL_SEQUENCE = [
    "#C9A66B", "#B5A081", "#A9B388", "#CBA890",
    "#9C8B7A", "#D8C3A5", "#B08968", "#C4B7A6",
]


def inject_css():
    """Injecte la feuille de style dans la page courante."""
    st.markdown(_CSS, unsafe_allow_html=True)


def style_fig(fig):
    """
    Applique un habillage cohérent à une figure Plotly : fond transparent
    (pour épouser le dégradé crème de la page), police sobre et couleur de texte
    chaleureuse. Retourne la figure pour permettre le chaînage.
    """
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Mulish, sans-serif", color="#5C4A38"),
        title_font=dict(family="Playfair Display, serif", color="#5C4A38"),
        legend=dict(bgcolor="rgba(255,253,249,0.6)"),
    )
    return fig


def banner(title, subtitle=""):
    """
    Affiche une bannière d'entête élégante en dégradé de tons sable/taupe.
    Utilisée en haut des pages à la place d'un simple `st.header`.
    """
    sub = (
        f"<div style='font-size:0.95rem;color:#5C4A38;opacity:.8;margin-top:4px;'>{subtitle}</div>"
        if subtitle else ""
    )
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #D8C8AE 0%, #C7B391 100%);
            padding: 22px 28px;
            border-radius: 16px;
            box-shadow: 0 6px 18px rgba(150, 125, 90, 0.18);
            border: 1px solid #D5C4A4;
            margin-bottom: 18px;">
            <div style="
                font-family:'Playfair Display', Georgia, serif;
                font-size: 1.7rem;
                font-weight: 700;
                color: #4A3D2E;">
                {title}
            </div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )
