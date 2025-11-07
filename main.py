# main.py
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView

from mqtt_client import MqttHandler
from database import Database
from screens.login_screen import LoginScreen
from screens.dashboard import DashboardScreen
from screens.manage_screen import ManageScreen

# Load KV files
Builder.load_file("kv/login.kv")
Builder.load_file("kv/dashboard.kv")
Builder.load_file("kv/manage.kv")


class SmartDoorApp(App):
    def build(self):
        # ------------------ Database ------------------
        self.db = Database()          # Initialize database
        self.current_user = None      # Store logged-in username

        # ------------------ MQTT ----------------------
        self.mqtt = MqttHandler(
            host="bffac683e63348f5b429862109209547.s1.eu.hivemq.cloud",
            port=8883,
            user="hivemq.webclient.1762324468600",
            password="Cv;*bFcq>y8KT237.DhJ",
            app=self
        )
        self.mqtt.connect()
        
        Clock.schedule_interval(self.check_connection, 1)

        # ------------------ Screen Manager ------------------
        self.sm = ScreenManager()
        self.sm.app = self

        # Add screens
        self.sm.add_widget(LoginScreen(name="login"))
        self.sm.add_widget(DashboardScreen(name="dashboard"))
        self.sm.add_widget(ManageScreen(name="manage"))

        return self.sm

    # ------------------ User ------------------
    def set_user(self, username):
        """Store logged-in username globally"""
        self.current_user = username

    # ------------------ Popup Messages ------------------
    def toast(self, message, color=(1, 1, 1, 1), duration=2):
        """Temporary message popup"""
        view = ModalView(size_hint=(None, None), size=(300, 50), background_color=(0, 0, 0, 0.8))
        lbl = Label(text=message, color=color)
        view.add_widget(lbl)
        view.open()
        Clock.schedule_once(lambda dt: view.dismiss(), duration)

    # ------------------ Offline Banner ------------------
    def check_connection(self, dt):
        """Show/hide offline banner depending on MQTT"""
        online = self.mqtt.is_online()
        current_screen = self.sm.current

        if online:
            if hasattr(self, "offline_banner") and self.offline_banner:
                self.offline_banner.dismiss()
                self.offline_banner = None
        else:
            if current_screen == "dashboard":
                if not hasattr(self, "offline_banner") or not self.offline_banner:
                    self.show_offline_banner()

    def show_offline_banner(self):
        """Show a small banner at the top when offline"""
        self.offline_banner = ModalView(size_hint=(1, 0.1), background_color=(0, 0, 0, 0.7))
        self.offline_banner.add_widget(Label(text="⚠ OFFLINE – reconnecting...", color=(1, 0.8, 0, 1)))
        self.offline_banner.open()

    # ------------------ Temporary Manage Popup ------------------
    def show_manage_popup(self):
        from kivy.uix.popup import Popup
        Popup(
            title="Manage Cards & PIN",
            content=Label(text="Coming soon: Edit/Delete/Update..."),
            size_hint=(0.8, 0.5)
        ).open()


if __name__ == "__main__":
    SmartDoorApp().run()
