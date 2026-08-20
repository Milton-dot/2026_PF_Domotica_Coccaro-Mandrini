# Hábitat Asistencial Seguro e Inteligente

## Tabla de contenidos

- [Introducción](#introducción)
- [Descripción de la Propuesta](#descripción-de-la-propuesta)
- [Alcance](#alcance)
  - [Pilar 1: Monitoreo Biométrico y Ambiental No Invasivo (Radar mmWave 60 GHz)](#pilar-1-monitoreo-biométrico-y-ambiental-no-invasivo-radar-mmwave-60-ghz)
  - [Pilar 2: Gestión y Trazabilidad de Medicación (Dispensador Inteligente)](#pilar-2-gestión-y-trazabilidad-de-medicación-dispensador-inteligente)
  - [Pilar 3: Interfaz Conversacional con IA y Núcleo de Control Local](#pilar-3-interfaz-conversacional-con-ia-y-núcleo-de-control-local)

---

## Introducción

El aumento global en la expectativa de vida ha impulsado la necesidad de soluciones tecnológicas que permitan a las personas mayores envejecer en sus propios hogares (Aging in Place) de manera autónoma, digna y segura. Sin embargo, este deseo de independencia conlleva desafíos críticos: el riesgo de caídas no detectadas a tiempo, los errores en la adherencia a tratamientos médicos y la dificultad de interactuar con interfaces digitales complejas en momentos de emergencia.

Los sistemas tradicionales de asistencia suelen presentar serias limitaciones: los dispositivos tipo wearable (colgantes o pulseras de emergencia) con frecuencia se olvidan o no se utilizan dentro del hogar, mientras que las cámaras de videovigilancia comprometen la privacidad e intimidad en espacios clave como el baño o el dormitorio.

Para resolver esta problemática, la presente propuesta plantea el desarrollo e integración de un Ecosistema de Domótica Asistencial Pasiva e Inteligente. Este sistema combina sensado biomecánico no invasivo, automatización de la salud y procesamiento de lenguaje natural local para garantizar la seguridad del usuario sin alterar su rutina diaria ni invadir su privacidad.

## Descripción de la Propuesta

La presente propuesta se centra en la creación de un Hábitat Asistencial Seguro e Inteligente, diseñado para proteger de manera continua a la persona mayor dentro de su hogar, preservando en todo momento su autonomía, su comodidad y su intimidad.

Para construir este entorno protegido, la solución despliega un ecosistema sinérgico integrado por tres dispositivos clave:

- 1. El Nodo de Monitoreo Ambiental No Invasivo (Radar mmWave 60 GHz).

- 2. El Dispensador de Pastillas Inteligente (Dispensador Mecatrónico).

- 3. La Interfaz Conversacional con IA y Núcleo de Control Local.

En lugar de funcionar como herramientas aisladas, estos tres dispositivos operan de forma orquestada para constituir una red pasiva de protección y acompañamiento en la vivienda. Su acción conjunta permite tejer una capa invisible de seguridad que previene situaciones de vulnerabilidad, respalda las rutinas esenciales de salud y mantiene un canal permanente de resguardo, transformando la vivienda en un espacio preventivo y adaptativo sin requerir el uso de cámaras, pulseras ni el aprendizaje de tecnologías complejas.

![Diagrama de arquitectura](images/1.png)

## Alcance

### Pilar 1: Monitoreo Biométrico y Ambiental No Invasivo (Radar mmWave 60 GHz)

Un nodo de sensado ubicado en el ambiente que utiliza tecnología de ondas milimétricas a 60 GHz. Al operar por reflexión electromagnética de micro-movimientos:

- Detección de Caídas: Mapea la posición del cuerpo en tres dimensiones, identificando caídas e inmovilidad a nivel del suelo en tiempo real sin requerir el uso de cámaras.

- Control de Signos Vitales sin Contacto: Mide la frecuencia respiratoria y ritmos cardíacos básicos mientras la persona descansa o permanece en la habitación.

- Acondicionamiento del Entorno: Detecta la presencia exacta del usuario para gestionar la iluminación automatizada (rutas nocturnas anti-tropezones) y la climatización del espacio.

### Pilar 2: Gestión y Trazabilidad de Medicación (Dispensador Inteligente)

Un dispositivo mecatrónico diseñado para la administración segura y controlada de fármacos:

- Dosificación Automatizada: Libera mecánicamente la dosis exacta en el horario programado.

- Verificación de Retiro: Mediante sensores ópticos o de peso, confirma que la pastilla haya sido efectivamente tomada del receptáculo y no permanezca olvidada.

- Control de Stock e Inventario: Mantiene un registro dinámico del número de dosis restantes en los compartimentos, notificando con anticipación la necesidad de recarga.

### Pilar 3: Interfaz Conversacional con IA y Núcleo de Control Local

Un asistente de voz con procesamiento de inteligencia artificial enfocado en la usabilidad de la persona mayor:

- Interacción Natural e Intuitiva: Permite al usuario controlar el ambiente (luces, temperatura, avisos) o consultar su rutina mediante comandos de voz simples, sin necesidad de aprender menús complejos ni usar aplicaciones móviles.

- Orquestación entre Dispositivos: Recibe eventos del dispensador (ej. "Pastilla no retirada tras 15 minutos") y del radar (ej. "Inmovilidad inusual"), generando recordatorios de voz paulatinos o verificando el estado del usuario ("¿Te encuentras bien?").

- Protocolo de Emergencia Multi-Canal: Si el sistema detecta una caída o no recibe respuesta del usuario ante una alerta crítica, el módulo de IA transmite de forma inmediata llamadas y mensajes de auxilio priorizados a familiares o cuidadores.
