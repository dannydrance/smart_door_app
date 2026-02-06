import time
import paho.mqtt.client as mqtt
from jnius import autoclass

BROKER = "broker.hivemq.com"
TOPIC = "esp32/notification"

PythonService = autoclass('org.kivy.android.PythonService')
Context = autoclass('android.content.Context')
NotificationBuilder = autoclass('android.app.Notification$Builder')
NotificationManager = autoclass('android.app.NotificationManager')
NotificationChannel = autoclass('android.app.NotificationChannel')
BuildVersion = autoclass('android.os.Build$VERSION')
BuildVersionCodes = autoclass('android.os.Build$VERSION_CODES')


def create_channel(service):
    if BuildVersion.SDK_INT >= BuildVersionCodes.O:
        channel = NotificationChannel(
            "smartdoor",
            "Smart Door Alerts",
            NotificationManager.IMPORTANCE_HIGH
        )
        nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
        nm.createNotificationChannel(channel)


def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    message = msg.payload.decode()
    service = PythonService.mService

    create_channel(service)

    nm = service.getSystemService(Context.NOTIFICATION_SERVICE)

    builder = NotificationBuilder(service, "smartdoor")
    builder.setContentTitle("🚪 Smart Door Alert")
    builder.setContentText(message)
    builder.setSmallIcon(service.getApplicationInfo().icon)
    builder.setAutoCancel(True)

    nm.notify(int(time.time()), builder.build())


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, 1883, 60)
    client.loop_start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
