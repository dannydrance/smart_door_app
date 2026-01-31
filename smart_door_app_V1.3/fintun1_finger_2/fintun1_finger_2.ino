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
const long gmtOffset_sec = 2 * 3600;
const int daylightOffset_sec = 0;

// ---------- MQTT Settings ----------
const char* mqtt_server = "bffac683e63348f5b429862109209547.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char* mqtt_user = "hivemq.webclient.1762324468600";
const char* mqtt_password = "Cv;*bFcq>y8KT237.DhJ";

const char* topic_status  = "door/status";
const char* topic_event   = "door/events";
const char* topic_command = "door/command";

// ---------- Fingerprint Sensor ----------
HardwareSerial fingerSerial(2);
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&fingerSerial);

// ---------- Heartbeat ----------
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_INTERVAL = 60000;

// ---------- OLED ----------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ---------- RFID ----------
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
byte colPins[COLS] = {32, 33, 26, 25};
Keypad keypad = Keypad(makeKeymap(hexaKeys), rowPins, colPins, ROWS, COLS);

// ---------- Hardware Pins ----------
#define RELAY_PIN 16
#define VIBRATION_PIN 35
#define IR_SENSOR_PIN 34
//#define LED 17
#define BUZZER_PIN 15

// ---------- UNIFIED USER SYSTEM ----------
#define MAX_USERS 10
#define EEPROM_SIZE 512
#define USER_RECORD_SIZE 40  // UID(12) + Name(20) + PIN(6) + FP_ID(1) + Active(1)

struct User {
  char rfid_uid[12];        // RFID card UID
  char name[20];            // User name
  char pin[6];              // 4-digit PIN + null
  uint8_t fingerprint_id;   // Fingerprint ID (1-127, 0=none)
  bool active;              // Is user active
};

User users[MAX_USERS];
int userCount = 0;

// Registration state
bool registrationMode = false;
int regUserIndex = -1;
String tempRFID = "";
String tempName = "";
String tempPIN = "";
int regStage = 0; // 0=RFID, 1=Name, 2=PIN, 3=FP1, 4=FP2
int tempFPID = 0;

// Authentication state
String currentAuthRFID = "";
bool awaitingPIN = false;
String EnterPassword = "";

// ---------- Timing ----------
unsigned long lastActivity = 0;
unsigned long lastDisplayUpdate = 0;
bool doorUnlocked = false;
unsigned long doorOpenStart = 0;
const unsigned long DOOR_OPEN_TIMEOUT = 10000;

// ---------- Network ----------
WiFiClientSecure espClient;
PubSubClient client(espClient);

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

// ---------- USER MANAGEMENT ----------

void initUsers() {
  userCount = 0;
  for (int i = 0; i < MAX_USERS; i++) {
    int addr = i * USER_RECORD_SIZE;
    
    // Read active flag
    users[i].active = EEPROM.read(addr);
    if (!users[i].active) continue;
    
    // Read RFID
    for (int j = 0; j < 12; j++) {
      users[i].rfid_uid[j] = EEPROM.read(addr + 1 + j);
    }
    
    // Read Name
    for (int j = 0; j < 20; j++) {
      users[i].name[j] = EEPROM.read(addr + 13 + j);
    }
    
    // Read PIN
    for (int j = 0; j < 6; j++) {
      users[i].pin[j] = EEPROM.read(addr + 33 + j);
    }
    
    // Read Fingerprint ID
    users[i].fingerprint_id = EEPROM.read(addr + 39);
    
    if (users[i].active) userCount++;
  }
  
  Serial.println("✅ Loaded " + String(userCount) + " users from EEPROM");
}

void saveUser(int index) {
  if (index < 0 || index >= MAX_USERS) return;
  
  int addr = index * USER_RECORD_SIZE;
  
  EEPROM.write(addr, users[index].active ? 1 : 0);
  
  for (int i = 0; i < 12; i++) {
    EEPROM.write(addr + 1 + i, users[index].rfid_uid[i]);
  }
  
  for (int i = 0; i < 20; i++) {
    EEPROM.write(addr + 13 + i, users[index].name[i]);
  }
  
  for (int i = 0; i < 6; i++) {
    EEPROM.write(addr + 33 + i, users[index].pin[i]);
  }
  
  EEPROM.write(addr + 39, users[index].fingerprint_id);
  
  EEPROM.commit();
}

