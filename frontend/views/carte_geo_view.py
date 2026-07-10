import flet as ft
import requests
import os

API_BASE = "http://127.0.0.1:8000/api"  # adapte si besoin

def carte_geo_view(page: ft.Page, token: str):
    """
    token : le JWT récupéré après le login (voir note plus bas)
    """
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(f"{API_BASE}/carte/caveaux", headers=headers)
        response.raise_for_status()
        caveaux = response.json()
    except Exception as e:
        print(f"Erreur chargement caveaux: {e}")
        caveaux = []

    # Génère les marqueurs Leaflet colorés selon le statut
    markers_js = ""
    for c in caveaux:
        lat, lng = c.get("latitude"), c.get("longitude")
        if lat is None or lng is None:
            continue
        couleur = c.get("couleur", "#3388ff")
        popup = f"{c.get('reference')} — {c.get('statut')}"
        markers_js += f"""
        L.circleMarker([{lat}, {lng}], {{
            radius: 8, color: "{couleur}", fillColor: "{couleur}", fillOpacity: 0.9
        }}).addTo(map).bindPopup("{popup}");
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
      <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
      <style>#map {{ height: 100vh; width: 100%; }} body {{ margin: 0; }}</style>
    </head>
    <body>
      <div id="map"></div>
      <script>
        var map = L.map('map').setView([-4.7761, 11.8636], 15);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
        {markers_js}
      </script>
    </body>
    </html>
    """

    assets_dir = "frontend/assets"
    os.makedirs(assets_dir, exist_ok=True)
    with open(f"{assets_dir}/carte.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    return ft.View(
        "/carte",
        [
            ft.AppBar(title=ft.Text("Carte des caveaux")),
            ft.WebView(url="/carte.html", expand=True),
        ],
    )