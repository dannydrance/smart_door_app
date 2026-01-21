# smart_door_app/screens/dashboard.py
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.uix.dropdown import DropDown
from kivy.uix.button import Button
from datetime import datetime, timedelta
import re   # ### FIX — needed for cleaning message text

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
                continue  # 🚫 skip heartbeat

            ts = datetime.fromisoformat(timestamp)
            self.last_notifications[msg] = ts
            self.add_notification_to_ui(msg, status, ts)

    def add_notification_to_ui(self, message, status, timestamp, msg_type="event"):
        card = self.build_notification_card(message, timestamp, msg_type)
        self.ids.notification_list.add_widget(card)

    ###########################################################################
    # FIXED CARD — FULL WIDTH + CLEANED MESSAGE + WRAPPING
    ###########################################################################
    # Fix the build_notification_card method to handle proper text wrapping:
    def build_notification_card(self, message, timestamp, msg_type):
        # Clean message first
        message = re.sub(r"^\s*\d{1,2}:\d{2}(:\d{2})?\s*", "", message).strip()

        # Colors
        bg_color = (0.14, 0.16, 0.20, 1)
        line_color = (0.4, 0.4, 0.4, 0.25)
        text_color = self.TYPE_COLORS.get(msg_type, (1, 1, 1, 1))
        chip_color = (*text_color[:3], 0.25)

        container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=78,
            padding=[14, 8],
            spacing=4,
        )

        container.size_hint_x = 1

        container.notif_id = None

        # Background
        with container.canvas.before:
            Color(*bg_color)
            container.bg_rect = Rectangle(pos=container.pos, size=container.size)
        container.bind(pos=lambda *_: setattr(container.bg_rect, 'pos', container.pos))
        container.bind(size=lambda *_: setattr(container.bg_rect, 'size', container.size))

        # Header row
        header_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=6)

        ts_label = Label(
            text=f"[b]{timestamp.strftime('%H:%M:%S')}[/b]",
            markup=True,
            font_size=14,
            color=(0.75, 0.85, 1, 1),
            halign='left',
            valign='middle',
            size_hint_x=None,
            width=80,
        )

        chip = Label(
            text=msg_type.upper(),
            font_size=11,
            bold=True,
            color=text_color,
            size_hint=(None, None),
            height=20,
            width=80,
            halign="center",
            valign="middle",
            text_size=(80, 20),
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
            font_size=15,
            halign='left',
            valign='top',
            size_hint_y=None,
            size_hint_x=1,
        )

        def update_wrap(*args):
            if container.width > 0:
                msg_label.text_size = (container.width - 40, None)  # Subtract padding
        
        msg_label.bind(width=update_wrap)
        msg_label.bind(texture_size=lambda _, size: setattr(msg_label, 'height', size[1]))
        
        # Ensure message follows container width
        container.bind(width=lambda _, w: setattr(msg_label, "width", max(0, w - 40)))
        
        # Divider
        divider = Widget(size_hint_y=None, height=1)
        with divider.canvas.before:
            Color(*line_color)
            divider.rect = Rectangle(pos=divider.pos, size=divider.size)
        divider.bind(pos=lambda *_: setattr(divider.rect, 'pos', divider.pos))
        divider.bind(size=lambda *_: setattr(divider.rect, 'size', divider.size))

        # Add widgets
        container.add_widget(header_row)
        container.add_widget(msg_label)
        container.add_widget(divider)

        return container
    ###########################################################################

    # Add a method to update RSSI from received messages:
    def update_rssi(self, rssi_value):
        self.rssi = f"{rssi_value} dBm"
        self.ids.wifi_label.text = f"Signal: {self.rssi}"
        # Update color based on signal strength
        if rssi_value >= -50:
            self.ids.wifi_label.color = (0.2, 1, 0.2, 1)  # Good
        elif rssi_value >= -70:
            self.ids.wifi_label.color = (1, 1, 0, 1)  # Fair
        else:
            self.ids.wifi_label.color = (1, 0.3, 0.3, 1)  # Poor

    # Fix the update_ui method to handle status updates:
    def update_ui(self, dt):
        # Only update connection status display (don't touch device status)
        self.ids.connection_label.text = f"MQTT: {self.connection_status}"
        if self.connection_status == "Connected":
            self.ids.connection_label.color = (0, 1, 0, 1)
        else:
            self.ids.connection_label.color = (1, 0.3, 0.3, 1)
        
        # Let update_status handle the device/door status display
        # Don't override it here

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

    # Fix the handle_event method to properly parse and display messages:
    def handle_event(self, event_msg: str, msg_type="event"):
        now = datetime.now()

        # Always update status / heartbeat timers
        self.update_status(event_msg)

        # 🚫 Do NOT show heartbeat in notifications
        if self.is_heartbeat_message(event_msg):
            return
    
        last_time = self.last_notifications.get(event_msg)
        if last_time and (now - last_time) < timedelta(minutes=1):
            self.update_notification_time(event_msg)
            return

        self.last_notifications[event_msg] = now

        # Parse the event message for status updates
        if "State: LOCKED" in event_msg:
            self.door_status = "Closed"
        elif "State: UNLOCKED" in event_msg:
            self.door_status = "Open"
        elif "ALERT" in event_msg:
            self.door_status = "Unknown"

        # Clean the message before displaying
        cleaned_message = re.sub(r"^\s*\d{1,2}:\d{2}(:\d{2})?\s*", "", event_msg).strip()
        
        self.add_notification(cleaned_message, msg_type=msg_type)
        
        # Refresh status display and heartbeat
        self.update_status(event_msg)  # Add this line

    def update_notification_time(self, message):
        for container in self.ids.notification_list.children:
            for widget in container.children:
                if isinstance(widget, Label) and "[b]" in widget.text:
                    widget.text = f"[b]{datetime.now().strftime('%H:%M:%S')}[/b]"
                    return

    # In the DashboardScreen class, fix the update_status method:
    def update_status(self, message):
        self.start_heartbeat_timer()
        
        # Update rssi if present in message
        if "RSSI:" in message:
            try:
                rssi_val = int(message.split("RSSI:")[-1].strip().split()[0])
                self.update_rssi(rssi_val)
            except (ValueError, IndexError):
                pass  # Ignore if parsing fails
        
        # Always show device as online when we receive a status message
        if self.connection_status == "Connected":
            if self.door_status != "N/A":
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
        # 🚫 Never store or show heartbeat messages
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

    # ---------------- Additional UI features -----------------

    def open_menu(self, btn):
        if self.menu_open:
            self.dropdown.dismiss()
            self.menu_open = False
            return
        self.dropdown = DropDown(auto_dismiss=True)
        btn_profile = Button(text="Profile", size_hint_y=None, height=44,
                             background_normal='', background_color=(0.2,0.6,0.9,1),
                             color=(1,1,1,1))
        btn_profile.bind(on_release=lambda _: self.show_profile())
        btn_logout = Button(text="Logout", size_hint_y=None, height=44,
                            background_normal='', background_color=(0.9,0.3,0.3,1),
                            color=(1,1,1,1))
        btn_logout.bind(on_release=lambda _: self.logout())
        self.dropdown.add_widget(btn_profile)
        self.dropdown.add_widget(btn_logout)
        self.dropdown.open(btn)
        self.menu_open = True
        self.dropdown.bind(on_dismiss=lambda *_: setattr(self,'menu_open',False))

    def show_profile(self):
        self.manager.app.toast("Profile: Admin", color=(0.6,0.9,1,1))
        self.dropdown.dismiss()

    def logout(self):
        self.dropdown.dismiss()
        self.manager.app.toast("Logged out successfully", color=(1,0.6,0.6,1))
        self.manager.current = "login"