int findUserByRFID(String rfid) {
  rfid.toUpperCase();
  for (int i = 0; i < MAX_USERS; i++) {
    if (users[i].active && String(users[i].rfid_uid) == rfid) {
      return i;
    }
  }
  return -1;
}

int findUserByFingerprint(uint8_t fp_id) {
  for (int i = 0; i < MAX_USERS; i++) {
    if (users[i].active && users[i].fingerprint_id == fp_id) {
      return i;
    }
  }
  return -1;
}

int findEmptySlot() {
  for (int i = 0; i < MAX_USERS; i++) {
    if (!users[i].active) return i;
  }
  return -1;
}

void deleteUser(int index) {
  if (index < 0 || index >= MAX_USERS) return;
  
  // Delete fingerprint from sensor
  if (users[index].fingerprint_id > 0) {
    finger.deleteModel(users[index].fingerprint_id);
  }
  
  // Clear user data
  users[index].active = false;
  memset(users[index].rfid_uid, 0, 12);
  memset(users[index].name, 0, 20);
  memset(users[index].pin, 0, 6);
  users[index].fingerprint_id = 0;
  
  saveUser(index);
  userCount--;
  
  mqttPublish(topic_event, "User deleted successfully");
}

void clearAllUsers() {
  // Delete all fingerprints from sensor
  finger.emptyDatabase();
  
  // Clear all users from EEPROM
  for (int i = 0; i < MAX_USERS; i++) {
    if (users[i].active) {
      users[i].active = false;
      memset(users[i].rfid_uid, 0, 12);
      memset(users[i].name, 0, 20);
      memset(users[i].pin, 0, 6);
      users[i].fingerprint_id = 0;
      saveUser(i);
    }
  }
  
  userCount = 0;
  
  buzzerSuccess();
  showMessage("All users cleared!");
  mqttPublish(topic_event, "✅ All users cleared successfully");
  Serial.println("✅ All users and fingerprints cleared");
}

void listUsers() {
  String list = "=== REGISTERED USERS ===\n";
  for (int i = 0; i < MAX_USERS; i++) {
    if (users[i].active) {
      list += String(i + 1) + ". " + String(users[i].name) + "\n";
      list += "   RFID: " + String(users[i].rfid_uid) + "\n";
      list += "   PIN: ****\n";
      list += "   FP ID: " + String(users[i].fingerprint_id) + "\n\n";
    }
  }
  list += "Total: " + String(userCount) + "/" + String(MAX_USERS);
  mqttPublish(topic_event, list);
}

// ---------- USER REGISTRATION ----------

void startRegistration(String name) {
  if (userCount >= MAX_USERS) {
    mqttPublish(topic_event, "ERROR: User limit reached");
    return;
  }
  
  registrationMode = true;
  regStage = 0;
  tempName = name;
  tempRFID = "";
  tempPIN = "";
  tempFPID = 0;
  
  showMessage("Registration:\nScan RFID card");
  mqttPublish(topic_event, "Registration started for: " + name + "\nStep 1: Scan RFID card");
  Serial.println("🔐 Registration started for: " + name);
}

