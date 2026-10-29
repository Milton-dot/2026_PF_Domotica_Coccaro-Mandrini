import json
import os
import uuid
from datetime import datetime, timedelta, time as dtime

import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# Configuración
# ---------------------------------------------------------
ARCHIVO_ALARMAS = "alarmas.json"
ARCHIVO_PASTILLERO = "config.json"
ARCHIVO_MEMORIA = "memoria_usuario.json"

st.set_page_config(
    page_title="Dashboard Asistente", 
    layout="wide", 
    page_icon="🏠"
)

DIAS_SEMANA_NOMBRES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}
NOMBRES_ORDENADOS = [DIAS_SEMANA_NOMBRES[i] for i in range(7)]
NOMBRE_A_INDICE = {v: k for k, v in DIAS_SEMANA_NOMBRES.items()}

# Nombres amigables para los tipos de alarma (solo para mostrar en pantalla;
# el JSON sigue guardando internamente "unica" / "recurrente").
ETIQUETA_UNICA = "📅 Una vez"
ETIQUETA_RECURRENTE = "🔁 Se repite"

# ---------------------------------------------------------
# PALETA DE COLORES MODERNA
# ---------------------------------------------------------
ACENTO_ALARMA = "#3b82f6"       # Azul moderno
FONDO_TARJETA_EVENTO = "#1e293b"# Tono oscuro elegante para tarjetas
COLOR_TEXTO_EVENTO = "#f8fafc"
COLOR_NOMBRE_DIA = "#38bdf8"
COLOR_FECHA_DIA = "#94a3b8"
COLOR_SIN_EVENTOS = "#64748b"

PALETA_PASTILLAS = [
    ("#8b5cf6", "🟪"),  # Violeta
    ("#10b981", "🟩"),  # Esmeralda
    ("#f59e0b", "🟧"),  # Ámbar
    ("#0ea5e9", "🟦"),  # Celeste
    ("#f43f5e", "🟥"),  # Rosa/Rojo
    ("#eab308", "🟨"),  # Amarillo
    ("#64748b", "⬛"),  # Gris
]


