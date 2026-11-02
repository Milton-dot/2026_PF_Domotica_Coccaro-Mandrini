import json
import os
import uuid
from datetime import datetime, timedelta, time as dtime

import pandas as pd
import streamlit as st

ARCHIVO_DATOS = "alarmas.json"
ARCHIVO_MEMORIA = "memoria_usuario.json"

st.set_page_config(page_title="Dashboard Asistente", layout="wide", page_icon="🏠")

DIAS_SEMANA_NOMBRES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}
NOMBRES_ORDENADOS = [DIAS_SEMANA_NOMBRES[i] for i in range(7)]
NOMBRE_A_INDICE = {v: k for k, v in DIAS_SEMANA_NOMBRES.items()}

ETIQUETA_UNICA = "📅 Una vez"
ETIQUETA_RECURRENTE = "🔁 Se repite"
ETIQUETA_PASTILLERO = "💊 Pastillero"

ACENTO_ALARMA = "#3b82f6"
COLOR_SIN_EVENTOS = "#64748b"
PALETA_PASTILLAS = [
    ("#8b5cf6", "🟪"), ("#10b981", "🟩"), ("#f59e0b", "🟧"),
    ("#0ea5e9", "🟦"), ("#f43f5e", "🟥"), ("#eab308", "🟨"), ("#64748b", "⬛"),
]

