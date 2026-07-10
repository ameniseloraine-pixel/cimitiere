
# Largeur (en pixels) sous laquelle on considère l'écran comme "mobile"
# et on bascule vers un layout empilé / cartes / NavigationBar en bas.
SEUIL_MOBILE = 700


def est_mobile(page) -> bool:
    """Retourne True si la largeur actuelle de la page est en dessous du seuil mobile.

    page.width peut être None très brièvement avant le premier rendu ;
    dans ce cas on considère par défaut qu'on n'est PAS en mobile pour
    éviter un flash de layout mobile sur desktop au premier chargement.
    """
    return page.width is not None and page.width < SEUIL_MOBILE