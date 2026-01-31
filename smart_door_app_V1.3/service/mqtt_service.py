import time
import paho.mqtt.client as mqtt
from jnius import autoclass, cast

# ---- MODIFY THIS ----
BROKER = "broker.hivemq.com"
TOPIC = "esp32/notification"
# ----------------------

PythonService = autoclass('org.kivy.android.PythonService')
Context = autoclass('android.content.Context')
NotificationManager = autoclass('android.app.NotificationManager')
NotificationChannel = autoclass('android.app.NotificationChannel')
NotificationBuilder = autoclass('android.app.Notification$Builder')
Build = autoclass('android.os.Build')
VERSION = Build.VERSION

CHANNEL_ID = "smartdoor_channel"

def create_channel(service):
    if VERSION.SDK_INT >= 26:
        nm = cast(NotificationManager, service.getSystemService(Context.NOTIFICATION_SERVICE))
        importance = NotificationManager.IMPORTANCE_HIGH
        channel = NotificationChannel(CHANNEL_ID, "SmartDoor Alerts", importance)
        channel.setDescription("Notifications for SmartDoor events")
        nm.createNotificationChannel(channel)

def notify(service, title, message):
    nm = cast(NotificationManager, service.getSystemService(Context.NOTIFICATION_SERVICE))
    if VERSION.SDK_INT >= 26:
        builder = NotificationBuilder(service, CHANNEL_ID)
    else:
        builder = NotificationBuilder(service)
    builder.setContentTitle(title)
    builder.setContentText(message)
    # ⚠ Must set a small icon
    builder.setSmallIcon(service.getApplicationInfo().icon)
    nm.notify(1, builder.build())

def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    message = msg.payload.decode()
    service = PythonService.mService
    notify(service, "Smart Door Alert", message)

def main():
    service = PythonService.mService
    create_channel(service)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, 1883, 60)
    client.loop_start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
