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

# Nombres amigables para los tipos (solo para mostrar en pantalla;
# el JSON sigue guardando internamente "unica" / "recurrente").
ETIQUETA_UNICA = "📅 Una vez"
ETIQUETA_RECURRENTE = "🔁 Se repite"

LETRAS_DISPONIBLES = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# ---------------------------------------------------------
# PALETA DE COLORES MODERNA
# ---------------------------------------------------------
ACENTO_ALARMA = "#3b82f6"       # Azul moderno
FONDO_TARJETA_EVENTO = "#1e293b"
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
# Pastillero: carga con migración del formato viejo
# ---------------------------------------------------------
def migrar_item_pastilla(item):
    """Convierte una entrada del formato viejo ({"hora": "08:00", ...}) al
    formato nuevo (igual al de alarmas.json). Devuelve (item_o_None, hubo_cambio)."""
    if not isinstance(item, dict):
        return None, True

    if "tipo" in item:
        cambio = False
        if not item.get("id"):
            item["id"] = uuid.uuid4().hex[:8]
            cambio = True
        if "mensaje" not in item:
            item["mensaje"] = item.get("pastilla_texto", "")
            cambio = True
        return item, cambio

    # Formato viejo
    try:
        hh, mm = str(item.get("hora", "")).split(":")
        hora, minuto = int(hh), int(mm)
    except ValueError:
        return None, True  # entrada corrupta, se descarta

    texto = item.get("pastilla_texto", "")
    nuevo = {
        "id": uuid.uuid4().hex[:8],
        "mensaje": texto,
        "tipo": "recurrente",
        "hora": hora,
        "minuto": minuto,
        "dias_semana": [0, 1, 2, 3, 4, 5, 6],
        "pastilla_texto": texto,
        "pastilla_letra": str(item.get("pastilla_letra", "")).upper(),
        "cantidad": str(item.get("cantidad", "1")),
    }
    return nuevo, True


def cargar_pastillero():
    datos = cargar_json(ARCHIVO_PASTILLERO)
    if not isinstance(datos, list):
        return []

    resultado = []
    hubo_cambios = False
    for item in datos:
        nuevo, cambio = migrar_item_pastilla(item)
        hubo_cambios = hubo_cambios or cambio
        if nuevo is not None:
            resultado.append(nuevo)

    if hubo_cambios:
        guardar_json(ARCHIVO_PASTILLERO, resultado)
    return resultado


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
# LÓGICA DE TIEMPO (sirve tanto para alarmas como para pastillas,
# porque ahora usan el mismo formato)
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


def time_de_item(item, defecto=dtime(hour=8, minute=0)):
    """Devuelve un datetime.time a partir de los campos hora/minuto de un item."""
    try:
        return dtime(hour=int(item.get("hora", defecto.hour)), minute=int(item.get("minuto", defecto.minute)))
    except (ValueError, TypeError):
        return defecto


# ===========================================================
# ALARMAS: TABLA, EDICIÓN Y ALTA
# ===========================================================

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
    hora_defecto = time_de_item(a)
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


# ===========================================================
# PASTILLERO: TABLA, EDICIÓN Y ALTA
# ===========================================================

def formatear_pastilla_para_tabla(p, ahora, color_pastillas):
    tipo = p.get("tipo", "?")
    tipo_mostrado = {"unica": ETIQUETA_UNICA, "recurrente": ETIQUETA_RECURRENTE}.get(tipo, tipo)
    letra = p.get("pastilla_letra", "?")
    _, emoji = color_pastillas.get(letra, (None, "⬛"))
    proxima = proximo_datetime_alarma(p, ahora)

    return {
        "Letra": f"{emoji} {letra}",
        "Pastilla": p.get("pastilla_texto", ""),
        "Cantidad": p.get("cantidad", ""),
        "Tipo": tipo_mostrado,
        "Cuándo": texto_cuando_alarma(p),
        "Próxima vez": proxima.strftime("%d/%m/%Y %H:%M") if proxima else "—",
        "_sort": proxima or datetime.max,
    }


def mostrar_tabla_pastillero(pastillero_vigente, ahora, color_pastillas):
    if not pastillero_vigente:
        st.info("No hay pastillas programadas.")
        return
    filas = [formatear_pastilla_para_tabla(p, ahora, color_pastillas) for p in pastillero_vigente]
    filas.sort(key=lambda f: f["_sort"])
    for f in filas:
        del f["_sort"]
    df = pd.DataFrame(filas)
    st.dataframe(df, use_container_width=True, hide_index=True)


