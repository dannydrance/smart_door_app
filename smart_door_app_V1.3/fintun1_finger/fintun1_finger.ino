#include <SPI.h>
#include <Wire.h>
#include <WiFi.h>
#include <Keypad.h>
#include <MFRC522.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Adafruit_Fingerprint.h>
#include "time.h"
#include <EEPROM.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

// ---------- WiFi Settings ----------
const char* ssid = "Mine";
const char* password = "1234567890";

// ---------- NTP Settings ----------
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 2 * 3600;   // GMT+2
const int daylightOffset_sec = 0;

// ---------- MQTT (HiveMQ) Settings ----------
const char* mqtt_server = "bffac683e63348f5b429862109209547.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char* mqtt_user = "hivemq.webclient.1762324468600";
const char* mqtt_password = "Cv;*bFcq>y8KT237.DhJ";

const char* topic_status  = "door/status";
const char* topic_event   = "door/events";
const char* topic_command = "door/command";

// ---------- Fingerprint Sensor (AS608) ----------
// Connect to ESP32 Serial2: RX=16, TX=17
HardwareSerial fingerSerial(2);
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&fingerSerial);

// Fingerprint enrollment state
bool enrollMode = false;
int enrollID = 0;
int enrollStage = 0;

// ---------- Heartbeat ----------
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_INTERVAL = 60000; // 60 seconds

// ---------- OLED Settings ----------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ---------- RFID Settings ----------
#define RST_PIN 5
#define SS_PIN 4
MFRC522 mfrc522(SS_PIN, RST_PIN);

// ---------- Keypad ----------
const byte ROWS = 4;
const byte COLS = 4;
char hexaKeys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[ROWS] = {13, 12, 14, 27};
byte colPins[COLS] = {17, 16, 26, 25};
Keypad keypad = Keypad(makeKeymap(hexaKeys), rowPins, colPins, ROWS, COLS);

// ---------- Hardware Pins ----------
#define RELAY_PIN 35
#define VIBRATION_PIN 33
#define IR_SENSOR_PIN 32
#define LED 34
#define BUZZER_PIN 15

// ---------- Timing ----------
unsigned long lastActivity = 0;
unsigned long lastDisplayUpdate = 0;
unsigned long lastDoorCheck = 0;

// ---------- Door Status ----------
bool doorUnlocked = false;
unsigned long doorOpenStart = 0;
const unsigned long DOOR_OPEN_TIMEOUT = 10000; // 10 seconds

// ---------- EEPROM ----------
#define EEPROM_SIZE 256
#define MAX_CARDS 10
#define CARD_SIZE 12 // bytes per UID
#define PIN_ADDR (MAX_CARDS * CARD_SIZE)
String Password = ""; // default PIN

// ---------- Network ----------
WiFiClientSecure espClient;
PubSubClient client(espClient);

// ---------- State ----------
String EnterPassword = "";
bool cardAccepted = false;

// ---------- UTILITIES ----------
void buzzerBeep(int d = 100) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(d);
  digitalWrite(BUZZER_PIN, LOW);
}
void buzzerSuccess() { buzzerBeep(80); delay(50); buzzerBeep(80); }
void buzzerError() { buzzerBeep(250); }

void mqttPublish(const char* topic, String msg) {
  if (client.connected()) client.publish(topic, msg.c_str());
}

void showMessage(String msg) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(5, 10);
  display.println(msg);
  display.display();
}

void showHomeScreen() {
  EnterPassword = "";
  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(10, 5);
  display.println(getCurrentTime());
  display.setTextSize(1);
  display.setCursor(25, 25);
  display.println(getCurrentDate());
  display.display();
}

// ---------- EEPROM FUNCTIONS ----------
void saveCard(String uid, int index) {
  int addr = index * CARD_SIZE;
  for (int i = 0; i < CARD_SIZE; i++) {
    EEPROM.write(addr + i, i < uid.length() ? uid[i] : 0);
  }
  EEPROM.commit();
}

