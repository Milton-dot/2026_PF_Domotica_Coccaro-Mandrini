import datetime
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext
import requests

try:
  from PIL import Image, ImageTk
  from ultralytics import YOLO
  import cv2

  YOLO_DISPONIBLE = True
except ImportError:
  YOLO_DISPONIBLE = False

CONFIG_FILE = "config.json"
MENSAJES_FILE = "mensajes.json"
CAPTURAS_DIR = "capturas"


class DispensadorApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Sistema Automatizado de Dispensador de Pastillas e IA")
    self.root.geometry("950x750")

    if not os.path.exists(CAPTURAS_DIR):
      os.makedirs(CAPTURAS_DIR)

    self.last_config_mtime = 0

    self.yolo_model = None
    if YOLO_DISPONIBLE:
      try:
        if getattr(sys, "frozen", False):
          base_dir = os.path.dirname(sys.executable)
        else:
          base_dir = os.path.abspath(".")

        ruta_modelo = os.path.join(base_dir, "best.pt")
        if os.path.exists(ruta_modelo):
          self.yolo_model = YOLO(ruta_modelo)
          print("¡Modelo YOLO cargado con éxito!")
        else:
          print(
              "Error crítico: El archivo 'best.pt' no se encuentra en la"
              " carpeta."
          )
      except Exception as e:
        print(f"Error al cargar el modelo YOLO: {e}")

    self.cargar_config()
    self.crear_widgets()

    self.activo = True
    self.hilo_cron = threading.Thread(target=self.bucle_horario, daemon=True)
    self.hilo_cron.start()

    threading.Thread(target=self.verificar_conexion, daemon=True).start()

  def log(self, mensaje):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    texto_log = f"[{timestamp}] {mensaje}\n"
    if hasattr(self, "text_log"):
      self.text_log.insert(tk.END, texto_log)
      self.text_log.see(tk.END)

  def guardar_mensaje(self, texto):
    try:
      mensajes = []
      if os.path.exists(MENSAJES_FILE):
        with open(MENSAJES_FILE, "r", encoding="utf-8") as f:
          mensajes = json.load(f)
      mensajes.append({
          "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "mensaje": texto,
      })
      with open(MENSAJES_FILE, "w", encoding="utf-8") as f:
        json.dump(mensajes, f, indent=4, ensure_ascii=False)
    except Exception as e:
      print(f"Error al guardar en mensajes.json: {e}")

  def cargar_config(self):
    default_config = {
        "ip": "192.168.24.81",
        "horarios": [{
            "hora": "08:00",
            "pastilla_letra": "A",
            "cantidad": 1,
            "fecha": datetime.date.today().strftime("%Y-%m-%d"),
        }],
    }
    if os.path.exists(CONFIG_FILE):
      try:
        self.last_config_mtime = os.path.getmtime(CONFIG_FILE)
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
          data = json.load(f)
          if isinstance(data, dict):
            if "horarios" not in data and "hora" in data:
              data["horarios"] = [{
                  "hora": data.get("hora", "08:00"),
                  "pastilla_letra": data.get("pastilla_letra", "A"),
                  "cantidad": data.get("cantidad", 1),
                  "fecha": data.get(
                      "fecha", datetime.date.today().strftime("%Y-%m-%d")
                  ),
              }]
            self.config_data = {**default_config, **data}
          else:
            self.config_data = default_config
      except Exception:
        self.config_data = default_config
    else:
      self.config_data = default_config

  def guardar_ip(self):
    try:
      self.config_data["ip"] = self.entry_ip.get().strip()
      with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(self.config_data, f, indent=4)
      self.last_config_mtime = os.path.getmtime(CONFIG_FILE)
      self.log("Dirección IP guardada correctamente.")
      messagebox.showinfo("Éxito", "IP guardada correctamente.")
    except Exception as e:
      self.log(f"Error al guardar IP: {e}")

  def actualizar_lista_horarios(self):
    if hasattr(self, "listbox_horarios"):
      self.listbox_horarios.delete(0, tk.END)
      for h in self.config_data.get("horarios", []):
        fecha_str = h.get("fecha", "N/A")
        texto = f"[{fecha_str}] Hora: {h['hora']} | Pastilla: {h['pastilla_letra']} | Cantidad: {h['cantidad']}"
        self.listbox_horarios.insert(tk.END, texto)

  def agregar_horario(self):
    hora = self.entry_hora.get().strip()
    letra = self.entry_letra.get().strip().upper()
    cantidad_str = self.entry_cantidad.get().strip()

    if not hora or not letra or not cantidad_str:
      messagebox.showwarning(
          "Advertencia", "Por favor complete todos los campos de horario."
      )
      return

    try:
      cantidad = int(cantidad_str)
    except ValueError:
      messagebox.showerror("Error", "La cantidad debe ser un número entero.")
      return

    fecha_actual = datetime.date.today().strftime("%Y-%m-%d")
    nuevo_item = {
        "hora": hora,
        "pastilla_letra": letra,
        "cantidad": cantidad,
        "fecha": fecha_actual,
    }
    if "horarios" not in self.config_data:
      self.config_data["horarios"] = []
    self.config_data["horarios"].append(nuevo_item)

    try:
      with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(self.config_data, f, indent=4)
      self.last_config_mtime = os.path.getmtime(CONFIG_FILE)
    except Exception as e:
      self.log(f"Error al guardar horario: {e}")

    self.actualizar_lista_horarios()
    self.log(
        f"Horario agendado: {hora} - Pastilla {letra} ({cantidad} unid.) [Fecha:"
        f" {fecha_actual}]"
    )
    messagebox.showinfo("Éxito", "Horario agendado correctamente.")

  def eliminar_horario(self):
    seleccion = self.listbox_horarios.curselection()
    if not seleccion:
      messagebox.showwarning(
          "Advertencia", "Seleccione un horario de la lista para eliminar."
      )
      return
    idx = seleccion[0]
    eliminado = self.config_data["horarios"].pop(idx)

    try:
      with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(self.config_data, f, indent=4)
      self.last_config_mtime = os.path.getmtime(CONFIG_FILE)
    except Exception as e:
      self.log(f"Error al actualizar archivo config: {e}")

    self.actualizar_lista_horarios()
    self.log(
        f"Horario eliminado: {eliminado['hora']} - Pastilla"
        f" {eliminado['pastilla_letra']}"
    )

  def crear_widgets(self):
    frame_top = tk.LabelFrame(
        self.root,
        text="Configuración de Red y Estado",
        font=("Arial", 10, "bold"),
    )
    frame_top.pack(fill="x", padx=15, pady=5)

    tk.Label(frame_top, text="IP ESP32-CAM:", font=("Arial", 9)).grid(
        row=0, column=0, sticky="w", padx=10, pady=5
    )
    self.entry_ip = tk.Entry(frame_top, font=("Arial", 9), width=15)
    self.entry_ip.grid(row=0, column=1, padx=5, pady=5)
    self.entry_ip.insert(0, self.config_data.get("ip", "192.168.24.81"))

    btn_test_ip = tk.Button(
        frame_top,
        text="Probar Conexión",
        command=lambda: threading.Thread(
            target=self.verificar_conexion, daemon=True
        ).start(),
        font=("Arial", 9),
    )
    btn_test_ip.grid(row=0, column=2, padx=5, pady=5)

    btn_guardar_ip = tk.Button(
        frame_top,
        text="Guardar IP",
        command=self.guardar_ip,
        font=("Arial", 9),
    )
    btn_guardar_ip.grid(row=0, column=3, padx=5, pady=5)

    self.lbl_estado = tk.Label(
        frame_top,
        text="● Verificando...",
        font=("Arial", 10, "bold"),
        fg="orange",
    )
    self.lbl_estado.grid(row=0, column=4, padx=15, pady=5)

    frame_main = tk.Frame(self.root)
    frame_main.pack(fill="both", expand=True, padx=15, pady=5)

    frame_left = tk.Frame(frame_main)
    frame_left.pack(side=tk.LEFT, fill="both", expand=True, padx=5)

    frame_right = tk.Frame(frame_main)
    frame_right.pack(side=tk.RIGHT, fill="both", padx=5)

    frame_manual = tk.LabelFrame(
        frame_left, text="Dispensado Manual", font=("Arial", 10, "bold")
    )
    frame_manual.pack(fill="x", pady=5)

    tk.Button(
        frame_manual,
        text="Pastilla A",
        bg="#4CAF50",
        fg="white",
        font=("Arial", 9, "bold"),
        command=lambda: self.ejecutar_dispensado_manual("A", 1),
    ).pack(side=tk.LEFT, expand=True, fill="x", padx=3, pady=5)
    tk.Button(
        frame_manual,
        text="Pastilla B",
        bg="#2196F3",
        fg="white",
        font=("Arial", 9, "bold"),
        command=lambda: self.ejecutar_dispensado_manual("B", 1),
    ).pack(side=tk.LEFT, expand=True, fill="x", padx=3, pady=5)
    tk.Button(
        frame_manual,
        text="Pastilla C",
        bg="#FF9800",
        fg="white",
        font=("Arial", 9, "bold"),
        command=lambda: self.ejecutar_dispensado_manual("C", 1),
    ).pack(side=tk.LEFT, expand=True, fill="x", padx=3, pady=5)

    frame_prog = tk.LabelFrame(
        frame_left, text="Programación de Medicación", font=("Arial", 10, "bold")
    )
    frame_prog.pack(fill="x", pady=5)

    f_inputs = tk.Frame(frame_prog)
    f_inputs.pack(fill="x", padx=5, pady=5)

    tk.Label(f_inputs, text="Hora (HH:MM):", font=("Arial", 9)).grid(
        row=0, column=0, sticky="w", padx=2, pady=2
    )
    self.entry_hora = tk.Entry(f_inputs, font=("Arial", 9), width=7)
    self.entry_hora.grid(row=0, column=1, padx=2, pady=2)
    self.entry_hora.insert(0, "08:00")

    # Modificado de "Canal:" a "Pastilla:"
    tk.Label(f_inputs, text="Pastilla:", font=("Arial", 9)).grid(
        row=0, column=2, sticky="w", padx=2, pady=2
    )
    self.entry_letra = tk.Entry(f_inputs, font=("Arial", 9), width=5)
    self.entry_letra.grid(row=0, column=3, padx=2, pady=2)
    self.entry_letra.insert(0, "A")

    tk.Label(f_inputs, text="Cant:", font=("Arial", 9)).grid(
        row=0, column=4, sticky="w", padx=2, pady=2
    )
    self.entry_cantidad = tk.Entry(f_inputs, font=("Arial", 9), width=5)
    self.entry_cantidad.grid(row=0, column=5, padx=2, pady=2)
    self.entry_cantidad.insert(0, "1")

    tk.Button(
        f_inputs,
        text="Agregar Horario",
        command=self.agregar_horario,
        font=("Arial", 9, "bold"),
        bg="#4CAF50",
        fg="white",
    ).grid(row=0, column=6, padx=5, pady=2)

    frame_agendados = tk.LabelFrame(
        frame_left,
        text="Horarios y Cantidades de Pastillas Agendados",
        font=("Arial", 10, "bold"),
    )
    frame_agendados.pack(fill="both", expand=True, pady=5)

    self.listbox_horarios = tk.Listbox(
        frame_agendados, font=("Consolas", 9), height=5
    )
    self.listbox_horarios.pack(
        side=tk.LEFT, fill="both", expand=True, padx=5, pady=5
    )

    scrollbar = tk.Scrollbar(frame_agendados, orient="vertical")
    scrollbar.pack(side=tk.RIGHT, fill="y", pady=5)
    self.listbox_horarios.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=self.listbox_horarios.yview)

    tk.Button(
        frame_left,
        text="Eliminar Horario Seleccionado",
        command=self.eliminar_horario,
        font=("Arial", 9),
        bg="#f44336",
        fg="white",
    ).pack(fill="x", pady=2)

    self.actualizar_lista_horarios()

    frame_img = tk.LabelFrame(
        frame_right, text="Última Verificación IA", font=("Arial", 10, "bold")
    )
    frame_img.pack(fill="both", expand=True)

    self.lbl_imagen = tk.Label(
        frame_img,
        text="Sin imagen capturada",
        bg="#222222",
        fg="white",
        width=30,
        height=14,
    )
    self.lbl_imagen.pack(padx=5, pady=5, fill="both", expand=True)

    frame_log = tk.LabelFrame(
        self.root, text="Registro de Estados del Sistema", font=("Arial", 10, "bold")
    )
    frame_log.pack(fill="both", expand=True, padx=15, pady=5)

    self.text_log = scrolledtext.ScrolledText(
        frame_log, font=("Consolas", 8), height=7
    )
    self.text_log.pack(fill="both", expand=True, padx=5, pady=5)

    if self.yolo_model:
      self.log("Sistema YOLO inicializado correctamente con 'best.pt'.")
    else:
      self.log(
          "Aviso: Modelo YOLO no cargado ('best.pt' ausente o librería"
          " faltante)."
      )

  def verificar_conexion(self):
    ip = self.entry_ip.get().strip()
    url = f"http://{ip}/"
    try:
      response = requests.get(url, timeout=3)
      if response.status_code == 200:
        self.lbl_estado.config(text="● ONLINE", fg="green")
      else:
        self.lbl_estado.config(text="● OFFLINE", fg="red")
    except Exception:
      self.lbl_estado.config(text="● OFFLINE", fg="red")

  def enviar_comando_dispensa(self, letra, cantidad):
    ip = self.entry_ip.get().strip()
    for i in range(cantidad):
      url_comando = f"http://{ip}/enviar?cmd=1{letra}"
      try:
        response = requests.get(url_comando, timeout=5)
        if response.status_code == 200:
          self.log(
              f"Comando 1{letra} (Unidad {i+1}/{cantidad}) enviado con éxito."
          )
        else:
          self.log(
              f"Advertencia: ESP32 respondió con código {response.status_code}"
          )
      except Exception as e:
        self.log(f"Error de comunicación con ESP32-CAM: {e}")
        return False
      time.sleep(1)
    return True

  def ejecutar_dispensado_manual(self, letra, cantidad):
    item_manual = [{"hora": "MANUAL", "pastilla_letra": letra, "cantidad": cantidad}]
    threading.Thread(
        target=self.proceso_dispensado_lote_y_captura,
        args=(item_manual,),
        daemon=True,
    ).start()

  def proceso_dispensado_lote_y_captura(self, horarios_lote):
    expectativas_totales = {}
    for h in horarios_lote:
      letra = h.get("pastilla_letra", "A").upper()
      cantidad = h.get("cantidad", 1)
      expectativas_totales[letra] = expectativas_totales.get(letra, 0) + cantidad

    intentos = 0
    max_intentos = 5
    faltantes_actuales = expectativas_totales.copy()

    while intentos < max_intentos:
      ip = self.entry_ip.get().strip()
      hora_etiq = horarios_lote[0].get("hora", "LOTE")
      
      lote_a_dispensar = (
          expectativas_totales.copy()
          if intentos == 0
          else faltantes_actuales.copy()
      )

      self.log(
          f"Iniciando dispensado de lote (Horario/Origen: {hora_etiq}) -"
          f" Intento {intentos + 1}..."
      )

      max_cantidad = max(lote_a_dispensar.values()) if lote_a_dispensar else 1
      tiempo_espera = max_cantidad * 9

      exito_envio = True
      for letra, cantidad in lote_a_dispensar.items():
        self.log(f"Dispensando Pastilla {letra} (Cantidad a enviar: {cantidad})...")
        if not self.enviar_comando_dispensa(letra, cantidad):
          exito_envio = False
          break

      if not exito_envio:
        break

      self.log(
          f"Esperando {tiempo_espera} segundos ({max_cantidad} x 9s) para que"
          " caiga la última unidad..."
      )
      time.sleep(tiempo_espera)

      url_captura = f"http://{ip}/capture"
      timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
      ruta_imagen = os.path.join(
          CAPTURAS_DIR, f"captura_lote_{timestamp_str}.jpg"
      )

      try:
        self.log("Solicitando imagen de verificación del lote...")
        img_response = requests.get(url_captura, timeout=8)
        if img_response.status_code == 200:
          with open(ruta_imagen, "wb") as f:
            f.write(img_response.content)
          self.log(f"Imagen guardada en {ruta_imagen}")

          conteo_clases, ruta_annotada = self.analizar_imagen_yolo(
              ruta_imagen, "LOTE"
          )

          detectadas_por_letra = {}
          for letra_esp in expectativas_totales.keys():
            detectadas = sum(
                cant
                for nombre, cant in conteo_clases.items()
                if nombre.upper().endswith(f"_{letra_esp}")
                or nombre.upper() == letra_esp
            )
            detectadas_por_letra[letra_esp] = detectadas

          error_faltante = False
          error_excedente = False
          faltantes_actuales = {}

          for letra_esp, cant_esperada_total in expectativas_totales.items():
            det = detectadas_por_letra.get(letra_esp, 0)
            if det < cant_esperada_total:
              error_faltante = True
              faltantes_actuales[letra_esp] = cant_esperada_total - det
            elif det > cant_esperada_total:
              error_excedente = True

          clases_inesperadas = False
          for nombre, cant in conteo_clases.items():
            encontrado = any(
                nombre.upper().endswith(f"_{letra_esp}")
                or nombre.upper() == letra_esp
                for letra_esp in expectativas_totales.keys()
            )
            if not encontrado:
              clases_inesperadas = True

          if not error_faltante and not error_excedente and not clases_inesperadas:
            msg = (
                "Verificación OK: Se dispensaron correctamente todas las"
                " pastillas programadas. Por favor, retire las pastillas."
            )
            self.log(msg)
            self.guardar_mensaje(msg)
            messagebox.showinfo("Éxito", msg)

            self.log("Esperando 1 minuto para que se retiren las pastillas...")
            threading.Thread(
                target=self.verificar_retiro_posterior,
                args=(expectativas_totales,),
                daemon=True,
            ).start()
            break

          elif error_faltante and not error_excedente and not clases_inesperadas:
            msg = (
                "Faltan algunas pastillas en el lote. Reintentando faltantes:"
                f" {faltantes_actuales}..."
            )
            self.log(msg)
            self.guardar_mensaje(msg)
            
            intentos += 1
            continue

          else:
            msg_excedente = (
                "¡EXCEDENTE O ERROR DE CLASE DETECTADO! NO CONSUMIR LAS"
                " PASTILLAS y devolver a las tolvas."
            )
            self.log(msg_excedente)
            self.guardar_mensaje(msg_excedente)
            messagebox.showwarning("Advertencia", msg_excedente)

            msg_espera_tolva = (
                "Esperando 1 minuto para devolver las pastillas a las tolvas."
            )
            self.log(msg_espera_tolva)
            self.guardar_mensaje(msg_espera_tolva)
            time.sleep(60)

            self.log(
                "Tomando foto para verificar que no hay pastillas en el"
                " contenedor..."
            )
            try:
              img_resp_limpieza = requests.get(url_captura, timeout=8)
              if img_resp_limpieza.status_code == 200:
                ruta_limpieza = os.path.join(
                    CAPTURAS_DIR, f"limpieza_lote_{timestamp_str}.jpg"
                )
                with open(ruta_limpieza, "wb") as f:
                  f.write(img_resp_limpieza.content)
                conteo_limpieza, _ = self.analizar_imagen_yolo(
                    ruta_limpieza, "LOTE"
                )
                if sum(conteo_limpieza.values()) == 0:
                  self.log("Contenedor verificado: vacío correctamente.")
                else:
                  self.log("Aviso: Aún se detectan elementos en el contenedor.")
              else:
                self.log(
                    "Error al capturar imagen de verificación de contenedor"
                    " vacío."
                )
            except Exception as e:
              self.log(f"Excepción al verificar contenedor vacío: {e}")

            faltantes_actuales = expectativas_totales.copy()

            intentos += 1
            if intentos < max_intentos:
              self.log("Reiniciando el dispensado del último lote de pastillas...")
              continue
            else:
              msg_limite = (
                  "Se alcanzó el límite de intentos por excedente. Lote"
                  " cancelado."
              )
              self.log(msg_limite)
              self.guardar_mensaje(msg_limite)
              break
        else:
          self.log("Error al capturar imagen desde el ESP32-CAM.")
          break
      except Exception as e:
        self.log(f"Excepción al capturar lote: {e}")
        break

  def analizar_imagen_yolo(self, ruta_img, letra_esperada):
    conteo_clases = {}
    ruta_annotada = ruta_img
    if not self.yolo_model:
      self.log("YOLO Detección -> Modelo no disponible para análisis.")
      self.mostrar_imagen_en_gui(ruta_img)
      return conteo_clases, ruta_annotada

    try:
      self.log("Ejecutando análisis con YOLO...")
      resultados = self.yolo_model(ruta_img)

      for r in resultados:
        boxes = r.boxes
        for box in boxes:
          cls_id = int(box.cls[0])
          cls_name = self.yolo_model.names[cls_id]
          conteo_clases[cls_name] = conteo_clases.get(cls_name, 0) + 1

        img_plot = r.plot()
        ruta_annotada = ruta_img.replace(".jpg", "_det.jpg")
        cv2.imwrite(ruta_annotada, img_plot)
        self.mostrar_imagen_en_gui(ruta_annotada)

      if conteo_clases:
        detalles = ", ".join(
            [f"{nombre} ({cant} unid.)" for nombre, cant in conteo_clases.items()]
        )
        self.log(f"YOLO Detección -> {detalles}")
      else:
        self.log("YOLO Detección -> No se detectaron objetos en la imagen.")
        self.mostrar_imagen_en_gui(ruta_img)
    except Exception as e:
      self.log(f"Error en inferencia de YOLO: {e}")
      self.mostrar_imagen_en_gui(ruta_img)

    return conteo_clases, ruta_annotada

  def verificar_retiro_posterior(self, expectativas_totales):
    time.sleep(60)

    ip = self.entry_ip.get().strip()
    url_captura = f"http://{ip}/capture"
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_imagen = os.path.join(
        CAPTURAS_DIR, f"retiro_lote_{timestamp_str}.jpg"
    )

    try:
      self.log(
          "Tomando segunda foto para verificar si se retiraron las"
          " pastillas..."
      )
      img_response = requests.get(url_captura, timeout=8)
      if img_response.status_code == 200:
        with open(ruta_imagen, "wb") as f:
          f.write(img_response.content)

        conteo_clases, ruta_annotada = self.analizar_imagen_yolo(
            ruta_imagen, "LOTE"
        )
        total_en_bandeja = sum(conteo_clases.values())

        if total_en_bandeja == 0:
          msg = (
              "Confirmado: Las pastillas fueron retiradas correctamente."
              " Sistema en espera."
          )
          self.log(msg)
          self.guardar_mensaje(msg)
        else:
          msg = (
              "No se retiró la medicación de la bandeja después de 1 minuto."
          )
          self.log(msg)
          self.guardar_mensaje(msg)
          messagebox.showwarning("Advertencia de Retiro", msg)
      else:
        self.log("Error al capturar imagen de verificación de retiro.")
    except Exception as e:
      self.log(f"Excepción al verificar retiro: {e}")

  def mostrar_imagen_en_gui(self, ruta_imagen):
    try:
      img = Image.open(ruta_imagen)
      img = img.resize((240, 180), Image.Resampling.LANCZOS)
      img_tk = ImageTk.PhotoImage(img)
      self.lbl_imagen.config(image=img_tk, text="")
      self.lbl_imagen.image = img_tk
    except Exception as e:
      print(f"Error al mostrar imagen en GUI: {e}")

  def bucle_horario(self):
    ultimo_minuto_ejecutado = ""
    while self.activo:
      try:
        if os.path.exists(CONFIG_FILE):
          current_mtime = os.path.getmtime(CONFIG_FILE)
          if current_mtime > self.last_config_mtime:
            self.cargar_config()
            self.root.after(0, self.actualizar_lista_horarios)
            self.log(
                "Configuración recargada automáticamente (cambio externo"
                " detectado)."
            )
      except Exception:
        pass

      hora_actual = datetime.datetime.now().strftime("%H:%M")
      if hora_actual != ultimo_minuto_ejecutado:
        horarios = self.config_data.get("horarios", [])
        
        horarios_lote_actual = [
            h for h in horarios if h.get("hora") == hora_actual
        ]

        if horarios_lote_actual:
          self.log(
              f"Hora programada alcanzada ({hora_actual}). "
              f"Procesando lote de {len(horarios_lote_actual)} orden(es)..."
          )
          threading.Thread(
              target=self.proceso_dispensado_lote_y_captura,
              args=(horarios_lote_actual,),
              daemon=True,
          ).start()
          ultimo_minuto_ejecutado = hora_actual

      time.sleep(5)


if __name__ == "__main__":
  root = tk.Tk()
  app = DispensadorApp(root)
  root.mainloop()