def guardar_pastilla_editada(pastillero_raw, id_pastilla, nuevos_campos):
    nueva_lista = [
        nuevos_campos if p.get("id") == id_pastilla else p
        for p in pastillero_raw
    ]
    guardar_json(ARCHIVO_PASTILLERO, nueva_lista)


def eliminar_pastilla(pastillero_raw, id_pastilla):
    nueva_lista = [p for p in pastillero_raw if p.get("id") != id_pastilla]
    guardar_json(ARCHIVO_PASTILLERO, nueva_lista)


def _cantidad_a_int(valor):
    try:
        return max(1, min(10, int(valor)))
    except (ValueError, TypeError):
        return 1


def tarjeta_edicion_pastilla(p, pastillero_raw, ahora):
    id_p = p.get("id", "")
    tipo = p.get("tipo")
    es_unica = tipo == "unica"

    etiqueta_tipo = ETIQUETA_UNICA if es_unica else ETIQUETA_RECURRENTE
    st.caption(f"🔖 Tipo: **{etiqueta_tipo}**")

    col_a, col_b, col_c = st.columns([3, 1, 1])
    with col_a:
        texto = st.text_input("Pastilla", value=p.get("pastilla_texto", ""), key=f"pst_texto_{id_p}")
    with col_b:
        letra_actual = str(p.get("pastilla_letra", "A")).upper()
        indice_letra = LETRAS_DISPONIBLES.index(letra_actual) if letra_actual in LETRAS_DISPONIBLES else 0
        letra = st.selectbox("Letra", LETRAS_DISPONIBLES, index=indice_letra, key=f"pst_letra_{id_p}")
    with col_c:
        cantidad = st.number_input(
            "Cantidad", min_value=1, max_value=10, step=1,
            value=_cantidad_a_int(p.get("cantidad", 1)), key=f"pst_cant_{id_p}",
        )

    if es_unica:
        dt_actual = calcular_dt_unica(p)
        fecha_defecto = dt_actual.date() if dt_actual else ahora.date()
        hora_defecto = dt_actual.time().replace(second=0, microsecond=0) if dt_actual else dtime(hour=8, minute=0)

        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=fecha_defecto, key=f"pst_fecha_{id_p}")
        with col2:
            hora = st.time_input("Hora", value=hora_defecto, key=f"pst_hora_u_{id_p}")

        if datetime.combine(fecha, hora) < ahora:
            st.warning("⚠️ Esa fecha y hora ya pasaron.")
        seleccion = None
    else:
        hora = st.time_input("Hora", value=time_de_item(p), key=f"pst_hora_r_{id_p}")
        nombres_actuales = [DIAS_SEMANA_NOMBRES[d] for d in sorted(p.get("dias_semana") or []) if d in DIAS_SEMANA_NOMBRES]
        seleccion = st.multiselect(
            "Días", options=NOMBRES_ORDENADOS, default=nombres_actuales, key=f"pst_dias_{id_p}"
        )

    st.caption("El tipo no se puede cambiar acá. Para eso, eliminá esta pastilla y creá una nueva.")

    col_guardar, col_eliminar = st.columns(2)
    with col_guardar:
        if st.button("💾 Guardar cambios", key=f"pst_guardar_{id_p}"):
            if not texto.strip():
                st.error("El nombre de la pastilla no puede estar vacío.")
            elif not es_unica and not seleccion:
                st.error("Elegí al menos un día.")
            else:
                nuevos_campos = {
                    "id": id_p,
                    "mensaje": texto.strip(),
                    "tipo": "unica" if es_unica else "recurrente",
                    "pastilla_texto": texto.strip(),
                    "pastilla_letra": letra,
                    "cantidad": str(int(cantidad)),
                }
                if es_unica:
                    nuevos_campos.update({
                        "dia": fecha.day, "mes": fecha.month, "anio": fecha.year,
                        "hora": hora.hour, "minuto": hora.minute, "segundo": 0,
                    })
                else:
                    nuevos_campos.update({
                        "hora": hora.hour, "minuto": hora.minute,
                        "dias_semana": sorted(NOMBRE_A_INDICE[n] for n in seleccion),
                    })
                guardar_pastilla_editada(pastillero_raw, id_p, nuevos_campos)
                st.success("✅ Pastilla actualizada.")
                st.rerun()
    with col_eliminar:
        if st.button("🗑️ Eliminar", key=f"pst_eliminar_{id_p}"):
            eliminar_pastilla(pastillero_raw, id_p)
            st.success("Pastilla eliminada.")
            st.rerun()


