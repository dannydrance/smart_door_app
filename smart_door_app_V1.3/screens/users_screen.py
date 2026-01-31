# screens/users_screen.py - User Management
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.app import App
from kivy.metrics import dp, sp

class UsersScreen(Screen):
    users = ListProperty([])
    registration_state = StringProperty("")  # none, waiting_rfid, waiting_pin, waiting_fp
    temp_user_name = StringProperty("")
    temp_user_rfid = StringProperty("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mqtt_event = None
    
    def on_enter(self):
        """Called when screen is entered"""
        self.refresh_users()
        self.mqtt_event = Clock.schedule_interval(self.listen_mqtt, 0.5)
    
    def on_leave(self):
        """Called when screen is left"""
        if self.mqtt_event:
            self.mqtt_event.cancel()
    
    def refresh_users(self):
        """Request user list from ESP32"""
        app = self.manager.app
        if app.mqtt.is_online():
            app.mqtt.publish("door/command", "LIST_USERS")
            self.ids.feedback.text = "⏳ Loading users..."
        else:
            self.ids.feedback.text = "🚫 Offline - cannot refresh"
    
    def listen_mqtt(self, dt):
        """Listen for MQTT messages"""
        app = self.manager.app
        while True:
            msg = app.mqtt.get_message()
            if not msg:
                break
            topic, payload = msg
            self.handle_mqtt_message(payload)
    
    def handle_mqtt_message(self, payload):
        """Handle incoming MQTT messages"""
        app = self.manager.app
        
        # User list response
        if payload.startswith("=== REGISTERED USERS ==="):
            self.parse_user_list(payload)
        
        # Registration flow
        elif payload.startswith("Registration started for:"):
            self.registration_state = "waiting_rfid"
            self.ids.feedback.text = "👆 Step 1: Scan RFID card on reader..."
            app.toast("Scan RFID card now", color=(0.6,0.9,1,1))
        
        elif "RFID captured:" in payload and self.registration_state == "waiting_rfid":
            # Extract RFID from message
            lines = payload.split("\n")
            for line in lines:
                if "RFID captured:" in line:
                    self.temp_user_rfid = line.split(":")[-1].strip()
                    break
            self.registration_state = "waiting_pin"
            self.show_pin_dialog()
        
        elif payload.startswith("PIN set:") and self.registration_state == "waiting_pin":
            self.registration_state = "waiting_fp"
            self.ids.feedback.text = "👆 Step 3: Place finger on sensor..."
            app.toast("Enroll fingerprint now", color=(0.6,0.9,1,1))
        
        elif "First fingerprint captured" in payload:
            self.ids.feedback.text = "👆 Remove finger, then place again..."
            app.toast("Place same finger again", color=(0.6,0.9,1,1))
        
        elif payload.startswith("✅ USER REGISTERED"):
            self.registration_state = "none"
            self.ids.feedback.text = "✅ User registered successfully!"
            app.toast("Registration complete!", color=(0.4,1,0.4,1))
            # Add to local database
            self.save_user_to_db(payload)
            Clock.schedule_once(lambda dt: self.refresh_users(), 1)
        
        elif "Enrollment failed" in payload or "ERROR:" in payload:
            self.registration_state = "none"
            self.ids.feedback.text = "❌ " + payload
            app.toast(payload, color=(1,0.3,0.3,1))
        
        # User deletion
        elif payload.startswith("User deleted:"):
            self.ids.feedback.text = payload
            app.toast(payload)
            Clock.schedule_once(lambda dt: self.refresh_users(), 0.5)
        
        # Clear all users
        elif "All users cleared" in payload:
            self.ids.feedback.text = "🗑️ All users cleared!"
            app.toast("All users deleted", color=(1,0.6,0.2,1))
            Clock.schedule_once(lambda dt: self.refresh_users(), 0.5)
        
        else:
            self.ids.feedback.text = payload
    
    def parse_user_list(self, payload):
        """Parse user list from ESP32"""
        lines = payload.split("\n")
        users = []
        
        current_user = {}
        for line in lines:
            line = line.strip()
            
            # Skip header and total lines
            if not line or "===" in line or "Total:" in line:
                continue
            
            if line and line[0].isdigit() and ". " in line:
                # New user entry - save previous user if exists
                if current_user and "name" in current_user:
                    users.append(current_user)
                name = line.split(". ", 1)[1]
                current_user = {"name": name}
            
            elif "RFID:" in line and current_user:
                rfid = line.split("RFID:")[-1].strip()
                current_user["rfid"] = rfid
            elif "FP ID:" in line and current_user:
                fp_id = line.split("FP ID:")[-1].strip()
                current_user["fp_id"] = fp_id
        
        # Don't forget the last user
        if current_user and "name" in current_user:
            users.append(current_user)
        
        self.users = users
        print(f"📋 Parsed {len(users)} users from ESP32")
        for user in users:
            print(f"  - {user}")
        
        self.update_user_list_ui()
    
    def update_user_list_ui(self):
        """Update the user list display"""
        layout = self.ids.user_list
        layout.clear_widgets()
        
        if not self.users:
            empty_label = Label(
                text="No users registered yet.\nTap 'Register New User' to add one.",
                color=(0.7, 0.7, 0.7, 1),
                font_size=sp(14),
                halign="center",
                valign="middle"
            )
            empty_label.bind(size=lambda *args: setattr(empty_label, 'text_size', empty_label.size))
            layout.add_widget(empty_label)
            self.ids.feedback.text = "No users found"
            return
        
        for user in self.users:
            card = self.build_user_card(user)
            layout.add_widget(card)
        
        self.ids.feedback.text = f"📋 {len(self.users)} user(s) registered"
    
    def build_user_card(self, user):
        """Build a card widget for a user"""
        container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(150),
            padding=[dp(12), dp(10)],
            spacing=dp(8)
        )
        
        # Background
        from kivy.graphics import Color, RoundedRectangle
        with container.canvas.before:
            Color(0.18, 0.22, 0.28, 1)
            container.bg = RoundedRectangle(pos=container.pos, size=container.size, radius=[dp(8)])
        container.bind(
            pos=lambda *_: setattr(container.bg, 'pos', container.pos),
            size=lambda *_: setattr(container.bg, 'size', container.size)
        )
        
        # User name
        name_label = Label(
            text=f"👤 {user.get('name', 'Unknown')}",
            font_size=sp(16),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(25),
            halign='left',
            valign='middle'
        )
        name_label.bind(size=lambda *_: setattr(name_label, 'text_size', (name_label.width, None)))
        
        # Info row
        info_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(10))
        
        rfid_label = Label(
            text=f"📇 {user.get('rfid', 'N/A')}",
            font_size=sp(12),
            color=(0.7, 0.9, 1, 1),
            halign='left',
            valign='middle'
        )
        rfid_label.bind(size=lambda *_: setattr(rfid_label, 'text_size', (rfid_label.width, None)))
        
        fp_label = Label(
            text=f"👆 FP:{user.get('fp_id', '?')}",
            font_size=sp(12),
            color=(0.7, 1, 0.7, 1),
            halign='right',
            valign='middle'
        )
        fp_label.bind(size=lambda *_: setattr(fp_label, 'text_size', (fp_label.width, None)))
        
        info_box.add_widget(rfid_label)
        info_box.add_widget(fp_label)
        
        # Button row
        btn_row = BoxLayout(size_hint_y=None, height=dp(35), spacing=dp(8))
        
        btn_edit = Button(
            text="✏️ Edit",
            background_normal='',
            background_color=(0.2, 0.6, 0.9, 1),
            color=(1, 1, 1, 1),
            font_size=sp(12),
            bold=True
        )
        btn_edit.bind(on_release=lambda btn: self.show_edit_dialog(user))
        
        btn_delete = Button(
            text="🗑️ Delete",
            background_normal='',
            background_color=(0.9, 0.3, 0.2, 1),
            color=(1, 1, 1, 1),
            font_size=sp(12),
            bold=True
        )
        btn_delete.bind(on_release=lambda btn: self.confirm_delete_user(user))
        
        btn_row.add_widget(btn_edit)
        btn_row.add_widget(btn_delete)
        
        container.add_widget(name_label)
        container.add_widget(info_box)
        container.add_widget(btn_row)
        
        return container
    
    def show_register_dialog(self):
        """Show dialog to register new user"""
        app = self.manager.app
        
        if not app.mqtt.is_online():
            app.toast("🚫 Offline - cannot register", color=(1,0.3,0.3,1))
            return
        
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        box.add_widget(Label(
            text="Enter User Name",
            font_size=sp(16),
            bold=True,
            size_hint_y=None,
            height=dp(30)
        ))
        
        name_input = TextInput(
            hint_text="e.g., John Doe",
            multiline=False,
            font_size=sp(14),
            size_hint_y=None,
            height=dp(45)
        )
        box.add_widget(name_input)
        
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_start = Button(
            text="Start Registration",
            background_color=(0.2, 0.7, 0.4, 1),
            font_size=sp(13),
            bold=True
        )
        btn_cancel = Button(
            text="Cancel",
            background_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(13)
        )
        btn_row.add_widget(btn_start)
        btn_row.add_widget(btn_cancel)
        box.add_widget(btn_row)
        
        popup = Popup(
            title="Register New User",
            content=box,
            size_hint=(0.85, 0.4),
            auto_dismiss=False
        )
        
        def start_registration(_):
            name = name_input.text.strip()
            if not name:
                app.toast("⚠ Please enter a name", color=(1,0.7,0.2,1))
                return
            
            self.temp_user_name = name
            app.mqtt.publish("door/command", f"REGISTER_USER:{name}")
            app.toast(f"Starting registration for {name}...")
            popup.dismiss()
        
        btn_start.bind(on_release=start_registration)
        btn_cancel.bind(on_release=lambda _: popup.dismiss())
        
        popup.open()
    
    def show_pin_dialog(self):
        """Show dialog to enter PIN during registration"""
        app = self.manager.app
        
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        box.add_widget(Label(
            text=f"Set PIN for {self.temp_user_name}",
            font_size=sp(16),
            bold=True,
            size_hint_y=None,
            height=dp(30)
        ))
        
        box.add_widget(Label(
            text=f"RFID: {self.temp_user_rfid}",
            font_size=sp(12),
            color=(0.7, 0.9, 1, 1),
            size_hint_y=None,
            height=dp(25)
        ))
        
        pin_input = TextInput(
            hint_text="Enter 4-digit PIN",
            multiline=False,
            input_filter='int',
            password=True,
            font_size=sp(14),
            size_hint_y=None,
            height=dp(45)
        )
        box.add_widget(pin_input)
        
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_set = Button(
            text="Set PIN",
            background_color=(0.2, 0.7, 0.4, 1),
            font_size=sp(13),
            bold=True
        )
        btn_cancel = Button(
            text="Cancel",
            background_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(13)
        )
        btn_row.add_widget(btn_set)
        btn_row.add_widget(btn_cancel)
        box.add_widget(btn_row)
        
        popup = Popup(
            title="Step 2: Set PIN",
            content=box,
            size_hint=(0.85, 0.45),
            auto_dismiss=False
        )
        
        def set_pin(_):
            pin = pin_input.text.strip()
            if len(pin) != 4:
                app.toast("⚠ PIN must be 4 digits", color=(1,0.7,0.2,1))
                return
            
            app.mqtt.publish("door/command", f"SET_REG_PIN:{pin}")
            app.toast("PIN set! Now enroll fingerprint...")
            popup.dismiss()
        
        def cancel_registration(_):
            self.registration_state = "none"
            popup.dismiss()
            app.toast("Registration cancelled", color=(1,0.6,0.2,1))
        
        btn_set.bind(on_release=set_pin)
        btn_cancel.bind(on_release=cancel_registration)
        
        popup.open()
    
    def show_edit_dialog(self, user):
        """Show dialog to edit user credentials"""
        app = self.manager.app
        
        if not app.mqtt.is_online():
            app.toast("🚫 Offline - cannot edit", color=(1,0.3,0.3,1))
            return
        
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        box.add_widget(Label(
            text=f"Edit User: {user.get('name', 'Unknown')}",
            font_size=sp(16),
            bold=True,
            size_hint_y=None,
            height=dp(30)
        ))
        
        box.add_widget(Label(
            text="Select what to update:",
            font_size=sp(13),
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=dp(25)
        ))
        
        # Button to change PIN
        btn_change_pin = Button(
            text="🔐 Change PIN",
            size_hint_y=None,
            height=dp(45),
            background_color=(0.2, 0.6, 0.9, 1),
            font_size=sp(14),
            bold=True
        )
        
        # Button to re-enroll fingerprint
        btn_change_fp = Button(
            text="👆 Re-enroll Fingerprint",
            size_hint_y=None,
            height=dp(45),
            background_color=(0.6, 0.3, 0.9, 1),
            font_size=sp(14),
            bold=True
        )
        
        # Button to change RFID (needs new card)
        btn_change_rfid = Button(
            text="📇 Change RFID Card",
            size_hint_y=None,
            height=dp(45),
            background_color=(0.2, 0.7, 0.4, 1),
            font_size=sp(14),
            bold=True
        )
        
        btn_cancel = Button(
            text="Cancel",
            size_hint_y=None,
            height=dp(45),
            background_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(13)
        )
        
        box.add_widget(btn_change_pin)
        box.add_widget(btn_change_fp)
        box.add_widget(btn_change_rfid)
        box.add_widget(btn_cancel)
        
        popup = Popup(
            title="Edit Credentials",
            content=box,
            size_hint=(0.85, 0.7),
            auto_dismiss=False
        )
        
        def change_pin(_):
            popup.dismiss()
            self.show_change_pin_dialog(user)
        
        def change_fp(_):
            popup.dismiss()
            self.show_change_fp_dialog(user)
        
        def change_rfid(_):
            popup.dismiss()
            self.show_change_rfid_dialog(user)
        
        btn_change_pin.bind(on_release=change_pin)
        btn_change_fp.bind(on_release=change_fp)
        btn_change_rfid.bind(on_release=change_rfid)
        btn_cancel.bind(on_release=lambda _: popup.dismiss())
        
        popup.open()
    
    def show_change_pin_dialog(self, user):
        """Dialog to change user's PIN"""
        app = self.manager.app
        
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        box.add_widget(Label(
            text=f"Change PIN for {user.get('name', 'Unknown')}",
            font_size=sp(14),
            bold=True,
            size_hint_y=None,
            height=dp(30)
        ))
        
        new_pin_input = TextInput(
            hint_text="Enter new 4-digit PIN",
            multiline=False,
            input_filter='int',
            password=True,
            font_size=sp(14),
            size_hint_y=None,
            height=dp(45)
        )
        box.add_widget(new_pin_input)
        
        confirm_pin_input = TextInput(
            hint_text="Confirm new PIN",
            multiline=False,
            input_filter='int',
            password=True,
            font_size=sp(14),
            size_hint_y=None,
            height=dp(45)
        )
        box.add_widget(confirm_pin_input)
        
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_save = Button(text="Save", background_color=(0.2, 0.7, 0.4, 1), font_size=sp(13), bold=True)
        btn_cancel = Button(text="Cancel", background_color=(0.5, 0.5, 0.5, 1), font_size=sp(13))
        btn_row.add_widget(btn_save)
        btn_row.add_widget(btn_cancel)
        box.add_widget(btn_row)
        
        popup = Popup(title="Change PIN", content=box, size_hint=(0.85, 0.5), auto_dismiss=False)
        
        def save_pin(_):
            new_pin = new_pin_input.text.strip()
            confirm = confirm_pin_input.text.strip()
            
            if len(new_pin) != 4:
                app.toast("⚠ PIN must be 4 digits", color=(1,0.7,0.2,1))
                return
            if new_pin != confirm:
                app.toast("⚠ PINs don't match", color=(1,0.7,0.2,1))
                return
            
            # Send command to update PIN (will need ESP32 support)
            rfid = user.get('rfid', '')
            app.mqtt.publish("door/command", f"UPDATE_PIN:{rfid}:{new_pin}")
            app.toast(f"Updating PIN for {user.get('name')}...")
            popup.dismiss()
        
        btn_save.bind(on_release=save_pin)
        btn_cancel.bind(on_release=lambda _: popup.dismiss())
        popup.open()
    
    def show_change_fp_dialog(self, user):
        """Dialog to re-enroll fingerprint"""
        app = self.manager.app
        
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        box.add_widget(Label(
            text=f"Re-enroll fingerprint for\n{user.get('name', 'Unknown')}",
            font_size=sp(14),
            bold=True,
            size_hint_y=None,
            height=dp(50)
        ))
        
        box.add_widget(Label(
            text="This will:\n1. Delete old fingerprint\n2. Enroll new fingerprint\n3. Keep same Fingerprint ID",
            font_size=sp(12),
            color=(1, 0.8, 0.2, 1),
            size_hint_y=None,
            height=dp(70)
        ))
        
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_start = Button(text="Start Enrollment", background_color=(0.6, 0.3, 0.9, 1), font_size=sp(13), bold=True)
        btn_cancel = Button(text="Cancel", background_color=(0.5, 0.5, 0.5, 1), font_size=sp(13))
        btn_row.add_widget(btn_start)
        btn_row.add_widget(btn_cancel)
        box.add_widget(btn_row)
        
        popup = Popup(title="Re-enroll Fingerprint", content=box, size_hint=(0.85, 0.5), auto_dismiss=False)
        
        def start_reenroll(_):
            rfid = user.get('rfid', '')
            app.mqtt.publish("door/command", f"REENROLL_FP:{rfid}")
            app.toast(f"Place finger on sensor to re-enroll...")
            popup.dismiss()
        
        btn_start.bind(on_release=start_reenroll)
        btn_cancel.bind(on_release=lambda _: popup.dismiss())
        popup.open()
    
    def show_change_rfid_dialog(self, user):
        """Dialog to change RFID card"""
        app = self.manager.app
        
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        box.add_widget(Label(
            text=f"Change RFID card for\n{user.get('name', 'Unknown')}",
            font_size=sp(14),
            bold=True,
            size_hint_y=None,
            height=dp(50)
        ))
        
        box.add_widget(Label(
            text=f"Current RFID: {user.get('rfid', 'N/A')}",
            font_size=sp(12),
            color=(0.7, 0.9, 1, 1),
            size_hint_y=None,
            height=dp(25)
        ))
        
        box.add_widget(Label(
            text="Scan new RFID card on reader...",
            font_size=sp(12),
            color=(1, 0.8, 0.2, 1),
            size_hint_y=None,
            height=dp(50)
        ))
        
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_start = Button(text="Start Scan", background_color=(0.2, 0.7, 0.4, 1), font_size=sp(13), bold=True)
        btn_cancel = Button(text="Cancel", background_color=(0.5, 0.5, 0.5, 1), font_size=sp(13))
        btn_row.add_widget(btn_start)
        btn_row.add_widget(btn_cancel)
        box.add_widget(btn_row)
        
        popup = Popup(title="Change RFID Card", content=box, size_hint=(0.85, 0.55), auto_dismiss=False)
        
        def start_scan(_):
            old_rfid = user.get('rfid', '')
            app.mqtt.publish("door/command", f"CHANGE_RFID:{old_rfid}")
            app.toast("Scan new RFID card now...")
            popup.dismiss()
        
        btn_start.bind(on_release=start_scan)
        btn_cancel.bind(on_release=lambda _: popup.dismiss())
        popup.open()
    
    def confirm_delete_user(self, user):
        """Show confirmation dialog before deleting user"""
        app = self.manager.app
        
        if not app.mqtt.is_online():
            app.toast("🚫 Offline - cannot delete", color=(1,0.3,0.3,1))
            return
        
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        box.add_widget(Label(
            text=f"Delete user '{user.get('name', 'Unknown')}'?",
            font_size=sp(14),
            size_hint_y=None,
            height=dp(40)
        ))
        
        box.add_widget(Label(
            text="This will remove:\n• RFID card\n• Fingerprint\n• PIN code",
            font_size=sp(12),
            color=(1, 0.7, 0.2, 1),
            size_hint_y=None,
            height=dp(60)
        ))
        
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_yes = Button(
            text="Yes, Delete",
            background_color=(0.9, 0.2, 0.2, 1),
            font_size=sp(13),
            bold=True
        )
        btn_no = Button(
            text="Cancel",
            background_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(13)
        )
        btn_row.add_widget(btn_yes)
        btn_row.add_widget(btn_no)
        box.add_widget(btn_row)
        
        popup = Popup(
            title="Confirm Deletion",
            content=box,
            size_hint=(0.85, 0.5),
            auto_dismiss=False
        )
        
        def delete_user(_):
            rfid = user.get('rfid', '')
            if rfid:
                app.mqtt.publish("door/command", f"DELETE_USER:{rfid}")
                app.toast(f"Deleting {user.get('name')}...")
                # Delete from local DB
                app.db.delete_door_user(rfid)
            popup.dismiss()
        
        btn_yes.bind(on_release=delete_user)
        btn_no.bind(on_release=lambda _: popup.dismiss())
        
        popup.open()
    
    def clear_all_users(self):
        """Clear all users with confirmation"""
        app = self.manager.app
        
        if not app.mqtt.is_online():
            app.toast("🚫 Offline - cannot clear users", color=(1,0.3,0.3,1))
            return
        
        box = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        box.add_widget(Label(
            text="⚠️ Delete ALL users?",
            font_size=sp(16),
            bold=True,
            color=(1, 0.3, 0.3, 1),
            size_hint_y=None,
            height=dp(30)
        ))
        
        box.add_widget(Label(
            text="This will permanently remove:\n• All RFID cards\n• All fingerprints\n• All PIN codes\n\nThis action cannot be undone!",
            font_size=sp(12),
            color=(1, 0.7, 0.2, 1),
            size_hint_y=None,
            height=dp(90)
        ))
        
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_yes = Button(
            text="Yes, Clear All",
            background_color=(0.9, 0.2, 0.2, 1),
            font_size=sp(13),
            bold=True
        )
        btn_no = Button(
            text="Cancel",
            background_color=(0.5, 0.5, 0.5, 1),
            font_size=sp(13)
        )
        btn_row.add_widget(btn_yes)
        btn_row.add_widget(btn_no)
        box.add_widget(btn_row)
        
        popup = Popup(
            title="⚠️ Confirm Clear All",
            content=box,
            size_hint=(0.85, 0.6),
            auto_dismiss=False
        )
        
        def confirm_clear(_):
            app.mqtt.publish("door/command", "CLEAR_ALL_USERS")
            app.toast("Clearing all users...")
            popup.dismiss()
        
        btn_yes.bind(on_release=confirm_clear)
        btn_no.bind(on_release=lambda _: popup.dismiss())
        
        popup.open()
    
    def save_user_to_db(self, payload):
        """Save user to local database after registration"""
        app = self.manager.app
        
        # Parse registration completion message
        name = self.temp_user_name
        rfid = self.temp_user_rfid
        fp_id = None
        
        lines = payload.split("\n")
        for line in lines:
            if "Fingerprint ID:" in line:
                try:
                    fp_id = int(line.split(":")[-1].strip())
                except:
                    pass
        
        # Add to database (PIN is already set during registration)
        if name and rfid:
            app.db.add_door_user(name, rfid, "****", fp_id)
    
    def back_to_dashboard(self):
        """Navigate back to dashboard"""
        self.manager.current = "dashboard"