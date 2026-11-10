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
ARCHIVO_MENSAJES = "mensajes.json"

st.set_page_config(
    page_title="Dashboard Asistente",
    layout="wide",
    page_icon="🏠"
)

DIAS_SEMANA_NOMBRES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}
NOMBRES_ORDENADOS = [DIAS_SEMANA_NOMBRES[i] for i in range(7)]
NOMBRE_A_INDICE = {v: k for k, v in DIAS_SEMANA_NOMBRES.items()}

ETIQUETA_UNICA = "📅 Una vez"
ETIQUETA_RECURRENTE = "🔁 Se repite"

LETRAS_DISPONIBLES = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# ---------------------------------------------------------
# PALETA DE COLORES
# ---------------------------------------------------------
ACENTO_ALARMA = "#3b82f6"
FONDO_TARJETA_EVENTO = "#1e293b"
COLOR_TEXTO_EVENTO = "#f8fafc"
COLOR_NOMBRE_DIA = "#38bdf8"
COLOR_FECHA_DIA = "#94a3b8"
COLOR_SIN_EVENTOS = "#64748b"

PALETA_PASTILLAS = [
    ("#8b5cf6", "🟪"),
    ("#10b981", "🟩"),
    ("#f59e0b", "🟧"),
    ("#0ea5e9", "🟦"),
    ("#f43f5e", "🟥"),
    ("#eab308", "🟨"),
    ("#64748b", "⬛"),
]