def mostrar_editor_pastillero(pastillero_vigente, pastillero_raw, ahora, color_pastillas):
    if not pastillero_vigente:
        st.info("No hay pastillas para editar.")
        return

    ordenadas = sorted(
        pastillero_vigente,
        key=lambda p: proximo_datetime_alarma(p, ahora) or datetime.max,
    )

    for p in ordenadas:
        id_p = p.get("id", "")
        letra = p.get("pastilla_letra", "?")
        _, emoji = color_pastillas.get(letra, (None, "⬛"))
        titulo = f"{emoji} {letra} — {p.get('pastilla_texto', '(sin nombre)')} — {texto_cuando_alarma(p)}"

        with st.expander(titulo):
            if p.get("tipo") in ("unica", "recurrente"):
                tarjeta_edicion_pastilla(p, pastillero_raw, ahora)
            else:
                st.warning("Esta entrada tiene un tipo desconocido.")
                if st.button("🗑️ Eliminar", key=f"pst_borrar_desconocida_{id_p}"):
                    eliminar_pastilla(pastillero_raw, id_p)
                    st.rerun()


def formulario_nueva_pastilla(pastillero_raw):
    contador_key = "contador_nueva_pastilla"
    if contador_key not in st.session_state:
        st.session_state[contador_key] = 0
    sufijo = st.session_state[contador_key]

    tipo = st.radio(
        "Tipo de pastilla", [ETIQUETA_UNICA, ETIQUETA_RECURRENTE],
        key=f"pst_tipo_nueva_{sufijo}", horizontal=True,
    )

    col_a, col_b, col_c = st.columns([3, 1, 1])
    with col_a:
        texto = st.text_input("Pastilla (ej: Pastilla para la presión)", value="", key=f"pst_texto_nueva_{sufijo}")
    with col_b:
        letra = st.selectbox("Letra", LETRAS_DISPONIBLES, key=f"pst_letra_nueva_{sufijo}")
    with col_c:
        cantidad = st.number_input(
            "Cantidad", min_value=1, max_value=10, step=1, value=1, key=f"pst_cant_nueva_{sufijo}"
        )

    if tipo == ETIQUETA_UNICA:
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=datetime.now().date(), key=f"pst_fecha_nueva_{sufijo}")
        with col2:
            hora = st.time_input("Hora", value=dtime(hour=8, minute=0), key=f"pst_hora_nueva_u_{sufijo}")

        if st.button("➕ Agregar pastilla", key=f"pst_agregar_unica_{sufijo}"):
            if not texto.strip():
                st.error("El nombre de la pastilla no puede estar vacío.")
            else:
                nueva = {
                    "id": nuevo_id_alarma(),
                    "mensaje": texto.strip(),
                    "tipo": "unica",
                    "dia": fecha.day,
                    "mes": fecha.month,
                    "anio": fecha.year,
                    "hora": hora.hour,
                    "minuto": hora.minute,
                    "segundo": 0,
                    "pastilla_texto": texto.strip(),
                    "pastilla_letra": letra,
                    "cantidad": str(int(cantidad)),
                }
                guardar_json(ARCHIVO_PASTILLERO, pastillero_raw + [nueva])
                st.session_state[contador_key] += 1
                st.success("✅ Pastilla agregada.")
                st.rerun()

    else:
        hora = st.time_input("Hora", value=dtime(hour=8, minute=0), key=f"pst_hora_nueva_r_{sufijo}")
        seleccion = st.multiselect(
            "Días", options=NOMBRES_ORDENADOS, default=NOMBRES_ORDENADOS, key=f"pst_dias_nueva_{sufijo}"
        )

        if st.button("➕ Agregar pastilla", key=f"pst_agregar_rec_{sufijo}"):
            if not texto.strip():
                st.error("El nombre de la pastilla no puede estar vacío.")
            elif not seleccion:
                st.error("Elegí al menos un día.")
            else:
                nueva = {
                    "id": nuevo_id_alarma(),
                    "mensaje": texto.strip(),
                    "tipo": "recurrente",
                    "hora": hora.hour,
                    "minuto": hora.minute,
                    "dias_semana": sorted(NOMBRE_A_INDICE[n] for n in seleccion),
                    "pastilla_texto": texto.strip(),
                    "pastilla_letra": letra,
                    "cantidad": str(int(cantidad)),
                }
                guardar_json(ARCHIVO_PASTILLERO, pastillero_raw + [nueva])
                st.session_state[contador_key] += 1
                st.success("✅ Pastilla agregada.")
                st.rerun()


