"""Lectura y agregación de los resultados electorales de San Salvador Sur.

Lee el Excel exportado de la app "APP POLÍTICA SSSUR" y deja los datos listos
para el dashboard: centros de votación con sus votos por partido, y funciones
para sumar por municipio o distrito.
"""

import json
import math
import unicodedata
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
EXCEL = BASE / "datos" / "APP_POLITICA_SSSUR.xlsx"
GEOJSON = BASE.parent / "data" / "SAN SALVADOR SUR.geojson"

YEARS = [2024, 2021]

PARTIDOS = [
    "NUEVAS IDEAS", "ARENA", "FMLN", "PDC", "NUESTRO TIEMPO", "GANA", "CD",
    "FUERZA SOLIDARIA", "VAMOS", "PCN", "ARENA - DS", "DEMOCRACIA SALVADOREÑA",
]
NOMBRE = {
    "NUEVAS IDEAS": "Nuevas Ideas", "ARENA": "ARENA", "FMLN": "FMLN", "PDC": "PDC",
    "NUESTRO TIEMPO": "Nuestro Tiempo", "GANA": "GANA", "CD": "CD",
    "FUERZA SOLIDARIA": "Fuerza Solidaria", "VAMOS": "Vamos", "PCN": "PCN",
    "ARENA - DS": "ARENA–DS", "DEMOCRACIA SALVADOREÑA": "Democracia Salvadoreña",
}
SIGLA = {
    "NUEVAS IDEAS": "NI", "ARENA": "ARENA", "FMLN": "FMLN", "PDC": "PDC",
    "NUESTRO TIEMPO": "NT", "GANA": "GANA", "CD": "CD", "FUERZA SOLIDARIA": "FS",
    "VAMOS": "VAMOS", "PCN": "PCN", "ARENA - DS": "A-DS", "DEMOCRACIA SALVADOREÑA": "DS",
}
LOGO = {
    "NUEVAS IDEAS": "nuevas-ideas", "ARENA": "arena", "FMLN": "fmln", "PDC": "pdc",
    "NUESTRO TIEMPO": "nuestro-tiempo", "GANA": "gana", "CD": "cd",
    "FUERZA SOLIDARIA": "fuerza-solidaria", "VAMOS": "vamos", "PCN": "pcn",
    "ARENA - DS": "arena",  # la coalición usa el logo de ARENA
}

# Colores de los cuatro partidos principales (validados para daltonismo); el resto va en gris.
COLOR = {"NUEVAS IDEAS": "#14a0b5", "ARENA": "#2a5fd6", "FMLN": "#e34948", "PDC": "#d99a00"}
OTRO = "#a3adbb"
GRUPOS = ["NUEVAS IDEAS", "ARENA", "FMLN", "PDC", "Otros"]

# Color principal de la bandera de cada partido (muestreado de los logos), para el mapa.
BANDERA = {
    "NUEVAS IDEAS": "#00adef", "ARENA": "#005aab", "FMLN": "#d3252f", "PDC": "#00732e",
    "NUESTRO TIEMPO": "#22305e", "GANA": "#e67306", "CD": "#1a1a8c", "FUERZA SOLIDARIA": "#c9cb12",
    "VAMOS": "#104c90", "PCN": "#1837b4", "ARENA - DS": "#005aab", "DEMOCRACIA SALVADOREÑA": "#7a7a7a",
}

# Rangos de cantidad de JRV por centro: (clave, mínimo, máximo, diámetro del punto en px, tamaño del número de JRV en px).
RANGOS_JRV = [("r1", 0, 2, 16, 9), ("r2", 3, 5, 19, 10), ("r3", 6, 8, 22, 11), ("r4", 9, 11, 26, 12), ("r5", 12, 99, 30, 13)]


def rango_jrv(n):
    return next(r for r in RANGOS_JRV if r[1] <= n <= r[2])