# ---------------------------------------------------------
# CSS global
# ---------------------------------------------------------
def aplicar_estilos():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

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

        .stDataFrame {
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #334155;
        }

        .stButton>button {
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.2s ease;
        }

        .stButton>button:hover {
            border-color: #38bdf8;
            color: #38bdf8;
        }

        .streamlit-expanderHeader {
            background-color: #1e293b;
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Carga y guardado de archivos
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
# Mensajes del dispensador
# ---------------------------------------------------------
def cargar_mensajes_dispensador():
    datos = cargar_json(ARCHIVO_MENSAJES)

    if not isinstance(datos, list):
        return []

    mensajes = []

    for indice, item in enumerate(datos):
        if not isinstance(item, dict):
            continue

        texto = item.get("mensaje")
        if not isinstance(texto, str) or not texto.strip():
            continue

        timestamp = str(item.get("timestamp") or "").strip()

        try:
            fecha = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            fecha = None

        mensajes.append({
            "mensaje": texto.strip(),
            "timestamp": timestamp,
            "fecha": fecha,
            "indice": indice,
        })

    # Los mensajes con fecha válida quedan en orden cronológico.
    mensajes.sort(
        key=lambda item: (
            item["fecha"] is not None,
            item["fecha"] or datetime.min,
            item["indice"],
        )
    )

    return mensajes


def formatear_fecha_mensaje(item):
    if item["fecha"] is not None:
        return item["fecha"].strftime("%d/%m/%Y %H:%M:%S")

    return item["timestamp"] or "Fecha no disponible"


def mostrar_mensajes_dispensador(mensajes):
    st.header("🚨 Mensajes del dispensador")
    st.caption(
        "Los mensajes iguales están agrupados. "
        "Podés abrir el detalle para ver cada registro individual."
    )

    if not mensajes:
        st.info("Todavía no hay mensajes del dispensador.")
        return

    busqueda = st.text_input(
        "Buscar mensaje",
        key="busqueda_mensajes_dispensador",
        placeholder="Por ejemplo: faltan, excedente, retiro...",
    ).strip().casefold()

    if busqueda:
        mensajes_filtrados = [
            item
            for item in mensajes
            if busqueda in item["mensaje"].casefold()
        ]
    else:
        mensajes_filtrados = mensajes

    if not mensajes_filtrados:
        st.info("No hay mensajes que coincidan con la búsqueda.")
        return

    grupos = {}

    for item in mensajes_filtrados:
        grupos.setdefault(item["mensaje"], []).append(item)

    grupos_ordenados = sorted(
        grupos.items(),
        key=lambda grupo: grupo[1][-1]["fecha"] or datetime.min,
        reverse=True,
    )

    filas = []

    for texto, ocurrencias in grupos_ordenados:
        filas.append({
            "Última vez": formatear_fecha_mensaje(ocurrencias[-1]),
            "Repeticiones": len(ocurrencias),
            "Mensaje": texto,
            "Primera vez": (
                formatear_fecha_mensaje(ocurrencias[0])
                if len(ocurrencias) > 1
                else "—"
            ),
        })

    st.dataframe(
        pd.DataFrame(filas),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Ver los últimos 200 registros individuales"):
        recientes = list(reversed(mensajes_filtrados[-200:]))

        detalle = [
            {
                "Fecha": formatear_fecha_mensaje(item),
                "Mensaje": item["mensaje"],
            }
            for item in recientes
        ]

        st.dataframe(
            pd.DataFrame(detalle),
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# Pastillero: carga con migración del formato viejo
# ---------------------------------------------------------
def migrar_item_pastilla(item):
    """Convierte una entrada vieja al formato nuevo."""
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

    try:
        hh, mm = str(item.get("hora", "")).split(":")
        hora, minuto = int(hh), int(mm)
    except (ValueError, TypeError):
        return None, True

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
    letras = sorted({
        p.get("pastilla_letra", "?")
        for p in pastillero_raw
    })

    mapa = {}

    for i, letra in enumerate(letras):
        mapa[letra] = PALETA_PASTILLAS[i % len(PALETA_PASTILLAS)]

    return mapa


# ===========================================================
# Lógica de tiempo
# ===========================================================
def nuevo_id_alarma():
    return uuid.uuid4().hex[:8]


def calcular_dt_unica(item):
    try:
        return datetime(
            int(item["anio"]),
            int(item["mes"]),
            int(item["dia"]),
            int(item.get("hora", 0)),
            int(item.get("minuto", 0)),
            int(item.get("segundo", 0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def alarma_vencida(item, ahora):
    if item.get("tipo") != "unica":
        return False

    fecha_hora = calcular_dt_unica(item)

    if fecha_hora is None:
        return False

    return fecha_hora < ahora


def texto_cuando_alarma(item):
    tipo = item.get("tipo")

    if tipo == "unica":
        fecha_hora = calcular_dt_unica(item)

        if fecha_hora is None:
            return "⚠️ Datos inválidos"

        dia_semana = DIAS_SEMANA_NOMBRES[fecha_hora.weekday()]

        return (
            f"{dia_semana} "
            f"{fecha_hora.strftime('%d/%m/%Y')} "
            f"a las {fecha_hora.strftime('%H:%M')}"
        )

    if tipo == "recurrente":
        hora = item.get("hora")
        minuto = item.get("minuto")
        dias_semana = sorted(item.get("dias_semana") or [])

        if hora is None or minuto is None:
            return "⚠️ Datos inválidos"

        if not dias_semana:
            return "⚠️ Sin días configurados"

        if len(dias_semana) == 7:
            return f"Todos los días a las {hora:02d}:{minuto:02d}"

        nombres = ", ".join(
            DIAS_SEMANA_NOMBRES.get(dia, "?")
            for dia in dias_semana
        )

        return f"{nombres} a las {hora:02d}:{minuto:02d}"

    return f"⚠️ Tipo desconocido ({tipo})"


def proximo_datetime_alarma(item, ahora):
    tipo = item.get("tipo")

    if tipo == "unica":
        fecha_hora = calcular_dt_unica(item)

        if fecha_hora is None or fecha_hora < ahora:
            return None

        return fecha_hora

    if tipo == "recurrente":
        hora = item.get("hora")
        minuto = item.get("minuto")
        dias_semana = item.get("dias_semana") or []

        if hora is None or minuto is None or not dias_semana:
            return None

        mejor = None

        for dia in dias_semana:
            candidato = ahora.replace(
                hour=hora,
                minute=minuto,
                second=0,
                microsecond=0,
            )

            delta_dias = (dia - ahora.weekday()) % 7
            candidato += timedelta(days=delta_dias)

            if candidato <= ahora:
                candidato += timedelta(days=7)

            if mejor is None or candidato < mejor:
                mejor = candidato

        return mejor

    return None


def ocurrencias_alarma_en_rango(item, fecha_inicio, dias, ahora):
    tipo = item.get("tipo")
    resultado = []

    if tipo == "unica":
        fecha_hora = calcular_dt_unica(item)

        if fecha_hora is None or fecha_hora < ahora:
            return []

        if fecha_inicio <= fecha_hora.date() < fecha_inicio + timedelta(days=dias):
            resultado.append((
                fecha_hora.date(),
                fecha_hora.strftime("%H:%M"),
            ))

    elif tipo == "recurrente":
        hora = item.get("hora")
        minuto = item.get("minuto")
        dias_semana = item.get("dias_semana") or []

        if hora is None or minuto is None:
            return []

        for i in range(dias):
            fecha = fecha_inicio + timedelta(days=i)

            if fecha.weekday() in dias_semana:
                resultado.append((
                    fecha,
                    f"{hora:02d}:{minuto:02d}",
                ))

    return resultado


def time_de_item(item, defecto=dtime(hour=8, minute=0)):
    """Devuelve un datetime.time a partir de los campos hora/minuto."""
    try:
        return dtime(
            hour=int(item.get("hora", defecto.hour)),
            minute=int(item.get("minuto", defecto.minute)),
        )
    except (ValueError, TypeError):
        return defecto


# ===========================================================
# Alarmas: tabla, edición y alta
# ===========================================================
def formatear_alarma_para_tabla(item, ahora):
    tipo = item.get("tipo", "?")

    tipo_mostrado = {
        "unica": ETIQUETA_UNICA,
        "recurrente": ETIQUETA_RECURRENTE,
    }.get(tipo, tipo)

    cuando = texto_cuando_alarma(item)
    proxima = proximo_datetime_alarma(item, ahora)

    return {
        "Mensaje": item.get("mensaje", ""),
        "Tipo": tipo_mostrado,
        "Cuándo": cuando,
        "Próxima vez": (
            proxima.strftime("%d/%m/%Y %H:%M")
            if proxima
            else "—"
        ),
        "_sort": proxima or datetime.max,
    }


def mostrar_tabla_alarmas(alarmas_vigentes, ahora):
    if not alarmas_vigentes:
        st.info("No hay alarmas programadas.")
        return

    filas = [
        formatear_alarma_para_tabla(item, ahora)
        for item in alarmas_vigentes
    ]

    filas.sort(key=lambda fila: fila["_sort"])

    for fila in filas:
        del fila["_sort"]

    st.dataframe(
        pd.DataFrame(filas),
        use_container_width=True,
        hide_index=True,
    )


def guardar_alarma_editada(alarmas_raw, id_alarma, nuevos_campos):
    nueva_lista = [
        nuevos_campos if item.get("id") == id_alarma else item
        for item in alarmas_raw
    ]

    guardar_json(ARCHIVO_ALARMAS, nueva_lista)


def eliminar_alarma(alarmas_raw, id_alarma):
    nueva_lista = [
        item for item in alarmas_raw
        if item.get("id") != id_alarma
    ]

    guardar_json(ARCHIVO_ALARMAS, nueva_lista)


def tarjeta_edicion_unica(item, alarmas_raw, ahora):
    id_alarma = item.get("id", "")
    dt_actual = calcular_dt_unica(item)

    fecha_defecto = dt_actual.date() if dt_actual else ahora.date()
    hora_defecto = dt_actual.time() if dt_actual else dtime(hour=8, minute=0)

    st.caption(f"🔖 Tipo: **{ETIQUETA_UNICA}**")

    mensaje = st.text_input(
        "Mensaje",
        value=item.get("mensaje", ""),
        key=f"msg_unica_{id_alarma}",
    )

    col1, col2 = st.columns(2)

    with col1:
        fecha = st.date_input(
            "Fecha",
            value=fecha_defecto,
            key=f"fecha_unica_{id_alarma}",
        )

    with col2:
        hora = st.time_input(
            "Hora",
            value=hora_defecto,
            key=f"hora_unica_{id_alarma}",
        )

    st.caption(
        "El tipo no se puede cambiar acá. "
        "Para eso, eliminá esta alarma y creá una nueva."
    )

    dt_resultante = datetime.combine(fecha, hora)

    if dt_resultante < ahora:
        st.warning("⚠️ Esa fecha y hora ya pasaron.")

    col_guardar, col_eliminar = st.columns(2)

    with col_guardar:
        if st.button(
            "💾 Guardar cambios",
            key=f"guardar_unica_{id_alarma}",
        ):
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

                guardar_alarma_editada(
                    alarmas_raw,
                    id_alarma,
                    nuevos_campos,
                )

                st.success("✅ Alarma actualizada.")
                st.rerun()

    with col_eliminar:
        if st.button(
            "🗑️ Eliminar",
            key=f"eliminar_unica_{id_alarma}",
        ):
            eliminar_alarma(alarmas_raw, id_alarma)
            st.success("Alarma eliminada.")
            st.rerun()


def tarjeta_edicion_recurrente(item, alarmas_raw, ahora):
    id_alarma = item.get("id", "")
    hora_defecto = time_de_item(item)
    dias_actuales = sorted(item.get("dias_semana") or [])

    nombres_actuales = [
        DIAS_SEMANA_NOMBRES[dia]
        for dia in dias_actuales
    ]

    st.caption(f"🔖 Tipo: **{ETIQUETA_RECURRENTE}**")

    mensaje = st.text_input(
        "Mensaje",
        value=item.get("mensaje", ""),
        key=f"msg_rec_{id_alarma}",
    )

    hora = st.time_input(
        "Hora",
        value=hora_defecto,
        key=f"hora_rec_{id_alarma}",
    )

    seleccion = st.multiselect(
        "Días",
        options=NOMBRES_ORDENADOS,
        default=nombres_actuales,
        key=f"dias_rec_{id_alarma}",
    )

    st.caption(
        "El tipo no se puede cambiar acá. "
        "Para eso, eliminá esta alarma y creá una nueva."
    )

    col_guardar, col_eliminar = st.columns(2)

    with col_guardar:
        if st.button(
            "💾 Guardar cambios",
            key=f"guardar_rec_{id_alarma}",
        ):
            if not mensaje.strip():
                st.error("El mensaje no puede estar vacío.")
            elif not seleccion:
                st.error("Elegí al menos un día.")
            else:
                dias_nuevos = sorted(
                    NOMBRE_A_INDICE[nombre]
                    for nombre in seleccion
                )

                nuevos_campos = {
                    "id": id_alarma,
                    "mensaje": mensaje.strip(),
                    "tipo": "recurrente",
                    "hora": hora.hour,
                    "minuto": hora.minute,
                    "dias_semana": dias_nuevos,
                }

                guardar_alarma_editada(
                    alarmas_raw,
                    id_alarma,
                    nuevos_campos,
                )

                st.success("✅ Alarma actualizada.")
                st.rerun()

    with col_eliminar:
        if st.button(
            "🗑️ Eliminar",
            key=f"eliminar_rec_{id_alarma}",
        ):
            eliminar_alarma(alarmas_raw, id_alarma)
            st.success("Alarma eliminada.")
            st.rerun()


def mostrar_editor_alarmas(alarmas_vigentes, alarmas_raw, ahora):
    if not alarmas_vigentes:
        st.info("No hay alarmas para editar.")
        return

    ordenadas = sorted(
        alarmas_vigentes,
        key=lambda item: proximo_datetime_alarma(item, ahora) or datetime.max,
    )

    for item in ordenadas:
        id_alarma = item.get("id", "")
        tipo = item.get("tipo")

        titulo = (
            f"{item.get('mensaje', '(sin mensaje)')} — "
            f"{texto_cuando_alarma(item)}"
        )

        with st.expander(titulo):
            if tipo == "unica":
                tarjeta_edicion_unica(item, alarmas_raw, ahora)

            elif tipo == "recurrente":
                tarjeta_edicion_recurrente(item, alarmas_raw, ahora)

            else:
                if st.button(
                    "🗑️ Eliminar",
                    key=f"borrar_desconocida_{id_alarma}",
                ):
                    eliminar_alarma(alarmas_raw, id_alarma)
                    st.rerun()


def formulario_nueva_alarma(alarmas_raw):
    contador_key = "contador_nueva_alarma"

    if contador_key not in st.session_state:
        st.session_state[contador_key] = 0

    sufijo = st.session_state[contador_key]

    tipo = st.radio(
        "Tipo de alarma",
        [ETIQUETA_UNICA, ETIQUETA_RECURRENTE],
        key=f"tipo_nueva_{sufijo}",
        horizontal=True,
    )

    mensaje = st.text_input(
        "Mensaje",
        value="",
        key=f"msg_nueva_{sufijo}",
    )

    if tipo == ETIQUETA_UNICA:
        col1, col2 = st.columns(2)

        with col1:
            fecha = st.date_input(
                "Fecha",
                value=datetime.now().date(),
                key=f"fecha_nueva_{sufijo}",
            )

        with col2:
            hora = st.time_input(
                "Hora",
                value=dtime(hour=8, minute=0),
                key=f"hora_nueva_{sufijo}",
            )

        if st.button(
            "➕ Agregar alarma",
            key=f"agregar_nueva_unica_{sufijo}",
        ):
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

                guardar_json(
                    ARCHIVO_ALARMAS,
                    alarmas_raw + [nueva],
                )

                st.session_state[contador_key] += 1
                st.success("✅ Alarma creada.")
                st.rerun()

    else:
        hora = st.time_input(
            "Hora",
            value=dtime(hour=8, minute=0),
            key=f"hora_nueva_rec_{sufijo}",
        )

        seleccion = st.multiselect(
            "Días",
            options=NOMBRES_ORDENADOS,
            default=[],
            key=f"dias_nueva_rec_{sufijo}",
        )

        if st.button(
            "➕ Agregar alarma",
            key=f"agregar_nueva_rec_{sufijo}",
        ):
            if not mensaje.strip():
                st.error("El mensaje no puede estar vacío.")
            elif not seleccion:
                st.error("Elegí al menos un día.")
            else:
                dias_nuevos = sorted(
                    NOMBRE_A_INDICE[nombre]
                    for nombre in seleccion
                )

                nueva = {
                    "id": nuevo_id_alarma(),
                    "mensaje": mensaje.strip(),
                    "tipo": "recurrente",
                    "hora": hora.hour,
                    "minuto": hora.minute,
                    "dias_semana": dias_nuevos,
                }

                guardar_json(
                    ARCHIVO_ALARMAS,
                    alarmas_raw + [nueva],
                )

                st.session_state[contador_key] += 1
                st.success("✅ Alarma creada.")
                st.rerun()


# ===========================================================
# Pastillero: tabla, edición y alta
# ===========================================================
def formatear_pastilla_para_tabla(item, ahora, color_pastillas):
    tipo = item.get("tipo", "?")

    tipo_mostrado = {
        "unica": ETIQUETA_UNICA,
        "recurrente": ETIQUETA_RECURRENTE,
    }.get(tipo, tipo)

    letra = item.get("pastilla_letra", "?")
    _, emoji = color_pastillas.get(letra, (None, "⬛"))
    proxima = proximo_datetime_alarma(item, ahora)

    return {
        "Letra": f"{emoji} {letra}",
        "Pastilla": item.get("pastilla_texto", ""),
        "Cantidad": item.get("cantidad", ""),
        "Tipo": tipo_mostrado,
        "Cuándo": texto_cuando_alarma(item),
        "Próxima vez": (
            proxima.strftime("%d/%m/%Y %H:%M")
            if proxima
            else "—"
        ),
        "_sort": proxima or datetime.max,
    }


def mostrar_tabla_pastillero(pastillero_vigente, ahora, color_pastillas):
    if not pastillero_vigente:
        st.info("No hay pastillas programadas.")
        return

    filas = [
        formatear_pastilla_para_tabla(item, ahora, color_pastillas)
        for item in pastillero_vigente
    ]

    filas.sort(key=lambda fila: fila["_sort"])

    for fila in filas:
        del fila["_sort"]

    st.dataframe(
        pd.DataFrame(filas),
        use_container_width=True,
        hide_index=True,
    )


def guardar_pastilla_editada(pastillero_raw, id_pastilla, nuevos_campos):
    nueva_lista = [
        nuevos_campos if item.get("id") == id_pastilla else item
        for item in pastillero_raw
    ]

    guardar_json(ARCHIVO_PASTILLERO, nueva_lista)


def eliminar_pastilla(pastillero_raw, id_pastilla):
    nueva_lista = [
        item for item in pastillero_raw
        if item.get("id") != id_pastilla
    ]

    guardar_json(ARCHIVO_PASTILLERO, nueva_lista)


def _cantidad_a_int(valor):
    try:
        return max(1, min(10, int(valor)))
    except (ValueError, TypeError):
        return 1


def tarjeta_edicion_pastilla(item, pastillero_raw, ahora):
    id_pastilla = item.get("id", "")
    tipo = item.get("tipo")
    es_unica = tipo == "unica"

    etiqueta_tipo = ETIQUETA_UNICA if es_unica else ETIQUETA_RECURRENTE
    st.caption(f"🔖 Tipo: **{etiqueta_tipo}**")

    col_a, col_b, col_c = st.columns([3, 1, 1])

    with col_a:
        texto = st.text_input(
            "Pastilla",
            value=item.get("pastilla_texto", ""),
            key=f"pst_texto_{id_pastilla}",
        )

    with col_b:
        letra_actual = str(item.get("pastilla_letra", "A")).upper()

        indice_letra = (
            LETRAS_DISPONIBLES.index(letra_actual)
            if letra_actual in LETRAS_DISPONIBLES
            else 0
        )

        letra = st.selectbox(
            "Letra",
            LETRAS_DISPONIBLES,
            index=indice_letra,
            key=f"pst_letra_{id_pastilla}",
        )

    with col_c:
        cantidad = st.number_input(
            "Cantidad",
            min_value=1,
            max_value=10,
            step=1,
            value=_cantidad_a_int(item.get("cantidad", 1)),
            key=f"pst_cant_{id_pastilla}",
        )

    if es_unica:
        dt_actual = calcular_dt_unica(item)

        fecha_defecto = dt_actual.date() if dt_actual else ahora.date()

        hora_defecto = (
            dt_actual.time().replace(second=0, microsecond=0)
            if dt_actual
            else dtime(hour=8, minute=0)
        )

        col1, col2 = st.columns(2)

        with col1:
            fecha = st.date_input(
                "Fecha",
                value=fecha_defecto,
                key=f"pst_fecha_{id_pastilla}",
            )

        with col2:
            hora = st.time_input(
                "Hora",
                value=hora_defecto,
                key=f"pst_hora_u_{id_pastilla}",
            )

        if datetime.combine(fecha, hora) < ahora:
            st.warning("⚠️ Esa fecha y hora ya pasaron.")

        seleccion = None

    else:
        hora = st.time_input(
            "Hora",
            value=time_de_item(item),
            key=f"pst_hora_r_{id_pastilla}",
        )

        nombres_actuales = [
            DIAS_SEMANA_NOMBRES[dia]
            for dia in sorted(item.get("dias_semana") or [])
            if dia in DIAS_SEMANA_NOMBRES
        ]

        seleccion = st.multiselect(
            "Días",
            options=NOMBRES_ORDENADOS,
            default=nombres_actuales,
            key=f"pst_dias_{id_pastilla}",
        )

    st.caption(
        "El tipo no se puede cambiar acá. "
        "Para eso, eliminá esta pastilla y creá una nueva."
    )

    col_guardar, col_eliminar = st.columns(2)

    with col_guardar:
        if st.button(
            "💾 Guardar cambios",
            key=f"pst_guardar_{id_pastilla}",
        ):
            if not texto.strip():
                st.error("El nombre de la pastilla no puede estar vacío.")
            elif not es_unica and not seleccion:
                st.error("Elegí al menos un día.")
            else:
                nuevos_campos = {
                    "id": id_pastilla,
                    "mensaje": texto.strip(),
                    "tipo": "unica" if es_unica else "recurrente",
                    "pastilla_texto": texto.strip(),
                    "pastilla_letra": letra,
                    "cantidad": str(int(cantidad)),
                }

                if es_unica:
                    nuevos_campos.update({
                        "dia": fecha.day,
                        "mes": fecha.month,
                        "anio": fecha.year,
                        "hora": hora.hour,
                        "minuto": hora.minute,
                        "segundo": 0,
                    })
                else:
                    nuevos_campos.update({
                        "hora": hora.hour,
                        "minuto": hora.minute,
                        "dias_semana": sorted(
                            NOMBRE_A_INDICE[nombre]
                            for nombre in seleccion
                        ),
                    })

                guardar_pastilla_editada(
                    pastillero_raw,
                    id_pastilla,
                    nuevos_campos,
                )

                st.success("✅ Pastilla actualizada.")
                st.rerun()

    with col_eliminar:
        if st.button(
            "🗑️ Eliminar",
            key=f"pst_eliminar_{id_pastilla}",
        ):
            eliminar_pastilla(pastillero_raw, id_pastilla)
            st.success("Pastilla eliminada.")
            st.rerun()


def mostrar_editor_pastillero(
    pastillero_vigente,
    pastillero_raw,
    ahora,
    color_pastillas,
):
    if not pastillero_vigente:
        st.info("No hay pastillas para editar.")
        return

    ordenadas = sorted(
        pastillero_vigente,
        key=lambda item: proximo_datetime_alarma(item, ahora) or datetime.max,
    )

    for item in ordenadas:
        id_pastilla = item.get("id", "")
        letra = item.get("pastilla_letra", "?")
        _, emoji = color_pastillas.get(letra, (None, "⬛"))

        titulo = (
            f"{emoji} {letra} — "
            f"{item.get('pastilla_texto', '(sin nombre)')} — "
            f"{texto_cuando_alarma(item)}"
        )

        with st.expander(titulo):
            if item.get("tipo") in ("unica", "recurrente"):
                tarjeta_edicion_pastilla(
                    item,
                    pastillero_raw,
                    ahora,
                )
            else:
                st.warning("Esta entrada tiene un tipo desconocido.")

                if st.button(
                    "🗑️ Eliminar",
                    key=f"pst_borrar_desconocida_{id_pastilla}",
                ):
                    eliminar_pastilla(pastillero_raw, id_pastilla)
                    st.rerun()


def formulario_nueva_pastilla(pastillero_raw):
    contador_key = "contador_nueva_pastilla"

    if contador_key not in st.session_state:
        st.session_state[contador_key] = 0

    sufijo = st.session_state[contador_key]

    tipo = st.radio(
        "Tipo de pastilla",
        [ETIQUETA_UNICA, ETIQUETA_RECURRENTE],
        key=f"pst_tipo_nueva_{sufijo}",
        horizontal=True,
    )

    col_a, col_b, col_c = st.columns([3, 1, 1])

    with col_a:
        texto = st.text_input(
            "Pastilla (ej: Pastilla para la presión)",
            value="",
            key=f"pst_texto_nueva_{sufijo}",
        )

    with col_b:
        letra = st.selectbox(
            "Letra",
            LETRAS_DISPONIBLES,
            key=f"pst_letra_nueva_{sufijo}",
        )

    with col_c:
        cantidad = st.number_input(
            "Cantidad",
            min_value=1,
            max_value=10,
            step=1,
            value=1,
            key=f"pst_cant_nueva_{sufijo}",
        )

    if tipo == ETIQUETA_UNICA:
        col1, col2 = st.columns(2)

        with col1:
            fecha = st.date_input(
                "Fecha",
                value=datetime.now().date(),
                key=f"pst_fecha_nueva_{sufijo}",
            )

        with col2:
            hora = st.time_input(
                "Hora",
                value=dtime(hour=8, minute=0),
                key=f"pst_hora_nueva_u_{sufijo}",
            )

        if st.button(
            "➕ Agregar pastilla",
            key=f"pst_agregar_unica_{sufijo}",
        ):
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

                guardar_json(
                    ARCHIVO_PASTILLERO,
                    pastillero_raw + [nueva],
                )

                st.session_state[contador_key] += 1
                st.success("✅ Pastilla agregada.")
                st.rerun()

    else:
        hora = st.time_input(
            "Hora",
            value=dtime(hour=8, minute=0),
            key=f"pst_hora_nueva_r_{sufijo}",
        )

        seleccion = st.multiselect(
            "Días",
            options=NOMBRES_ORDENADOS,
            default=NOMBRES_ORDENADOS,
            key=f"pst_dias_nueva_r_{sufijo}",
        )

        if st.button(
            "➕ Agregar pastilla",
            key=f"pst_agregar_rec_{sufijo}",
        ):
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
                    "dias_semana": sorted(
                        NOMBRE_A_INDICE[nombre]
                        for nombre in seleccion
                    ),
                    "pastilla_texto": texto.strip(),
                    "pastilla_letra": letra,
                    "cantidad": str(int(cantidad)),
                }

                guardar_json(
                    ARCHIVO_PASTILLERO,
                    pastillero_raw + [nueva],
                )

                st.session_state[contador_key] += 1
                st.success("✅ Pastilla agregada.")
                st.rerun()


def mostrar_limpieza_vencidas(pastillero_raw, ahora):
    vencidas = [
        item for item in pastillero_raw
        if alarma_vencida(item, ahora)
    ]

    if not vencidas:
        return

    st.markdown("<br>", unsafe_allow_html=True)

    st.caption(
        f"Hay {len(vencidas)} pastilla(s) de una sola vez que ya pasaron. "
        "No se muestran en el dashboard, pero siguen guardadas en config.json."
    )

    if st.button(
        "🧹 Borrar pastillas únicas vencidas",
        key="pst_limpiar_vencidas",
    ):
        restantes = [
            item for item in pastillero_raw
            if not alarma_vencida(item, ahora)
        ]

        guardar_json(ARCHIVO_PASTILLERO, restantes)
        st.success("✅ Pastillas vencidas eliminadas.")
        st.rerun()


# ---------------------------------------------------------
# Eventos de hoy
# ---------------------------------------------------------
def formatear_delta(delta):
    total_segundos = int(delta.total_seconds())

    if total_segundos < -60:
        return "Ya pasó"

    if total_segundos < 0:
        total_segundos = 0

    dias, resto = divmod(total_segundos, 86400)
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
    segundos = delta.total_seconds()

    if segundos < -60:
        return "⚪ Pasado"

    horas = segundos / 3600

    if horas < 1:
        return "🔴 Urgente"
    elif horas < 3:
        return "🟡 Pronto"

    return "🟢 A tiempo"


def eventos_de_hoy(
    alarmas_vigentes,
    pastillero_vigente,
    ahora,
    color_pastillas,
):
    hoy = ahora.date()
    eventos = []

    for alarma in alarmas_vigentes:
        ocurrencias = ocurrencias_alarma_en_rango(
            alarma,
            hoy,
            1,
            ahora,
        )

        for fecha, hora_str in ocurrencias:
            hora, minuto = map(int, hora_str.split(":"))

            dt = ahora.replace(
                hour=hora,
                minute=minuto,
                second=0,
                microsecond=0,
            )

            delta = dt - ahora

            eventos.append({
                "Estado": estado_por_urgencia(delta),
                "Hora": hora_str,
                "Tipo": "⏰ Alarma",
                "Elemento": "—",
                "Descripción": alarma.get("mensaje", ""),
                "Faltan": formatear_delta(delta),
                "_sort": hora_str,
            })

    for pastilla in pastillero_vigente:
        letra = pastilla.get("pastilla_letra", "?")
        _, emoji = color_pastillas.get(letra, (None, "⬛"))

        ocurrencias = ocurrencias_alarma_en_rango(
            pastilla,
            hoy,
            1,
            ahora,
        )

        for fecha, hora_str in ocurrencias:
            hora, minuto = map(int, hora_str.split(":"))

            dt = ahora.replace(
                hour=hora,
                minute=minuto,
                second=0,
                microsecond=0,
            )

            delta = dt - ahora

            eventos.append({
                "Estado": estado_por_urgencia(delta),
                "Hora": hora_str,
                "Tipo": "💊 Pastilla",
                "Elemento": f"{emoji} {letra}",
                "Descripción": (
                    f"{pastilla.get('pastilla_texto', '')} "
                    f"(x{pastilla.get('cantidad', '')})"
                ),
                "Faltan": formatear_delta(delta),
                "_sort": hora_str,
            })

    eventos.sort(key=lambda evento: evento["_sort"])

    for evento in eventos:
        del evento["_sort"]

    return eventos


def mostrar_tabla_hoy(eventos):
    if not eventos:
        st.info("No hay nada programado para hoy.")
        return

    st.dataframe(
        pd.DataFrame(eventos),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# Calendario semanal
# ---------------------------------------------------------
def construir_calendario(
    alarmas_vigentes,
    pastillero_vigente,
    fecha_inicio,
    color_pastillas,
    ahora,
    dias=7,
):
    calendario = {
        fecha_inicio + timedelta(days=i): []
        for i in range(dias)
    }

    for alarma in alarmas_vigentes:
        ocurrencias = ocurrencias_alarma_en_rango(
            alarma,
            fecha_inicio,
            dias,
            ahora,
        )

        for fecha, hora_str in ocurrencias:
            calendario[fecha].append({
                "hora": hora_str,
                "icono": "⏰",
                "desc": alarma.get("mensaje", ""),
                "acento": ACENTO_ALARMA,
            })

    for pastilla in pastillero_vigente:
        letra = pastilla.get("pastilla_letra", "?")
        hex_color, _ = color_pastillas.get(letra, ("#64748b", "⬛"))

        ocurrencias = ocurrencias_alarma_en_rango(
            pastilla,
            fecha_inicio,
            dias,
            ahora,
        )

        for fecha, hora_str in ocurrencias:
            calendario[fecha].append({
                "hora": hora_str,
                "icono": "💊",
                "desc": f"{letra} · {pastilla.get('pastilla_texto', '')}",
                "acento": hex_color,
            })

    for fecha in calendario:
        calendario[fecha].sort(key=lambda evento: evento["hora"])

    return calendario


def mostrar_calendario(calendario, fecha_inicio):
    columnas = st.columns(7)

    for i, columna in enumerate(columnas):
        fecha = fecha_inicio + timedelta(days=i)
        nombre_dia = DIAS_SEMANA_NOMBRES[fecha.weekday()]
        es_hoy = fecha == fecha_inicio

        with columna:
            bg_header = "#0284c7" if es_hoy else "#1e293b"

            border_header = (
                "border: 2px solid #38bdf8;"
                if es_hoy
                else "border: 1px solid #334155;"
            )

            st.markdown(
                f"<div style='background-color:{bg_header}; "
                f"{border_header} padding:8px; "
                f"border-radius:8px 8px 0 0; text-align:center; "
                f"margin-bottom:4px;'>"
                f"<b style='color:#ffffff; font-size:0.95em;'>"
                f"{nombre_dia}</b><br>"
                f"<span style='color:#e2e8f0; font-size:0.8em;'>"
                f"{fecha.strftime('%d/%m')}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            eventos = calendario[fecha]

            if not eventos:
                st.markdown(
                    f"<div style='background-color:#0f172a; "
                    f"padding:12px; border-radius:0 0 8px 8px; "
                    f"text-align:center; color:{COLOR_SIN_EVENTOS}; "
                    f"font-size:0.85em; border:1px solid #334155; "
                    f"border-top:none;'>Sin eventos</div>",
                    unsafe_allow_html=True,
                )
            else:
                for evento in eventos:
                    st.markdown(
                        f"<div style='background-color:#1e293b; "
                        f"border-left:4px solid {evento['acento']}; "
                        f"color:#f8fafc; padding:8px; border-radius:4px; "
                        f"margin-bottom:4px; font-size:0.85em; "
                        f"border-top:1px solid #334155; "
                        f"border-right:1px solid #334155; "
                        f"border-bottom:1px solid #334155;'>"
                        f"<b>{evento['icono']} {evento['hora']}</b><br>"
                        f"<span style='color:#cbd5e1;'>"
                        f"{evento['desc']}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )


# ---------------------------------------------------------
# Edición de la memoria de usuario
# ---------------------------------------------------------
def mostrar_editor_memoria(memoria):
    st.caption(
        "Editá cualquier valor haciendo clic sobre la celda. "
        "Usá el ➕ al pie de la tabla para agregar un dato nuevo. "
        "Para borrar un dato, usá el selector de más abajo."
    )

    if memoria:
        claves = list(memoria.keys())

        df = pd.DataFrame({
            "Clave": claves,
            "Valor": [str(memoria[clave]) for clave in claves],
        })
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
                errores.append(
                    f"Fila {i + 1}: la clave '{clave}' está repetida."
                )
                continue

            claves_vistas.add(clave)
            nueva_memoria[clave] = valor

        if errores:
            for error in errores:
                st.error(error)
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

    if st.button(
        "🗑️ Eliminar este dato",
        key="boton_borrar_memoria",
    ):
        nueva_memoria = {
            clave: valor
            for clave, valor in memoria.items()
            if clave != clave_elegida
        }

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

    clave = st.text_input(
        "Clave",
        value="",
        key=f"clave_nueva_mem_{sufijo}",
    )

    valor = st.text_input(
        "Valor",
        value="",
        key=f"valor_nueva_mem_{sufijo}",
    )

    if st.button(
        "➕ Agregar dato",
        key=f"agregar_nuevo_dato_mem_{sufijo}",
    ):
        clave_limpia = clave.strip()
        valor_limpio = valor.strip()

        if not clave_limpia or not valor_limpio:
            st.error("Completá la clave y el valor.")
        elif clave_limpia in memoria:
            st.error(
                f"Ya existe un dato con la clave '{clave_limpia}'. "
                "Editalo en la tabla de arriba."
            )
        else:
            nueva_memoria = dict(memoria)
            nueva_memoria[clave_limpia] = valor_limpio

            guardar_memoria(nueva_memoria)
            st.session_state[contador_key] += 1
            st.success("✅ Dato agregado.")
            st.rerun()


# ---------------------------------------------------------
# Interfaz principal
# ---------------------------------------------------------
aplicar_estilos()

col_title, col_btn = st.columns([5, 1])

with col_title:
    st.title("🏠 Dashboard Asistente")
    st.caption(
        f"Última actualización: "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

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
mensajes_dispensador = cargar_mensajes_dispensador()

color_pastillas = asignar_colores_pastillas(pastillero_raw)

alarmas_vigentes = [
    alarma
    for alarma in alarmas_raw
    if not alarma_vencida(alarma, ahora)
]

pastillero_vigente = [
    pastilla
    for pastilla in pastillero_raw
    if not alarma_vencida(pastilla, ahora)
]


tab_vista, tab_pastillero, tab_alarmas, tab_mensajes, tab_memoria = st.tabs(
    [
        "📊 Vista general",
        "💊 Pastillero",
        "⏰ Alarmas",
        "🚨 Dispensador",
        "🧠 Memoria",
    ]
)


# ======================= TAB 1: VISTA GENERAL =======================
with tab_vista:
    proximas_alarmas = sorted(
        [
            (proximo_datetime_alarma(alarma, ahora), alarma)
            for alarma in alarmas_vigentes
        ],
        key=lambda par: par[0] or datetime.max,
    )

    proximas_pastillas = sorted(
        [
            (proximo_datetime_alarma(pastilla, ahora), pastilla)
            for pastilla in pastillero_vigente
        ],
        key=lambda par: par[0] or datetime.max,
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("⏰ Alarmas activas", len(alarmas_vigentes))
    c2.metric("💊 Pastillas configuradas", len(pastillero_vigente))

    if proximas_alarmas and proximas_alarmas[0][0] is not None:
        fecha_hora, alarma = proximas_alarmas[0]

        c3.metric(
            "Próxima alarma",
            alarma.get("mensaje", ""),
            delta=f"en {formatear_delta(fecha_hora - ahora)}",
        )
    else:
        c3.metric("Próxima alarma", "—")

    if proximas_pastillas and proximas_pastillas[0][0] is not None:
        fecha_hora, pastilla = proximas_pastillas[0]

        c4.metric(
            "Próxima pastilla",
            pastilla.get("pastilla_texto", ""),
            delta=f"en {formatear_delta(fecha_hora - ahora)}",
        )
    else:
        c4.metric("Próxima pastilla", "—")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🚨 Último mensaje del dispensador")

    if mensajes_dispensador:
        ultimo_mensaje = mensajes_dispensador[-1]

        st.caption(
            f"Registrado: {formatear_fecha_mensaje(ultimo_mensaje)}"
        )
        st.info(ultimo_mensaje["mensaje"])
    else:
        st.caption("Todavía no hay mensajes registrados.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("📍 Eventos de Hoy")

    eventos_hoy = eventos_de_hoy(
        alarmas_vigentes,
        pastillero_vigente,
        ahora,
        color_pastillas,
    )

    mostrar_tabla_hoy(eventos_hoy)

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("🗓️ Calendario Semanal")

    calendario = construir_calendario(
        alarmas_vigentes,
        pastillero_vigente,
        ahora.date(),
        color_pastillas,
        ahora,
        dias=7,
    )

    mostrar_calendario(calendario, ahora.date())


# ======================= TAB 2: PASTILLERO =======================
with tab_pastillero:
    st.header("💊 Pastillas Programadas")

    mostrar_tabla_pastillero(
        pastillero_vigente,
        ahora,
        color_pastillas,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("✏️ Editar o Eliminar Pastillas")

    mostrar_editor_pastillero(
        pastillero_vigente,
        pastillero_raw,
        ahora,
        color_pastillas,
    )

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

    mostrar_editor_alarmas(
        alarmas_vigentes,
        alarmas_raw,
        ahora,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("➕ Agregar Nueva Alarma")

    formulario_nueva_alarma(alarmas_raw)


# ======================= TAB 4: MENSAJES DEL DISPENSADOR =======================
with tab_mensajes:
    mostrar_mensajes_dispensador(mensajes_dispensador)


# ======================= TAB 5: MEMORIA =======================
with tab_memoria:
    st.header("🧠 Memoria del Usuario")
    st.caption(
        "Datos que el asistente fue guardando sobre el usuario "
        "durante las conversaciones."
    )

    mostrar_editor_memoria(memoria_usuario)
    mostrar_borrado_memoria(memoria_usuario)
    formulario_nuevo_dato_memoria(memoria_usuario)