def mostrar_limpieza_vencidas(pastillero_raw, ahora):
    vencidas = [p for p in pastillero_raw if alarma_vencida(p, ahora)]
    if not vencidas:
        return
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(
        f"Hay {len(vencidas)} pastilla(s) de una sola vez que ya pasaron. "
        "No se muestran en el dashboard, pero siguen guardadas en config.json."
    )
    if st.button("🧹 Borrar pastillas únicas vencidas", key="pst_limpiar_vencidas"):
        restantes = [p for p in pastillero_raw if not alarma_vencida(p, ahora)]
        guardar_json(ARCHIVO_PASTILLERO, restantes)
        st.success("✅ Pastillas vencidas eliminadas.")
        st.rerun()


# ---------------------------------------------------------
# Eventos de hoy
# ---------------------------------------------------------
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


def eventos_de_hoy(alarmas_vigentes, pastillero_vigente, ahora, color_pastillas):
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

    for p in pastillero_vigente:
        letra = p.get("pastilla_letra", "?")
        _, emoji = color_pastillas.get(letra, (None, "⬛"))
        for fecha, hora_str in ocurrencias_alarma_en_rango(p, hoy, 1, ahora):
            hora, minuto = map(int, hora_str.split(":"))
            dt = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            delta = dt - ahora
            eventos.append({
                "Estado": estado_por_urgencia(delta),
                "Hora": hora_str,
                "Tipo": "💊 Pastilla",
                "Elemento": f"{emoji} {letra}",
                "Descripción": f"{p.get('pastilla_texto', '')} (x{p.get('cantidad', '')})",
                "Faltan": formatear_delta(delta),
                "_sort": hora_str,
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
# Calendario semanal (Diseño en Tarjetas)
# ---------------------------------------------------------
def construir_calendario(alarmas_vigentes, pastillero_vigente, fecha_inicio, color_pastillas, ahora, dias=7):
    calendario = {fecha_inicio + timedelta(days=i): [] for i in range(dias)}

    for a in alarmas_vigentes:
        for fecha, hora_str in ocurrencias_alarma_en_rango(a, fecha_inicio, dias, ahora):
            calendario[fecha].append({
                "hora": hora_str,
                "icono": "⏰",
                "desc": a.get("mensaje", ""),
                "acento": ACENTO_ALARMA,
            })

    for p in pastillero_vigente:
        letra = p.get("pastilla_letra", "?")
        hex_color, _ = color_pastillas.get(letra, ("#64748b", "⬛"))
        for fecha, hora_str in ocurrencias_alarma_en_rango(p, fecha_inicio, dias, ahora):
            calendario[fecha].append({
                "hora": hora_str,
                "icono": "💊",
                "desc": f"{letra} · {p.get('pastilla_texto', '')}",
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
                f"<div style='background-color:{bg_header}; {border_header} padding:8px; border-radius:8px 8px 0 0; text-align:center; margin-bottom:4px;'>"
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
if not isinstance(alarmas_raw, list):
    alarmas_raw = []
pastillero_raw = cargar_pastillero()
memoria_usuario = cargar_memoria()
color_pastillas = asignar_colores_pastillas(pastillero_raw)
alarmas_vigentes = [a for a in alarmas_raw if not alarma_vencida(a, ahora)]
pastillero_vigente = [p for p in pastillero_raw if not alarma_vencida(p, ahora)]

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
        [(proximo_datetime_alarma(p, ahora), p) for p in pastillero_vigente],
        key=lambda t: t[0] or datetime.max,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⏰ Alarmas activas", len(alarmas_vigentes))
    c2.metric("💊 Pastillas configuradas", len(pastillero_vigente))

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
    eventos_hoy = eventos_de_hoy(alarmas_vigentes, pastillero_vigente, ahora, color_pastillas)
    mostrar_tabla_hoy(eventos_hoy)

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("🗓️ Calendario Semanal")
    calendario = construir_calendario(
        alarmas_vigentes, pastillero_vigente, ahora.date(), color_pastillas, ahora, dias=7
    )
    mostrar_calendario(calendario, ahora.date())

# ======================= TAB 2: PASTILLERO =======================
with tab_pastillero:
    st.header("💊 Pastillas Programadas")
    mostrar_tabla_pastillero(pastillero_vigente, ahora, color_pastillas)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("✏️ Editar o Eliminar Pastillas")
    mostrar_editor_pastillero(pastillero_vigente, pastillero_raw, ahora, color_pastillas)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("➕ Agregar Nueva Pastilla")
    formulario_nueva_pastilla(pastillero_raw)

    mostrar_limpieza_vencidas(pastillero_raw, ahora)

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