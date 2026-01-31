# screens/dashboard.py (Updated with responsive units)
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.uix.dropdown import DropDown
from kivy.uix.button import Button
from kivy.metrics import dp, sp  # ADDED
from datetime import datetime, timedelta
import re

from kivy.app import App
from kivy.uix.modalview import ModalView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

from kivy.utils import platform
if platform == "android":
    from jnius import autoclass
    PythonService = autoclass('org.kivy.android.PythonService')
    Context = autoclass('android.content.Context')
    NotificationBuilder = autoclass('android.app.Notification$Builder')
    NotificationManager = autoclass('android.app.NotificationManager')
else:
    PythonService = None
    Context = None
    NotificationBuilder = None
    NotificationManager = None


class DashboardScreen(Screen):
    door_status = "N/A"
    rssi = StringProperty("N/A")
    connection_status = StringProperty("Disconnected")

    STATUS_COLORS = {
        "Open": (0,1,0,1),
        "Closed": (1,0,0,1),
        "Unknown": (1,1,0,1)
    }
    TYPE_COLORS = {
        "status": (0.2, 0.6, 1, 1),
        "event": (0.6, 1, 0.2, 1),
        "command": (1, 0.6, 0.2, 1),
        "unknown": (0.7, 0.7, 0.7, 1)
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_interval(self.update_ui, 1)
        self.start_time = Clock.get_boottime()
        self.menu_open = False
        self.heartbeat_event = None
        self.heartbeat_timeout = 100
        self.start_heartbeat_timer()
        self.last_notifications = {}

    def on_pre_enter(self):
        if not self.last_notifications:
            self.load_last_notifications_from_db()

    def load_last_notifications_from_db(self):
        db = self.manager.app.db
        notifications = db.get_notifications(limit=50)
        for id, msg, status, timestamp in notifications:
            if self.is_heartbeat_message(msg):
                continue
            ts = datetime.fromisoformat(timestamp)
            self.last_notifications[msg] = ts
            self.add_notification_to_ui(msg, status, ts)

    def add_notification_to_ui(self, message, status, timestamp, msg_type="event"):
        card = self.build_notification_card(message, timestamp, msg_type)
        self.ids.notification_list.add_widget(card)

    # UPDATED with dp/sp units
    def build_notification_card(self, message, timestamp, msg_type):
        message = re.sub(r"^\s*\d{1,2}:\d{2}(:\d{2})?\s*", "", message).strip()

        bg_color = (0.14, 0.16, 0.20, 1)
        line_color = (0.4, 0.4, 0.4, 0.25)
        text_color = self.TYPE_COLORS.get(msg_type, (1, 1, 1, 1))
        chip_color = (*text_color[:3], 0.25)

        container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            #height=dp(80),   RESPONSIVE
            padding=[dp(12), dp(8)],  # RESPONSIVE
            spacing=dp(4),  # RESPONSIVE
        )
        container.size_hint_x = 1
        container.notif_id = None

        with container.canvas.before:
            Color(*bg_color)
            container.bg_rect = Rectangle(pos=container.pos, size=container.size)
        container.bind(pos=lambda *_: setattr(container.bg_rect, 'pos', container.pos))
        container.bind(size=lambda *_: setattr(container.bg_rect, 'size', container.size))

        # Header row
        header_row = BoxLayout(
            orientation="horizontal", 
            size_hint_y=None, 
            height=dp(22),  # RESPONSIVE
            spacing=dp(6)  # RESPONSIVE
        )

        ts_label = Label(
            text=f"[b]{timestamp.strftime('%H:%M:%S')}[/b]",
            markup=True,
            font_size=sp(12),  # RESPONSIVE
            color=(0.75, 0.85, 1, 1),
            halign='left',
            valign='middle',
            size_hint_x=None,
            width=dp(80),  # RESPONSIVE
        )

        chip = Label(
            text=msg_type.upper(),
            font_size=sp(10),  # RESPONSIVE
            bold=True,
            color=text_color,
            size_hint=(None, None),
            height=dp(20),  # RESPONSIVE
            width=dp(70),  # RESPONSIVE
            halign="center",
            valign="middle",
            text_size=(dp(70), dp(20)),  # RESPONSIVE
        )
        with chip.canvas.before:
            Color(*chip_color)
            chip.bg = Rectangle(pos=chip.pos, size=chip.size)
        chip.bind(pos=lambda *_: setattr(chip.bg, 'pos', chip.pos))
        chip.bind(size=lambda *_: setattr(chip.bg, 'size', chip.size))

        header_row.add_widget(ts_label)
        header_row.add_widget(chip)

        # Message label with proper wrapping
        msg_label = Label(
            text=message,
            markup=True,
            color=text_color,
            font_size=sp(13),  # RESPONSIVE
            halign='left',
            valign='top',
            size_hint_y=None,
            size_hint_x=1,
        )

        def update_wrap(*args):
            if container.width > 0:
                msg_label.text_size = (container.width - dp(40), None)  # RESPONSIVE
        
        msg_label.bind(width=update_wrap)
        msg_label.bind(texture_size=lambda _, size: setattr(msg_label, 'height', size[1]))
        container.bind(width=lambda _, w: setattr(msg_label, "width", max(0, w - dp(40))))  # RESPONSIVE
        
        # Divider
        divider = Widget(size_hint_y=None, height=1)
        with divider.canvas.before:
            Color(*line_color)
            divider.rect = Rectangle(pos=divider.pos, size=divider.size)
        divider.bind(pos=lambda *_: setattr(divider.rect, 'pos', divider.pos))
        divider.bind(size=lambda *_: setattr(divider.rect, 'size', divider.size))

        container.add_widget(header_row)
        container.add_widget(msg_label)
        container.add_widget(divider)

        def update_container_height(*_):
            container.height = (
                header_row.height
                + msg_label.height
                + divider.height
                + dp(16)  # padding compensation
            )
        msg_label.bind(height=update_container_height)
        container.bind(width=lambda *_: update_wrap())
        
        return container

    def update_rssi(self, rssi_value):
        self.rssi = f"{rssi_value} dBm"
        self.ids.wifi_label.text = f"Signal: {self.rssi}"
        if rssi_value >= -50:
            self.ids.wifi_label.color = (0.2, 1, 0.2, 1)
        elif rssi_value >= -70:
            self.ids.wifi_label.color = (1, 1, 0, 1)
        else:
            self.ids.wifi_label.color = (1, 0.3, 0.3, 1)

    def update_ui(self, dt):
        self.ids.connection_label.text = f"MQTT: {self.connection_status}"
        if self.connection_status == "Connected":
            self.ids.connection_label.color = (0, 1, 0, 1)
        else:
            self.ids.connection_label.color = (1, 0.3, 0.3, 1)

    def start_heartbeat_timer(self):
        if self.heartbeat_event:
            self.heartbeat_event.cancel()
        self.heartbeat_event = Clock.schedule_once(self.mark_offline, self.heartbeat_timeout)

    def mark_offline(self, dt):
        self.ids.status_label.text = "Device Offline"
        self.ids.status_label.color = (1, 0.3, 0.3, 1)

    def update_mqtt_status(self, connected: bool):
        if connected:
            self.connection_status = "Connected"
            self.ids.connection_label.color = (0,1,0,1)
        else:
            self.connection_status = "Disconnected"
            self.ids.connection_label.color = (1,0.3,0.3,1)

    def send_command(self, cmd: str):
        app = self.manager.app
        if app.mqtt.is_online():
            app.mqtt.publish("door/command", cmd)
            app.toast(f"📤 Sent command: {cmd}")
            self.add_notification(f"Sent command: {cmd}", msg_type="command")
        else:
            app.toast("Offline – cannot send command", color=(1,0.3,0.3,1))

    def is_heartbeat_message(self, message: str) -> bool:
        return (
            "HEARTBEAT" in message
            or "Uptime:" in message
            or "WiFi RSSI:" in message
            or "RSSI:" in message
        )

    def handle_event(self, event_msg: str, msg_type="event"):
        now = datetime.now()
        self.update_status(event_msg)

        if self.is_heartbeat_message(event_msg):
            return
    
        last_time = self.last_notifications.get(event_msg)
        if last_time and (now - last_time) < timedelta(minutes=1):
            self.update_notification_time(event_msg)
            return

        self.last_notifications[event_msg] = now

        #if "State: LOCKED" in event_msg:
            #self.door_status = "Closed"
        #elif "State: UNLOCKED" in event_msg:
            #self.door_status = "Open"
        #elif "ALERT" in event_msg:
            #self.door_status = "Unknown"

        cleaned_message = re.sub(r"^\s*\d{1,2}:\d{2}(:\d{2})?\s*", "", event_msg).strip()
        self.add_notification(cleaned_message, msg_type=msg_type)
        self.update_status(event_msg)

    def update_notification_time(self, message):
        for container in self.ids.notification_list.children:
            for widget in container.children:
                if isinstance(widget, Label) and "[b]" in widget.text:
                    widget.text = f"[b]{datetime.now().strftime('%H:%M:%S')}[/b]"
                    return

    def update_status(self, message):
        self.start_heartbeat_timer()

        if "State: LOCKED" in message:
            self.door_status = "Closed"
        elif "State: UNLOCKED" in message:
            self.door_status = "Open"
        
        if "RSSI:" in message:
            try:
                rssi_val = int(message.split("RSSI:")[-1].strip().split()[0])
                self.update_rssi(rssi_val)
            except (ValueError, IndexError):
                pass

        if self.connection_status == "Connected":
            if self.door_status != "N/A" or self.door_status != "Unknown":
                self.ids.status_label.text = f"Door: {self.door_status}"
                self.ids.status_label.color = self.STATUS_COLORS.get(self.door_status, (1, 1, 0, 1))
            else:
                self.ids.status_label.text = "Device Online"
                self.ids.status_label.color = (0, 1, 0, 1)
        else:
            self.ids.status_label.text = "Device Offline"
            self.ids.status_label.color = (1, 0.3, 0.3, 1)

    def add_notification(self, message, msg_type="unknown"):
        now = datetime.now()
        if self.is_heartbeat_message(message):
            return
        
        db = self.manager.app.db
        notif_id = db.add_notification(message, self.door_status)
        card = self.build_notification_card(message, now, msg_type)
        card.notif_id = notif_id
        self.ids.notification_list.add_widget(card, index=0)

        if len(self.ids.notification_list.children) > 50:
            self.ids.notification_list.remove_widget(self.ids.notification_list.children[-1])

        self.send_android_notification(message, msg_type)

    def clear_notifications(self):
        self.manager.app.db.clear_notifications()
        self.ids.notification_list.clear_widgets()
        self.last_notifications.clear()
        self.manager.app.toast("Notifications cleared", color=(0.6,0.9,1,1))

    def send_android_notification(self, message, msg_type="unknown"):
        try:
            service = PythonService.mService
            nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
            builder = NotificationBuilder(service)
            builder.setContentTitle("Smart Door Alert")
            builder.setContentText(message)
            builder.setSmallIcon(service.getApplicationInfo().icon)
            nm.notify(hash(message), builder.build())
        except Exception as e:
            print("Android notification failed:", e)

    def open_profile_edit(self):
        """Popup for editing profile"""
        app = App.get_running_app()
        user = app.db.get_user(app.current_user)
        display_name = user[3] if user else ""

        box = BoxLayout(
            orientation='vertical', 
            spacing=dp(10),
            padding=dp(15)
        )

        name_input = TextInput(
            text=display_name, 
            hint_text="Display Name", 
            multiline=False,
            font_size=sp(14)
        )
        pass_input = TextInput(
            hint_text="New Password (optional)", 
            password=True, 
            multiline=False,
            font_size=sp(14)
        )

        btn_save = Button(
            text="💾 Save", 
            size_hint_y=None, 
            height=dp(45),
            background_color=(0.2,0.6,0.9,1),
            font_size=sp(14)
        )
        btn_cancel = Button(
            text="❌ Cancel", 
            size_hint_y=None, 
            height=dp(45),
            background_color=(0.5,0.5,0.5,1),
            font_size=sp(14)
        )

        box.add_widget(Label(
            text="Edit Profile", 
            font_size=sp(18),
            bold=True
        ))
        box.add_widget(name_input)
        box.add_widget(pass_input)
        box.add_widget(btn_save)
        box.add_widget(btn_cancel)

        popup = Popup(title="", content=box, size_hint=(0.85, 0.5), auto_dismiss=False)

        def save_changes(_):
            new_name = name_input.text.strip()
            new_pass = pass_input.text.strip() or None
            if new_name:
                app.db.update_profile(app.current_user, new_name, new_pass)
                popup.dismiss()
                app.toast("✅ Profile updated!")
            else:
                app.toast("⚠ Enter a valid name")

        btn_save.bind(on_release=save_changes)
        btn_cancel.bind(on_release=lambda _: popup.dismiss())
        popup.open()

    def open_profile_window(self):
        """Full profile edit window with email and password confirmation"""
        app = App.get_running_app()
        user = app.db.get_user(app.current_user)
        if not user:
            app.toast("⚠ User not found!", color=(1, 0.4, 0.4, 1))
            return

        _, username, _, display_name, email, _ = user

        profile_popup = ModalView(size_hint=(0.85, 0.7), background_color=(0,0,0,0.8))
        box = BoxLayout(
            orientation='vertical', 
            padding=dp(20),
            spacing=dp(15)
        )
        box.add_widget(Label(
            text="Edit Profile", 
            font_size=sp(20),
            color=(1,1,1,1)
        ))

        self.display_name_input = TextInput(
            hint_text="Display Name", 
            text=display_name or "", 
            multiline=False,
            font_size=sp(14)
        )
        self.email_input = TextInput(
            hint_text="Email Address", 
            text=email or "", 
            multiline=False,
            font_size=sp(14)
        )
        self.new_password_input = TextInput(
            hint_text="New Password (optional)", 
            password=True, 
            multiline=False,
            font_size=sp(14)
        )
        self.confirm_password_input = TextInput(
            hint_text="Confirm Password", 
            password=True, 
            multiline=False,
            font_size=sp(14)
        )

        box.add_widget(self.display_name_input)
        box.add_widget(self.email_input)
        box.add_widget(self.new_password_input)
        box.add_widget(self.confirm_password_input)

        btn_row = BoxLayout(
            size_hint_y=None, 
            height=dp(50),
            spacing=dp(10)
        )
        btn_save = Button(
            text="Save Changes", 
            background_color=(0.2,0.7,0.4,1), 
            color=(1,1,1,1), 
            bold=True,
            font_size=sp(14)
        )
        btn_cancel = Button(
            text="Cancel", 
            background_color=(0.5,0.5,0.5,1), 
            color=(1,1,1,1), 
            bold=True,
            font_size=sp(14)
        )
        btn_save.bind(on_release=lambda _: self.save_profile(profile_popup))
        btn_cancel.bind(on_release=lambda _: profile_popup.dismiss())

        btn_row.add_widget(btn_save)
        btn_row.add_widget(btn_cancel)
        box.add_widget(btn_row)
        profile_popup.add_widget(box)
        profile_popup.open()

    def save_profile(self, popup):
        app = App.get_running_app()
        username = app.current_user
        display_name = self.display_name_input.text.strip()
        email = self.email_input.text.strip()
        new_pw = self.new_password_input.text.strip()
        confirm_pw = self.confirm_password_input.text.strip()

        if not display_name or not email:
            app.toast("⚠ Display name and email are required!", color=(1,0.6,0.2,1))
            return
        if new_pw and new_pw != confirm_pw:
            app.toast("❌ Passwords do not match!", color=(1,0.3,0.3,1))
            return

        try:
            app.db.update_profile(username, display_name, email, new_pw if new_pw else None)
            popup.dismiss()
            app.toast("✅ Profile updated successfully!", color=(0.4,1,0.4,1))
        except Exception as e:
            app.toast(f"❌ Failed to update profile: {e}", color=(1,0.3,0.3,1))

     # --------------------------
    # Dropdown menu
    # --------------------------
    def open_menu(self, btn):
        self.dropdown = DropDown(auto_dismiss=True)

        btn_profile = Button(
            text="Edit Profile",
            size_hint_y=None,
            height=dp(44),
            background_normal='',
            background_color=(0.2,0.6,0.9,1),
            color=(1,1,1,1),
            font_size=sp(14)
        )
        btn_profile.bind(on_release=lambda _: self.open_profile_window())

        btn_logout = Button(
            text="Logout",
            size_hint_y=None,
            height=dp(44),
            background_normal='',
            background_color=(0.9,0.3,0.3,1),
            color=(1,1,1,1),
            font_size=sp(14)
        )
        btn_logout.bind(on_release=lambda _: self.logout())

        self.dropdown.add_widget(btn_profile)
        self.dropdown.add_widget(btn_logout)
        self.dropdown.open(btn)

    def logout(self):
        self.dropdown.dismiss()
        self.manager.app.toast("Logged out successfully", color=(1,0.6,0.6,1))
        self.manager.current = "login"