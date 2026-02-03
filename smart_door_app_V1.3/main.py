# main.py
import kivy
kivy.require('2.3.0')

from kivy.logger import Logger
Logger.info("SmartDoorApp: Starting application")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivy.utils import platform

from mqtt_client import MqttHandler
from database import Database
from screens.login_screen import LoginScreen
from screens.dashboard import DashboardScreen
from screens.manage_screen import ManageScreen
from screens.users_screen import UsersScreen

# Load KV files
Builder.load_file("kv/login.kv")
Builder.load_file("kv/dashboard.kv")
Builder.load_file("kv/manage.kv")
Builder.load_file("kv/users.kv")


def start_background_service():
    if platform == "android":
        from android import AndroidService
        service = AndroidService(
            "Smart Door Background Service",
            "Listening for Door Alerts..."
        )
        service.start()


class SmartDoorApp(App):

    def build(self):
        # ------------------ Database ------------------
        self.db = Database()
        self.current_user = None

        # ------------------ Screen Manager ------------------
        self.sm = ScreenManager()
        self.sm.app = self

        self.sm.add_widget(LoginScreen(name="login"))
        self.sm.add_widget(DashboardScreen(name="dashboard"))
        self.sm.add_widget(ManageScreen(name="manage"))
        self.sm.add_widget(UsersScreen(name="users"))

        # ------------------ MQTT State ------------------
        self.mqtt = None
        self.offline_banner = None
        self.was_online = True

        # ------------------ Global Status Bar ------------------
        self.status_bar = Label(
            text="🔴 MQTT OFFLINE",
            size_hint_y=None,
            height=dp(28),
            color=(1, 0.4, 0.4, 1)
        )

        root = BoxLayout(orientation="vertical")
        root.add_widget(self.status_bar)
        root.add_widget(self.sm)

        start_background_service()
        return root   # ✅ RETURN ROOT (FIXED)

    # ------------------ MQTT UI Status ------------------
    def update_mqtt_status(self, online):
        if online:
            self.status_bar.text = "🟢 MQTT CONNECTED"
            self.status_bar.color = (0.4, 1, 0.4, 1)
        else:
            self.status_bar.text = "🔴 MQTT OFFLINE"
            self.status_bar.color = (1, 0.4, 0.4, 1)

    # ------------------ App Start ------------------
    def on_start(self):
        Clock.schedule_once(self.start_mqtt, 2)
        Clock.schedule_interval(self.check_connection, 1)

    def start_mqtt(self, *_):
        Logger.info("MQTT: Initializing connection")
        self.mqtt = MqttHandler(
            host="bffac683e63348f5b429862109209547.s1.eu.hivemq.cloud",
            port=8883,
            user="hivemq.webclient.1762324468600",
            password="Cv;*bFcq>y8KT237.DhJ",
            app=self
        )
        self.mqtt.connect()

    # ------------------ User ------------------
    def set_user(self, username):
        self.current_user = username

    # ------------------ Toast ------------------
    def toast(self, message, color=(1, 1, 1, 1), duration=2):
        view = ModalView(
            size_hint=(None, None),
            size=(300, 50),
            background_color=(0, 0, 0, 0.8)
        )
        view.add_widget(Label(text=message, color=color))
        view.open()
        Clock.schedule_once(lambda dt: view.dismiss(), duration)

    # ------------------ Offline Banner (EDGE-TRIGGERED) ------------------
    def check_connection(self, _):
        if not self.mqtt:
            return

        online = self.mqtt.is_online()

        # ONLINE → OFFLINE
        if self.was_online and not online:
            self.was_online = False
            self.show_offline_banner()

        # OFFLINE → ONLINE
        elif not self.was_online and online:
            self.was_online = True
            self.hide_offline_banner()

    def show_offline_banner(self):
        if self.offline_banner:
            return

        self.offline_banner = ModalView(
            size_hint=(1, 0.1),
            auto_dismiss=False,
            background_color=(0, 0, 0, 0.7)
        )
        self.offline_banner.add_widget(
            Label(
                text="⚠ OFFLINE – reconnecting...",
                color=(1, 0.8, 0, 1)
            )
        )
        self.offline_banner.open()

    def hide_offline_banner(self):
        if self.offline_banner:
            self.offline_banner.dismiss()
            self.offline_banner = None


if __name__ == "__main__":
    SmartDoorApp().run()
