import json
import os
import time
from datetime import datetime
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import requests

# Nombre fijo para el archivo único de novedades
JSON_FILE = "Novedades_Radar.json"

class RadarApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor de Radar C1001 - Wi-Fi")
        self.root.geometry("420x510")
        self.root.resizable(False, False)

        # Sesión persistente (HTTP Keep-Alive) para reutilizar la conexión TCP
        self.session = requests.Session()
        
        # Candado para evitar la superposición de hilos de red
        self.consultando_red = False

        # Variables de estado previo para detectar cambios
        self.prev_presence = None
        self.prev_fall = None
        self.prev_static = None
        self.prev_modo = 0
        self.modo_actual = 0  # 0: Caídas, 1: Signos Vitales

        # Variables para el cálculo del promedio de 1 minuto en Signos Vitales
        self.vital_start_time = None
        self.bpm_samples = []
        self.rpm_samples = []

        # --- Panel de Configuración de Red ---
        frame_config = ttk.LabelFrame(root, text=" Configuración de Red ")
        frame_config.pack(fill="x", padx=20, pady=10)

        ttk.Label(frame_config, text="IP del ESP32:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        
        # IP fija predeterminada usando StringVar (editable en tiempo real)
        self.ip_var = tk.StringVar(value="10.129.104.200")
        self.entry_ip = ttk.Entry(frame_config, textvariable=self.ip_var, width=18, font=("Arial", 10))
        self.entry_ip.grid(row=0, column=1, padx=5, pady=8)

        self.btn_ping = ttk.Button(frame_config, text="Probar Conexión", command=self.probar_conexion)
        self.btn_ping.grid(row=0, column=2, padx=5, pady=8)

        # --- Botón de Cambio de Modo ---
        self.btn_modo = ttk.Button(root, text="Cambiar a Modo: Signos Vitales", command=self.alternar_modo)
        self.btn_modo.pack(fill="x", padx=20, pady=2)

        # --- Estado y Controles ---
        self.lbl_connection = ttk.Label(root, text="Estado: Desconectado", font=("Arial", 10, "bold"), foreground="gray")
        self.lbl_connection.pack(pady=2)

        # --- Marco de información del Radar ---
        frame_info = ttk.LabelFrame(root, text=" Estados Actuales ")
        frame_info.pack(fill="both", expand=True, padx=20, pady=10)

        self.lbl_presence = ttk.Label(frame_info, text="Presencia: --", font=("Arial", 11))
        self.lbl_presence.pack(anchor="w", padx=10, pady=5)

        self.lbl_movement = ttk.Label(frame_info, text="Movimiento: --", font=("Arial", 11))
        self.lbl_movement.pack(anchor="w", padx=10, pady=5)

        self.lbl_range = ttk.Label(frame_info, text="Intensidad de movimiento: --", font=("Arial", 11))
        self.lbl_range.pack(anchor="w", padx=10, pady=5)

        # Etiquetas dinámicas
        self.lbl_extra1 = ttk.Label(frame_info, text="Caída: --", font=("Arial", 11, "bold"), foreground="green")
        self.lbl_extra1.pack(anchor="w", padx=10, pady=5)

        self.lbl_extra2 = ttk.Label(frame_info, text="Permanencia Estática: --", font=("Arial", 11))
        self.lbl_extra2.pack(anchor="w", padx=10, pady=5)

        # Iniciar el bucle de monitoreo automático (cada 2 segundos)
        self.loop_activo = True
        self.update_data()

    def probar_conexion(self):
        def tarea_ping():
            ip = self.ip_var.get().strip()
            url = f"http://{ip}/data"
            try:
                response = self.session.get(url, timeout=5)
                if response.status_code == 200:
                    self.root.after(0, lambda: messagebox.showinfo("Éxito", f"¡Conexión exitosa con el ESP32 en {ip}!"))
                    self.root.after(0, lambda: self.lbl_connection.config(text="Estado: Conectado OK", foreground="green"))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Atención", f"Respondió con código HTTP: {response.status_code}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error Técnico", f"No se pudo conectar:\n{e}"))

        threading.Thread(target=tarea_ping, daemon=True).start()

    def alternar_modo(self):
        """Envía una petición al ESP32 para cambiar el modo de trabajo del radar"""
        nuevo_modo = 1 if self.modo_actual == 0 else 0
        ip = self.ip_var.get().strip()
        url = f"http://{ip}/mode?val={nuevo_modo}"

        def tarea_cambio():
            try:
                response = self.session.get(url, timeout=5)
                if response.status_code == 200:
                    self.modo_actual = nuevo_modo
                    if self.modo_actual == 1:
                        self.root.after(0, lambda: self.btn_modo.config(text="Cambiar a Modo: Caídas"))
                    else:
                        self.root.after(0, lambda: self.btn_modo.config(text="Cambiar a Modo: Signos Vitales"))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Atención", "El ESP32 no pudo cambiar de modo"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error de Red", f"No se pudo enviar la orden:\n{e}"))

        threading.Thread(target=tarea_cambio, daemon=True).start()

    def log_event(self, event_type, description):
        """Escribe los eventos en el archivo único Novedades_Radar.json"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        event_entry = {
            "timestamp": timestamp,
            "evento": event_type,
            "detalle": description
        }

        data = []
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = []

        data.append(event_entry)

        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def update_data(self):
        if not self.loop_activo:
            return

        if self.consultando_red:
            self.root.after(2000, self.update_data)
            return

        def tarea_fondo():
            self.consultando_red = True
            ip = self.ip_var.get().strip()
            url = f"http://{ip}/data"
            try:
                response = self.session.get(url, timeout=4)
                if response.status_code == 200:
                    data = response.json()
                    self.root.after(0, lambda: self.procesar_datos_exitosos(data))
                else:
                    self.root.after(0, lambda: self.lbl_connection.config(text="Estado: Error de servidor", foreground="red"))
            except requests.exceptions.RequestException:
                self.root.after(0, lambda: self.lbl_connection.config(text="Estado: Desconectado / Sin señal", foreground="red"))
            finally:
                self.consultando_red = False

        threading.Thread(target=tarea_fondo, daemon=True).start()
        self.root.after(2000, self.update_data)

    def procesar_datos_exitosos(self, data):
        self.lbl_connection.config(text="Estado: Monitoreando en vivo", foreground="green")

        self.modo_actual = data.get("modo", 0)
        presence = data.get("presence")
        movement = data.get("movement")
        moving_range = data.get("movingRange")
        fall_state = data.get("fallState")
        static_state = data.get("staticState")
        bpm = data.get("bpm", 0)
        rpm = data.get("rpm", 0)

        # --- DETECTAR CAMBIO DE MODO PARA EL LOG ---
        if self.prev_modo is not None and self.prev_modo != self.modo_actual:
            modo_texto = "Signos Vitales" if self.modo_actual == 1 else "Caídas"
            self.log_event("Cambio de Modo", f"El sistema cambió al modo: {modo_texto}")
            
            # Si acaba de entrar a signos vitales, inicializamos el temporizador de 1 minuto
            if self.modo_actual == 1:
                self.vital_start_time = time.time()
                self.bpm_samples.clear()
                self.rpm_samples.clear()

        self.prev_modo = self.modo_actual

        # Sincronizar texto del botón según el modo que reporta el ESP32
        if self.modo_actual == 1:
            self.btn_modo.config(text="Cambiar a Modo: Caídas")
        else:
            self.btn_modo.config(text="Cambiar a Modo: Signos Vitales")

        # Actualizar textos comunes
        pres_text = "Hay alguien presente" if presence == 1 else "No hay nadie presente"
        self.lbl_presence.config(text=f"Presencia: {pres_text}")

        mov_dict = {0: "Ninguno", 1: "Quieto", 2: "En movimiento"}
        self.lbl_movement.config(text=f"Movimiento: {mov_dict.get(movement, 'Desconocido')}")
        self.lbl_range.config(text=f"Intensidad de movimiento: {moving_range}")

        # --- RENDERIZADO SEGÚN EL MODO ACTIVO ---
        if self.modo_actual == 0:
            # Modo Caídas
            fall_text = "¡CAÍDA DETECTADA!" if fall_state == 1 else "Sin caída"
            self.lbl_extra1.config(
                text=f"Caída: {fall_text}", 
                foreground="red" if fall_state == 1 else "green",
                font=("Arial", 11, "bold")
            )
            static_text = "Permanencia estática detectada" if static_state == 1 else "Sin permanencia estática"
            self.lbl_extra2.config(text=f"Permanencia Estática: {static_text}", foreground="black", font=("Arial", 11))

            # --- Detectar cambios para guardar en Novedades_Radar.json ---
            if self.prev_presence is not None and self.prev_presence != presence:
                desc = "Hay presencia" if presence == 1 else "No hay presencia"
                self.log_event("Cambio de Presencia", desc)

            if self.prev_fall is not None and self.prev_fall != fall_state:
                desc = "¡Caída detectada!" if fall_state == 1 else "Se reestableció la caída"
                self.log_event("Cambio de Estado de Caída", desc)

            if self.prev_static is not None and self.prev_static != static_state:
                desc = "Permanencia estática iniciada" if static_state == 1 else "Sin permanencia estática"
                self.log_event("Cambio de Permanencia", desc)

            self.prev_presence = presence
            self.prev_fall = fall_state
            self.prev_static = static_state

        else:
            # Modo Signos Vitales
            bpm_str = f"{bpm} lpm" if bpm > 0 else "Buscando / Quieto..."
            rpm_str = f"{rpm} rpm" if rpm > 0 else "Buscando / Quieto..."
            
            self.lbl_extra1.config(text=f"Ritmo Cardíaco (BPM): {bpm_str}", foreground="blue", font=("Arial", 11, "bold"))
            self.lbl_extra2.config(text=f"Ritmo Respiratorio (RPM): {rpm_str}", foreground="purple", font=("Arial", 11, "bold"))

            # Acumular muestras válidas si están midiendo
            if bpm > 0:
                self.bpm_samples.append(bpm)
            if rpm > 0:
                self.rpm_samples.append(rpm)

            # Verificar si ya pasaron 60 segundos (1 minuto) en este modo para promediar y registrar
            if self.vital_start_time and (time.time() - self.vital_start_time >= 60):
                if len(self.bpm_samples) > 0 and len(self.rpm_samples) > 0:
                    prom_bpm = sum(self.bpm_samples) / len(self.bpm_samples)
                    prom_rpm = sum(self.rpm_samples) / len(self.rpm_samples)
                    
                    detalle_promedio = f"Promedio 1 Minuto -> BPM: {prom_bpm:.1f} lpm | RPM: {prom_rpm:.1f} rpm"
                    self.log_event("Reporte Signos Vitales", detalle_promedio)

                # Reiniciar temporizador y muestras para el siguiente minuto
                self.vital_start_time = time.time()
                self.bpm_samples.clear()
                self.rpm_samples.clear()

if __name__ == "__main__":
    root = tk.Tk()
    app = RadarApp(root)
    root.mainloop()