# ---------------------------------------------------------
# CSS global estilizado (Modo Modern Dashboard)
# ---------------------------------------------------------
def aplicar_estilos():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        
        /* Contenedores principales y métricas */
        [data-testid="stMetric"] {
            background-color: #1e293b;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        [data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
            color: #f8fafc !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.9rem !important;
            color: #94a3b8 !important;
        }
        
        /* Dataframes */
        .stDataFrame { 
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #334155;
        }

        /* Botones */
        .stButton>button {
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        .stButton>button:hover {
            border-color: #38bdf8;
            color: #38bdf8;
        }

        /* Expanders */
        .streamlit-expanderHeader {
            background-color: #1e293b;
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Carga / guardado de datos
# ---------------------------------------------------------
def cargar_json(ruta):
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def guardar_json(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)


def cargar_memoria():
    if not os.path.exists(ARCHIVO_MEMORIA):
        return {}
    try:
        with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
            datos = json.load(f)
            return datos if isinstance(datos, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def guardar_memoria(memoria):
    with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=4)


# ---------------------------------------------------------
# Asignación de color por letra de pastilla
# ---------------------------------------------------------
def asignar_colores_pastillas(pastillero_raw):
    letras = sorted({p.get("pastilla_letra", "?") for p in pastillero_raw})
    mapa = {}
    for i, letra in enumerate(letras):
        mapa[letra] = PALETA_PASTILLAS[i % len(PALETA_PASTILLAS)]
    return mapa


# ===========================================================
# LÓGICA DE ALARMAS
# ===========================================================

def nuevo_id_alarma():
    return uuid.uuid4().hex[:8]


def calcular_dt_unica(a):
    try:
        return datetime(
            int(a["anio"]), int(a["mes"]), int(a["dia"]),
            int(a.get("hora", 0)), int(a.get("minuto", 0)), int(a.get("segundo", 0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def alarma_vencida(a, ahora):
    if a.get("tipo") != "unica":
        return False
    dt = calcular_dt_unica(a)
    if dt is None:
        return False
    return dt < ahora


def texto_cuando_alarma(a):
    tipo = a.get("tipo")
    if tipo == "unica":
        dt = calcular_dt_unica(a)
        if dt is None:
            return "⚠️ Datos inválidos"
        dia_semana = DIAS_SEMANA_NOMBRES[dt.weekday()]
        return f"{dia_semana} {dt.strftime('%d/%m/%Y')} a las {dt.strftime('%H:%M')}"

    if tipo == "recurrente":
        hora = a.get("hora")
        minuto = a.get("minuto")
        dias_semana = sorted(a.get("dias_semana") or [])
        if hora is None or minuto is None:
            return "⚠️ Datos inválidos"
        if not dias_semana:
            return "⚠️ Sin días configurados"
        if len(dias_semana) == 7:
            return f"Todos los días a las {hora:02d}:{minuto:02d}"
        nombres = ", ".join(DIAS_SEMANA_NOMBRES.get(d, "?") for d in dias_semana)
        return f"{nombres} a las {hora:02d}:{minuto:02d}"

    return f"⚠️ Tipo desconocido ({tipo})"


def proximo_datetime_alarma(a, ahora):
    tipo = a.get("tipo")
    if tipo == "unica":
        dt = calcular_dt_unica(a)
        if dt is None or dt < ahora:
            return None
        return dt

    if tipo == "recurrente":
        hora = a.get("hora")
        minuto = a.get("minuto")
        dias_semana = a.get("dias_semana") or []
        if hora is None or minuto is None or not dias_semana:
            return None

        mejor = None
        for dia in dias_semana:
            candidato = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            delta_dias = (dia - ahora.weekday()) % 7
            candidato += timedelta(days=delta_dias)
            if candidato <= ahora:
                candidato += timedelta(days=7)
            if mejor is None or candidato < mejor:
                mejor = candidato
        return mejor

    return None


def ocurrencias_alarma_en_rango(a, fecha_inicio, dias, ahora):
    tipo = a.get("tipo")
    resultado = []

    if tipo == "unica":
        dt = calcular_dt_unica(a)
        if dt is None or dt < ahora:
            return []
        if fecha_inicio <= dt.date() < fecha_inicio + timedelta(days=dias):
            resultado.append((dt.date(), dt.strftime("%H:%M")))

    elif tipo == "recurrente":
        hora = a.get("hora")
        minuto = a.get("minuto")
        dias_semana = a.get("dias_semana") or []
        if hora is None or minuto is None:
            return []
        for i in range(dias):
            fecha = fecha_inicio + timedelta(days=i)
            if fecha.weekday() in dias_semana:
                resultado.append((fecha, f"{hora:02d}:{minuto:02d}"))

    return resultado


def formatear_alarma_para_tabla(a, ahora):
    tipo = a.get("tipo", "?")
    tipo_mostrado = {"unica": ETIQUETA_UNICA, "recurrente": ETIQUETA_RECURRENTE}.get(tipo, tipo)
    cuando = texto_cuando_alarma(a)
    proxima = proximo_datetime_alarma(a, ahora)

    return {
        "Mensaje": a.get("mensaje", ""),
        "Tipo": tipo_mostrado,
        "Cuándo": cuando,
        "Próxima vez": proxima.strftime("%d/%m/%Y %H:%M") if proxima else "—",
        "_sort": proxima or datetime.max,
    }


def mostrar_tabla_alarmas(alarmas_vigentes, ahora):
    if not alarmas_vigentes:
        st.info("No hay alarmas programadas.")
        return
    filas = [formatear_alarma_para_tabla(a, ahora) for a in alarmas_vigentes]
    filas.sort(key=lambda f: f["_sort"])
    for f in filas:
        del f["_sort"]
    df = pd.DataFrame(filas)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# Edición y borrado de alarmas
# ---------------------------------------------------------
def guardar_alarma_editada(alarmas_raw, id_alarma, nuevos_campos):
    nueva_lista = [
        nuevos_campos if a.get("id") == id_alarma else a
        for a in alarmas_raw
    ]
    guardar_json(ARCHIVO_ALARMAS, nueva_lista)


def eliminar_alarma(alarmas_raw, id_alarma):
    nueva_lista = [a for a in alarmas_raw if a.get("id") != id_alarma]
    guardar_json(ARCHIVO_ALARMAS, nueva_lista)


def tarjeta_edicion_unica(a, alarmas_raw, ahora):
    id_alarma = a.get("id", "")
    dt_actual = calcular_dt_unica(a)
    fecha_defecto = dt_actual.date() if dt_actual else ahora.date()
    hora_defecto = dt_actual.time() if dt_actual else dtime(hour=8, minute=0)

    st.caption(f"🔖 Tipo: **{ETIQUETA_UNICA}**")

    mensaje = st.text_input("Mensaje", value=a.get("mensaje", ""), key=f"msg_unica_{id_alarma}")
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha", value=fecha_defecto, key=f"fecha_unica_{id_alarma}")
    with col2:
        hora = st.time_input("Hora", value=hora_defecto, key=f"hora_unica_{id_alarma}")

    st.caption("El tipo no se puede cambiar acá. Para eso, eliminá esta alarma y creá una nueva.")

    dt_resultante = datetime.combine(fecha, hora)
    if dt_resultante < ahora:
        st.warning("⚠️ Esa fecha y hora ya pasaron.")

    col_guardar, col_eliminar = st.columns(2)
    with col_guardar:
        if st.button("💾 Guardar cambios", key=f"guardar_unica_{id_alarma}"):
            if not mensaje.strip():
                st.error("El mensaje no puede estar vacío.")
            else:
                nuevos_campos = {
                    "id": id_alarma,
                    "mensaje": mensaje.strip(),
                    "tipo": "unica",
                    "dia": fecha.day,
                    "mes": fecha.month,
                    "anio": fecha.year,
                    "hora": hora.hour,
                    "minuto": hora.minute,
                    "segundo": 0,
                }
                guardar_alarma_editada(alarmas_raw, id_alarma, nuevos_campos)
                st.success("✅ Alarma actualizada.")
                st.rerun()
    with col_eliminar:
        if st.button("🗑️ Eliminar", key=f"eliminar_unica_{id_alarma}"):
            eliminar_alarma(alarmas_raw, id_alarma)
            st.success("Alarma eliminada.")
            st.rerun()


def tarjeta_edicion_recurrente(a, alarmas_raw, ahora):
    id_alarma = a.get("id", "")
    hora_defecto = dtime(hour=a.get("hora", 8), minute=a.get("minuto", 0))
    dias_actuales = sorted(a.get("dias_semana") or [])
    nombres_actuales = [DIAS_SEMANA_NOMBRES[d] for d in dias_actuales]

    st.caption(f"🔖 Tipo: **{ETIQUETA_RECURRENTE}**")

    mensaje = st.text_input("Mensaje", value=a.get("mensaje", ""), key=f"msg_rec_{id_alarma}")
    hora = st.time_input("Hora", value=hora_defecto, key=f"hora_rec_{id_alarma}")
    seleccion = st.multiselect(
        "Días", options=NOMBRES_ORDENADOS, default=nombres_actuales, key=f"dias_rec_{id_alarma}"
    )

    st.caption("El tipo no se puede cambiar acá. Para eso, eliminá esta alarma y creá una nueva.")

    col_guardar, col_eliminar = st.columns(2)
    with col_guardar:
        if st.button("💾 Guardar cambios", key=f"guardar_rec_{id_alarma}"):
            if not mensaje.strip():
                st.error("El mensaje no puede estar vacío.")
            elif not seleccion:
                st.error("Elegí al menos un día.")
            else:
                dias_nuevos = sorted(NOMBRE_A_INDICE[n] for n in seleccion)
                nuevos_campos = {
                    "id": id_alarma,
                    "mensaje": mensaje.strip(),
                    "tipo": "recurrente",
                    "hora": hora.hour,
                    "minuto": hora.minute,
                    "dias_semana": dias_nuevos,
                }
                guardar_alarma_editada(alarmas_raw, id_alarma, nuevos_campos)
                st.success("✅ Alarma actualizada.")
                st.rerun()
    with col_eliminar:
        if st.button("🗑️ Eliminar", key=f"eliminar_rec_{id_alarma}"):
            eliminar_alarma(alarmas_raw, id_alarma)
            st.success("Alarma eliminada.")
            st.rerun()


def mostrar_editor_alarmas(alarmas_vigentes, alarmas_raw, ahora):
    if not alarmas_vigentes:
        st.info("No hay alarmas para editar.")
        return

    ordenadas = sorted(
        alarmas_vigentes,
        key=lambda a: proximo_datetime_alarma(a, ahora) or datetime.max,
    )

    for a in ordenadas:
        id_alarma = a.get("id", "")
        tipo = a.get("tipo")
        titulo = f"{a.get('mensaje', '(sin mensaje)')} — {texto_cuando_alarma(a)}"

        with st.expander(titulo):
            if tipo == "unica":
                tarjeta_edicion_unica(a, alarmas_raw, ahora)
            elif tipo == "recurrente":
                tarjeta_edicion_recurrente(a, alarmas_raw, ahora)
            else:
                if st.button("🗑️ Eliminar", key=f"borrar_desconocida_{id_alarma}"):
                    eliminar_alarma(alarmas_raw, id_alarma)
                    st.rerun()


def formulario_nueva_alarma(alarmas_raw):
    contador_key = "contador_nueva_alarma"
    if contador_key not in st.session_state:
        st.session_state[contador_key] = 0
    sufijo = st.session_state[contador_key]

    tipo = st.radio(
        "Tipo de alarma", [ETIQUETA_UNICA, ETIQUETA_RECURRENTE],
        key=f"tipo_nueva_{sufijo}", horizontal=True,
    )
    mensaje = st.text_input("Mensaje", value="", key=f"msg_nueva_{sufijo}")

    if tipo == ETIQUETA_UNICA:
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=datetime.now().date(), key=f"fecha_nueva_{sufijo}")
        with col2:
            hora = st.time_input("Hora", value=dtime(hour=8, minute=0), key=f"hora_nueva_{sufijo}")

        if st.button("➕ Agregar alarma", key=f"agregar_nueva_unica_{sufijo}"):
            if not mensaje.strip():
                st.error("El mensaje no puede estar vacío.")
            else:
                nueva = {
                    "id": nuevo_id_alarma(),
                    "mensaje": mensaje.strip(),
                    "tipo": "unica",
                    "dia": fecha.day,
                    "mes": fecha.month,
                    "anio": fecha.year,
                    "hora": hora.hour,
                    "minuto": hora.minute,
                    "segundo": 0,
                }
                guardar_json(ARCHIVO_ALARMAS, alarmas_raw + [nueva])
                st.session_state[contador_key] += 1
                st.success("✅ Alarma creada.")
                st.rerun()

    else:
        hora = st.time_input("Hora", value=dtime(hour=8, minute=0), key=f"hora_nueva_rec_{sufijo}")
        seleccion = st.multiselect(
            "Días", options=NOMBRES_ORDENADOS, default=[], key=f"dias_nueva_rec_{sufijo}"
        )

        if st.button("➕ Agregar alarma", key=f"agregar_nueva_rec_{sufijo}"):
            if not mensaje.strip():
                st.error("El mensaje no puede estar vacío.")
            elif not seleccion:
                st.error("Elegí al menos un día.")
            else:
                dias_nuevos = sorted(NOMBRE_A_INDICE[n] for n in seleccion)
                nueva = {
                    "id": nuevo_id_alarma(),
                    "mensaje": mensaje.strip(),
                    "tipo": "recurrente",
                    "hora": hora.hour,
                    "minuto": hora.minute,
                    "dias_semana": dias_nuevos,
                }
                guardar_json(ARCHIVO_ALARMAS, alarmas_raw + [nueva])
                st.session_state[contador_key] += 1
                st.success("✅ Alarma creada.")
                st.rerun()


# ---------------------------------------------------------
# Cálculo pastillas y eventos
# ---------------------------------------------------------
def proximo_datetime_pastilla(p, ahora):
    try:
        hora, minuto = map(int, p["hora"].split(":"))
    except (ValueError, KeyError):
        return None
    candidato = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if candidato <= ahora:
        candidato += timedelta(days=1)
    return candidato


def formatear_delta(delta):
    total_seg = int(delta.total_seconds())
    if total_seg < -60:
        return "Ya pasó"
    if total_seg < 0:
        total_seg = 0
    dias, resto = divmod(total_seg, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, _ = divmod(resto, 60)
    partes = []
    if dias:
        partes.append(f"{dias}d")
    if horas:
        partes.append(f"{horas}h")
    if minutos or not partes:
        partes.append(f"{minutos}m")
    return " ".join(partes)


def estado_por_urgencia(delta):
    seg = delta.total_seconds()
    if seg < -60:
        return "⚪ Pasado"
    horas = seg / 3600
    if horas < 1:
        return "🔴 Urgente"
    elif horas < 3:
        return "🟡 Pronto"
    else:
        return "🟢 A tiempo"


def eventos_de_hoy(alarmas_vigentes, pastillero_raw, ahora, color_pastillas):
    hoy = ahora.date()
    eventos = []

    for a in alarmas_vigentes:
        for fecha, hora_str in ocurrencias_alarma_en_rango(a, hoy, 1, ahora):
            hora, minuto = map(int, hora_str.split(":"))
            dt = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            delta = dt - ahora
            eventos.append({
                "Estado": estado_por_urgencia(delta),
                "Hora": hora_str,
                "Tipo": "⏰ Alarma",
                "Elemento": "—",
                "Descripción": a.get("mensaje", ""),
                "Faltan": formatear_delta(delta),
                "_sort": hora_str,
            })

    for p in pastillero_raw:
        try:
            hora, minuto = map(int, p["hora"].split(":"))
        except (ValueError, KeyError):
            continue
        dt = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        delta = dt - ahora
        letra = p.get("pastilla_letra", "?")
        _, emoji = color_pastillas.get(letra, (None, "⬛"))
        eventos.append({
            "Estado": estado_por_urgencia(delta),
            "Hora": p.get("hora", "?"),
            "Tipo": "💊 Pastilla",
            "Elemento": f"{emoji} {letra}",
            "Descripción": f"{p.get('pastilla_texto', '')} (x{p.get('cantidad', '')})",
            "Faltan": formatear_delta(delta),
            "_sort": p.get("hora", "?"),
        })

    eventos.sort(key=lambda e: e["_sort"])
    for e in eventos:
        del e["_sort"]
    return eventos


def mostrar_tabla_hoy(eventos):
    if not eventos:
        st.info("No hay nada programado para hoy.")
        return
    df = pd.DataFrame(eventos)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# Calendario semanal mejorado (Diseño en Tarjetas)
# ---------------------------------------------------------
def construir_calendario(alarmas_vigentes, pastillero_raw, fecha_inicio, color_pastillas, ahora, dias=7):
    calendario = {fecha_inicio + timedelta(days=i): [] for i in range(dias)}

    for a in alarmas_vigentes:
        for fecha, hora_str in ocurrencias_alarma_en_rango(a, fecha_inicio, dias, ahora):
            calendario[fecha].append({
                "hora": hora_str,
                "icono": "⏰",
                "desc": a.get("mensaje", ""),
                "acento": ACENTO_ALARMA,
            })

    for p in pastillero_raw:
        hora_str = p.get("hora", "")
        if not hora_str:
            continue
        letra = p.get("pastilla_letra", "?")
        hex_color, _ = color_pastillas.get(letra, ("#64748b", "⬛"))
        for i in range(dias):
            fecha = fecha_inicio + timedelta(days=i)
            calendario[fecha].append({
                "hora": hora_str,
                "icono": "💊",
                "desc": p.get("pastilla_texto", ""),
                "acento": hex_color,
            })

    for fecha in calendario:
        calendario[fecha].sort(key=lambda e: e["hora"])

    return calendario


def mostrar_calendario(calendario, fecha_inicio):
    columnas = st.columns(7)
    for i, col in enumerate(columnas):
        fecha = fecha_inicio + timedelta(days=i)
        nombre_dia = DIAS_SEMANA_NOMBRES[fecha.weekday()]
        es_hoy = fecha == fecha_inicio

        with col:
            bg_header = "#0284c7" if es_hoy else "#1e293b"
            border_header = "border: 2px solid #38bdf8;" if es_hoy else "border: 1px solid #334155;"
            
            st.markdown(
                f"<div style='{bg_header and f'background-color:{bg_header};'} {border_header} padding:8px; border-radius:8px 8px 0 0; text-align:center; margin-bottom:4px;'>"
                f"<b style='color:#ffffff; font-size:0.95em;'>{nombre_dia}</b><br>"
                f"<span style='color:#e2e8f0; font-size:0.8em;'>{fecha.strftime('%d/%m')}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            eventos = calendario[fecha]
            if not eventos:
                st.markdown(
                    f"<div style='background-color:#0f172a; padding:12px; border-radius:0 0 8px 8px; text-align:center; color:{COLOR_SIN_EVENTOS}; font-size:0.85em; border: 1px solid #334155; border-top: none;'>Sin eventos</div>",
                    unsafe_allow_html=True,
                )
            else:
                for e in eventos:
                    st.markdown(
                        f"<div style='background-color:#1e293b; "
                        f"border-left: 4px solid {e['acento']}; "
                        f"color:#f8fafc; "
                        f"padding:8px; border-radius:4px; margin-bottom:4px; font-size:0.85em; border-top: 1px solid #334155; border-right: 1px solid #334155; border-bottom: 1px solid #334155;'>"
                        f"<b>{e['icono']} {e['hora']}</b><br>"
                        f"<span style='color:#cbd5e1;'>{e['desc']}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )


# ---------------------------------------------------------
# Edición del pastillero
# ---------------------------------------------------------
LETRAS_DISPONIBLES = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
COLUMNAS_PASTILLERO = {
    "hora": "Hora",
    "pastilla_texto": "Pastilla",
    "pastilla_letra": "Letra",
    "cantidad": "Cantidad",
}


def hora_str_a_time(s):
    try:
        h, m = map(int, str(s).split(":"))
        return dtime(hour=h, minute=m)
    except (ValueError, AttributeError):
        return dtime(hour=8, minute=0)


def time_a_hora_str(t):
    if isinstance(t, dtime):
        return f"{t.hour:02d}:{t.minute:02d}"
    return "08:00"


def mostrar_editor_pastillero(pastillero_raw):
    st.caption(
        "Editá cualquier celda haciendo clic sobre ella. Usá el ➕ al pie de la tabla "
        "para agregar una pastilla nueva. Para **borrar** una pastilla, usá el selector "
        "de más abajo (es más fácil que hacerlo desde la tabla)."
    )

    if pastillero_raw:
        df = pd.DataFrame(pastillero_raw)[list(COLUMNAS_PASTILLERO.keys())]
    else:
        df = pd.DataFrame(columns=list(COLUMNAS_PASTILLERO.keys()))

    df = df.rename(columns=COLUMNAS_PASTILLERO)
    df["Hora"] = df["Hora"].apply(hora_str_a_time)
    if not df.empty:
        df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce").fillna(1).astype(int)
    else:
        df["Cantidad"] = df["Cantidad"].astype(int)

    df_editado = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_pastillero",
        column_config={
            "Hora": st.column_config.TimeColumn("Hora", format="HH:mm", step=60, required=True),
            "Pastilla": st.column_config.TextColumn(required=True),
            "Letra": st.column_config.SelectboxColumn(options=LETRAS_DISPONIBLES, required=True),
            "Cantidad": st.column_config.NumberColumn(min_value=1, max_value=10, step=1, required=True),
        },
    )

    if st.button("💾 Guardar cambios en el pastillero"):
        errores = []
        nuevos_registros = []

        for i, fila in df_editado.iterrows():
            texto = str(fila["Pastilla"]).strip()
            letra = str(fila["Letra"]).strip()

            if not texto or not letra or pd.isna(fila["Hora"]) or pd.isna(fila["Cantidad"]):
                errores.append(f"Fila {i + 1}: hay campos vacíos.")
                continue

            nuevos_registros.append({
                "hora": time_a_hora_str(fila["Hora"]),
                "pastilla_texto": texto,
                "pastilla_letra": letra,
                "cantidad": str(int(fila["Cantidad"])),
            })

        if errores:
            for e in errores:
                st.error(e)
        else:
            guardar_json(ARCHIVO_PASTILLERO, nuevos_registros)
            st.success("✅ Pastillero actualizado correctamente.")
            st.rerun()


def mostrar_borrado_pastillero(pastillero_raw):
    """
    Control explícito de borrado, aparte de la tabla editable:
    un selector con todas las pastillas actuales + un botón de eliminar.
    Evita depender del gesto poco intuitivo de seleccionar fila + basurero
    dentro de la tabla.
    """
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🗑️ Eliminar una pastilla")

    if not pastillero_raw:
        st.info("No hay pastillas cargadas todavía.")
        return

    def etiqueta(indice):
        p = pastillero_raw[indice]
        return f"{p.get('pastilla_letra', '?')} — {p.get('pastilla_texto', '')} a las {p.get('hora', '?')}"

    indice_elegido = st.selectbox(
        "Elegí la pastilla que querés borrar",
        options=list(range(len(pastillero_raw))),
        format_func=etiqueta,
        key="selector_borrar_pastilla",
    )

    if st.button("🗑️ Eliminar esta pastilla", key="boton_borrar_pastilla"):
        nueva_lista = [p for i, p in enumerate(pastillero_raw) if i != indice_elegido]
        guardar_json(ARCHIVO_PASTILLERO, nueva_lista)
        st.success("✅ Pastilla eliminada.")
        st.rerun()


# ---------------------------------------------------------
# Edición de la memoria de usuario
# ---------------------------------------------------------
def mostrar_editor_memoria(memoria):
    st.caption(
        "Editá cualquier valor haciendo clic sobre la celda. Usá el ➕ al pie de la tabla "
        "para agregar un dato nuevo. Para **borrar** un dato, usá el selector de más abajo."
    )

    if memoria:
        claves = list(memoria.keys())
        df = pd.DataFrame({"Clave": claves, "Valor": [str(memoria[c]) for c in claves]})
    else:
        df = pd.DataFrame(columns=["Clave", "Valor"])

    df_editado = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_memoria",
        column_config={
            "Clave": st.column_config.TextColumn(required=True),
            "Valor": st.column_config.TextColumn(required=True),
        },
    )

    if st.button("💾 Guardar cambios en memoria"):
        errores = []
        nueva_memoria = {}
        claves_vistas = set()

        for i, fila in df_editado.iterrows():
            clave = str(fila["Clave"]).strip()
            valor = str(fila["Valor"]).strip()

            if not clave or not valor:
                errores.append(f"Fila {i + 1}: hay campos vacíos.")
                continue
            if clave in claves_vistas:
                errores.append(f"Fila {i + 1}: la clave '{clave}' está repetida.")
                continue

            claves_vistas.add(clave)
            nueva_memoria[clave] = valor

        if errores:
            for e in errores:
                st.error(e)
        else:
            guardar_memoria(nueva_memoria)
            st.success("✅ Memoria actualizada correctamente.")
            st.rerun()


def mostrar_borrado_memoria(memoria):
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🗑️ Eliminar un dato")

    if not memoria:
        st.info("No hay datos guardados todavía.")
        return

    claves = list(memoria.keys())

    def etiqueta(clave):
        return f"{clave}: {memoria[clave]}"

    clave_elegida = st.selectbox(
        "Elegí el dato que querés borrar",
        options=claves,
        format_func=etiqueta,
        key="selector_borrar_memoria",
    )

    if st.button("🗑️ Eliminar este dato", key="boton_borrar_memoria"):
        nueva_memoria = {k: v for k, v in memoria.items() if k != clave_elegida}
        guardar_memoria(nueva_memoria)
        st.success("✅ Dato eliminado.")
        st.rerun()


def formulario_nuevo_dato_memoria(memoria):
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("➕ Agregar Dato Nuevo")

    contador_key = "contador_nuevo_dato_memoria"
    if contador_key not in st.session_state:
        st.session_state[contador_key] = 0
    sufijo = st.session_state[contador_key]

    clave = st.text_input("Clave", value="", key=f"clave_nueva_mem_{sufijo}")
    valor = st.text_input("Valor", value="", key=f"valor_nueva_mem_{sufijo}")

    if st.button("➕ Agregar dato", key=f"agregar_nuevo_dato_mem_{sufijo}"):
        clave_limpia = clave.strip()
        valor_limpio = valor.strip()
        if not clave_limpia or not valor_limpio:
            st.error("Completá la clave y el valor.")
        elif clave_limpia in memoria:
            st.error(f"Ya existe un dato con la clave '{clave_limpia}'. Editalo en la tabla de arriba.")
        else:
            nueva_memoria = dict(memoria)
            nueva_memoria[clave_limpia] = valor_limpio
            guardar_memoria(nueva_memoria)
            st.session_state[contador_key] += 1
            st.success("✅ Dato agregado.")
            st.rerun()


# ---------------------------------------------------------
# Interfaz Principal
# ---------------------------------------------------------
aplicar_estilos()

# Header superior
col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("🏠 Dashboard Asistente")
    st.caption(f"Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
with col_btn:
    st.write("")
    if st.button("🔄 Actualizar"):
        st.rerun()

ahora = datetime.now()
alarmas_raw = cargar_json(ARCHIVO_ALARMAS)
pastillero_raw = cargar_json(ARCHIVO_PASTILLERO)
memoria_usuario = cargar_memoria()
color_pastillas = asignar_colores_pastillas(pastillero_raw)
alarmas_vigentes = [a for a in alarmas_raw if not alarma_vencida(a, ahora)]

tab_vista, tab_pastillero, tab_alarmas, tab_memoria = st.tabs(
    ["📊 Vista general", "💊 Pastillero", "⏰ Alarmas", "🧠 Memoria"]
)

# ======================= TAB 1: VISTA GENERAL =======================
with tab_vista:
    proximas_alarmas = sorted(
        [(proximo_datetime_alarma(a, ahora), a) for a in alarmas_vigentes],
        key=lambda t: t[0] or datetime.max,
    )
    proximas_pastillas = sorted(
        [(proximo_datetime_pastilla(p, ahora), p) for p in pastillero_raw],
        key=lambda t: t[0] or datetime.max,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⏰ Alarmas activas", len(alarmas_vigentes))
    c2.metric("💊 Pastillas configuradas", len(pastillero_raw))

    if proximas_alarmas and proximas_alarmas[0][0] is not None:
        dt, a = proximas_alarmas[0]
        c3.metric("Próxima alarma", a.get("mensaje", ""), delta=f"en {formatear_delta(dt - ahora)}")
    else:
        c3.metric("Próxima alarma", "—")

    if proximas_pastillas and proximas_pastillas[0][0] is not None:
        dt, p = proximas_pastillas[0]
        c4.metric("Próxima pastilla", p.get("pastilla_texto", ""), delta=f"en {formatear_delta(dt - ahora)}")
    else:
        c4.metric("Próxima pastilla", "—")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("📍 Eventos de Hoy")
    eventos_hoy = eventos_de_hoy(alarmas_vigentes, pastillero_raw, ahora, color_pastillas)
    mostrar_tabla_hoy(eventos_hoy)

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("🗓️ Calendario Semanal")
    calendario = construir_calendario(alarmas_vigentes, pastillero_raw, ahora.date(), color_pastillas, ahora, dias=7)
    mostrar_calendario(calendario, ahora.date())

# ======================= TAB 2: PASTILLERO =======================
with tab_pastillero:
    st.header("✏️ Gestión de Pastillero")
    mostrar_editor_pastillero(pastillero_raw)
    mostrar_borrado_pastillero(pastillero_raw)

# ======================= TAB 3: ALARMAS =======================
with tab_alarmas:
    st.header("⏰ Alarmas Programadas")
    mostrar_tabla_alarmas(alarmas_vigentes, ahora)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("✏️ Editar o Eliminar Alarmas")
    mostrar_editor_alarmas(alarmas_vigentes, alarmas_raw, ahora)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("➕ Agregar Nueva Alarma")
    formulario_nueva_alarma(alarmas_raw)

# ======================= TAB 4: MEMORIA =======================
with tab_memoria:
    st.header("🧠 Memoria del Usuario")
    st.caption("Datos que el asistente fue guardando sobre el usuario durante las conversaciones.")
    mostrar_editor_memoria(memoria_usuario)
    mostrar_borrado_memoria(memoria_usuario)
    formulario_nuevo_dato_memoria(memoria_usuario)