def aplicar_estilos():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        [data-testid="stMetric"] { background-color: #1e293b; padding: 16px; border-radius: 12px; border: 1px solid #334155; }
        [data-testid="stMetricValue"] { font-size: 1.6rem !important; color: #f8fafc !important; }
        [data-testid="stMetricLabel"] { font-size: 0.9rem !important; color: #94a3b8 !important; }
        .stDataFrame { border-radius: 8px; overflow: hidden; border: 1px solid #334155; }
        </style>
        """,
        unsafe_allow_html=True,
    )

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

def asignar_colores_pastillas(datos):
    letras = sorted({p.get("pastilla_letra", "?") for p in datos if p.get("tipo") == "pastillero"})
    return {letra: PALETA_PASTILLAS[i % len(PALETA_PASTILLAS)] for i, letra in enumerate(letras)}

def nuevo_id():
    return uuid.uuid4().hex[:8]

def calcular_dt_unica(a):
    try:
        return datetime(int(a["anio"]), int(a["mes"]), int(a["dia"]), int(a.get("hora", 0)), int(a.get("minuto", 0)), int(a.get("segundo", 0)))
    except (KeyError, TypeError, ValueError):
        return None

def alarma_vencida(a, ahora):
    if a.get("tipo") != "unica":
        return False
    dt = calcular_dt_unica(a)
    return dt < ahora if dt else False

def proximo_datetime(a, ahora):
    tipo = a.get("tipo")
    if tipo == "unica":
        dt = calcular_dt_unica(a)
        return dt if dt and dt >= ahora else None
    elif tipo in ("recurrente", "pastillero"):
        hora, minuto = a.get("hora"), a.get("minuto")
        dias_semana = a.get("dias_semana") or []
        if hora is None or minuto is None or not dias_semana:
            return None
        mejor = None
        for dia in dias_semana:
            candidato = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            candidato += timedelta(days=(dia - ahora.weekday()) % 7)
            if candidato <= ahora:
                candidato += timedelta(days=7)
            if mejor is None or candidato < mejor:
                mejor = candidato
        return mejor
    return None

def ocurrencias_en_rango(a, fecha_inicio, dias, ahora):
    tipo = a.get("tipo")
    resultado = []
    if tipo == "unica":
        dt = calcular_dt_unica(a)
        if dt and dt >= ahora and fecha_inicio <= dt.date() < fecha_inicio + timedelta(days=dias):
            resultado.append((dt.date(), dt.strftime("%H:%M")))
    elif tipo in ("recurrente", "pastillero"):
        hora, minuto = a.get("hora"), a.get("minuto")
        dias_semana = a.get("dias_semana") or []
        if hora is not None and minuto is not None:
            for i in range(dias):
                fecha = fecha_inicio + timedelta(days=i)
                if fecha.weekday() in dias_semana:
                    resultado.append((fecha, f"{hora:02d}:{minuto:02d}"))
    return resultado

def formatear_delta(delta):
    seg = int(delta.total_seconds())
    if seg < -60: return "Ya pasó"
    if seg < 0: seg = 0
    dias, resto = divmod(seg, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, _ = divmod(resto, 60)
    partes = []
    if dias: partes.append(f"{dias}d")
    if horas: partes.append(f"{horas}h")
    if minutos or not partes: partes.append(f"{minutos}m")
    return " ".join(partes)

def estado_por_urgencia(delta):
    seg = delta.total_seconds()
    if seg < -60: return "⚪ Pasado"
    return "🔴 Urgente" if seg / 3600 < 1 else ("🟡 Pronto" if seg / 3600 < 3 else "🟢 A tiempo")

aplicar_estilos()

col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("🏠 Dashboard Asistente Unificado")
    st.caption(f"Actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
with col_btn:
    st.write("")
    if st.button("🔄 Actualizar"): st.rerun()

ahora = datetime.now()
datos_raw = cargar_json(ARCHIVO_DATOS)
memoria_usuario = cargar_memoria()
color_pastillas = asignar_colores_pastillas(datos_raw)
vigentes = [a for a in datos_raw if not alarma_vencida(a, ahora)]

tab_vista, tab_gestion, tab_memoria = st.tabs(["📊 Vista general", "⚙️ Gestionar Alarmas y Pastillas", "🧠 Memoria"])

with tab_vista:
    prox_alarmas = sorted([(proximo_datetime(a, ahora), a) for a in vigentes if a.get("tipo") != "pastillero"], key=lambda t: t[0] or datetime.max)
    prox_pastillas = sorted([(proximo_datetime(p, ahora), p) for p in vigentes if p.get("tipo") == "pastillero"], key=lambda t: t[0] or datetime.max)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⏰ Activas", len([a for a in vigentes if a.get("tipo") != "pastillero"]))
    c2.metric("💊 Pastillas", len([p for p in vigentes if p.get("tipo") == "pastillero"]))
    c3.metric("Próxima alarma", prox_alarmas[0][1].get("mensaje", "—") if prox_alarmas and prox_alarmas[0][0] else "—")
    c4.metric("Próxima pastilla", prox_pastillas[0][1].get("mensaje", "—") if prox_pastillas and prox_pastillas[0][0] else "—")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("📍 Eventos de Hoy")
    eventos_hoy = []
    for a in vigentes:
        for fecha, h_str in ocurrencias_en_rango(a, ahora.date(), 1, ahora):
            h, m = map(int, h_str.split(":"))
            dt = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
            delta = dt - ahora
            es_p = a.get("tipo") == "pastillero"
            letra = a.get("pastilla_letra", "") if es_p else "—"
            _, emoji = color_pastillas.get(letra, (None, "💊")) if es_p else (None, "⏰")
            eventos_hoy.append({
                "Estado": estado_por_urgencia(delta), "Hora": h_str,
                "Tipo": ETIQUETA_PASTILLERO if es_p else ("🔁 Recurrente" if a.get("tipo")=="recurrente" else ETIQUETA_UNICA),
                "Elemento": f"{emoji} {letra}" if es_p else "—",
                "Descripción": a.get("mensaje", ""), "Faltan": formatear_delta(delta), "_sort": h_str
            })
    eventos_hoy.sort(key=lambda x: x["_sort"])
    for e in eventos_hoy: del e["_sort"]
    if eventos_hoy: st.dataframe(pd.DataFrame(eventos_hoy), use_container_width=True, hide_index=True)
    else: st.info("No hay eventos para hoy.")

with tab_gestion:
    st.header("⚙️ Elementos Registrados")
    if vigentes:
        tabla_gen = []
        for a in vigentes:
            tipo = a.get("tipo")
            t_str = ETIQUETA_PASTILLERO if tipo == "pastillero" else (ETIQUETA_RECURRENTE if tipo == "recurrente" else ETIQUETA_UNICA)
            tabla_gen.append({"ID": a.get("id"), "Tipo": t_str, "Mensaje": a.get("mensaje"), "Detalle": f"{a.get('hora', 0):02d}:{a.get('minuto', 0):02d}"})
        st.dataframe(pd.DataFrame(tabla_gen), use_container_width=True, hide_index=True)

        id_borrar = st.selectbox("Seleccioná el ID del elemento a eliminar", options=[a.get("id") for a in vigentes])
        if st.button("🗑️ Eliminar elemento"):
            nuevo = [a for a in datos_raw if a.get("id") != id_borrar]
            guardar_json(ARCHIVO_DATOS, nuevo)
            st.success("Eliminado correctamente.")
            st.rerun()
    else:
        st.info("No hay registros guardados.")

with tab_memoria:
    st.header("🧠 Memoria del Usuario")
    if memoria_usuario:
        df_mem = pd.DataFrame({"Clave": list(memoria_usuario.keys()), "Valor": list(memoria_usuario.values())})
        st.dataframe(df_mem, use_container_width=True, hide_index=True)
    else:
        st.info("No hay memoria guardada.")