void handleRegistration() {
  if (!registrationMode) return;
  
  if (regStage == 0) {
    // Wait for RFID scan
    if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) return;
    
    tempRFID = getUID();
    
    // Check if RFID already exists
    if (findUserByRFID(tempRFID) != -1) {
      mqttPublish(topic_event, "ERROR: RFID card already registered");
      showMessage("Card exists!");
      buzzerError();
      delay(2000);
      registrationMode = false;
      return;
    }
    
    buzzerBeep();
    mqttPublish(topic_event, "RFID captured: " + tempRFID + "\nStep 2: Send PIN via MQTT\nCommand: SET_REG_PIN:1234");
    showMessage("RFID OK!\nWaiting for PIN");
    regStage = 1;
    mfrc522.PICC_HaltA();
  }
  else if (regStage == 2) {
    // PIN received, now enroll fingerprint
    showMessage("Place finger...");
    int p = finger.getImage();
    if (p != FINGERPRINT_OK) return;
    
    p = finger.image2Tz(1);
    if (p != FINGERPRINT_OK) {
      mqttPublish(topic_event, "ERROR: Fingerprint scan failed");
      registrationMode = false;
      buzzerError();
      return;
    }
    
    buzzerBeep();
    showMessage("Remove finger");
    delay(1000);
    mqttPublish(topic_event, "First fingerprint captured\nPlace same finger again");
    regStage = 3;
  }
  else if (regStage == 3) {
    // Wait for finger removal
    if (finger.getImage() != FINGERPRINT_NOFINGER) return;
    regStage = 4;
  }
  else if (regStage == 4) {
    // Second fingerprint scan
    showMessage("Place finger again");
    int p = finger.getImage();
    if (p != FINGERPRINT_OK) return;
    
    p = finger.image2Tz(2);
    if (p != FINGERPRINT_OK) {
      mqttPublish(topic_event, "ERROR: Second fingerprint failed");
      registrationMode = false;
      buzzerError();
      return;
    }
    
    // Create model
    p = finger.createModel();
    if (p != FINGERPRINT_OK) {
      mqttPublish(topic_event, "ERROR: Fingerprints don't match");
      registrationMode = false;
      buzzerError();
      return;
    }
    
    // Find next available fingerprint ID
    tempFPID = 0;
    for (int id = 1; id <= 127; id++) {
      bool used = false;
      for (int i = 0; i < MAX_USERS; i++) {
        if (users[i].active && users[i].fingerprint_id == id) {
          used = true;
          break;
        }
      }
      if (!used) {
        tempFPID = id;
        break;
      }
    }
    
    if (tempFPID == 0) {
      mqttPublish(topic_event, "ERROR: No fingerprint slots available");
      registrationMode = false;
      buzzerError();
      return;
    }
    
    // Store fingerprint
    p = finger.storeModel(tempFPID);
    if (p != FINGERPRINT_OK) {
      mqttPublish(topic_event, "ERROR: Failed to store fingerprint");
      registrationMode = false;
      buzzerError();
      return;
    }
    
    // Create user record
    int slot = findEmptySlot();
    if (slot == -1) {
      mqttPublish(topic_event, "ERROR: No user slots available");
      registrationMode = false;
      buzzerError();
      return;
    }
    
    users[slot].active = true;
    tempRFID.toCharArray(users[slot].rfid_uid, 12);
    tempName.toCharArray(users[slot].name, 20);
    tempPIN.toCharArray(users[slot].pin, 6);
    users[slot].fingerprint_id = tempFPID;
    
    saveUser(slot);
    userCount++;
    
    buzzerSuccess();
    showMessage("User registered!");
    
    String msg = "✅ USER REGISTERED\n";
    msg += "Name: " + tempName + "\n";
    msg += "RFID: " + tempRFID + "\n";
    msg += "PIN: ****\n";
    msg += "Fingerprint ID: " + String(tempFPID);
    mqttPublish(topic_event, msg);
    
    Serial.println("✅ User registered: " + tempName);
    
    registrationMode = false;
    delay(2000);
  }
}

// ---------- AUTHENTICATION ----------

void authenticateWithRFID(String rfid) {
  int userIndex = findUserByRFID(rfid);
  
  if (userIndex == -1) {
    mqttPublish(topic_event, "UNAUTHORIZED: Unknown RFID " + rfid);
    showMessage("Access Denied!");
    buzzerError();
    delay(1000);
    return;
  }
  
  currentAuthRFID = rfid;
  awaitingPIN = true;
  EnterPassword = "";
  
  showMessage("Welcome " + String(users[userIndex].name) + "!\nEnter PIN:");
  mqttPublish(topic_event, "RFID recognized: " + String(users[userIndex].name) + "\nWaiting for PIN...");
  buzzerBeep();
}

