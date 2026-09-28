#include <driver/i2s.h>

#define MIC_SD 32
#define MIC_WS 25
#define MIC_SCK 33
#define SPK_BCLK 13
#define SPK_LRC 4
#define SPK_DOUT 2
#define BOTON 26

#define REC_SAMPLE_RATE 16000
#define SERIAL_BAUD 921600

int32_t micBuf[1024];
uint8_t spkBuf[2048];

void setupMic() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = REC_SAMPLE_RATE, .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1, .dma_buf_count = 4, .dma_buf_len = 1024,
    .use_apll = false, .tx_desc_auto_clear = false, .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {.bck_io_num=MIC_SCK, .ws_io_num=MIC_WS, .data_out_num=I2S_PIN_NO_CHANGE, .data_in_num=MIC_SD};
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
}

void setupSpk(int rate) {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = rate, .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1, .dma_buf_count = 8, .dma_buf_len = 1024,
    .use_apll = false, .tx_desc_auto_clear = true, .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {.bck_io_num=SPK_BCLK, .ws_io_num=SPK_LRC, .data_out_num=SPK_DOUT, .data_in_num=I2S_PIN_NO_CHANGE};
  i2s_driver_install(I2S_NUM_1, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pins);
}

void setup() {
  Serial.setRxBufferSize(8192);
  Serial.begin(SERIAL_BAUD);
  Serial.setTimeout(5000);
  pinMode(BOTON, INPUT_PULLUP);
  Serial.println("Listo. Mantené el botón para hablar.");
}

void grabarMientrasApretado() {
  setupMic();
  Serial.println("START");
  while (digitalRead(BOTON) == LOW) {
    size_t br = 0;
    i2s_read(I2S_NUM_0, micBuf, sizeof(micBuf), &br, portMAX_DELAY);
    int cnt = br / sizeof(int32_t);
    for (int i = 0; i < cnt; i++) {
            int32_t v = micBuf[i] >> 13;   // 8x más ganancia que >> 16
      if (v > 32767) v = 32767;
      if (v < -32768) v = -32768;
      int16_t s16 = (int16_t)v;
      Serial.write((uint8_t*)&s16, 2);
    }
  }
  Serial.print("\nEND\n");
  i2s_driver_uninstall(I2S_NUM_0);
}

void reproducir() {
  uint8_t header[8];
  int got = 0;
  while (got < 8) got += Serial.readBytes(header + got, 8 - got);
  uint32_t sampleRate = header[0] | (header[1]<<8) | (header[2]<<16) | (header[3]<<24);
  uint32_t totalBytes = header[4] | (header[5]<<8) | (header[6]<<16) | (header[7]<<24);

  setupSpk(sampleRate);
  Serial.printf("Reproduciendo a %u Hz, %u bytes\n", sampleRate, totalBytes);

  uint32_t received = 0;
  while (received < totalBytes) {
    int chunk = min((uint32_t)sizeof(spkBuf), totalBytes - received);
    int r = Serial.readBytes(spkBuf, chunk);
    size_t bw = 0;
    i2s_write(I2S_NUM_1, spkBuf, r, &bw, portMAX_DELAY);
    received += r;
  }

  // Vaciar el buffer DMA: escribir silencio empuja la cola de audio real hacia afuera
  memset(spkBuf, 0, sizeof(spkBuf));
  for (int i = 0; i < 20; i++) {
    size_t bw = 0;
    i2s_write(I2S_NUM_1, spkBuf, sizeof(spkBuf), &bw, portMAX_DELAY);
  }
  delay(100);

  i2s_driver_uninstall(I2S_NUM_1);
  Serial.println("PLAYED");
}

void loop() {
  if (digitalRead(BOTON) == LOW) {
    grabarMientrasApretado();
  }
  if (Serial.available() > 0 && Serial.peek() == 'p') {
    Serial.read();
    reproducir();
  }
}