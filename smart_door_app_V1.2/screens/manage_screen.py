# screens/manage_screen.py (Updated with responsive units)
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.properties import ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.modalview import ModalView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.app import App
from kivy.metrics import dp, sp  # ADDED

class ManageScreen(Screen):
    cards = ListProperty([])

    def open_profile_edit(self):
        """Popup for editing profile"""
        app = App.get_running_app()
        user = app.db.get_user(app.current_user)
        display_name = user[3] if user else ""

        box = BoxLayout(
            orientation='vertical', 
            spacing=dp(10),  # RESPONSIVE
            padding=dp(15)  # RESPONSIVE
        )

        name_input = TextInput(
            text=display_name, 
            hint_text="Display Name", 
            multiline=False,
            font_size=sp(14)  # RESPONSIVE
        )
        pass_input = TextInput(
            hint_text="New Password (optional)", 
            password=True, 
            multiline=False,
            font_size=sp(14)  # RESPONSIVE
        )

        btn_save = Button(
            text="💾 Save", 
            size_hint_y=None, 
            height=dp(45),  # RESPONSIVE
            background_color=(0.2,0.6,0.9,1),
            font_size=sp(14)  # RESPONSIVE
        )
        btn_cancel = Button(
            text="❌ Cancel", 
            size_hint_y=None, 
            height=dp(45),  # RESPONSIVE
            background_color=(0.5,0.5,0.5,1),
            font_size=sp(14)  # RESPONSIVE
        )

        box.add_widget(Label(
            text="Edit Profile", 
            font_size=sp(18),  # RESPONSIVE
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
            padding=dp(20),  # RESPONSIVE
            spacing=dp(15)  # RESPONSIVE
        )
        box.add_widget(Label(
            text="Edit Profile", 
            font_size=sp(20),  # RESPONSIVE
            color=(1,1,1,1)
        ))

        self.display_name_input = TextInput(
            hint_text="Display Name", 
            text=display_name or "", 
            multiline=False,
            font_size=sp(14)  # RESPONSIVE
        )
        self.email_input = TextInput(
            hint_text="Email Address", 
            text=email or "", 
            multiline=False,
            font_size=sp(14)  # RESPONSIVE
        )
        self.new_password_input = TextInput(
            hint_text="New Password (optional)", 
            password=True, 
            multiline=False,
            font_size=sp(14)  # RESPONSIVE
        )
        self.confirm_password_input = TextInput(
            hint_text="Confirm Password", 
            password=True, 
            multiline=False,
            font_size=sp(14)  # RESPONSIVE
        )

        box.add_widget(self.display_name_input)
        box.add_widget(self.email_input)
        box.add_widget(self.new_password_input)
        box.add_widget(self.confirm_password_input)

        btn_row = BoxLayout(
            size_hint_y=None, 
            height=dp(50),  # RESPONSIVE
            spacing=dp(10)  # RESPONSIVE
        )
        btn_save = Button(
            text="Save Changes", 
            background_color=(0.2,0.7,0.4,1), 
            color=(1,1,1,1), 
            bold=True,
            font_size=sp(14)  # RESPONSIVE
        )
        btn_cancel = Button(
            text="Cancel", 
            background_color=(0.5,0.5,0.5,1), 
            color=(1,1,1,1), 
            bold=True,
            font_size=sp(14)  # RESPONSIVE
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

    def handle_event(self, payload):
        app = self.manager.app
        if payload.startswith("Stored cards:"):
            self.parse_card_list(payload)
        elif payload.startswith("Card added:") or payload.startswith("Card removed:"):
            self.ids.feedback.text = payload
            app.toast(payload)
            self.refresh_list()
        elif payload.startswith("PIN updated"):
            self.ids.feedback.text = "🔐 PIN updated!"
            app.toast("PIN changed successfully!")
        elif payload.startswith("ALERT:"):
            self.ids.feedback.text = payload
            app.toast(payload, color=(1,0.3,0.3,1))
        elif payload.startswith("EEPROM reset"):
            self.ids.feedback.text = "⚙️ EEPROM Reset!"
            app.toast("EEPROM reset done!")
        else:
            self.ids.feedback.text = payload

    def on_enter(self):
        self.refresh_list()
        self.mqtt_event = Clock.schedule_interval(self.listen_mqtt, 0.5)
        self.update_ui()

    def on_leave(self):
        if hasattr(self, "mqtt_event"):
            self.mqtt_event.cancel()

    def update_ui(self):
        app = self.manager.app
        online = app.mqtt.is_online()
        self.ids.card_uid.disabled = not online
        self.ids.new_pin.disabled = not online

    def refresh_list(self):
        app = self.manager.app
        if app.mqtt.is_online():
            app.mqtt.publish("door/command", "LIST_RFID")
            self.ids.feedback.text = "⏳ Requesting card list..."
            self.ids.card_list.clear_widgets()
        else:
            self.ids.feedback.text = "🚫 Offline – cannot refresh"

    def listen_mqtt(self, dt):
        app = self.manager.app
        while True:
            msg = app.mqtt.get_message()
            if not msg:
                break
            topic, payload = msg
            self.handle_event(payload)

    def parse_card_list(self, payload):
        lines = payload.splitlines()[1:]
        new_cards = [line.strip() for line in lines if line.strip() and not line.startswith("PIN")]
        self.cards = new_cards
        self.ids.feedback.text = f"📋 {len(new_cards)} cards found."
        self.update_card_list_ui()

    def update_card_list_ui(self):
        layout = self.ids.card_list
        layout.clear_widgets()
        for uid in self.cards:
            row = BoxLayout(
                size_hint_y=None, 
                height=dp(45),  # RESPONSIVE
                spacing=dp(8)  # RESPONSIVE
            )
            row.add_widget(Label(
                text=uid, 
                color=(1,1,1,1),
                font_size=sp(13)  # RESPONSIVE
            ))
            btn_del = Button(
                text="❌ Delete",
                size_hint_x=0.35,
                background_normal='',
                background_color=(0.8,0.2,0.2,1),
                color=(1,1,1,1),
                font_size=sp(12)  # RESPONSIVE
            )
            btn_del.bind(on_release=lambda btn, u=uid: self.remove_card(u))
            row.add_widget(btn_del)
            layout.add_widget(row)
        layout.parent.scroll_y = 1

    def add_card(self):
        uid = self.ids.card_uid.text.strip().upper()
        if not uid:
            self.manager.app.toast("⚠ Enter card UID", color=(1,0.7,0.2,1))
            return
        app = self.manager.app
        if not app.mqtt.is_online():
            app.toast("🚫 Offline – cannot send", color=(1,0.3,0.3,1))
            return
        app.mqtt.publish("door/command", f"ADD_RFID:{uid}")
        app.toast(f"📤 Adding {uid}")
        self.ids.card_uid.text = ""

    def remove_card(self, uid):
        app = self.manager.app
        if not app.mqtt.is_online():
            app.toast("🚫 Offline – cannot remove card", color=(1,0.3,0.3,1))
            return
        app.mqtt.publish("door/command", f"REMOVE_RFID:{uid}")
        app.toast(f"🗑 Removing card {uid}...")

    def change_pin(self):
        pin = self.ids.new_pin.text.strip()
        if len(pin) < 4:
            self.ids.feedback.text = "⚠️ PIN must be ≥ 4 digits."
            return
        app = self.manager.app
        if not app.mqtt.is_online():
            app.toast("🚫 Offline – cannot send", color=(1,0.3,0.3,1))
            return
        app.mqtt.publish("door/command", f"SET_PIN:{pin}")
        app.toast("🔐 Changing PIN...")
        self.ids.new_pin.text = ""

    def back_to_dashboard(self):
        self.manager.current = "dashboard"

    def open_menu(self, btn):
        self.dropdown = DropDown(auto_dismiss=True)

        btn_profile = Button(
            text="Edit Profile",
            size_hint_y=None,
            height=dp(44),  # RESPONSIVE
            background_normal='',
            background_color=(0.2,0.6,0.9,1),
            color=(1,1,1,1),
            font_size=sp(14)  # RESPONSIVE
        )
        btn_profile.bind(on_release=lambda _: self.open_profile_window())

        btn_logout = Button(
            text="Logout",
            size_hint_y=None,
            height=dp(44),  # RESPONSIVE
            background_normal='',
            background_color=(0.9,0.3,0.3,1),
            color=(1,1,1,1),
            font_size=sp(14)  # RESPONSIVE
        )
        btn_logout.bind(on_release=lambda _: self.logout())

        self.dropdown.add_widget(btn_profile)
        self.dropdown.add_widget(btn_logout)
        self.dropdown.open(btn)

    def logout(self):
        self.dropdown.dismiss()
        self.manager.app.toast("Logged out successfully", color=(1,0.6,0.6,1))
        self.manager.current = "login"