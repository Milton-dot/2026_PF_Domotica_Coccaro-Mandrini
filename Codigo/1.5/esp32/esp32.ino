#include <Arduino.h>
#include <driver/i2s.h>


// ============================================================
// PINES
// ============================================================

#define MIC_SD 32
#define MIC_WS 25
#define MIC_SCK 33

#define SPK_BCLK 13
#define SPK_LRC 4
#define SPK_DOUT 2

#define BOTON 26
#define LED_PIN 27


// ============================================================
// CONFIGURACIÓN
// ============================================================

#define REC_SAMPLE_RATE 16000

#define SERIAL_BAUD 921600

#define MAX_PAYLOAD 2048


// ============================================================
// PROTOCOLO
// ============================================================

const uint8_t MAGIC[4] = {
  0xAA, 0x55, 0xAA, 0x55
};

#define PKT_START 1
#define PKT_AUDIO_REC 2
#define PKT_END 3

#define PKT_PLAY_BEGIN 4
#define PKT_PLAY_DATA 5

#define PKT_READY 6
#define PKT_PLAYED 7
#define PKT_INTERRUPTED 8
#define PKT_ERROR 9


// ============================================================
// BUFFERS
// ============================================================

int32_t micBuf[1024];

uint8_t packetBuf[MAX_PAYLOAD];

uint8_t txPacket[MAX_PAYLOAD + 11];

uint8_t crcBuffer[MAX_PAYLOAD + 5];


// ============================================================
// ESTADOS
// ============================================================

bool grabando = false;

bool reproduciendo = false;

bool estadoBotonAnterior = HIGH;

unsigned long ultimoCambioBoton = 0;

const unsigned long debounceDelay = 50;

uint16_t secuenciaTX = 0;


// ============================================================
// CRC16
// ============================================================

uint16_t crc16(
  const uint8_t* datos,
  size_t longitud
) {

  uint16_t crc = 0xFFFF;

  for (size_t i = 0; i < longitud; i++) {

    crc ^= datos[i];

    for (int j = 0; j < 8; j++) {

      if (crc & 1) {

        crc = (crc >> 1) ^ 0xA001;

      } else {

        crc >>= 1;
      }
    }
  }

  return crc;
}


// ============================================================
// ENVIAR PAQUETE
// ============================================================

void enviarPaquete(
  uint8_t tipo,
  const uint8_t* datos,
  uint16_t longitud
) {

  if (longitud > MAX_PAYLOAD) {
    return;
  }

  txPacket[0] = MAGIC[0];
  txPacket[1] = MAGIC[1];
  txPacket[2] = MAGIC[2];
  txPacket[3] = MAGIC[3];

  txPacket[4] = tipo;

  txPacket[5] = longitud & 0xFF;
  txPacket[6] = (longitud >> 8) & 0xFF;

  txPacket[7] = secuenciaTX & 0xFF;
  txPacket[8] = (secuenciaTX >> 8) & 0xFF;

  secuenciaTX++;

  if (longitud > 0 && datos != NULL) {

    memcpy(
      txPacket + 9,
      datos,
      longitud
    );
  }

  uint16_t crc = crc16(
    txPacket + 4,
    longitud + 5
  );

  txPacket[9 + longitud] = crc & 0xFF;

  txPacket[10 + longitud] = (
    crc >> 8
  ) & 0xFF;

  size_t total = longitud + 11;

  size_t enviados = 0;

  while (enviados < total) {

    size_t n = Serial.write(
      txPacket + enviados,
      total - enviados
    );

    if (n == 0) {
      delay(1);
      continue;
    }

    enviados += n;
  }
}


// ============================================================
// RECIBIR PAQUETE
// ============================================================

