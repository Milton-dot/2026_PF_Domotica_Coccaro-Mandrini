#include <WiFi.h>
#include <WebServer.h>
#include "DFRobot_HumanDetection.h"

const char* ssid = "Zonawifi";         
const char* password = "Mandry55"; 

IPAddress local_ip(10, 129, 104, 200);   
IPAddress gateway(10, 129, 104, 94);     
IPAddress subnet(255, 255, 255, 0);     
IPAddress primary_dns(8, 8, 8, 8);      

const int RELAY_PIN = 10;                 

WebServer server(80);
DFRobot_HumanDetection hu(&Serial2);

// Variables de Estado y Modos (0 = Caídas, 1 = Signos Vitales)
int modoActual = 0; 

volatile int c_presence = 0;
volatile int c_movement = 0;
volatile int c_movingRange = 0;
volatile int c_fallState = 0;
volatile int c_staticState = 0;
volatile int c_bpm = 0;
volatile int c_rpm = 0;

unsigned long ultimaLectura = 0;
const long intervaloLectura = 1500; // Intervalo óptimo para ambos

void handleData() {
  String json = "{";
  json += "\"modo\":" + String(modoActual) + ",";
  json += "\"presence\":" + String(c_presence) + ",";
  json += "\"movement\":" + String(c_movement) + ",";
  json += "\"movingRange\":" + String(c_movingRange) + ",";
  json += "\"fallState\":" + String(c_fallState) + ",";
  json += "\"staticState\":" + String(c_staticState) + ",";
  json += "\"bpm\":" + String(c_bpm) + ",";
  json += "\"rpm\":" + String(c_rpm);
  json += "}";
  server.send(200, "application/json", json);
}

void handleSetMode() {
  if (server.hasArg("val")) {
    int nuevoModo = server.arg("val").toInt();
    if (nuevoModo != modoActual) {
      modoActual = nuevoModo;
      if (modoActual == 0) {
        hu.configWorkMode(hu.eFallingMode);
        Serial.println("Cambiando a Modo Caídas");
      } else {
        hu.configWorkMode(hu.eSleepMode);
        hu.sensorRet();
        Serial.println("Cambiando a Modo Signos Vitales");
      }
      delay(1000);
    }
    server.send(200, "text/plain", "OK");
  } else {
    server.send(400, "text/plain", "Falta argumento val");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); 

  Serial2.begin(115200, SERIAL_8N1, 4, 5);

  if (!WiFi.config(local_ip, gateway, subnet, primary_dns)) {
    Serial.println("¡Error al configurar la IP estática!");
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n¡WiFi conectado con éxito!");

  while (hu.begin() != 0) {
    Serial.println("Esperando sensor C1001...");
    delay(1000);
  }
  
  // Iniciar por defecto en Modo Caídas
  hu.configWorkMode(hu.eFallingMode);
  hu.configLEDLight(hu.eFALLLed, 1);         
  hu.configLEDLight(hu.eHPLed, 1);           
  hu.dmInstallHeight(246);                    
  delay(200);
  hu.dmFallTime(5);                           
  delay(200);
  hu.dmUnmannedTime(1);                       
  delay(200);
  hu.dmFallConfig(hu.eResidenceTime, 60);     
  delay(200);
  hu.dmFallConfig(hu.eFallSensitivityC, 3);  

  server.on("/data", handleData);
  server.on("/mode", handleSetMode);
  server.begin();
  Serial.println("Servidor HTTP listo.");
}

void loop() {
  server.handleClient();

  unsigned long currentMillis = millis();
  if (currentMillis - ultimaLectura >= intervaloLectura) {
    ultimaLectura = currentMillis;

    c_presence = hu.smHumanData(hu.eHumanPresence);
    c_movement = hu.smHumanData(hu.eHumanMovement);

    if (modoActual == 0) {
      // --- MODO CAÍDAS ---
      c_movingRange = hu.smHumanData(hu.eHumanMovingRange);
      c_fallState = hu.getFallData(hu.eFallState);
      c_staticState = hu.getFallData(hu.estaticResidencyState);

      if (c_presence == 1 || c_movement > 0) {
        digitalWrite(RELAY_PIN, LOW);   
      } else {
        digitalWrite(RELAY_PIN, HIGH);  
      }
    } else {
      // --- MODO SIGNOS VITALES ---
      if (c_presence == 1 && c_movement == 1) { // En reposo / quieto
        int bpmVal = hu.getHeartRate();
        int rpmVal = hu.getBreatheValue();
        if (bpmVal >= 20 && bpmVal <= 180) c_bpm = bpmVal;
        if (rpmVal >= 3 && rpmVal <= 60) c_rpm = rpmVal;
      } else {
        c_bpm = 0;
        c_rpm = 0;
      }
    }
  }
  yield();
}