void authenticateWithFingerprint(uint8_t fp_id, uint16_t confidence) {
  int userIndex = findUserByFingerprint(fp_id);
  
  if (userIndex == -1) {
    mqttPublish(topic_event, "UNAUTHORIZED: Unknown fingerprint");
    showMessage("Access Denied!");
    buzzerError();
    delay(1000);
    return;
  }
  
  // Fingerprint alone grants access
  mqttPublish(topic_event, "AUTHORIZED: " + String(users[userIndex].name));
  showMessage("Welcome!\n" + String(users[userIndex].name));
  buzzerSuccess();
  unlockDoor();
  delay(2000);
}

void verifyPIN() {
  if (!awaitingPIN) return;
  
  int userIndex = findUserByRFID(currentAuthRFID);
  if (userIndex == -1) {
    awaitingPIN = false;
    return;
  }
  
  if (EnterPassword == String(users[userIndex].pin)) {
    mqttPublish(topic_event, "AUTHORIZED: " + String(users[userIndex].name) + " (RFID + PIN)");
    showMessage("Access Granted!\n" + String(users[userIndex].name));
    buzzerSuccess();
    unlockDoor();
    delay(2000);
  } else {
    mqttPublish(topic_event, "UNAUTHORIZED: Wrong PIN for " + String(users[userIndex].name));
    showMessage("Wrong PIN!");
    buzzerError();
    delay(1000);
  }
  
  awaitingPIN = false;
  currentAuthRFID = "";
  EnterPassword = "";
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
  if (registrationMode) {
    handleRegistration();
    return;
  }
  
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) return;
  
  String uid = getUID();
  authenticateWithRFID(uid);
  mfrc522.PICC_HaltA();
}

void fingerprintHandler() {
  if (registrationMode) {
    handleRegistration();
    return;
  }
  
  if (awaitingPIN) return; // Skip fingerprint if waiting for PIN
  
  uint8_t p = finger.getImage();
  if (p != FINGERPRINT_OK) return;
  
  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) return;
  
  p = finger.fingerSearch();
  if (p == FINGERPRINT_OK) {
    authenticateWithFingerprint(finger.fingerID, finger.confidence);
  } else if (p == FINGERPRINT_NOTFOUND) {
    mqttPublish(topic_event, "UNAUTHORIZED: Fingerprint not recognized");
    showMessage("Unknown finger!");
    buzzerError();
    delay(1000);
  }
}

void keypadHandler() {
  char key = keypad.getKey();
  if (!key) return;
  
  lastActivity = millis();
  
  if (key >= '0' && key <= '9') EnterPassword += key;
  if (key == 'D' && EnterPassword.length() > 0) EnterPassword.remove(EnterPassword.length() - 1);
  if (key == 'C') EnterPassword = "";
  
  if (key == '#') {
    verifyPIN();
    return;
  }
  
  // Display masked PIN
  String masked = "";
  for (int i = 0; i < EnterPassword.length(); i++) masked += '*';
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(10, 5);
  display.println("Enter PIN:");
  display.setTextSize(2);
  display.setCursor(20, 15);
  display.println(masked);
  display.display();
}

void displayHandler() {
  if (millis() - lastDisplayUpdate > 1000 && !awaitingPIN && !registrationMode) {
    showHomeScreen();
    lastDisplayUpdate = millis();
  }
}

void handleTimeouts() {
  if (millis() - lastActivity > 30000) {
    EnterPassword = "";
    awaitingPIN = false;
    currentAuthRFID = "";
    lastActivity = millis();
  }
}

int viblast =0;
void sensorHandler() {
  int vib = digitalRead(VIBRATION_PIN);
  int door = digitalRead(IR_SENSOR_PIN);
  if (vib == HIGH && vib != viblast) {
    Serial.println("⚠️ Vibration detected!");
    showMessage("Vibration Alert!");
    mqttPublish(topic_event, "ALERT: Vibration detected");
    buzzerError();
  }
  viblast = vib;
  if (doorUnlocked && door == LOW && millis() - doorOpenStart > DOOR_OPEN_TIMEOUT) {
    mqttPublish(topic_event, "ALERT: Door open too long");
    doorOpenStart = millis();
    lockDoor();
  }
}

