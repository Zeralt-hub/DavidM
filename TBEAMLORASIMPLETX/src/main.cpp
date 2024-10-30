#include <LoRa.h>
#include "LoRaBoards.h"
#include <TinyGPSPlus.h>
#include <ClosedCube_HDC1080.h>
#include <WiFi.h>

const char* ssid = "UPBWiFi";  
const char* host = "10.38.32.137";
const uint16_t port = 1026;

// Configuración de GPS
TinyGPSPlus gps;
HardwareSerial ss(1);  // Serial1 (TX=12, RX=34) 

// Configuración del sensor de temperatura y humedad (TinyCube)
ClosedCube_HDC1080 sensor;

WiFiClient client;

unsigned long lastDisplayTime = 0;
unsigned long lastSendTime = 0;
const unsigned long displayInterval = 5000;    // Mostrar en consola cada 5 segundos
const unsigned long sendInterval = 300000;     // Enviar al servidor cada 5 minutos (300,000 ms)

void setup()
{
    Serial.begin(115200);
    ss.begin(9600, SERIAL_8N1, 34, 12);  // Configuración para GPS en TTGO T-Beam (RX=34, TX=12)

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid);

    Serial.print("Conectando al WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(200);
        Serial.print(".");
    }
    Serial.println("\nConectado al WiFi");

    sensor.begin(0x40);
    delay(100);  // Asegurar que el sensor esté listo

    Serial.println("Sistema listo.");
}

void loop()
{
    while (ss.available()) {
        gps.encode(ss.read());
    }

    unsigned long currentTime = millis();

    if (currentTime - lastDisplayTime >= displayInterval) {
        lastDisplayTime = currentTime;
        
        Serial.print("Latitud: "); Serial.println(gps.location.lat(), 6);
        Serial.print("Longitud: "); Serial.println(gps.location.lng(), 6);
        Serial.print("Altitud: "); Serial.println(gps.altitude.meters());
        Serial.print("Fecha: "); Serial.print(gps.date.month()); Serial.print("/"); Serial.print(gps.date.day()); Serial.print("/"); Serial.println(gps.date.year());
        Serial.print("Hora: "); Serial.print(gps.time.hour()); Serial.print(":"); Serial.print(gps.time.minute()); Serial.print(":"); Serial.println(gps.time.second());
        Serial.print("Temperatura: "); Serial.print(sensor.readTemperature()); Serial.println(" C");
        Serial.print("Humedad: "); Serial.print(sensor.readHumidity()); Serial.println(" %");
    }

    if (currentTime - lastSendTime >= sendInterval && gps.location.isValid()) {
        lastSendTime = currentTime;
        
        float temperatura = sensor.readTemperature();
        float humedad = sensor.readHumidity();
        double latitud = gps.location.lat();
        double longitud = gps.location.lng();

        String jsonData = "{\"lat\":{\"value\":" + String(latitud, 6) + ", \"type\":\"Float\"},"
                          "\"lon\":{\"value\":" + String(longitud, 6) + ", \"type\":\"Float\"},"
                          "\"temp\":{\"value\":" + String(temperatura) + ", \"type\":\"Float\"},"
                          "\"humedad\":{\"value\":" + String(humedad) + ", \"type\":\"Float\"}}";

        //Actualizar la entidad con PATCH
        if (client.connect(host, port)) {
            client.println("PATCH /v2/entities/DavidM001/attrs HTTP/1.1");
            client.println("Host: 10.38.32.137:1026");
            client.println("Content-Type: application/json");
            client.println("Connection: close");
            client.print("Content-Length: ");
            client.println(jsonData.length());
            client.println();
            client.println(jsonData);

            delay(100);
            if (client.available()) {
                String response = client.readString();
                Serial.print("Respuesta del servidor: ");
                Serial.println(response);

                // Si el servidor responde con un error, intenta crear la entidad con POST (por si se cae el server o tengo que borrar la entidad.)
                if (response.indexOf("Not Found") > 0) {
                    client.stop();
                    if (client.connect(host, port)) {
                        Serial.println("Creando la entidad por primera vez");

                        String createData = "{\"id\":\"DavidM001\",\"type\":\"SensorData\","
                                            "\"lat\":{\"value\":" + String(latitud, 6) + ", \"type\":\"Float\"},"
                                            "\"lon\":{\"value\":" + String(longitud, 6) + ", \"type\":\"Float\"},"
                                            "\"temp\":{\"value\":" + String(temperatura) + ", \"type\":\"Float\"},"
                                            "\"humedad\":{\"value\":" + String(humedad) + ", \"type\":\"Float\"}}";

                        client.println("POST /v2/entities HTTP/1.1");
                        client.println("Host: 10.38.32.137:1026");
                        client.println("Content-Type: application/json");
                        client.println("Connection: close");
                        client.print("Content-Length: ");
                        client.println(createData.length());
                        client.println();
                        client.println(createData);
                    }
                }
            }
            client.stop();
        } else {
            Serial.println("Error al conectar con el servidor");
        }
    }

    delay(100);  // Pequeña espera para evitar sobrecarga
}