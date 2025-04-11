#include <SoftwareSerial.h>
#include <PubSubClient.h>
#include <ESP8266WiFi.h>
#include <Adafruit_Fingerprint.h>
#include <Servo.h>

// WiFi and MQTT credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* mqtt_server = "broker.hivemq.com"; // or your local broker

// MQTT Topics
const char* topicReceive = "smartdustbin/commands";
const char* topicSend = "smartdustbin/responses";

// Pin definitions (keep your existing setup)
int unrollingmotorpin1 = 8;
int unrollingmotorpin2 = 9;
int compactionmotorpin1 = 10;
int compactionmotorpin2 = 11;
int ultrasonicTrig = 3;
int ultrasonicEcho = 2;
int gasSensor = A5;
int servoPin = 4;
int irPin = 5;
int ledpin = 6;

// Objects
WiFiClient espClient;
PubSubClient client(espClient);
Servo servoMotor;
SoftwareSerial mySerial(12, 13); // For fingerprint sensor
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&mySerial);

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  
  // Convert payload to String
  String command = "";
  for (int i = 0; i < length; i++) {
    command += (char)payload[i];
  }
  
  // Process the command (same as your original processCommand)
  processCommand(command);
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ArduinoDustbinClient")) {
      Serial.println("connected");
      client.subscribe(topicReceive);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

// Keep all your existing helper functions:
// isNumber(), enrollFingerprint(), verifyFingerprint(), readUltrasonicDistance()

// Modified processCommand to publish responses via MQTT
void processCommand(String command) {
  if (command.startsWith("register")) {
    String userIDstr = command.substring(8);
    if (isNumber(userIDstr.c_str())) {
      int userID = userIDstr.toInt();
      if (enrollFingerprint(userID)) {
        client.publish(topicSend, "Enrollment_Done");
        client.publish(topicSend, "registration_success");
      } else {
        client.publish(topicSend, "Enrollment_not_done");
        client.publish(topicSend, "registration_failed");
      }
    }
  }
  else if (command == "verify") {
    if (verifyFingerprint()) {
      client.publish(topicSend, "approved");
    } else {
      client.publish(topicSend, "denied");
    }
  }
  else if (command == "clear_all_users") {
    clearFingerprintDatabase();
  }
  else if (command == "get_ultra") {
    distance = 0.01723 * readUltrasonicDistance(ultrasonicTrig, ultrasonicEcho);
    char distanceStr[10];
    sprintf(distanceStr, "%d", distance);
    client.publish(topicSend, distanceStr);
  }
  else if (command == "get_gas") {
    gasLevel = analogRead(gasSensor);
    char gasStr[10];
    sprintf(gasStr, "%d", gasLevel);
    client.publish(topicSend, gasStr);
  }
  else if (command == "get_ir") {
    ir_status = digitalRead(irPin);
    if (ir_status == LOW) {
      client.publish(topicSend, "Detected");
    } else {
      client.publish(topicSend, "Not Detected");
    }
  }
  else if (command == "compaction") {
    // Your original compaction code
    digitalWrite(unrollingmotorpin1, HIGH); 
    digitalWrite(unrollingmotorpin2, LOW);
    delay(5000);
    digitalWrite(unrollingmotorpin1, LOW); 
    digitalWrite(unrollingmotorpin2, LOW);

    digitalWrite(compactionmotorpin1, HIGH);
    digitalWrite(compactionmotorpin2, LOW);
    delay(5000);
    digitalWrite(compactionmotorpin1, LOW);
    digitalWrite(compactionmotorpin2, HIGH);
    delay(5000);

    digitalWrite(unrollingmotorpin1, LOW); 
    digitalWrite(unrollingmotorpin2, HIGH);
    delay(5000);

    client.publish(topicSend, "Compaction done");
  }
  else if (command == "uv_led") {
    digitalWrite(ledpin, HIGH);
    delay(8000);
    client.publish(topicSend, "sterilised");
  }
  else if (command == "open_lid") {
    servoMotor.write(90);
  }
  else if (command == "close_lid") {
    servoMotor.write(0);
  }
}

void setup() {
  Serial.begin(9600);
  
  // Initialize fingerprint sensor
  mySerial.begin(57600);
  if (finger.verifyPassword()) {
    Serial.println("Fingerprint sensor detected!");
  } else {
    Serial.println("Fingerprint sensor not found :(");
    while (1);
  }
  
  // Initialize pins
  pinMode(gasSensor, INPUT);
  pinMode(irPin, INPUT);
  pinMode(ledpin, OUTPUT);
  pinMode(unrollingmotorpin1, OUTPUT);
  pinMode(unrollingmotorpin2, OUTPUT);
  pinMode(compactionmotorpin1, OUTPUT);
  pinMode(compactionmotorpin2, OUTPUT);
  servoMotor.attach(servoPin);
  
  setup_wifi();
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}
