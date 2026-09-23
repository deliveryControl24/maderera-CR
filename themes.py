"""Paletas de tema para PINO SYSTEM."""

THEMES = {
    "claro": {
        "id": "claro",
        "label": "Claro (Bosque)",
        "root_bg": "#1B5E20",
        "panel_bg": "#0D3D0D",
        "title_fg": "#FFFFFF",
        "sub_fg": "#A5D6A7",
        "status_bg": "#0D3D0D",
        "status_fg": "#A5D6A7",
        "status_accent": "#66BB6A",
        "tc_bg": "#0D3D0D",
        "tc_fg": "#C8E6C9",
        "btn_face": "#F5F5F5",
        "btn_fg": "#212121",
        "heading_bg": "#1B5E20",
        "heading_fg": "#FFFFFF",
        "tree_bg": "#FFFFFF",
        "tree_fg": "#000000",
        "tree_field": "#FFFFFF",
        "select": "#2E7D32",
        "accent": "#FFD54F",
        "menu_bg": "#1B5E20",
        "menu_fg": "#FFFFFF",
    },
    "oscuro": {
        "id": "oscuro",
        "label": "Oscuro",
        "root_bg": "#121212",
        "panel_bg": "#000000",
        "title_fg": "#FFFFFF",
        "sub_fg": "#9E9E9E",
        "status_bg": "#000000",
        "status_fg": "#9E9E9E",
        "status_accent": "#81C784",
        "tc_bg": "#1E1E1E",
        "tc_fg": "#B0BEC5",
        "btn_face": "#2C2C2C",
        "btn_fg": "#EEEEEE",
        "heading_bg": "#212121",
        "heading_fg": "#FFFFFF",
        "tree_bg": "#1E1E1E",
        "tree_fg": "#EEEEEE",
        "tree_field": "#1E1E1E",
        "select": "#43A047",
        "accent": "#FFD54F",
        "menu_bg": "#121212",
        "menu_fg": "#FFFFFF",
    },
    "bosque": {
        "id": "bosque",
        "label": "Bosque",
        "root_bg": "#1B4332",
        "panel_bg": "#081C15",
        "title_fg": "#F1FAEE",
        "sub_fg": "#95D5B2",
        "status_bg": "#081C15",
        "status_fg": "#95D5B2",
        "status_accent": "#52B788",
        "tc_bg": "#081C15",
        "tc_fg": "#D8F3DC",
        "btn_face": "#F1FAEE",
        "btn_fg": "#081C15",
        "heading_bg": "#1B4332",
        "heading_fg": "#F1FAEE",
        "tree_bg": "#F1FAEE",
        "tree_fg": "#081C15",
        "tree_field": "#F1FAEE",
        "select": "#2D6A4F",
        "accent": "#FFB703",
        "menu_bg": "#1B4332",
        "menu_fg": "#F1FAEE",
    },
}

DEFAULT_THEME = "claro"


def get_theme(theme_id=None):
    if not theme_id:
        theme_id = DEFAULT_THEME
    return THEMES.get(theme_id, THEMES[DEFAULT_THEME])


def theme_choices():
    return [(k, v["label"]) for k, v in THEMES.items()]
