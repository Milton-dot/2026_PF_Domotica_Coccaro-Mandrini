#include <driver/i2s.h>

#define MIC_SD 32
#define MIC_WS 25
#define MIC_SCK 33
#define SPK_BCLK 13
#define SPK_LRC 4
#define SPK_DOUT 2
#define BOTON 26
#define LED_PIN 27

#define REC_SAMPLE_RATE 16000
#define SERIAL_BAUD 921600

int32_t micBuf[1024];
int16_t micOut[1024];
uint8_t spkBuf[2048];

bool grabando = false;

// ---------- BOTÓN (interrupción por flanco, una sola vez por pulsación) ----------
volatile bool botonFlag = false;
volatile unsigned long ultimoIsr = 0;

void IRAM_ATTR isrBoton() {
  unsigned long t = millis();
  if (t - ultimoIsr > 250) {      // antirrebote
    ultimoIsr = t;
    botonFlag = true;
  }
}

bool botonPulsado() {
  if (botonFlag) {
    botonFlag = false;
    return true;
  }
  return false;
}

// ---------- I2S ----------
void setupMic() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = REC_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {.bck_io_num = MIC_SCK, .ws_io_num = MIC_WS, .data_out_num = I2S_PIN_NO_CHANGE, .data_in_num = MIC_SD};
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
}

void stopMic() {
  i2s_driver_uninstall(I2S_NUM_0);
}

void setupSpk(int rate) {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = rate,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {.bck_io_num = SPK_BCLK, .ws_io_num = SPK_LRC, .data_out_num = SPK_DOUT, .data_in_num = I2S_PIN_NO_CHANGE};
  i2s_driver_install(I2S_NUM_1, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pins);
}

// ---------- SERIAL ----------
void vaciarRx() {
  while (Serial.available()) Serial.read();
}

// Descarta bytes residuales hasta que pasen "ms_silencio" sin recibir nada
// (con un tope total de 1 segundo para no quedar atrapado).
void drenarSerial(unsigned long ms_silencio) {
  unsigned long inicio = millis();
  unsigned long ultimo = millis();
  while (millis() - ultimo < ms_silencio && millis() - inicio < 1000) {
    if (Serial.available()) {
      Serial.read();
      ultimo = millis();
    }
  }
}

void iniciarGrabacion() {
  grabando = true;
  setupMic();
  digitalWrite(LED_PIN, HIGH);
  vaciarRx();                    // por si quedó audio viejo en el buffer de entrada
  Serial.println("START");
  Serial.flush();
}

void detenerGrabacion() {
  grabando = false;
  digitalWrite(LED_PIN, LOW);
  stopMic();
  vaciarRx();
  Serial.println("END");         // se manda como "END\r\n", Python busca esa secuencia
  Serial.flush();
}

// ---------- REPRODUCCIÓN ----------
void reproducir() {
  uint8_t header[8];
  int got = 0;
  unsigned long start = millis();
  while (got < 8 && (millis() - start < 2000)) {
    if (Serial.available()) {
      got += Serial.readBytes(header + got, 8 - got);
    }
  }
  if (got < 8) {
    Serial.println("PLAYED");
    return;
  }

  uint32_t sampleRate = header[0] | (header[1] << 8) | (header[2] << 16) | ((uint32_t)header[3] << 24);
  uint32_t totalBytes = header[4] | (header[5] << 8) | (header[6] << 16) | ((uint32_t)header[7] << 24);

  setupSpk(sampleRate);

  uint32_t received = 0;
  bool interrumpido = false;
  unsigned long ultimoDato = millis();

  while (received < totalBytes) {
    if (botonPulsado()) {
      interrumpido = true;
      Serial.println("INTERRUPTED");
      Serial.flush();
      break;
    }

    if (Serial.available()) {
      int chunk = min((uint32_t)sizeof(spkBuf), totalBytes - received);
      int r = Serial.readBytes(spkBuf, chunk);
      if (r > 0) {
        size_t bw = 0;
        i2s_write(I2S_NUM_1, spkBuf, r, &bw, portMAX_DELAY);
        received += r;
        ultimoDato = millis();
      }
    } else if (millis() - ultimoDato > 3000) {
      break;                     // Python dejó de mandar datos: no quedarse colgado
    }
  }

  if (interrumpido) {
    i2s_zero_dma_buffer(I2S_NUM_1);   // corta el sonido ya
    drenarSerial(150);                // tira el audio que Python alcanzó a mandar
    i2s_driver_uninstall(I2S_NUM_1);
    botonFlag = false;                // ignora pulsaciones durante el cambio
    iniciarGrabacion();               // manda START
  } else {
    // silencio al final para que se escuche completa la cola del audio
    memset(spkBuf, 0, sizeof(spkBuf));
    for (int i = 0; i < 5; i++) {
      size_t bw = 0;
      i2s_write(I2S_NUM_1, spkBuf, sizeof(spkBuf), &bw, portMAX_DELAY);
    }
    i2s_driver_uninstall(I2S_NUM_1);
    Serial.println("PLAYED");
  }
}

// ---------- SETUP / LOOP ----------
void setup() {
  Serial.setRxBufferSize(8192);   // debe ir ANTES de Serial.begin()
  Serial.begin(SERIAL_BAUD);
  Serial.setTimeout(10);

  pinMode(BOTON, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(BOTON), isrBoton, FALLING);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println("READY");
}

void loop() {
  if (!grabando && Serial.available() > 0) {
    if (Serial.peek() == 'p') {
      Serial.read();
      reproducir();
      return;
    } else {
      Serial.read();              // descarta basura que no sea un comando válido
    }
  }

  if (botonPulsado()) {
    if (!grabando) {
      iniciarGrabacion();
    } else {
      detenerGrabacion();
    }
  }

  if (grabando) {
    size_t br = 0;
    i2s_read(I2S_NUM_0, micBuf, sizeof(micBuf), &br, portMAX_DELAY);
    int cnt = br / sizeof(int32_t);
    for (int i = 0; i < cnt; i++) {
      int32_t v = micBuf[i] >> 13;
      if (v > 32767) v = 32767;
      if (v < -32768) v = -32768;
      micOut[i] = (int16_t)v;
    }
    Serial.write((uint8_t*)micOut, cnt * 2);   // un solo write por bloque
  } else {
    delay(1);
  }
}