String readCard(int index) {
  String uid = "";
  int addr = index * CARD_SIZE;
  for (int i = 0; i < CARD_SIZE; i++) {
    char c = EEPROM.read(addr + i);
    if (c == 0) break;
    uid += c;
  }
  return uid;
}

void loadPIN() {
  Password = "";
  for (int i = 0; i < 12; i++) {
    char c = EEPROM.read(PIN_ADDR + i);
    if (c == 0) break;
    Password += c;
  }
  if (Password == "") Password = "1234"; // default
}

void savePIN(String pin) {
  for (int i = 0; i < 12; i++) {
    EEPROM.write(PIN_ADDR + i, i < pin.length() ? pin[i] : 0);
  }
  EEPROM.commit();
}

void addCard(String uid) {
  uid.toUpperCase();
  for (int i = 0; i < MAX_CARDS; i++) {
    if (readCard(i) == uid) {
      mqttPublish(topic_event, "Card already exists: " + uid);
      return;
    }
    if (readCard(i) == "") {
      saveCard(uid, i);
      mqttPublish(topic_event, "Card added: " + uid);
      return;
    }
  }
  mqttPublish(topic_event, "Storage full!");
}

void removeCard(String uid) {
  uid.toUpperCase();
  for (int i = 0; i < MAX_CARDS; i++) {
    if (readCard(i) == uid) {
      saveCard("", i);
      mqttPublish(topic_event, "Card removed: " + uid);
      return;
    }
  }
  mqttPublish(topic_event, "Card not found: " + uid);
}

bool isAuthorizedCard(String uid) {
  uid.toUpperCase();
  for (int i = 0; i < MAX_CARDS; i++) {
    if (readCard(i) == uid) return true;
  }
  return false;
}

void listCards() {
  String list = "Stored cards:\n";
  for (int i = 0; i < MAX_CARDS; i++) {
    String c = readCard(i);
    if (c != "") list += c + "\n";
  }
  mqttPublish(topic_event, list);
  mqttPublish(topic_event, "PIN: " + Password);
}

void resetEEPROM() {
  for (int i = 0; i < EEPROM_SIZE; i++) EEPROM.write(i, 0);
  EEPROM.commit();
  Password = "1234";
  mqttPublish(topic_event, "EEPROM reset done!");
}

// ---------- FINGERPRINT FUNCTIONS ----------

void initFingerprint() {
  fingerSerial.begin(57600, SERIAL_8N1, 16, 17); // RX=16, TX=17
  delay(100);
  
  if (finger.verifyPassword()) {
    Serial.println("✅ Fingerprint sensor found!");
    mqttPublish(topic_event, "Fingerprint sensor: Online");
  } else {
    Serial.println("❌ Fingerprint sensor not found!");
    mqttPublish(topic_event, "Fingerprint sensor: Failed");
  }
  
  // Get sensor parameters
  finger.getTemplateCount();
  Serial.print("Sensor contains ");
  Serial.print(finger.templateCount);
  Serial.println(" templates");
}

void listFingerprints() {
  finger.getTemplateCount();
  String msg = "Stored fingerprints: " + String(finger.templateCount) + "\n";
  msg += "Capacity: " + String(finger.capacity);
  mqttPublish(topic_event, msg);
}

void deleteFingerprint(int id) {
  uint8_t p = finger.deleteModel(id);
  if (p == FINGERPRINT_OK) {
    mqttPublish(topic_event, "Fingerprint deleted: ID " + String(id));
    showMessage("Deleted ID " + String(id));
    buzzerSuccess();
  } else {
    mqttPublish(topic_event, "Failed to delete fingerprint ID " + String(id));
    showMessage("Delete Failed!");
    buzzerError();
  }
}

