# pip install playwright && playwright install chromium
# 1) Levanta el visor:  npm run dev   (o  npm run build && npx vite preview)
# 2) python scripts/captura_visor.py http://localhost:5173
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"

with sync_playwright() as p:
    b = p.chromium.launch()
    # 1600x900 a x2 => 3200x1800: nítido en un póster de 128 cm
    ctx = b.new_context(viewport={"width": 1600, "height": 900},
                        device_scale_factor=2)
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle")

    # Si hay botón "Cargar caso demo", púlsalo (ajusta el texto si es otro)
    demo = page.get_by_text("Cargar caso demo", exact=False)
    if demo.count():
        demo.first.click()
    page.wait_for_timeout(4000)  # tiles de OSM + render del mapa

    page.screenshot(path="figures/prototipo.png", full_page=False)
    b.close()
print("OK -> figures/prototipo.png")