// ---------- DOOR CONTROL ----------

void unlockDoor() {
  digitalWrite(RELAY_PIN, HIGH);
  doorUnlocked = true;
  doorOpenStart = millis();
  mqttPublish(topic_status, "UNLOCKED");
}

void lockDoor() {
  digitalWrite(RELAY_PIN, LOW);
  doorUnlocked = false;
  showMessage("Door Locked");
  mqttPublish(topic_status, "LOCKED");
  SPI.begin();
  mfrc522.PCD_Init();
}

// ---------- TIME ----------

String getCurrentTime() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "00:00:00";
  char buf[10];
  strftime(buf, sizeof(buf), "%H:%M:%S", &timeinfo);
  return String(buf);
}

String getCurrentDate() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "0000-00-00";
  char buf[11];
  strftime(buf, sizeof(buf), "%Y-%m-%d", &timeinfo);
  return String(buf);
}

// ---------- HEARTBEAT ----------

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;
  
  long rssi = WiFi.RSSI();
  String state = doorUnlocked ? "UNLOCKED" : "LOCKED";
  
  String msg = "HEARTBEAT\n";
  msg += "State: " + state + "\n";
  msg += "Users: " + String(userCount) + "/" + String(MAX_USERS) + "\n";
  msg += "WiFi RSSI: " + String(rssi) + " dBm\n";
  msg += "Uptime: " + String(millis() / 60000) + " min";
  
  mqttPublish(topic_status, msg);
}

// ---------- MQTT ----------

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();

  bool waitingForNewRFID = false;
  String oldRFIDToReplace = "";

  Serial.println("MQTT: " + msg);
  
  if (msg == "LOCK") lockDoor();
  else if (msg == "UNLOCK") unlockDoor();
  else if (msg == "LIST_USERS") listUsers();
  else if (msg.startsWith("REGISTER_USER:")) {
    String name = msg.substring(14);
    startRegistration(name);
  }
  else if (msg.startsWith("SET_REG_PIN:")) {
    if (registrationMode && regStage == 1) {
      tempPIN = msg.substring(12);
      if (tempPIN.length() == 4) {
        mqttPublish(topic_event, "PIN set: ****\nStep 3: Enroll fingerprint\nPlace finger on sensor...");
        regStage = 2;
      } else {
        mqttPublish(topic_event, "ERROR: PIN must be 4 digits");
      }
    }
  }
  else if (msg.startsWith("DELETE_USER:")) {
    String rfid = msg.substring(12);
    rfid.toUpperCase();
    int idx = findUserByRFID(rfid);
    if (idx != -1) {
      String name = String(users[idx].name);
      deleteUser(idx);
      mqttPublish(topic_event, "User deleted: " + name);
    } else {
      mqttPublish(topic_event, "ERROR: User not found");
    }
  }
  else if (msg == "CLEAR_ALL_USERS") {
    clearAllUsers();
  }
  else if (msg == "SHOW_CONFIG") {
    String cfg = "=== SYSTEM STATUS ===\n";
    cfg += "Door: " + String(doorUnlocked ? "UNLOCKED" : "LOCKED") + "\n";
    cfg += "Users: " + String(userCount) + "/" + String(MAX_USERS) + "\n";
    cfg += "WiFi RSSI: " + String(WiFi.RSSI()) + " dBm";
    mqttPublish(topic_event, cfg);
  }
  else if (msg.startsWith("UPDATE_PIN:")) {
  // Format: UPDATE_PIN:RFID:1234
  int firstColon = msg.indexOf(':', 11);
  String rfid = msg.substring(11, firstColon);
  String newPin = msg.substring(firstColon + 1);
  
  int idx = findUserByRFID(rfid);
  if (idx != -1 && newPin.length() == 4) {
    newPin.toCharArray(users[idx].pin, 6);
    saveUser(idx);
    mqttPublish(topic_event, "PIN updated for " + String(users[idx].name));
    } else {
    mqttPublish(topic_event, "ERROR: User not found or invalid PIN");
    }
  }
  else if (msg.startsWith("REENROLL_FP:")) {
  String rfid = msg.substring(12);
  int idx = findUserByRFID(rfid);
  
  if (idx != -1) {
    // Delete old fingerprint
    finger.deleteModel(users[idx].fingerprint_id);
    
    // Start new enrollment with same ID
    tempFPID = users[idx].fingerprint_id;
    tempName = String(users[idx].name);
    tempRFID = rfid;
    tempPIN = String(users[idx].pin);
    
    registrationMode = true;
    regStage = 2;  // Skip to fingerprint stage
    
    mqttPublish(topic_event, "Re-enrolling fingerprint for " + tempName + "\nPlace finger on sensor...");
    } else {
    mqttPublish(topic_event, "ERROR: User not found");
    }
  }
  else if (msg.startsWith("CHANGE_RFID:")) {
    oldRFIDToReplace = msg.substring(12);
    oldRFIDToReplace.toUpperCase();
    
    int idx = findUserByRFID(oldRFIDToReplace);
    if (idx != -1) {
      waitingForNewRFID = true;
      mqttPublish(topic_event, "Scan new RFID card now...");
      showMessage("Scan new card...");
    } else {
      mqttPublish(topic_event, "ERROR: User not found");
    }
  }

  // In rfidHandler(), before normal authentication:
  if (waitingForNewRFID) {
    if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) return;
    
    String newRFID = getUID();
    
    // Check if new RFID already exists
    if (findUserByRFID(newRFID) != -1) {
      mqttPublish(topic_event, "ERROR: New card already registered");
      buzzerError();
      waitingForNewRFID = false;
      return;
    }
    
    // Update user's RFID
    int idx = findUserByRFID(oldRFIDToReplace);
    if (idx != -1) {
      newRFID.toCharArray(users[idx].rfid_uid, 12);
      saveUser(idx);
      
      mqttPublish(topic_event, "RFID updated for " + String(users[idx].name) + "\nNew RFID: " + newRFID);
      buzzerSuccess();
      showMessage("RFID updated!");
      }
    
    waitingForNewRFID = false;
    oldRFIDToReplace = "";
    mfrc522.PICC_HaltA();
    return;
    }
}