void clearAllFingerprints() {
  uint8_t p = finger.emptyDatabase();
  if (p == FINGERPRINT_OK) {
    mqttPublish(topic_event, "All fingerprints cleared");
    showMessage("All FP Cleared!");
    buzzerSuccess();
  } else {
    mqttPublish(topic_event, "Failed to clear fingerprints");
    showMessage("Clear Failed!");
    buzzerError();
  }
}

// Start fingerprint enrollment
void startEnrollFingerprint(int id) {
  if (id < 1 || id > 127) {
    mqttPublish(topic_event, "Invalid ID. Use 1-127");
    return;
  }
  enrollMode = true;
  enrollID = id;
  enrollStage = 1;
  showMessage("Place finger...");
  mqttPublish(topic_event, "Enrollment started for ID " + String(id));
  Serial.println("Starting enrollment for ID: " + String(id));
}

// Enrollment process handler
void handleEnrollment() {
  if (!enrollMode) return;
  
  if (enrollStage == 1) {
    // Stage 1: Get first image
    showMessage("Place finger...");
    int p = finger.getImage();
    if (p != FINGERPRINT_OK) return;
    
    p = finger.image2Tz(1);
    if (p != FINGERPRINT_OK) {
      mqttPublish(topic_event, "Enrollment failed: Image conversion error");
      enrollMode = false;
      buzzerError();
      return;
    }
    
    showMessage("Remove finger...");
    buzzerBeep();
    delay(1000);
    enrollStage = 2;
    mqttPublish(topic_event, "First scan captured. Place same finger again.");
  }
  else if (enrollStage == 2) {
    // Wait for finger removal
    if (finger.getImage() != FINGERPRINT_NOFINGER) return;
    enrollStage = 3;
  }
  else if (enrollStage == 3) {
    // Stage 2: Get second image
    showMessage("Place same finger");
    int p = finger.getImage();
    if (p != FINGERPRINT_OK) return;
    
    p = finger.image2Tz(2);
    if (p != FINGERPRINT_OK) {
      mqttPublish(topic_event, "Enrollment failed: Second image error");
      enrollMode = false;
      buzzerError();
      return;
    }
    
    // Create model
    p = finger.createModel();
    if (p != FINGERPRINT_OK) {
      mqttPublish(topic_event, "Enrollment failed: Fingerprints don't match");
      enrollMode = false;
      buzzerError();
      return;
    }
    
    // Store model
    p = finger.storeModel(enrollID);
    if (p == FINGERPRINT_OK) {
      mqttPublish(topic_event, "Fingerprint enrolled successfully! ID: " + String(enrollID));
      showMessage("Enrolled! ID:" + String(enrollID));
      buzzerSuccess();
    } else {
      mqttPublish(topic_event, "Enrollment failed: Storage error");
      showMessage("Storage Failed!");
      buzzerError();
    }
    
    enrollMode = false;
    enrollStage = 0;
    delay(2000);
  }
}

// Fingerprint verification handler
void fingerprintHandler() {
  if (enrollMode) {
    handleEnrollment();
    return;
  }
  
  if (cardAccepted) return; // Skip if card mode is active
  
  uint8_t p = finger.getImage();
  if (p != FINGERPRINT_OK) return;
  
  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) return;
  
  p = finger.fingerSearch();
  if (p == FINGERPRINT_OK) {
    // Fingerprint matched!
    Serial.println("✅ Fingerprint matched! ID: " + String(finger.fingerID) + 
                   " Confidence: " + String(finger.confidence));
    
    mqttPublish(topic_event, "Fingerprint authorized: ID " + String(finger.fingerID) + 
                " (Confidence: " + String(finger.confidence) + ")");
    
    showMessage("FP Authorized!");
    buzzerSuccess();
    unlockDoor();
    delay(1000);
  } else if (p == FINGERPRINT_NOTFOUND) {
    Serial.println("❌ Fingerprint not found");
    mqttPublish(topic_event, "Unauthorized fingerprint attempt");
    showMessage("FP Denied!");
    buzzerError();
    delay(1000);
    showHomeScreen();
  }
}