bool recibirPaquete(
  uint8_t &tipo,
  uint8_t* datos,
  uint16_t &longitud,
  unsigned long timeout
) {

  static uint8_t estado = 0;

  static uint8_t cabecera[5];

  static uint8_t cabPos = 0;

  static uint16_t longitudActual = 0;

  static uint16_t posicion = 0;

  static uint8_t crcBytes[2];

  static uint8_t crcPos = 0;

  static unsigned long ultimoByte = 0;

  unsigned long inicio = millis();

  while (millis() - inicio < timeout) {

    if (!Serial.available()) {

      if (
        estado != 0 &&
        millis() - ultimoByte > 1000
      ) {

        estado = 0;
        cabPos = 0;
        posicion = 0;
        crcPos = 0;
      }

      delay(1);

      continue;
    }

    uint8_t b = Serial.read();

    ultimoByte = millis();

    switch (estado) {

      case 0:

        if (b == MAGIC[0]) {
          estado = 1;
        }

        break;

      case 1:

        estado = (
          b == MAGIC[1]
        ) ? 2 : 0;

        break;

      case 2:

        estado = (
          b == MAGIC[2]
        ) ? 3 : 0;

        break;

      case 3:

        if (b == MAGIC[3]) {

          estado = 4;

          cabPos = 0;

        } else {

          estado = 0;
        }

        break;

      case 4:

        cabecera[cabPos++] = b;

        if (cabPos == 5) {

          longitudActual =
            (uint16_t)cabecera[1] |
            ((uint16_t)cabecera[2] << 8);

          if (longitudActual > MAX_PAYLOAD) {

            estado = 0;

          } else {

            posicion = 0;

            // IMPORTANTE:
            // Reiniciar posición CRC también
            // cuando el paquete no tiene datos.

            crcPos = 0;

            estado = (
              longitudActual == 0
            ) ? 6 : 5;
          }
        }

        break;

      case 5:

        datos[posicion++] = b;

        if (posicion >= longitudActual) {

          crcPos = 0;

          estado = 6;
        }

        break;

      case 6:

        crcBytes[crcPos++] = b;

        if (crcPos == 2) {

          estado = 0;

          uint16_t recibido =
            (uint16_t)crcBytes[0] |
            ((uint16_t)crcBytes[1] << 8);

          memcpy(
            crcBuffer,
            cabecera,
            5
          );

          if (longitudActual > 0) {

            memcpy(
              crcBuffer + 5,
              datos,
              longitudActual
            );
          }

          uint16_t calculado = crc16(
            crcBuffer,
            5 + longitudActual
          );

          if (calculado == recibido) {

            tipo = cabecera[0];

            longitud = longitudActual;

            return true;
          }
        }

        break;
    }
  }

  return false;
}


// ============================================================
// BOTÓN
// ============================================================

bool botonPresionado() {

  bool actual = digitalRead(BOTON);

  if (actual != estadoBotonAnterior) {

    if (
      millis() - ultimoCambioBoton >= debounceDelay
    ) {

      ultimoCambioBoton = millis();

      estadoBotonAnterior = actual;

      if (actual == LOW) {
        return true;
      }
    }
  }

  return false;
}


// ============================================================
// MICRÓFONO
// ============================================================

