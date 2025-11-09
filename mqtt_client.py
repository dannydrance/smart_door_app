#mqtt_client.py
import paho.mqtt.client as mqtt
from queue import Queue
import ssl, time
from kivy.clock import Clock
from screens.dashboard import DashboardScreen
import socket

class MqttHandler:
    def __init__(self, host, port, user, password, app=None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.app = app  # <-- SmartDoorApp instance
        self.client = mqtt.Client()
        self.client.username_pw_set(user, password)
        self.client.tls_set(cert_reqs=ssl.CERT_NONE)
        self.client.tls_insecure_set(True)
        self.messages = Queue()
        self.connected = False

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        self.connected = True
        self.client.subscribe("door/#")
        print("MQTT connected!")
        # Update dashboard
        if self.app:
            dashboard = self.app.sm.get_screen("dashboard")  # get the screen instance
            Clock.schedule_once(lambda dt: dashboard.update_mqtt_status(True))

    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        print("MQTT disconnected!")
        # Update dashboard
        if self.app:
            dashboard = self.app.sm.get_screen("dashboard")  # get the screen instance
            Clock.schedule_once(lambda dt: dashboard.update_mqtt_status(False))
            #Clock.schedule_once(lambda dt: DashboardScreen.update_mqtt_status(False))

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode().strip()
        print(f"📩 MQTT Message: {topic} -> {payload}")

        if not self.app:
            return

        dashboard = self.app.sm.get_screen("dashboard")
        manage = self.app.sm.get_screen("manage")

        # Handle status topic updates
        if topic == "door/status":
            Clock.schedule_once(lambda dt: dashboard.update_status(payload))
                                                               
        # Handle events topic updates
        elif topic == "door/events":
            Clock.schedule_once(lambda dt: dashboard.update_status(payload))
            Clock.schedule_once(lambda dt: manage.handle_event(payload))
            Clock.schedule_once(lambda dt: dashboard.handle_event(payload))

            # Forward important messages to dashboard notifications
            important_keywords = [
                "Authorized card:",
                "Card added:",
                "PIN updated",
                "Stored cards",
                "ALERT:"
            ]
            if any(k in payload for k in important_keywords):
                Clock.schedule_once(lambda dt: dashboard.add_notification(payload))

    def connect(self):
        try:
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()
            print(f"✅ Connected to MQTT broker {self.host}:{self.port}")
        except (socket.gaierror, OSError) as e:
            print(f"❌ MQTT connection failed: {e}")
            if self.app:
                # Show friendly message in the UI
                self.app.toast("⚠️ No internet connection — please connect to a network", color=(1,0.4,0.4,1))
            else:
                print("⚠️ No internet connection — please connect to a network")
    
    '''def connect(self):
        self.client.connect(self.host, self.port, 60)
        self.client.loop_start()'''

    def publish(self, topic, msg):
        if self.connected:
            self.client.publish(topic, msg)
        else:
            print("⚠ MQTT offline, message skipped:", msg)

    def get_message(self):
        if self.messages.empty():
            return None
        return self.messages.get()

    def is_online(self):
        return self.connected
