# Dashboard de votaciones San Salvador Sur (Python)

Dashboard web hecho con [Dash](https://dash.plotly.com/) y Plotly con los resultados
de las elecciones municipales 2021 y 2024 de San Salvador Sur.

## Cómo ejecutarlo

```bash
cd dashboard_python
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Luego abre <http://127.0.0.1:8050> en el navegador.

## Archivos

| Archivo | Qué contiene |
|---|---|
| `app.py` | La aplicación: diseño de la página, gráficos y filtros |
| `datos.py` | Lectura del Excel con pandas, sumas por distrito y validación de actas |
| `datos/APP_POLITICA_SSSUR.xlsx` | Datos de origen (exportados de la app APP POLÍTICA SSSUR) |
| `assets/style.css` | Estilo de la página (Dash lo carga automáticamente) |
| `assets/logos/` | Logos de los partidos |
| `assets/iconos/` | Íconos de las tarjetas de papeletas |

Los límites de los distritos se leen de `../data/SAN SALVADOR SUR.geojson`, la misma capa del visor.

## Actualizar los datos

Reemplaza `datos/APP_POLITICA_SSSUR.xlsx` por una versión nueva con las mismas hojas
(MUNICIPIO, DISTRITOS, CENTROS_VOTACION, GRAFICA_VOTOS y sus versiones `_2021`)
y reinicia `python app.py`.

## Publicarlo en un servidor

```bash
pip install gunicorn
gunicorn app:server --bind 0.0.0.0:8050
```