void setupMic() {

  i2s_config_t cfg = {

    .mode = (i2s_mode_t)(
      I2S_MODE_MASTER |
      I2S_MODE_RX
    ),

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

  i2s_pin_config_t pins = {

    .bck_io_num = MIC_SCK,

    .ws_io_num = MIC_WS,

    .data_out_num = I2S_PIN_NO_CHANGE,

    .data_in_num = MIC_SD
  };

  i2s_driver_install(
    I2S_NUM_0,
    &cfg,
    0,
    NULL
  );

  i2s_set_pin(
    I2S_NUM_0,
    &pins
  );
}


void stopMic() {

  i2s_driver_uninstall(
    I2S_NUM_0
  );
}


// ============================================================
// PARLANTE
// ============================================================

void setupSpk(int rate) {

  i2s_config_t cfg = {

    .mode = (i2s_mode_t)(
      I2S_MODE_MASTER |
      I2S_MODE_TX
    ),

    .sample_rate = rate,

    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,

    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,

    .communication_format = I2S_COMM_FORMAT_STAND_I2S,

    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,

    // Aumentamos los búferes DMA
    // para mejorar la continuidad.

    .dma_buf_count = 8,

    .dma_buf_len = 512,

    .use_apll = false,

    .tx_desc_auto_clear = true,

    .fixed_mclk = 0
  };

  i2s_pin_config_t pins = {

    .bck_io_num = SPK_BCLK,

    .ws_io_num = SPK_LRC,

    .data_out_num = SPK_DOUT,

    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(
    I2S_NUM_1,
    &cfg,
    0,
    NULL
  );

  i2s_set_pin(
    I2S_NUM_1,
    &pins
  );
}


// ============================================================
// GRABACIÓN
// ============================================================

void iniciarGrabacion() {

  if (grabando) {
    return;
  }

  setupMic();

  grabando = true;

  digitalWrite(
    LED_PIN,
    HIGH
  );

  enviarPaquete(
    PKT_START,
    NULL,
    0
  );
}


void detenerGrabacion() {

  if (!grabando) {
    return;
  }

  grabando = false;

  digitalWrite(
    LED_PIN,
    LOW
  );

  stopMic();

  enviarPaquete(
    PKT_END,
    NULL,
    0
  );
}


void capturarAudio() {

  size_t br = 0;

  i2s_read(
    I2S_NUM_0,
    micBuf,
    sizeof(micBuf),
    &br,
    portMAX_DELAY
  );

  int cantidad = br / sizeof(int32_t);

  uint8_t audio[2048];

  int posicion = 0;

  for (int i = 0; i < cantidad; i++) {

    int32_t valor = micBuf[i] >> 13;

    if (valor > 32767) {
      valor = 32767;
    }

    if (valor < -32768) {
      valor = -32768;
    }

    int16_t muestra = (int16_t)valor;

    audio[posicion++] = muestra & 0xFF;

    audio[posicion++] = (
      muestra >> 8
    ) & 0xFF;
  }

  if (posicion > 0) {

    enviarPaquete(
      PKT_AUDIO_REC,
      audio,
      posicion
    );
  }
}


// ============================================================
// REPRODUCCIÓN
// ============================================================

void reproducirAudio(
  uint32_t sampleRate,
  uint32_t totalBytes
) {

  if (
    sampleRate < 8000 ||
    sampleRate > 48000 ||
    totalBytes == 0 ||
    totalBytes % 2 != 0
  ) {

    enviarPaquete(
      PKT_ERROR,
      NULL,
      0
    );

    return;
  }

  reproduciendo = true;

  setupSpk(sampleRate);

  uint32_t recibidos = 0;

  bool interrumpido = false;
  bool error = false;

  while (recibidos < totalBytes) {

    if (botonPresionado()) {

      interrumpido = true;

      break;
    }

    // Pedimos un bloque solamente
    // cuando estamos preparados.

    enviarPaquete(
      PKT_READY,
      NULL,
      0
    );

    uint8_t tipo;
    uint16_t longitud;

    bool recibido = false;

    unsigned long inicio = millis();

    while (millis() - inicio < 5000) {

      if (botonPresionado()) {

        interrumpido = true;

        break;
      }

      if (
        recibirPaquete(
          tipo,
          packetBuf,
          longitud,
          5
        )
      ) {

        recibido = true;

        break;
      }
    }

    if (interrumpido) {
      break;
    }

    if (!recibido) {

      error = true;

      break;
    }

    if (tipo != PKT_PLAY_DATA) {

      error = true;

      break;
    }

    if (
      longitud == 0 ||
      longitud % 2 != 0 ||
      longitud > totalBytes - recibidos
    ) {

      error = true;

      break;
    }

    size_t escritos = 0;

    esp_err_t resultado = i2s_write(
      I2S_NUM_1,
      packetBuf,
      longitud,
      &escritos,
      portMAX_DELAY
    );

    if (
      resultado != ESP_OK ||
      escritos != longitud
    ) {

      error = true;

      break;
    }

    recibidos += longitud;
  }

  if (interrumpido) {

    i2s_zero_dma_buffer(
      I2S_NUM_1
    );
  }

  else if (!error && recibidos == totalBytes) {

    // Espera aproximada para permitir
    // que finalicen las muestras pendientes.
    // No equivale a una confirmación
    // exacta de vaciado del DMA.

    delay(200);
  }

  i2s_driver_uninstall(
    I2S_NUM_1
  );

  reproduciendo = false;

  if (interrumpido) {

    enviarPaquete(
      PKT_INTERRUPTED,
      NULL,
      0
    );

    iniciarGrabacion();
  }

  else if (error) {

    enviarPaquete(
      PKT_ERROR,
      NULL,
      0
    );
  }

  else {

    enviarPaquete(
      PKT_PLAYED,
      NULL,
      0
    );
  }
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(
    SERIAL_BAUD
  );

  Serial.setTimeout(10);

  pinMode(
    BOTON,
    INPUT_PULLUP
  );

  pinMode(
    LED_PIN,
    OUTPUT
  );

  digitalWrite(
    LED_PIN,
    LOW
  );

  estadoBotonAnterior = digitalRead(BOTON);

  delay(500);
}


// ============================================================
// LOOP PRINCIPAL
// ============================================================

void loop() {

  if (botonPresionado()) {

    if (grabando) {

      detenerGrabacion();

    }

    else if (!reproduciendo) {

      iniciarGrabacion();
    }
  }

  if (grabando) {

    capturarAudio();

    return;
  }

  uint8_t tipo;
  uint16_t longitud;

  if (
    recibirPaquete(
      tipo,
      packetBuf,
      longitud,
      10
    )
  ) {

    if (tipo == PKT_PLAY_BEGIN) {

      if (longitud != 8) {

        enviarPaquete(
          PKT_ERROR,
          NULL,
          0
        );

        return;
      }

      uint32_t sampleRate =
        (uint32_t)packetBuf[0] |
        ((uint32_t)packetBuf[1] << 8) |
        ((uint32_t)packetBuf[2] << 16) |
        ((uint32_t)packetBuf[3] << 24);

      uint32_t totalBytes =
        (uint32_t)packetBuf[4] |
        ((uint32_t)packetBuf[5] << 8) |
        ((uint32_t)packetBuf[6] << 16) |
        ((uint32_t)packetBuf[7] << 24);

      reproducirAudio(
        sampleRate,
        totalBytes
      );
    }
  }
}