def etiqueta_rango(r, maximo):
    return f"{r[1]} - {min(r[2], maximo) if r[2] == 99 else r[2]} JRVs"


DISTRITOS = ["PANCHIMALCO", "ROSARIO DE MORA", "SAN MARCOS", "SANTIAGO TEXACUANGOS", "SANTO TOMÁS"]

METRICAS = ["VOTOS OBTENIDOS", "NULOS", "ABSTENCIONES", "INPUGNADOS", "FALTANTES",
            "SOBRANTES", "INUTILIZADAS", "POBLACIÓN VOTANTE"]


def color(p):
    return COLOR.get(p, OTRO)


def color_grupo(g):
    return OTRO if g == "Otros" else COLOR[g]


def nombre_grupo(g):
    return "Otros" if g == "Otros" else NOMBRE[g]


def titulo(s):
    """'SANTIAGO TEXACUANGOS' -> 'Santiago Texacuangos', 'ROSARIO DE MORA' -> 'Rosario de Mora'."""
    return " ".join(w if w == "de" else w.capitalize() for w in str(s).lower().split())


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").upper()


def _limpiar(s):
    return str(s).replace(" 2021", "").strip()


def _hoja(xls, nombre):
    df = pd.read_excel(xls, sheet_name=nombre)
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
    return df.dropna(subset=[df.columns[0]])


def cargar(ruta=EXCEL):
    """Devuelve {año: {"municipio": dict, "distritos": DataFrame, "centros": DataFrame}}."""
    xls = pd.ExcelFile(ruta)
    datos = {}
    for year, suf in [(2024, ""), (2021, "_2021")]:
        centros = _hoja(xls, "CENTROS_VOTACION" + suf)
        centros["id"] = centros["ID CE_VOTACION"].astype(int)
        centros["distrito"] = centros["DISTRITO"].map(_limpiar)
        centros[["lat", "lon"]] = centros["UBICACIÓN GPS"].str.split(",", expand=True).astype(float)
        centros = centros.rename(columns={"NOMBRE CENTRO DE VOTACIÓN": "nombre", "DIRECCIÓN": "direccion"})
        centros[METRICAS + ["JRV"]] = centros[METRICAS + ["JRV"]].fillna(0).astype(int)

        votos = _hoja(xls, "GRAFICA_VOTOS" + suf)
        votos["id"] = votos["CENTRO DE VOTACIÓN"].astype(int)
        for p in PARTIDOS:
            votos[p] = votos[p].fillna(0).astype(int) if p in votos else 0
        centros = centros.merge(votos[["id"] + PARTIDOS], on="id", how="left")
        centros[PARTIDOS] = centros[PARTIDOS].fillna(0).astype(int)
        centros["validos"] = centros[PARTIDOS].sum(axis=1)

        distritos = _hoja(xls, "DISTRITOS" + suf)
        distritos["distrito"] = distritos["NOMBRE DISTRITO"].map(_limpiar)
        municipio = _hoja(xls, "MUNICIPIO" + suf).iloc[0].to_dict()

        datos[year] = {"municipio": municipio, "distritos": distritos, "centros": centros.sort_values("id")}
    return datos


def _simplificar(anillo, tol):
    """Douglas-Peucker: quita los vértices que se apartan menos de `tol` grados de la línea."""
    if len(anillo) < 5:
        return anillo
    (x0, y0), (x1, y1) = anillo[0][:2], anillo[-1][:2]
    dx, dy = x1 - x0, y1 - y0
    largo = math.hypot(dx, dy)
    dist = [abs(dy * x - dx * y + x1 * y0 - y1 * x0) / largo if largo else math.hypot(x - x0, y - y0)
            for x, y, *_ in anillo[1:-1]]
    i = max(range(len(dist)), key=dist.__getitem__)
    if dist[i] <= tol:
        return [anillo[0], anillo[-1]]
    return _simplificar(anillo[:i + 2], tol)[:-1] + _simplificar(anillo[i + 1:], tol)