void mqttReconnect() {
  while (!client.connected()) {
    Serial.print("Connecting MQTT...");
    if (client.connect("ESP32Door", mqtt_user, mqtt_password)) {
      Serial.println("OK");
      client.subscribe(topic_command);
      sendHeartbeat();
    } else {
      Serial.println("FAILED");
      delay(5000);
    }
  }
}

void initFingerprint() {
  fingerSerial.begin(57600, SERIAL_8N1, 2, 17);
  delay(100);
  
  if (finger.verifyPassword()) {
    Serial.println("✅ Fingerprint sensor OK");
    mqttPublish(topic_event, "Fingerprint sensor: Online");
  } else {
    Serial.println("❌ Fingerprint sensor FAILED");
    mqttPublish(topic_event, "Fingerprint sensor: Failed");
  }
}

// ---------- SETUP ----------

void setup() {
  Serial.begin(115200);
  EEPROM.begin(EEPROM_SIZE);
  
  SPI.begin();
  mfrc522.PCD_Init();
  initFingerprint();
  
  pinMode(RELAY_PIN, OUTPUT);
  //pinMode(LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(VIBRATION_PIN, INPUT);
  pinMode(IR_SENSOR_PIN, INPUT);
  
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println("OLED FAILED");
    for(;;);
  }
  
  showMessage("Connecting WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
  }
  
  espClient.setInsecure();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
  mqttReconnect();
  
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  
  initUsers();
  showHomeScreen();
  
  Serial.println("✅ System ready!");
}

// ---------- LOOP ----------

void loop() {
  if (!client.connected()) mqttReconnect();
  client.loop();
  
  handleTimeouts();

  if(doorUnlocked && millis() - doorOpenStart > 2000){
    lockDoor();
  }
  
  if (awaitingPIN) {
    keypadHandler();
  } else {
    rfidHandler();
    fingerprintHandler();
  }
  
  displayHandler();
  sensorHandler();
  
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }
}
