import time
import paho.mqtt.client as mqtt
from jnius import autoclass

# ---- MODIFY THIS ----
BROKER = "broker.hivemq.com"
TOPIC = "esp32/notification"
# ----------------------

PythonService = autoclass('org.kivy.android.PythonService')
Context = autoclass('android.content.Context')
NotificationBuilder = autoclass('android.app.Notification$Builder')
NotificationManager = autoclass('android.app.NotificationManager')


def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    message = msg.payload.decode()
    service = PythonService.mService
    nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
    builder = NotificationBuilder(service)
    builder.setContentTitle("Smart Door Alert")
    builder.setContentText(message)
    
    # Optional: change icon or color based on type
    if "ALERT" in message:
        # builder.setSmallIcon(alert_icon)
        pass
    elif "PIN updated" in message or "Sent" in message:
        # builder.setSmallIcon(command_icon)
        pass

    nm.notify(1, builder.build())


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
