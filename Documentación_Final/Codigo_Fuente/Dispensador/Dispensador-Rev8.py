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

# Importar el widget de calendario gráfico
try:
  from tkcalendar import Calendar
  CALENDAR_DISPONIBLE = True
except ImportError:
  CALENDAR_DISPONIBLE = False

MENSAJES_FILE = "mensajes.json"
STOCK_FILE = "stock.json"
CAPTURAS_DIR = "capturas"


class DispensadorApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Sistema Automatizado de Dispensador de Pastillas e IA")
    self.root.geometry("1200x820")

    if not os.path.exists(CAPTURAS_DIR):
      os.makedirs(CAPTURAS_DIR)

    self.last_config_mtime = 0
    self.last_stock_mtime = 0
    self.stock_entries = {}
    self.archivo_config_actual = ""

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
    self.cargar_stock()
    self.crear_widgets()

    self.activo = True
    self.hilo_cron = threading.Thread(target=self.bucle_horario, daemon=True)
    self.hilo_cron.start()

    threading.Thread(target=self.verificar_conexion, daemon=True).start()

  def obtener_nombre_archivo_config(self):
    """Genera el nombre del archivo basado en la fecha actual formato DDMMAA (Ej: 071126_config.json)"""
    fecha_str = datetime.date.today().strftime("%d%m%y")
    return f"{fecha_str}_config.json"

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
    self.archivo_config_actual = self.obtener_nombre_archivo_config()
    default_config = {
        "ip": "192.168.24.81",
        "horarios": [{
            "hora": "08:00",
            "pastilla_letra": "A",
            "cantidad": 1,
            "fecha": datetime.date.today().strftime("%Y-%m-%d"),
        }],
    }
    if os.path.exists(self.archivo_config_actual):
      try:
        self.last_config_mtime = os.path.getmtime(self.archivo_config_actual)
        with open(self.archivo_config_actual, "r", encoding="utf-8") as f:
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
      self.guardar_config_archivo(self.archivo_config_actual, self.config_data)

  def guardar_config_archivo(self, nombre_archivo, datos):
    try:
      with open(nombre_archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)
      if nombre_archivo == self.archivo_config_actual:
        self.last_config_mtime = os.path.getmtime(nombre_archivo)
    except Exception as e:
      self.log(f"Error al guardar {nombre_archivo}: {e}")

  def cargar_stock(self):
    default_stock = {"A": 30, "B": 30, "C": 30}
    if os.path.exists(STOCK_FILE):
      try:
        self.last_stock_mtime = os.path.getmtime(STOCK_FILE)
        with open(STOCK_FILE, "r", encoding="utf-8") as f:
          data = json.load(f)
          if isinstance(data, dict):
            self.stock_data = {**default_stock, **data}
          else:
            self.stock_data = default_stock
      except Exception:
        self.stock_data = default_stock
    else:
      self.stock_data = default_stock
      self.guardar_stock_archivo(default_stock)

  def guardar_stock_archivo(self, datos):
    try:
      with open(STOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)
      self.last_stock_mtime = os.path.getmtime(STOCK_FILE)
    except Exception as e:
      self.log(f"Error al guardar stock.json: {e}")

  def guardar_stock_desde_ui(self):
    try:
      nuevo_stock = {}
      for pastilla, entry in self.stock_entries.items():
        val = int(entry.get())
        if val < 0:
          raise ValueError("El stock no puede ser negativo.")
        nuevo_stock[pastilla] = val
      self.stock_data = nuevo_stock
      self.guardar_stock_archivo(self.stock_data)
      self.log("Stock actualizado manualmente desde la interfaz.")
      messagebox.showinfo("Éxito", "Stock guardado correctamente.")
    except ValueError as e:
      messagebox.showerror("Error", f"Dato inválido: {e}")

  def agregar_stock_parcial(self):
    letra = self.entry_add_letra.get().strip().upper()
    cant_str = self.entry_add_cant.get().strip()

    if letra not in ["A", "B", "C"]:
      messagebox.showwarning("Advertencia", "Ingrese un tipo de pastilla válido (A, B o C).")
      return

    try:
      cantidad_a_sumar = int(cant_str)
      if cantidad_a_sumar <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")
    except ValueError as e:
      messagebox.showerror("Error", f"Cantidad inválida: {e}")
      return

    self.stock_data[letra] = self.stock_data.get(letra, 0) + cantidad_a_sumar
    self.guardar_stock_archivo(self.stock_data)

    if letra in self.stock_entries:
      self.stock_entries[letra].delete(0, tk.END)
      self.stock_entries[letra].insert(0, str(self.stock_data[letra]))

    self.log(f"Recarga de stock: Se sumaron {cantidad_a_sumar} unidades a la Pastilla {letra}. Total actual: {self.stock_data[letra]}.")
    messagebox.showinfo("Éxito", f"Se agregaron {cantidad_a_sumar} unidades a la pastilla {letra}.")
    
    self.entry_add_cant.delete(0, tk.END)
    self.entry_add_cant.insert(0, "10")

  def descontar_stock_lote(self, cantidades_efectivas):
    for pastilla, cantidad in cantidades_efectivas.items():
      pastilla = pastilla.upper()
      if pastilla in self.stock_data:
        self.stock_data[pastilla] = max(0, self.stock_data[pastilla] - cantidad)
        
        if pastilla in self.stock_entries:
          self.root.after(0, lambda p=pastilla: [
              self.stock_entries[p].delete(0, tk.END),
              self.stock_entries[p].insert(0, str(self.stock_data[p]))
          ])
        self.log(f"Stock descontado por dispensado exitoso: Pastilla {pastilla} (-{cantidad}). Quedan {self.stock_data[pastilla]}.")
        
        stock_actual = self.stock_data[pastilla]
        if stock_actual <= 5:
          msg_stock = f"¡Atención! Solo quedan {stock_actual} Pastillas '{pastilla}' en stock."
          self.log(msg_stock)
          self.guardar_mensaje(msg_stock)
          self.root.after(0, lambda m=msg_stock: messagebox.showwarning("Stock Bajo", m))

    self.guardar_stock_archivo(self.stock_data)

  def guardar_ip(self):
    try:
      self.config_data["ip"] = self.entry_ip.get().strip()
      self.guardar_config_archivo(self.archivo_config_actual, self.config_data)
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

  def al_seleccionar_fecha(self, event):
    if CALENDAR_DISPONIBLE and hasattr(self, "cal"):
      fecha_seleccionada = self.cal.selection_get().strftime("%Y-%m-%d")
      self.entry_fecha_prog.delete(0, tk.END)
      self.entry_fecha_prog.insert(0, fecha_seleccionada)

  def agregar_horario(self):
    hora = self.entry_hora.get().strip()
    letra = self.entry_letra.get().strip().upper()
    cantidad_str = self.entry_cantidad.get().strip()
    fecha_ingresada = self.entry_fecha_prog.get().strip()

    if not hora or not letra or not cantidad_str or not fecha_ingresada:
      messagebox.showwarning(
          "Advertencia", "Por favor complete todos los campos de programación."
      )
      return

    try:
      cantidad = int(cantidad_str)
      parsed_date = datetime.datetime.strptime(fecha_ingresada, "%Y-%m-%d").date()
    except ValueError:
      messagebox.showerror("Error", "Cantidad inválida o formato de fecha incorrecto (use AAAA-MM-DD o selecciónela del calendario).")
      return

    nombre_archivo_destino = f"{parsed_date.strftime('%d%m%y')}_config.json"

    datos_destino = {"ip": self.entry_ip.get().strip(), "horarios": []}
    if os.path.exists(nombre_archivo_destino):
      try:
        with open(nombre_archivo_destino, "r", encoding="utf-8") as f:
          contenido = json.load(f)
          if isinstance(contenido, dict):
            datos_destino = contenido
      except Exception:
        pass

    if "horarios" not in datos_destino:
      datos_destino["horarios"] = []

    nuevo_item = {
        "hora": hora,
        "pastilla_letra": letra,
        "cantidad": cantidad,
        "fecha": fecha_ingresada,
    }
    datos_destino["horarios"].append(nuevo_item)

    self.guardar_config_archivo(nombre_archivo_destino, datos_destino)

    if nombre_archivo_destino == self.archivo_config_actual:
      self.config_data = datos_destino
      self.actualizar_lista_horarios()

    self.log(
        f"Horario agendado en {nombre_archivo_destino}: {hora} - Pastilla {letra} ({cantidad} unid.) [Fecha: {fecha_ingresada}]"
    )
    messagebox.showinfo("Éxito", f"Horario agendado correctamente para el {fecha_ingresada}.")

  def eliminar_horario(self):
    seleccion = self.listbox_horarios.curselection()
    if not seleccion:
      messagebox.showwarning(
          "Advertencia", "Seleccione un horario de la lista para eliminar."
      )
      return
    idx = seleccion[0]
    eliminado = self.config_data["horarios"].pop(idx)

    self.guardar_config_archivo(self.archivo_config_actual, self.config_data)
    self.actualizar_lista_horarios()
    self.log(
        f"Horario eliminado de {self.archivo_config_actual}: {eliminado['hora']} - Pastilla {eliminado['pastilla_letra']}"
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

    # ==========================================
    # EXTREMO DERECHO: Panel de Stock Actual y Recarga
    # ==========================================
    frame_stock_right = tk.LabelFrame(
        frame_main, text=" Gestión de Stock ", font=("Arial", 10, "bold")
    )
    frame_stock_right.pack(side=tk.RIGHT, fill="y", padx=5, pady=0)

    row_s = 0
    for pastilla in ["A", "B", "C"]:
      cant_val = self.stock_data.get(pastilla, 0)
      tk.Label(
          frame_stock_right, text=f"Pastilla {pastilla}:", font=("Arial", 9)
      ).grid(row=row_s, column=0, sticky="w", padx=10, pady=6)

      entry_s = tk.Entry(frame_stock_right, font=("Arial", 9), width=8)
      entry_s.insert(0, str(cant_val))
      entry_s.grid(row=row_s, column=1, padx=10, pady=6)

      self.stock_entries[pastilla] = entry_s
      row_s += 1

    btn_guardar_stock = tk.Button(
        frame_stock_right,
        text="Guardar Stock Completo",
        command=self.guardar_stock_desde_ui,
        font=("Arial", 9, "bold"),
        bg="#008CBA",
        fg="white",
    )
    btn_guardar_stock.grid(
        row=row_s, column=0, columnspan=2, padx=10, pady=10, sticky="we"
    )
    row_s += 1

    sub_frame_recarga = tk.LabelFrame(
        frame_stock_right, text=" Agregar al Stock ", font=("Arial", 9, "bold")
    )
    sub_frame_recarga.grid(row=row_s, column=0, columnspan=2, padx=5, pady=10, sticky="we")

    tk.Label(sub_frame_recarga, text="Tipo (A/B/C):", font=("Arial", 8)).grid(
        row=0, column=0, sticky="w", padx=5, pady=5
    )
    self.entry_add_letra = tk.Entry(sub_frame_recarga, font=("Arial", 9), width=6)
    self.entry_add_letra.grid(row=0, column=1, padx=5, pady=5)
    self.entry_add_letra.insert(0, "A")

    tk.Label(sub_frame_recarga, text="Cantidad:", font=("Arial", 8)).grid(
        row=1, column=0, sticky="w", padx=5, pady=5
    )
    self.entry_add_cant = tk.Entry(sub_frame_recarga, font=("Arial", 9), width=6)
    self.entry_add_cant.grid(row=1, column=1, padx=5, pady=5)
    self.entry_add_cant.insert(0, "10")

    btn_agregar = tk.Button(
        sub_frame_recarga,
        text="Agregar al Stock",
        command=self.agregar_stock_parcial,
        font=("Arial", 9, "bold"),
        bg="#4CAF50",
        fg="white",
    )
    btn_agregar.grid(row=2, column=0, columnspan=2, padx=5, pady=8, sticky="we")

    # ==========================================
    # LADO IZQUIERDO: Controles, Programación e Imagen IA
    # ==========================================
    frame_left_container = tk.Frame(frame_main)
    frame_left_container.pack(
        side=tk.LEFT, fill="both", expand=True, padx=5, pady=0
    )

    frame_left = tk.Frame(frame_left_container)
    frame_left.pack(side=tk.LEFT, fill="both", expand=True, padx=5)

    frame_right = tk.Frame(frame_left_container)
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
        frame_left, text="Programación de Medicación con Calendario", font=("Arial", 10, "bold")
    )
    frame_prog.pack(fill="x", pady=5)

    if CALENDAR_DISPONIBLE:
      f_cal = tk.Frame(frame_prog)
      f_cal.pack(fill="x", padx=5, pady=5)
      
      self.cal = Calendar(
          f_cal, 
          selectmode='day', 
          year=datetime.date.today().year, 
          month=datetime.date.today().month, 
          day=datetime.date.today().day,
          font=("Arial", 9),
          locale='es_ES'
      )
      self.cal.pack(fill="x", expand=True, padx=5, pady=2)
      self.cal.bind("<<CalendarSelected>>", self.al_seleccionar_fecha)
    else:
      tk.Label(
          frame_prog, 
          text="[Aviso: Librería 'tkcalendar' no instalada. Instálela con 'pip install tkcalendar']", 
          fg="red", 
          font=("Arial", 8)
      ).pack(padx=5, pady=2)

    f_inputs = tk.Frame(frame_prog)
    f_inputs.pack(fill="x", padx=5, pady=5)

    tk.Label(f_inputs, text="Fecha:", font=("Arial", 8, "bold")).grid(
        row=0, column=0, sticky="w", padx=2, pady=2
    )
    self.entry_fecha_prog = tk.Entry(f_inputs, font=("Arial", 9), width=10)
    self.entry_fecha_prog.grid(row=0, column=1, padx=2, pady=2, sticky="w")
    self.entry_fecha_prog.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

    tk.Label(f_inputs, text="Hora (HH:MM):", font=("Arial", 8)).grid(
        row=0, column=2, sticky="w", padx=2, pady=2
    )
    self.entry_hora = tk.Entry(f_inputs, font=("Arial", 9), width=6)
    self.entry_hora.grid(row=0, column=3, padx=2, pady=2, sticky="w")
    self.entry_hora.insert(0, "08:00")

    tk.Label(f_inputs, text="Pastilla:", font=("Arial", 8)).grid(
        row=1, column=0, sticky="w", padx=2, pady=2
    )
    self.entry_letra = tk.Entry(f_inputs, font=("Arial", 9), width=5)
    self.entry_letra.grid(row=1, column=1, padx=2, pady=2, sticky="w")
    self.entry_letra.insert(0, "A")

    tk.Label(f_inputs, text="Cant:", font=("Arial", 8)).grid(
        row=1, column=2, sticky="w", padx=2, pady=2
    )
    self.entry_cantidad = tk.Entry(f_inputs, font=("Arial", 9), width=6)
    self.entry_cantidad.grid(row=1, column=3, padx=2, pady=2, sticky="w")
    self.entry_cantidad.insert(0, "1")

    btn_agregar = tk.Button(
        f_inputs,
        text="Agregar Horario",
        command=self.agregar_horario,
        font=("Arial", 9, "bold"),
        bg="#4CAF50",
        fg="white",
    )
    btn_agregar.grid(row=1, column=4, padx=5, pady=2)

    frame_agendados = tk.LabelFrame(
        frame_left,
        text="Horarios y Cantidades de Pastillas Agendados (Día Actual)",
        font=("Arial", 10, "bold"),
    )
    frame_agendados.pack(fill="both", expand=True, pady=5)

    self.listbox_horarios = tk.Listbox(
        frame_agendados, font=("Consolas", 9), height=4
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
        text="Eliminar Horario Seleccionado (Día Actual)",
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
        frame_log, font=("Consolas", 8), height=6
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
            
            self.descontar_stock_lote(expectativas_totales)

            messagebox.showinfo("Éxito", msg)

            self.log("Esperando 1 minuto para el control de retiro...")
            threading.Thread(
                target=self.verificar_retiro_posterior,
                args=(expectativas_totales,),
                daemon=True,
            ).start()
            break

          elif error_faltante and not error_excedente and not clases_inesperadas:
            cantidades_parciales_exitosas = {}
            for letra_esp, cant_esperada_total in expectativas_totales.items():
              det = detectadas_por_letra.get(letra_esp, 0)
              if det > 0:
                cantidades_parciales_exitosas[letra_esp] = min(det, cant_esperada_total)
            
            if cantidades_parciales_exitosas:
              self.descontar_stock_lote(cantidades_parciales_exitosas)
            
            # (Silenciado el mensaje y guardado de reintento de faltantes por solicitud)
            
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
    # ==========================================
    # PRIMER CONTROL (A los 60 segundos)
    # ==========================================
    time.sleep(60)

    ip = self.entry_ip.get().strip()
    url_captura = f"http://{ip}/capture"
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_imagen_1 = os.path.join(
        CAPTURAS_DIR, f"retiro_lote_1_{timestamp_str}.jpg"
    )

    try:
      self.log("Tomando primera foto de verificación de retiro...")
      img_response = requests.get(url_captura, timeout=8)
      if img_response.status_code == 200:
        with open(ruta_imagen_1, "wb") as f:
          f.write(img_response.content)

        conteo_clases_1, _ = self.analizar_imagen_yolo(ruta_imagen_1, "LOTE")
        total_en_bandeja_1 = sum(conteo_clases_1.values())

        if total_en_bandeja_1 == 0:
          # Se retiraron a la primera
          msg = (
              "Confirmado: Las pastillas fueron retiradas correctamente."
              " Sistema en espera."
          )
          self.log(msg)
          self.guardar_mensaje(msg)
          return
        else:
          # Aún no se tomaron en el primer minuto: enviamos aviso y esperamos 1 minuto más para reintentar
          msg_aviso = "No se retiró la medicación de la bandeja después de 1 minuto."
          self.log(msg_aviso)
          self.guardar_mensaje(msg_aviso)
          
          self.log("Esperando 1 minuto más para la segunda y última foto de reintento...")
          
          # ==========================================
          # SEGUNDO CONTROL / REINTENTO (1 minuto adicional)
          # ==========================================
          time.sleep(60)
          
          timestamp_str_2 = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
          ruta_imagen_2 = os.path.join(
              CAPTURAS_DIR, f"retiro_lote_2_{timestamp_str_2}.jpg"
          )

          self.log("Tomando segunda y última foto de verificación de retiro...")
          img_response_2 = requests.get(url_captura, timeout=8)
          if img_response_2.status_code == 200:
            with open(ruta_imagen_2, "wb") as f:
              f.write(img_response_2.content)

            conteo_clases_2, _ = self.analizar_imagen_yolo(ruta_imagen_2, "LOTE")
            total_en_bandeja_2 = sum(conteo_clases_2.values())

            if total_en_bandeja_2 == 0:
              msg_exito = "Ahora si se retiraron las pastillas del Dispensador"
              self.log(f"Confirmado: {msg_exito}")
              self.guardar_mensaje(msg_exito)
            else:
              msg_alerta = "Siguen sin retirarse las Pastillas del Dispensador"
              self.log(f"Alerta: {msg_alerta}")
              self.guardar_mensaje(msg_alerta)
              self.root.after(0, lambda m=msg_alerta: messagebox.showwarning("Advertencia de Retiro", m))
          else:
            self.log("Error al capturar segunda imagen de verificación de retiro.")
      else:
        self.log("Error al capturar primera imagen de verificación de retiro.")
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
      archivo_esperado = self.obtener_nombre_archivo_config()
      if archivo_esperado != self.archivo_config_actual:
        self.log(f"Cambio de día detectado. Cambiando al archivo de configuración: {archivo_esperado}")
        self.cargar_config()
        self.root.after(0, self.actualizar_lista_horarios)

      try:
        if os.path.exists(self.archivo_config_actual):
          current_mtime = os.path.getmtime(self.archivo_config_actual)
          if current_mtime > self.last_config_mtime:
            self.cargar_config()
            self.root.after(0, self.actualizar_lista_horarios)
            self.log(
                f"Configuración recargada automáticamente desde {self.archivo_config_actual}."
            )
      except Exception:
        pass

      try:
        if os.path.exists(STOCK_FILE):
          current_stock_mtime = os.path.getmtime(STOCK_FILE)
          if current_stock_mtime > self.last_stock_mtime:
            self.cargar_stock()
            for pastilla, entry in self.stock_entries.items():
              val_actual = self.stock_data.get(pastilla, 0)
              self.root.after(0, lambda p=pastilla, v=val_actual: [
                  self.stock_entries[p].delete(0, tk.END),
                  self.stock_entries[p].insert(0, str(v))
              ])
            self.log("Stock recargado automáticamente (cambio externo detectado en stock.json).")
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