// ---------- HEARTBEAT ----------
void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;

  long rssi = WiFi.RSSI();
  String state = doorUnlocked ? "UNLOCKED" : "LOCKED";

  int cardCount = 0;
  for (int i = 0; i < MAX_CARDS; i++) {
    if (readCard(i) != "") cardCount++;
  }
  
  finger.getTemplateCount();
  int fpCount = finger.templateCount;

  unsigned long uptimeSec = millis() / 1000;
  unsigned long uptimeMin = uptimeSec / 60;

  String msg = "HEARTBEAT\n";
  msg += "State: " + state + "\n";
  msg += "Cards: " + String(cardCount) + "\n";
  msg += "Fingerprints: " + String(fpCount) + "\n";
  msg += "WiFi RSSI: " + String(rssi) + " dBm\n";
  msg += "Uptime: " + String(uptimeMin) + " min";

  mqttPublish(topic_status, msg);
  Serial.println("📡 Heartbeat sent:");
  Serial.println(msg);
}

// ---------- TIME ----------
String getCurrentTime() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "00:00:00";
  char buf[10]; strftime(buf, sizeof(buf), "%H:%M:%S", &timeinfo);
  return String(buf);
}

String getCurrentDate() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "0000-00-00";
  char buf[11]; strftime(buf, sizeof(buf), "%Y-%m-%d", &timeinfo);
  return String(buf);
}

// ---------- DOOR CONTROL ----------
void unlockDoor() {
  digitalWrite(RELAY_PIN, HIGH);
  doorUnlocked = true;
  doorOpenStart = millis();
  showMessage("Door Unlocked ✅");
  buzzerSuccess();
  mqttPublish(topic_status, "UNLOCKED");
}

void lockDoor() {
  digitalWrite(RELAY_PIN, LOW);
  doorUnlocked = false;
  showMessage("Door Locked 🔒");
  buzzerBeep();
  mqttPublish(topic_status, "LOCKED");
}

