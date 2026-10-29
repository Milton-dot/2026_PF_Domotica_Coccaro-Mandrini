import serial, wave, time, sys, os, struct
from anthropic import Anthropic
from piper import PiperVoice

PUERTO = "COM9"
BAUDRATE = 921600
SAMPLE_RATE = 16000
RECORD_SECONDS = 5
ARCHIVO_WAV = "grabacion.wav"
MODELO_WHISPER = "tiny"
MODELO_CLAUDE = "claude-haiku-4-5-20251001"
VOZ_PIPER = "es_AR-daniela-high.onnx"  # ajustá al archivo que descargaste

SYSTEM_PROMPT = """Sos un asistente de voz para el hogar de una persona mayor.
Hablá siempre en español, con frases cortas y claras, tono cálido y pausado.
No uses jerga técnica. No hagas más de una pregunta por respuesta.
Recordá el contexto de la conversación."""

TOOLS = [
    {"name": "controlar_luz", "description": "Enciende o apaga la luz de una habitación.",
     "input_schema": {"type": "object", "properties": {
         "habitacion": {"type": "string"}, "estado": {"type": "string", "enum": ["encender", "apagar"]}},
         "required": ["habitacion", "estado"]}},
    {"type": "web_search", "name": "web_search", "max_uses": 3}
]


def ejecutar_tool(nombre, entrada):
    if nombre == "controlar_luz":
        return f"Luz de {entrada['habitacion']} {'encendida' if entrada['estado']=='encender' else 'apagada'}."
    return "ok"


def grabar_audio(ser):
    total = SAMPLE_RATE * RECORD_SECONDS * 2
    ser.reset_input_buffer()
    ser.write(b'r')
    t1 = time.time()
    while time.time() - t1 < 8:
        if ser.readline().decode(errors="ignore").strip() == "START":
            break
    audio = b""
    while len(audio) < total:
        chunk = ser.read(total - len(audio))
        if chunk:
            audio += chunk
    with wave.open(ARCHIVO_WAV, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio)


def transcribir(whisper_model):
    r = whisper_model.transcribe(ARCHIVO_WAV, language="es", fp16=False)
    return r["text"].strip()


def hablar_con_claude(client, messages, texto):
    messages.append({"role": "user", "content": texto})
    resp = client.messages.create(model=MODELO_CLAUDE, max_tokens=400, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages)
    while resp.stop_reason == "tool_use":
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                out = ejecutar_tool(b.name, b.input) if b.name != "web_search" else None
                if out:
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
        if results:
            messages.append({"role": "user", "content": results})
        resp = client.messages.create(model=MODELO_CLAUDE, max_tokens=400, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages)
    texto_final = "".join(b.text for b in resp.content if b.type == "text")
    messages.append({"role": "assistant", "content": texto_final})
    return texto_final


def sintetizar_y_enviar(ser, piper_voice, texto):
    audio_bytes = bytearray()
    sample_rate = piper_voice.config.sample_rate
    for chunk in piper_voice.synthesize(texto):
        audio_bytes.extend(chunk.audio_int16_bytes)

    header = struct.pack("<II", sample_rate, len(audio_bytes))
    ser.write(header)
    ser.write(bytes(audio_bytes))
    ser.flush()

    t1 = time.time()
    while time.time() - t1 < 15:
        if ser.readline().decode(errors="ignore").strip() == "PLAYED":
            break


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Falta ANTHROPIC_API_KEY"); sys.exit(1)

    print("Cargando Whisper y Piper...")
    import whisper
    whisper_model = whisper.load_model(MODELO_WHISPER)
    piper_voice = PiperVoice.load(VOZ_PIPER)

    client = Anthropic(api_key=api_key)
    messages = []
    ser = serial.Serial(PUERTO, BAUDRATE, timeout=1)
    time.sleep(2)

    print("Listo. ENTER para hablar, 'salir' para terminar.")
    while True:
        if input().strip().lower() == "salir":
            break
        grabar_audio(ser)
        texto = transcribir(whisper_model)
        print("Vos:", texto)
        if not texto:
            continue
        respuesta = hablar_con_claude(client, messages, texto)
        print("Claude:", respuesta)
        sintetizar_y_enviar(ser, piper_voice, respuesta)

    ser.close()


if __name__ == "__main__":
    main()
