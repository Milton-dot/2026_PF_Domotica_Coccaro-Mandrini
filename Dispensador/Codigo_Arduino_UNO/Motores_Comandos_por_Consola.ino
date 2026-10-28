#include <AccelStepper.h>

#define MOTOR_INTERFACE_TYPE AccelStepper::DRIVER

// Definición de pines (Asegurando que el DIR de la Tolva A esté en el pin 6 correcto)
const int stepPin1 = 3; const int dirPin1 = 6; // Tolva A (Motor 1)
const int stepPin2 = 2; const int dirPin2 = 5; // Tolva B (Motor 2)
const int stepPin3 = 4; const int dirPin3 = 7; // Tolva C (Motor 3)

AccelStepper stepperA(MOTOR_INTERFACE_TYPE, stepPin1, dirPin1);
AccelStepper stepperB(MOTOR_INTERFACE_TYPE, stepPin2, dirPin2);
AccelStepper stepperC(MOTOR_INTERFACE_TYPE, stepPin3, dirPin3);

// Estructura para gestionar la máquina de estados de cada tolva de forma independiente
struct ControlTolva {
  AccelStepper *motor;
  int turnosRestantes;
  int subEstado;        // 0: Reposo, 1: Ir a 180°, 2: Volver 90°, 3: Ir a 360°, 4: Pausa 1s
  unsigned long tiempoEspera;
};

ControlTolva tolvaA = { &stepperA, 0, 0, 0 };
ControlTolva tolvaB = { &stepperB, 0, 0, 0 };
ControlTolva tolvaC = { &stepperC, 0, 0, 0 };

void setup() {
  Serial.begin(9600);
  
  // Configuración de velocidad y aceleración óptimas para los NEMA 17 con A4988 (1/16 micropasos)
  stepperA.setMaxSpeed(2000.0); stepperA.setAcceleration(1000.0);
  stepperB.setMaxSpeed(1000.0); stepperB.setAcceleration(1000.0);
  stepperC.setMaxSpeed(1000.0); stepperC.setAcceleration(1000.0);

  Serial.println("Sistema listo. Ingrese comandos (Ej: 2A 1B 2C)");
}

void loop() {
  // 1. Ejecutar el movimiento fluido de los tres motores en cada ciclo del loop
  stepperA.run();
  stepperB.run();
  stepperC.run();

  // 2. Actualizar la secuencia lógica de cada tolva de manera independiente
  actualizarTolva(tolvaA, "Tolva A");
  actualizarTolva(tolvaB, "Tolva B");
  actualizarTolva(tolvaC, "Tolva C");

  // 3. Leer el Monitor Serie si hay comandos nuevos
  if (Serial.available() > 0) {
    String inputString = Serial.readStringUntil('\n');
    inputString.trim();
    procesarComando(inputString);
  }
}

// Lógica de la secuencia de movimiento por pasos relativos (.move)
void actualizarTolva(ControlTolva &t, String nombre) {
  switch (t.subEstado) {
    case 0: // Reposo: Esperando comandos en cola
      if (t.turnosRestantes > 0) {
        t.motor->move(1600); // 1. Avanza 180° (1600 pasos)
        t.subEstado = 1;
        Serial.print(nombre); Serial.println(": Avanzando a 180°");
      }
      break;

    case 1: // Esperando terminar los 180°
      if (t.motor->distanceToGo() == 0) {
        t.motor->move(-800); // 2. Retrocede 90° (-800 pasos relativos hacia atrás)
        t.subEstado = 2;
        Serial.print(nombre); Serial.println(": Retrocediendo 90°");
      }
      break;

    case 2: // Esperando terminar el retroceso
      if (t.motor->distanceToGo() == 0) {
        t.motor->move(2400); // 3. Completa la vuelta hasta los 360° (2400 pasos restantes)
        t.subEstado = 3;
        Serial.print(nombre); Serial.println(": Completando a 360°");
      }
      break;

    case 3: // Esperando completar los 360°
      if (t.motor->distanceToGo() == 0) {
        t.turnosRestantes--;
        Serial.print(nombre); Serial.println(": ¡Ciclo completo!");
        
        if (t.turnosRestantes > 0) {
          t.tiempoEspera = millis();
          t.subEstado = 4; // Entra en pausa de 1 segundo antes del próximo giro
          Serial.print(nombre); Serial.println(": Esperando 1 segundo...");
        } else {
          t.subEstado = 0; // Vuelve a reposo
        }
      }
      break;

    case 4: // Pausa de 1 segundo entre giros múltiples
      if (millis() - t.tiempoEspera >= 1000) {
        t.motor->move(1600); // Inicia el siguiente ciclo (Avanza 180°)
        t.subEstado = 1;
        Serial.print(nombre); Serial.println(": Siguiente giro (Avanzando a 180°)");
      }
      break;
  }
}

// Intérprete del monitor serie para procesar cadenas como "2A 1B 2C"
void procesarComando(String comando) {
  int i = 0;
  while (i < comando.length()) {
    int inicioNum = i;
    while (i < comando.length() && isDigit(comando.charAt(i))) {
      i++;
    }
    
    if (inicioNum == i) {
      i++;
      continue;
    }

    int cantidadVueltas = comando.substring(inicioNum, i).toInt();

    if (i < comando.length()) {
      char tolva = toupper(comando.charAt(i));
      i++;

      if (tolva == 'A') {
        tolvaA.turnosRestantes += cantidadVueltas;
        Serial.print("Tolva A -> "); Serial.print(cantidadVueltas); Serial.println(" ciclo(s) en cola.");
      } 
      else if (tolva == 'B') {
        tolvaB.turnosRestantes += cantidadVueltas;
        Serial.print("Tolva B -> "); Serial.print(cantidadVueltas); Serial.println(" ciclo(s) en cola.");
      } 
      else if (tolva == 'C') {
        tolvaC.turnosRestantes += cantidadVueltas;
        Serial.print("Tolva C -> "); Serial.print(cantidadVueltas); Serial.println(" ciclo(s) en cola.");
      }
    }

    while (i < comando.length() && comando.charAt(i) == ' ') {
      i++;
    }
  }
}