def cargar_geojson(ruta=GEOJSON, tol=0.00005):
    """Límites distritales del visor, con el nombre del distrito como id de cada polígono.

    Las geometrías se simplifican (~5 m) y se redondean a 5 decimales: el archivo original pesa
    ~370 KB y Plotly lo reenvía al navegador en cada actualización del mapa."""
    geo = json.loads(Path(ruta).read_text(encoding="utf-8"))
    nombres = {sin_acentos(d): d for d in DISTRITOS}
    for f in geo["features"]:
        f["id"] = nombres[sin_acentos(f["properties"]["Municipio"])]
        f["properties"] = {}
        f["geometry"]["coordinates"] = [
            [[[round(x, 5), round(y, 5)] for x, y, *_ in _simplificar(anillo, tol)] for anillo in poligono]
            for poligono in f["geometry"]["coordinates"]]
    return geo


def filtrar(datos, year, distrito="ALL"):
    c = datos[year]["centros"]
    return c if distrito == "ALL" else c[c["distrito"] == distrito]


def resumen(centros):
    """Suma de votos por partido y de los conteos de papeletas de un conjunto de centros."""
    votos = centros[PARTIDOS].sum()
    return {
        "votos": votos,
        "validos": int(votos.sum()),
        "nulos": int(centros["NULOS"].sum()),
        "abst": int(centros["ABSTENCIONES"].sum()),
        "imp": int(centros["INPUGNADOS"].sum()),
        "falt": int(centros["FALTANTES"].sum()),
        "sobr": int(centros["SOBRANTES"].sum()),
        "inut": int(centros["INUTILIZADAS"].sum()),
        "pob": int(centros["POBLACIÓN VOTANTE"].sum()),
        "jrv": int(centros["JRV"].sum()),
        "centros": len(centros),
        "procesados": int((centros["validos"] > 0).sum()),
    }


def ranking(votos):
    """Partidos ordenados de más a menos votos, sin los que no recibieron votos."""
    v = votos.sort_values(ascending=False)
    return v[v > 0]


def grupos(votos):
    """Votos de los cuatro partidos principales más 'Otros'."""
    otros = sum(int(votos[p]) for p in PARTIDOS if p not in COLOR)
    return {g: (otros if g == "Otros" else int(votos[g])) for g in GRUPOS}


def validar(datos):
    """Diferencias entre las hojas del Excel (sumas por partido, centros, distritos y municipio)."""
    notas = []
    for year in YEARS:
        d = datos[year]
        c = d["centros"]
        for _, r in c[c["validos"] != c["VOTOS OBTENIDOS"]].iterrows():
            notas.append(f"{year} · {titulo(r['nombre'])}: la suma de votos por partido ({r['validos']:,}) "
                         f"no coincide con los votos obtenidos del acta ({r['VOTOS OBTENIDOS']:,}); "
                         f"diferencia de {r['validos'] - r['VOTOS OBTENIDOS']:,}.")
        suma_c = c.groupby("distrito")["VOTOS OBTENIDOS"].sum()
        for _, r in d["distritos"].iterrows():
            s = int(suma_c.get(r["distrito"], 0))
            if s != int(r["VOTOS OBTENIDOS"]):
                notas.append(f"{year} · Distrito {titulo(r['distrito'])}: la hoja DISTRITOS reporta "
                             f"{int(r['VOTOS OBTENIDOS']):,} votos, pero sus centros suman {s:,} "
                             f"(diferencia {s - int(r['VOTOS OBTENIDOS']):,}).")
        ms = int(d["distritos"]["VOTOS OBTENIDOS"].sum())
        if ms != int(d["municipio"]["VOTOS OBTENIDOS"]):
            notas.append(f"{year} · Municipio: la hoja MUNICIPIO reporta {int(d['municipio']['VOTOS OBTENIDOS']):,} "
                         f"votos y los distritos suman {ms:,}.")
    return notas
