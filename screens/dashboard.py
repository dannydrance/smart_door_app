# screens/dashboard.py
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.dropdown import DropDown
from kivy.uix.button import Button
from kivy.properties import StringProperty

class DashboardScreen(Screen):
    door_status = "N/A"
    rssi = StringProperty("N/A")  # <-- Add this
    connection_status = StringProperty("Disconnected")
    STATUS_COLORS = {
        "Open": (0,1,0,1),
        "Closed": (1,0,0,1),
        "Unknown": (1,1,0,1)
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_interval(self.update_ui, 1)
        self.start_time = Clock.get_boottime()
        self.menu_open = False
        self.heartbeat_event = None
        self.heartbeat_timeout = 100  # seconds
        self.start_heartbeat_timer()

    def update_ui(self, dt):
        elapsed = int(Clock.get_boottime() - self.start_time)
        mins, secs = divmod(elapsed, 60)
        #self.ids.uptime_label.text = f"Uptime: {mins} min {secs} sec"
       # if 'uptime' in self.ids:
        #    self.ids.uptime.text = f"Uptime: {mins} min {secs} sec"

    def start_heartbeat_timer(self):
        """Start or restart heartbeat timeout timer."""
        if self.heartbeat_event:
            self.heartbeat_event.cancel()
        self.heartbeat_event = Clock.schedule_once(self.mark_offline, self.heartbeat_timeout)

    def mark_offline(self, dt):
        """Called when heartbeat timeout expires."""
        self.ids.status_label.text  = "Device Offline"
        self.ids.status_label.color = (1, 0.3, 0.3, 1)

    def update_mqtt_status(self, connected: bool):
        """Update MQTT connection status label."""
        if connected:
            self.connection_status = "Connected"
            self.ids.connection_label.color = (0, 1, 0, 1)
        else:
            self.connection_status = "Disconnected"
            self.ids.connection_label.color = (1, 0.3, 0.3, 1)
    
    def send_command(self, cmd: str):
        app = self.manager.app
        if app.mqtt.is_online():
            app.mqtt.publish("door/command", cmd)
            app.toast(f"📤 Sent command: {cmd}")
            self.ids.notification_list.text = f"[b]Status:[/b] Sent {cmd}"
        else:
            app.toast("Offline – cannot send command", color=(1,0.3,0.3,1))
            self.ids.status.text = "[b]Status:[/b] Offline"

    def handle_event(self, event_msg: str):
        """Update door status, status label, and notifications."""
        if "UNLOCKED" in event_msg:
            self.door_status = "Open"
        elif "LOCKED" in event_msg:
            self.door_status = "Closed"

        # Update labels
        # self.ids.door_status_label.text = f"Door Status: {self.door_status}"
        # self.ids.door_status_label.color = self.STATUS_COLORS[self.door_status]
        # self.ids.status.text = f"[b]Event:[/b] {event_msg}"

        self.add_notification(event_msg)
        # Add notification
        '''label = self.Label(
            text=event_msg,
            size_hint_y=None,
            height=30,
            color=self.STATUS_COLORS[self.door_status]
        )
        self.ids.notification_list.add_widget(label)
        self.ids.notification_list.parent.scroll_y = 0'''

    def update_status(self, message):
        """
        Handles messages from door/status topic.
        """
        msg = message.strip()
        print(f"[Dashboard] Status update: {msg}")

        self.start_heartbeat_timer()
        
        if "Online" in msg:
            self.ids.status_label.text = "Device Online"
            self.ids.status_label.color = (0, 1, 0, 1)
        if "LOCKED" in msg:
            self.ids.status_label.text  = "Device Online"
            self.ids.status_label.color = (0, 1, 0, 1)

            #self.ids.door_state.text = "Door Locked"
            #self.ids.door_state.color = (0.2, 0.9, 0.2, 1)
        if "UNLOCKED" in msg:
            self.ids.status_label.text  = "Device Online"
            self.ids.status_label.color = (0, 1, 0, 1)

            #self.ids.door_state.text = "Door Unlocked"
            #self.ids.door_state.color= (0.9, 0.3, 0.3, 1)
        if "WiFi RSSI" in msg:
            # Parse extra info if it's multiline
            print('xxxxxgggggggggggggggggggggggggggggggggggggggggggggggg',msg)
            lines = msg.splitlines()
            info = {}
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    info[key.strip()] = val.strip()
                    print('hhhh',info)

            # Now update labels safely
            if "WiFi RSSI" in info:
                self.ids.wifi_label.text = f"{info['WiFi RSSI']}"
            '''if "Uptime" in info:
                self.ids.uptime_label.text = f"{info['Uptime']}"
            if "State" in info:
                self.ids.door_state.text = f"{info['State']}"'''
    
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.widget import Widget
    from kivy.graphics import Color, Rectangle
    from datetime import datetime

    def add_notification(self, message):
        """
        Add a formatted notification card to the notification list.
        Replaces text-appending behavior with proper scrollable layout.
        """
        print(f"[Dashboard] Notification: {message}")

        # Save in database
        db = self.manager.app.db  # assuming your App instance has `db = Database()`
        db.add_notification(message, self.door_status)

        # Create container for each notification
        container = self.BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=70,
            padding=[10, 5]
        )

        # Background card styling
        with container.canvas.before:
            self.Color(0.18, 0.22, 0.28, 1)  # dark gray-blue background
            container.bg_rect = self.Rectangle(pos=container.pos, size=container.size)
            container.bind(pos=lambda *x: setattr(container.bg_rect, 'pos', container.pos))
            container.bind(size=lambda *x: setattr(container.bg_rect, 'size', container.size))

        # Timestamp
        timestamp = self.datetime.now().strftime("%H:%M:%S")

        # Label for notification text
        msg_label = self.Label(
            text=f"[b]{timestamp}[/b]  {message}",
            markup=True,
            color=(1, 1, 1, 1),
            halign='left',
            valign='middle',
            text_size=(self.width - 40, None),  # wrap text if long
            size_hint_y=None,
            height=30,
            font_size=14
        )

        # Divider line for separation
        divider = self.Widget(size_hint_y=None, height=1)
        with divider.canvas.before:
            self.Color(0.5, 0.5, 0.5, 0.3)
            divider.line = self.Rectangle(pos=divider.pos, size=divider.size)
            divider.bind(pos=lambda *x: setattr(divider.line, 'pos', divider.pos))
            divider.bind(size=lambda *x: setattr(divider.line, 'size', divider.size))

        container.add_widget(msg_label)
        container.add_widget(divider)

        # Add to the top of the list (newest first)
        self.ids.notification_list.add_widget(container, index=0)

        # Optional: Limit number of notifications
        if len(self.ids.notification_list.children) > 50:
            # Remove oldest (bottom-most) item
            self.ids.notification_list.remove_widget(self.ids.notification_list.children[-1])

    from datetime import datetime
    def on_pre_enter(self, *args):
        """Load last 50 notifications when entering dashboard."""
        db = self.manager.app.db
        notifications = db.get_notifications(limit=50)

        # Clear existing notifications
        self.ids.notification_list.clear_widgets()

        for msg, status, ts in notifications:
            # Try to parse timestamp if it's a string
            if isinstance(ts, str):
                try:
                    # Adjust format if your DB uses a different one
                    ts_obj = self.datetime.fromisoformat(ts)
                except ValueError:
                    ts_obj = self.datetime.now()  # fallback if parsing fails
            else:
                ts_obj = ts or self.datetime.now()

            timestamp = ts_obj.strftime("%H:%M:%S")

            # Create container for each notification
            container = self.BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=70,
                padding=[10, 5]
            )

            # Background card styling
            with container.canvas.before:
                self.Color(0.18, 0.22, 0.28, 1)
                container.bg_rect = self.Rectangle(pos=container.pos, size=container.size)
            container.bind(pos=lambda *x: setattr(container.bg_rect, 'pos', container.pos))
            container.bind(size=lambda *x: setattr(container.bg_rect, 'size', container.size))

            # Label for notification text
            msg_label = self.Label(
                text=f"[b]{timestamp}[/b]  {msg}",
                markup=True,
                color=(1, 1, 1, 1),
                halign='left',
                valign='middle',
            )

            # Divider
            divider = self.Widget(size_hint_y=None, height=1)
            with divider.canvas.before:
                self.Color(0.5, 0.5, 0.5, 0.3)
                divider.line = self.Rectangle(pos=divider.pos, size=divider.size)
            divider.bind(pos=lambda *x: setattr(divider.line, 'pos', divider.pos))
            divider.bind(size=lambda *x: setattr(divider.line, 'size', divider.size))

            container.add_widget(msg_label)
            container.add_widget(divider)

            # Add newest first
            self.ids.notification_list.add_widget(container, index=0)

        # Keep at most 50
        if len(self.ids.notification_list.children) > 50:
            for _ in range(len(self.ids.notification_list.children) - 50):
                self.ids.notification_list.remove_widget(self.ids.notification_list.children[-1])

    def clear_notifications(self):
        """
        Remove all notifications from the UI and database.
        """
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button

        def confirm_clear(instance):
            # Clear from database
            db = self.manager.app.db
            db.clear_notifications()  # you must implement this in your Database class

            # Clear from UI
            self.ids.notification_list.clear_widgets()
            popup.dismiss()

        # Confirmation popup
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Label(text="Are you sure you want to clear all notifications?"))

        btns = BoxLayout(size_hint_y=None, height=40, spacing=10)
        yes_btn = Button(text="Yes", background_color=(0.8, 0.2, 0.2, 1))
        no_btn = Button(text="Cancel", background_color=(0.3, 0.3, 0.3, 1))
        btns.add_widget(yes_btn)
        btns.add_widget(no_btn)
        layout.add_widget(btns)

        popup = Popup(title="Confirm Clear",
                    content=layout,
                    size_hint=(None, None),
                    size=(400, 200),
                    auto_dismiss=False)
        
        yes_btn.bind(on_release=confirm_clear)
        no_btn.bind(on_release=lambda *x: popup.dismiss())
        popup.open()

    # ===========================
    # Dropdown menu for profile
    # ===========================
    def open_menu(self, btn):
        if self.menu_open:
            self.dropdown.dismiss()
            self.menu_open = False
            return

        self.dropdown = DropDown(auto_dismiss=True)

        # Profile option
        btn_profile = Button(
            text="Profile",
            size_hint_y=None,
            height=44,
            background_normal='',
            background_color=(0.2, 0.6, 0.9, 1),
            color=(1,1,1,1)
        )
        btn_profile.bind(on_release=lambda _: self.show_profile())

        # Logout option
        btn_logout = Button(
            text="Logout",
            size_hint_y=None,
            height=44,
            background_normal='',
            background_color=(0.9, 0.3, 0.3, 1),
            color=(1,1,1,1)
        )
        btn_logout.bind(on_release=lambda _: self.logout())

        self.dropdown.add_widget(btn_profile)
        self.dropdown.add_widget(btn_logout)
        self.dropdown.open(btn)
        self.menu_open = True
        self.dropdown.bind(on_dismiss=lambda _: setattr(self, 'menu_open', False))

    def show_profile(self):
        self.manager.app.toast("Profile: Admin", color=(0.6,0.9,1,1))
        self.dropdown.dismiss()

    def logout(self):
        self.dropdown.dismiss()
        self.manager.app.toast("Logged out successfully", color=(1,0.6,0.6,1))
        self.manager.current = "login"