// ---------- HANDLERS ----------
String getUID() {
  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    uid += (mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

void rfidHandler() {
  if (cardAccepted) return;
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) return;
  String uid = getUID();
  if (isAuthorizedCard(uid)) {
    Serial.println("Card Authorized ✅");
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(5, 10);
    display.println("Card Authorized!");
    display.setCursor(20, 25);
    display.println("Enter PIN:");
    display.display();
    buzzerSuccess();
    mqttPublish(topic_event, "Authorized card: " + uid);
    cardAccepted = true;
  } else {
    showMessage("Card Denied ❌");
    buzzerError();
    delay(1000);
    mqttPublish(topic_event, "Unauthorized card: " + uid);
    showHomeScreen();
    cardAccepted = false;
  }
  mfrc522.PICC_HaltA();
}

void keypadHandler() {
  char key = keypad.getKey();
  if (!key) return;
  lastActivity = millis();
  if (key >= '0' && key <= '9') EnterPassword += key;
  if (key == 'D' && EnterPassword.length() > 0) EnterPassword.remove(EnterPassword.length() - 1);
  if (key == 'C') EnterPassword = "";
  
  if (key == '#') {
    if (EnterPassword == Password) {
      mqttPublish(topic_event, "PIN accepted");
      Serial.println("Access Granted ✅");
      showMessage("Access Granted ✅");
      unlockDoor();
      buzzerSuccess();
      delay(1000);
      cardAccepted = false;
    } else {
      mqttPublish(topic_event, "PIN rejected");
      Serial.println("Access Denied ❌");
      showMessage("Access Denied ❌");
      lockDoor();
      buzzerError();
      delay(1000);
      cardAccepted = false;
      showHomeScreen();
    }
    EnterPassword = "";
  }
  String masked = "";
  for (int i = 0; i < EnterPassword.length(); i++) masked += '*';
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(10, 5);
  display.println("Enter Password:");
  display.setTextSize(2);
  display.setCursor(20, 15);
  display.println(masked);
  display.display();
}

void sensorHandler() {
  int vib = digitalRead(VIBRATION_PIN);
  int door = digitalRead(IR_SENSOR_PIN);
  if (vib == HIGH) {
    Serial.println("⚠️ Vibration detected!");
    showMessage("Vibration Alert!");
    mqttPublish(topic_event, "ALERT: Vibration detected");
    buzzerError();
  }
  //if (doorUnlocked && door == LOW && millis() - doorOpenStart > DOOR_OPEN_TIMEOUT) {
    //mqttPublish(topic_event, "ALERT: Door open too long");
    //lockDoor();
  //}
}

void displayHandler() {
  if (millis() - lastDisplayUpdate > 1000 && !cardAccepted && !enrollMode) {
    showHomeScreen();
    lastDisplayUpdate = millis();
  }
}

void handleTimeouts() {
  if (millis() - lastActivity > 30000) {
    EnterPassword = "";
    cardAccepted = false;
    lastActivity = millis();
  }
}

// ---------- MQTT ----------
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  Serial.println("MQTT command: " + msg);

  if (msg == "LOCK") lockDoor();
  else if (msg == "UNLOCK") unlockDoor();
  else if (msg == "RESET_EEPROM") resetEEPROM();
  else if (msg.startsWith("ADD_RFID:")) addCard(msg.substring(9));
  else if (msg.startsWith("REMOVE_RFID:")) removeCard(msg.substring(12));
  else if (msg == "LIST_RFID") listCards();
  else if (msg.startsWith("SET_PIN:")) { 
    Password = msg.substring(8); 
    savePIN(Password); 
    mqttPublish(topic_event, "PIN updated"); 
  }
  // Fingerprint commands
  else if (msg.startsWith("ENROLL_FP:")) {
    int id = msg.substring(10).toInt();
    startEnrollFingerprint(id);
  }
  else if (msg.startsWith("DELETE_FP:")) {
    int id = msg.substring(10).toInt();
    deleteFingerprint(id);
  }
  else if (msg == "CLEAR_FP") clearAllFingerprints();
  else if (msg == "LIST_FP") listFingerprints();
  else if (msg == "SHOW_CONFIG") {
    String cfg = "Door state: " + String(doorUnlocked ? "UNLOCKED" : "LOCKED") + "\n";
    cfg += "WiFi RSSI: " + String(WiFi.RSSI()) + " dBm\n";
    cfg += "Stored cards: ";
    int count = 0;
    for (int i = 0; i < MAX_CARDS; i++) if (readCard(i) != "") count++;
    cfg += String(count) + "\n";
    cfg += "PIN length: " + String(Password.length()) + "\n";
    finger.getTemplateCount();
    cfg += "Fingerprints: " + String(finger.templateCount);
    mqttPublish(topic_event, cfg);
  }
}

void mqttReconnect() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    if (client.connect("ESP32Door", mqtt_user, mqtt_password)) {
      Serial.println("connected");
      client.subscribe(topic_command);
      client.publish(topic_status, "Online");
      sendHeartbeat();
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5s");
      delay(5000);
    }
  }
}

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200);
  EEPROM.begin(EEPROM_SIZE);
  loadPIN();

  SPI.begin();
  mfrc522.PCD_Init();
  
  // Initialize fingerprint sensor
  initFingerprint();

  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(VIBRATION_PIN, INPUT);
  pinMode(IR_SENSOR_PIN, INPUT);

  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println("SSD1306 failed");
    for(;;);
  }

  showMessage("Connecting WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(300); }

  espClient.setInsecure();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
  mqttReconnect();

  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  showHomeScreen();
}

// ---------- LOOP ----------
void loop() {
  if (!client.connected()) mqttReconnect();
  client.loop();

  handleTimeouts();

  if (cardAccepted) {
    keypadHandler();
    return;
  }
  
  // Check fingerprint sensor
  fingerprintHandler();
  
  rfidHandler();
  displayHandler();
  
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }
}
