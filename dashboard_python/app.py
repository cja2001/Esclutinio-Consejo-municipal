"""Dashboard de resultados electorales de San Salvador Sur (2021 y 2024).

Ejecutar:
    pip install -r requirements.txt
    python app.py
y abrir http://127.0.0.1:8050 en el navegador.
"""

import math

import plotly.graph_objects as go
from dash import ALL, ClientsideFunction, Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update

import datos as D

DATA = D.cargar()
GEO = D.cargar_geojson()
NOTAS = D.validar(DATA)
MAX_JRV = max(int(DATA[y]["centros"]["JRV"].max()) for y in D.YEARS)

app = Dash(__name__, title="Escrutinio San Salvador Sur",
           meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
server = app.server  # para desplegar con gunicorn: gunicorn app:server

FONT = dict(family="Arial, Helvetica, sans-serif", size=12, color="#333")
GRID = "#e6e8ec"
PANTALLA = {"w": 680, "movil": False}  # hasta que el navegador mida la pantalla (assets/pantalla.js)


def otro(year):
    return 2021 if year == 2024 else 2024


def fmt(n):
    return f"{int(n):,}"


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def logo(p, h=14):
    """Logo del partido como imagen; si no hay logo, un recuadro con el color del partido."""
    if p in D.LOGO:
        return html.Img(src=app.get_asset_url(f"logos/{D.LOGO[p]}.png"), className="logo",
                        alt=D.NOMBRE[p], width=round(h * 1.5), height=h)
    return html.Span(style={"display": "inline-block", "width": round(h * 1.5), "height": h,
                            "background": D.color(p), "borderRadius": 2})


# ---------------------------------------------------------------- mapa

def _bounds(features):
    lons, lats = [], []
    for f in features:
        for poly in f["geometry"]["coordinates"]:
            for x, y, *_ in poly[0]:
                lons.append(x)
                lats.append(y)
    return min(lons), max(lons), min(lats), max(lats)


def _merc(lat):
    """Coordenada y de Web Mercator (en radianes) para una latitud."""
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _vista(features, w=680, h=400, margen=1.1):
    """Centro y zoom para encuadrar los polígonos en un mapa de w x h píxeles (teselas de 512 px)."""
    x0, x1, y0, y1 = _bounds(features)
    ancho = max(x1 - x0, 1e-4) / 360 * margen                       # fracción del mundo en x
    alto = max(_merc(y1) - _merc(y0), 1e-6) / (2 * math.pi) * margen  # fracción del mundo en y
    zoom = min(math.log2(w / 512 / ancho), math.log2(h / 512 / alto))
    centro_lat = math.degrees(2 * math.atan(math.exp((_merc(y0) + _merc(y1)) / 2)) - math.pi / 2)
    return {"lon": (x0 + x1) / 2, "lat": centro_lat}, zoom


def fig_mapa(year, distrito, rangos, pant):
    """Distritos teñidos con la bandera del ganador y centros de votación: tamaño = cantidad de JRV,
    color = bandera del partido con más votos en ese centro."""
    fig = go.Figure()
    ganador = {d: D.ranking(D.resumen(D.filtrar(DATA, year, d))["votos"]).index[0] for d in D.DISTRITOS}
    for p in dict.fromkeys(ganador.values()):
        locs = [d for d in D.DISTRITOS if ganador[d] == p]
        c = D.BANDERA[p]
        # Cada capa lleva solo sus distritos: el GeoJSON completo repetido por capa hacía pesado cada clic.
        geo = {"type": "FeatureCollection", "features": [f for f in GEO["features"] if f["id"] in locs]}
        fig.add_trace(go.Choroplethmap(
            geojson=geo, locations=locs, z=[1] * len(locs), colorscale=[[0, c], [1, c]], showscale=False,
            marker=dict(opacity=[0.45 if d == distrito else 0.28 if distrito == "ALL" else 0.1 for d in locs],
                        line=dict(color=["#0a2a43" if d == distrito else c for d in locs],
                                  width=[3 if d == distrito else 1.5 for d in locs])),
            text=[D.titulo(d) for d in locs], name=D.NOMBRE[p],
            hovertemplate="<b>%{text}</b><br>Ganador del distrito: " + D.NOMBRE[p] + "<extra></extra>"))
    c = DATA[year]["centros"].copy()
    c["rango"] = [D.rango_jrv(n)[0] for n in c["JRV"]]
    c = c[c["rango"].isin(rangos or [])]
    if len(c):
        c["gana"] = c[D.PARTIDOS].idxmax(axis=1)
        c["size"] = [D.rango_jrv(n)[3] for n in c["JRV"]]
        c["letra"] = [D.rango_jrv(n)[4] for n in c["JRV"]]
        c = c.sort_values("JRV", ascending=False)  # los puntos grandes abajo, los pequeños encima
        top = c[D.PARTIDOS].apply(lambda r: D.ranking(r).head(3), axis=1)
        hover = [
            f"<b>{D.titulo(r.nombre)}</b><br>{D.titulo(r.distrito)} · <b>{r.JRV} JRV</b> · {fmt(r.validos)} votos<br>"
            + "<br>".join(f"{D.NOMBRE[p]}: {fmt(v)} ({pct(v / r.validos)})" for p, v in top.loc[i].dropna().items())
            for i, r in c.iterrows()]
        op = [0.2 if distrito != "ALL" and d != distrito else 1 for d in c["distrito"]]
        # Scattermap no dibuja borde: un punto blanco un poco mayor hace de contorno.
        fig.add_trace(go.Scattermap(lat=c["lat"], lon=c["lon"], mode="markers", hoverinfo="skip",
                                    marker=dict(size=c["size"] + 4, color="#ffffff", opacity=op)))
        fig.add_trace(go.Scattermap(
            lat=c["lat"], lon=c["lon"], mode="markers", name="Centros de votación",
            marker=dict(size=c["size"], color=[D.BANDERA[p] for p in c["gana"]], opacity=op),
            customdata=c["distrito"], hovertext=hover, hoverinfo="text"))
        # Número de JRV dentro de cada punto. Scattermap no admite tamaño ni color de letra por punto,
        # así que va una capa de texto por cada tamaño y por atenuado/no atenuado.
        c["tenue"] = [o < 1 for o in op]
        for (letra, tenue), g in c.groupby(["letra", "tenue"]):
            fig.add_trace(go.Scattermap(
                lat=g["lat"], lon=g["lon"], mode="text", text=g["JRV"].astype(str), hoverinfo="skip",
                textposition="middle center", showlegend=False,
                textfont=dict(size=letra, family="Open Sans Bold",
                              color="rgba(255,255,255,0.35)" if tenue else "#ffffff")))
    features = GEO["features"] if distrito == "ALL" else [f for f in GEO["features"] if f["id"] == distrito]
    alto = 300 if pant["movil"] else 400
    centro, zoom = _vista(features, w=max(pant["w"], 200), h=alto)
    fig.update_layout(
        # Estilo sin dependencias + teselas raster de OSM France (sin clave de API): si el mapa base no carga, los distritos se siguen viendo.
        map=dict(style="white-bg", center=centro, zoom=zoom, layers=[dict(
            below="traces", sourcetype="raster", opacity=0.7,
            sourceattribution="© OpenStreetMap contributors · OSM France",
            source=[f"https://{s}.tile.openstreetmap.fr/osmfr/{{z}}/{{x}}/{{y}}.png" for s in "abc"])]),
        margin=dict(l=0, r=0, t=0, b=0), height=alto, showlegend=False, font=FONT,
        uirevision=f"{distrito}-{pant['w']}", hoverlabel=dict(bgcolor="#fff", font=FONT),
        datarevision=f"{year}-{distrito}-{'.'.join(sorted(rangos or []))}")  # obliga a redibujar los puntos
    return fig


# ---------------------------------------------------------------- gráficos

def fig_barras(r, pant):
    rk = D.ranking(r["votos"])
    siglas = [D.SIGLA[p] for p in rk.index]
    fig = go.Figure(go.Bar(
        x=siglas, y=rk.values, marker=dict(color=[D.color(p) for p in rk.index], cornerradius=4),
        width=0.5, customdata=[[D.NOMBRE[p], pct(v / r["validos"])] for p, v in rk.items()],
        hovertemplate="<b>%{customdata[0]}</b><br>%{y:,} votos · %{customdata[1]}<extra></extra>", name="Votos"))
    for p, s in zip(rk.index, siglas):
        if p in D.LOGO:
            fig.add_layout_image(source=app.get_asset_url(f"logos/{D.LOGO[p]}.png"), xref="x", yref="paper",
                                 x=s, y=-0.04, sizex=0.62, sizey=0.11, xanchor="center", yanchor="top",
                                 sizing="contain", layer="above")
    movil = pant["movil"]
    fig.update_layout(height=300 if movil else 330, margin=dict(l=48 if movil else 60, r=6 if movil else 10, t=10, b=70),
                      font=FONT, plot_bgcolor="#fff", paper_bgcolor="#fff", bargap=0.4, showlegend=False,
                      hoverlabel=dict(bgcolor="#fff"))
    # En el teléfono las siglas no caben juntas bajo los logos: van inclinadas y más pequeñas.
    fig.update_xaxes(ticklabelstandoff=34, tickangle=-45 if movil else 0, tickfont=dict(size=9 if movil else 10.5),
                     showline=True, linecolor="#333", fixedrange=True)
    fig.update_yaxes(title=None if movil else "Votos", gridcolor=GRID, tickformat="~s" if movil else ",",
                     zeroline=False, fixedrange=True)
    return fig


def fig_comparacion(distrito, pant):
    a = D.resumen(D.filtrar(DATA, 2024, distrito))
    b = D.resumen(D.filtrar(DATA, 2021, distrito))
    filas = [(p, a["votos"][p] / a["validos"], b["votos"][p] / b["validos"]) for p in D.PARTIDOS]
    filas = sorted([f for f in filas if f[1] or f[2]], key=lambda f: max(f[1], f[2]))
    fig = go.Figure()
    for p, s24, s21 in filas:
        y = D.SIGLA[p] if pant["movil"] else D.NOMBRE[p]  # en el teléfono el nombre completo deja sin espacio al gráfico
        c = D.color(p)
        fig.add_trace(go.Scatter(x=[s21, s24], y=[y, y], mode="lines", line=dict(color=c, width=2),
                                 opacity=0.55, hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=[s21], y=[y], mode="markers", showlegend=False,
                                 marker=dict(size=10, color="#fff", line=dict(color=c, width=2)),
                                 hovertemplate=f"<b>{D.NOMBRE[p]}</b><br>2021: {pct(s21)}<extra></extra>"))
        fig.add_trace(go.Scatter(x=[s24], y=[y], mode="markers", showlegend=False,
                                 marker=dict(size=12, color=c, line=dict(color="#fff", width=2)),
                                 hovertemplate=f"<b>{D.NOMBRE[p]}</b><br>2024: {pct(s24)}<extra></extra>"))
        # el cambio se escribe a la derecha del punto más alejado, para no tapar la línea
        fig.add_trace(go.Scatter(x=[max(s21, s24)], y=[y], mode="text", showlegend=False, hoverinfo="skip",
                                 text=[f"   {(s24 - s21) * 100:+.1f} pp"], textposition="middle right",
                                 textfont=dict(size=11, color="#555")))
    tope = max(max(f[1], f[2]) for f in filas)
    holgura = 0.2 if pant["movil"] else 0.12  # espacio a la derecha para el texto del cambio
    fig.update_layout(height=max(260, 26 * len(filas) + 60), margin=dict(l=10, r=20, t=10, b=30), font=FONT,
                      plot_bgcolor="#fff", paper_bgcolor="#fff", hoverlabel=dict(bgcolor="#fff"))
    fig.update_xaxes(tickformat=".0%", gridcolor=GRID, zeroline=False, fixedrange=True, range=[-0.015, tope + holgura])
    fig.update_yaxes(fixedrange=True, ticklabelstandoff=10)
    return fig


def fig_distritos(year, distrito):
    fig = go.Figure()
    filas = []
    for d in reversed(D.DISTRITOS):
        r = D.resumen(D.filtrar(DATA, year, d))
        filas.append((d, r["validos"], D.grupos(r["votos"])))
    for g in D.GRUPOS:
        xs = [gr[g] / v for _, v, gr in filas]
        fig.add_trace(go.Bar(
            y=[D.titulo(d) for d, _, _ in filas], x=xs, orientation="h", name=D.nombre_grupo(g),
            marker=dict(color=D.color_grupo(g), line=dict(color="#fff", width=1)),
            text=[f"{x * 100:.0f}%" if x > 0.09 else "" for x in xs], textposition="inside",
            insidetextanchor="middle", textfont=dict(color="#fff", size=11),
            customdata=[fmt(gr[g]) for _, _, gr in filas],
            hovertemplate="<b>%{y}</b><br>" + D.nombre_grupo(g) + ": %{customdata} · %{x:.1%}<extra></extra>"))
    sel = D.titulo(distrito) if distrito != "ALL" else None
    fig.update_layout(barmode="stack", height=300, margin=dict(l=10, r=10, t=10, b=10), font=FONT,
                      plot_bgcolor="#fff", paper_bgcolor="#fff", bargap=0.35,
                      legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center", traceorder="normal"), hoverlabel=dict(bgcolor="#fff"))
    fig.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
    fig.update_yaxes(fixedrange=True, tickfont=dict(size=12),
                     ticktext=[f"<b>{D.titulo(d)}</b>" if D.titulo(d) == sel else D.titulo(d) for d, _, _ in filas],
                     tickvals=[D.titulo(d) for d, _, _ in filas])
    return fig


# ---------------------------------------------------------------- piezas HTML

TARJETAS = [("Nulos", "nulos"), ("Abstenciones", "abst"), ("Impugnados", "imp"),
            ("Faltantes", "falt"), ("Sobrantes", "sobr"), ("Inutilizadas", "inut")]


def tarjetas(a, b, year):
    return [html.Div(className="tile", children=[
        html.Div(lab, className="t"),
        html.Div(className="v", children=[
            html.Span(html.Img(src=app.get_asset_url(f"iconos/{k}.svg"), alt=""), className="ic"),
            html.Span([html.Span(fmt(a[k]), className="num"), html.Span(f"{fmt(b[k])} en {otro(year)}", className="d")]),
        ])]) for lab, k in TARJETAS]


def tabla_partidos(r):
    filas = [html.Tr([html.Td(logo(p, 24)), html.Td(D.NOMBRE[p]), html.Td(html.B(fmt(v)), className="n"),
                      html.Td(pct(v / r["validos"]), className="n")]) for p, v in D.ranking(r["votos"]).items()]
    return html.Table(className="plain", children=[
        html.Thead(html.Tr([html.Th("", style={"width": 56}), html.Th("Partido político"),
                            html.Th("Votos", className="n"), html.Th("%", className="n")])),
        html.Tbody(filas),
        html.Tfoot(html.Tr([html.Td(""), html.Td(html.B("Votos válidos")), html.Td(html.B(fmt(r["validos"])), className="n"),
                            html.Td(html.B("100%"), className="n")]))])


def tabla_distritos(year, distrito):
    filas = []
    for d in D.DISTRITOS:
        r = D.resumen(D.filtrar(DATA, year, d))
        p, v = next(iter(D.ranking(r["votos"]).items()))
        filas.append(html.Tr([
            html.Td(html.Button(D.titulo(d), id={"type": "dbtn", "index": d}, n_clicks=0,
                                className="linkbtn sel" if d == distrito else "linkbtn")),
            html.Td(html.Span([logo(p, 14), f"{D.SIGLA[p]} {pct(v / r['validos'], 0)}"], className="wincell"))]))
    return html.Table(className="plain center", children=[
        html.Thead(html.Tr([html.Th("Distritos"), html.Th("Ganador")])), html.Tbody(filas)])


def datos_centros(year, distrito):
    filas = []
    for _, c in D.filtrar(DATA, year, distrito).iterrows():
        rk = D.ranking(c[D.PARTIDOS].astype(int))
        p1, v1 = rk.index[0], rk.iloc[0]
        v2 = rk.iloc[1] if len(rk) > 1 else 0
        filas.append({
            "centro": D.titulo(c["nombre"]), "distrito": D.titulo(c["distrito"]), "jrv": int(c["JRV"]),
            "votos": int(c["validos"]),
            "ganador": f"![{D.NOMBRE[p1]}]({app.get_asset_url('logos/' + D.LOGO[p1] + '.png')}) {D.NOMBRE[p1]}",
            "pct": round(v1 / c["validos"] * 100, 1), "margen": round((v1 - v2) / c["validos"] * 100, 1),
            "nulos": int(c["NULOS"]), "abst": int(c["ABSTENCIONES"]), "direccion": c["direccion"]})
    return filas


# ---------------------------------------------------------------- layout

app.layout = html.Div([
    dcc.Store(id="pantalla"),
    html.Div(className="wrap", children=[
        html.Header(className="head", children=[
            html.H1(id="titulo"),
            html.Div(id="migas", className="crumbs"),
            html.Div(className="toolbar", children=[
                dcc.RadioItems(id="year", value=2024, className="seg", inline=True,
                               options=[{"label": html.Span(f"Elección {y}"), "value": y} for y in D.YEARS]),
                html.Div(className="filter", children=[
                    html.Span("Distrito:"),
                    dcc.Dropdown(id="distrito", value="ALL", clearable=False, searchable=False, className="dd",
                                 options=[{"label": "Todo el municipio", "value": "ALL"}]
                                 + [{"label": D.titulo(d), "value": d} for d in D.DISTRITOS]),
                ]),
            ]),
        ]),
        html.Section(className="card progress", children=[
            html.P(id="avance-txt"), html.Div(className="bar", children=html.Div(id="avance-bar")),
            html.Div(id="avance-meta", className="meta")]),
        html.Div(className="row map-row", children=[
            html.Section(id="card-mapa", className="card", children=[
                html.H2('Distritos de "San Salvador Sur"', className="card-title"),
                dcc.Graph(id="mapa", config={"scrollZoom": True, "displaylogo": False, "responsive": True,
                                             "modeBarButtonsToRemove": ["select2d", "lasso2d"]}),
                html.Div(className="map-legend", children=[
                    html.Div(className="leg-block", children=[
                        dcc.Checklist(id="ver-centros", value=["si"], className="leg-master",
                                      options=[{"label": html.Span("Centros de Votación"), "value": "si"}]),
                        dcc.Checklist(id="rangos", value=[r[0] for r in D.RANGOS_JRV], className="leg-sizes",
                                      options=[{"label": html.Span([
                                          html.Span(html.Span(className="circ", style={"width": r[3], "height": r[3]}), className="circ-box"),
                                          D.etiqueta_rango(r, MAX_JRV)]), "value": r[0]} for r in D.RANGOS_JRV]),
                    ]),
                    html.Div(className="leg-block", children=[
                        html.Div("Color: partido con más votos en el centro", className="leg-title"),
                        html.Div(id="leyenda-colores", className="leg-colors"),
                    ]),
                ]),
            ]),
            html.Section(className="card", children=[
                html.Div(id="tabla-distritos"),
                html.P("Selecciona un distrito en la tabla o en el mapa para ver sus resultados.", className="hint")]),
        ]),
        html.Div(className="row half", children=[
            html.Section(className="card", children=[
                html.H2("Votos por Partido político", className="card-title"),
                dcc.Graph(id="barras", config={"displayModeBar": False, "responsive": True})]),
            html.Section(className="card", children=[
                html.H2("Votos por Partido político", className="card-title navy"), html.Div(id="tabla-partidos")]),
        ]),
        html.Section(id="tarjetas", className="tiles"),
        html.Div(className="row half", children=[
            html.Section(className="card", children=[
                html.H2("Comparación 2021 – 2024", className="card-title"),
                html.P("% de votos válidos · círculo vacío = 2021, círculo lleno = 2024", className="hint",
                       style={"textAlign": "center", "margin": "0 0 4px"}),
                dcc.Graph(id="comparacion", config={"displayModeBar": False, "responsive": True})]),
            html.Section(className="card", children=[
                html.H2("Resultados por distrito", className="card-title"),
                dcc.Graph(id="por-distrito", config={"displayModeBar": False, "responsive": True})]),
        ]),
        html.Section(className="card", children=[
            html.H2("Resultados por centro de votación", className="card-title navy"),
            dash_table.DataTable(
                id="centros", sort_action="native", filter_action="native", page_size=30,
                filter_options={"case": "insensitive", "placeholder_text": "Filtrar…"},
                markdown_options={"link_target": "_self"},
                columns=[
                    {"name": "Centro de votación", "id": "centro"}, {"name": "Distrito", "id": "distrito"},
                    {"name": "JRV", "id": "jrv", "type": "numeric"},
                    {"name": "Votos", "id": "votos", "type": "numeric", "format": {"specifier": ","}},
                    {"name": "Ganador", "id": "ganador", "presentation": "markdown"},
                    {"name": "% ganador", "id": "pct", "type": "numeric"},
                    {"name": "Margen (pp)", "id": "margen", "type": "numeric"},
                    {"name": "Nulos", "id": "nulos", "type": "numeric"},
                    {"name": "Abst.", "id": "abst", "type": "numeric"},
                ],
                tooltip_delay=300, tooltip_duration=None,
                style_table={"overflowX": "auto"},
                style_cell={"fontFamily": "Arial, Helvetica, sans-serif", "fontSize": 13, "padding": "7px 10px",
                            "border": "none", "borderTop": "1px solid #d9dde3", "textAlign": "left"},
                style_cell_conditional=[{"if": {"column_type": "numeric"}, "textAlign": "right"},
                                        {"if": {"column_id": "centro"}, "fontWeight": "bold", "minWidth": 240,
                                         "whiteSpace": "normal"}],
                style_header={"fontWeight": "bold", "color": "#222", "background": "#fff", "borderBottom": "2px solid #222",
                              "borderTop": "1px solid #d9dde3"},
                style_filter={"background": "#f8fafc"},
                style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#f2f2f2"}],
                css=[{"selector": ".dash-cell-value img", "rule": "height:14px;width:21px;object-fit:cover;vertical-align:-2px;border-radius:2px;box-shadow:0 0 0 1px rgba(0,0,0,.12)"},
                     {"selector": ".dash-cell-value p", "rule": "margin:0"}],
            ),
        ]),
        html.Section(className="card", children=[
            html.H2("Validación de actas", className="card-title navy"),
            html.Div(className="notes", children=[html.Div(n, className="note") for n in NOTAS] + [
                html.Div("Los totales de este tablero se calculan desde los votos por partido de cada centro "
                         "(hoja GRAFICA_VOTOS), por eso pueden diferir de los totales escritos en MUNICIPIO o DISTRITOS.",
                         className="ok")]),
        ]),
    ]),
    html.Footer(className="band", children=html.Div(
        "Datos: APP POLÍTICA SSSUR.xlsx (hojas MUNICIPIO, DISTRITOS, CENTROS_VOTACION y GRAFICA_VOTOS, 2021 y 2024). "
        "Límites distritales: capa SAN SALVADOR SUR del visor territorial. Mapa base © OpenStreetMap · OSM France.")),
])


# ---------------------------------------------------------------- callbacks

# El navegador mide la pantalla al cargar; assets/pantalla.js vuelve a medir al girar el teléfono.
app.clientside_callback(ClientsideFunction("pantalla", "medir"), Output("pantalla", "data"), Input("pantalla", "id"))


@app.callback(
    Output("distrito", "value"),
    Input("mapa", "clickData"), Input({"type": "dbtn", "index": ALL}, "n_clicks"),
    State("distrito", "value"), prevent_initial_call=True)
def elegir_distrito(click, _clicks, actual):
    """Un clic en el mapa o en la tabla de distritos filtra; un segundo clic vuelve al municipio."""
    trig = ctx.triggered_id
    if isinstance(trig, dict):
        # El valor se busca por el id del botón: ctx.triggered no lo encuentra si el distrito lleva tilde
        # (SANTO TOMÁS), y un botón recién dibujado con n_clicks=0 no cuenta como clic.
        clics = {i["id"]["index"]: i.get("value") for i in ctx.inputs_list[1]}
        if not clics.get(trig["index"]):
            return no_update
        d = trig["index"]
    elif trig == "mapa" and click:
        pt = click["points"][0]
        d = pt.get("location") or pt.get("customdata")
        if not d:
            return no_update
    else:
        return no_update
    return "ALL" if d == actual else d


@app.callback(
    Output("titulo", "children"), Output("migas", "children"),
    Output("avance-txt", "children"), Output("avance-bar", "style"), Output("avance-meta", "children"),
    Output("mapa", "figure"), Output("tabla-distritos", "children"),
    Output("barras", "figure"), Output("tabla-partidos", "children"),
    Output("tarjetas", "children"), Output("comparacion", "figure"), Output("por-distrito", "figure"),
    Output("centros", "data"), Output("centros", "tooltip_data"), Output("leyenda-colores", "children"),
    Input("year", "value"), Input("distrito", "value"), Input("rangos", "value"), Input("pantalla", "data"))
def actualizar(year, distrito, rangos, pant):
    pant = {**PANTALLA, **(pant or {})}
    a = D.resumen(D.filtrar(DATA, year, distrito))
    b = D.resumen(D.filtrar(DATA, otro(year), distrito))
    migas = "El Salvador / San Salvador / Sur" + ("" if distrito == "ALL" else f" / {D.titulo(distrito)}")
    avance = a["procesados"] / a["centros"]
    meta = [html.Span(["JRV en los centros: ", html.B(fmt(a["jrv"]))]),
            html.Span(["Votos válidos: ", html.B(fmt(a["validos"]))]),
            html.Span(["Población votante: ", html.B(fmt(a["pob"]))])]
    if distrito == "ALL":
        meta.append(html.Span(["Actas registradas en hoja MUNICIPIO: ",
                               html.B(fmt(DATA[year]["municipio"]["CANTIDAD TOTAL DE ACTAS"]))]))
    filas = datos_centros(year, distrito)
    return (
        f"Resultados: Nivel municipal de Concejo {year}", migas,
        ["Cantidad total de centros de votación procesados ", html.B(f"{a['procesados']}/{a['centros']}"),
         f" ({pct(avance, 2)})"],
        {"width": f"{avance * 100:.2f}%"}, meta,
        fig_mapa(year, distrito, rangos, pant), tabla_distritos(year, distrito),
        fig_barras(a, pant), tabla_partidos(a), tarjetas(a, b, year),
        fig_comparacion(distrito, pant), fig_distritos(year, distrito),
        filas, [{"centro": {"value": f["direccion"], "type": "text"}} for f in filas],
        leyenda_colores(year),
    )


def leyenda_colores(year):
    ganadores = DATA[year]["centros"][D.PARTIDOS].idxmax(axis=1).value_counts()
    return [html.Span([html.Span(className="circ", style={"background": D.BANDERA[p], "width": 12, "height": 12}),
                       logo(p, 12), f"{D.NOMBRE[p]} ({n})"], className="leg-item") for p, n in ganadores.items()]


@app.callback(Output("rangos", "value"), Output("ver-centros", "value"),
              Input("ver-centros", "value"), Input("rangos", "value"), prevent_initial_call=True)
def sincronizar_casillas(ver, rangos):
    """La casilla principal marca o desmarca todos los rangos; si no queda ningún rango, se desmarca."""
    if ctx.triggered_id == "ver-centros":
        return ([r[0] for r in D.RANGOS_JRV] if ver else []), no_update
    return no_update, (["si"] if rangos else [])


if __name__ == "__main__":
    app.run(debug=False)
