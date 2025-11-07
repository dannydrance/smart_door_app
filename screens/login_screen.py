# screens/login_screen.py
from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.clock import Clock

class LoginScreen(Screen):

    def validate_user(self):
        """Authenticate user from SQLite database."""
        username = self.ids.username.text.strip()
        password = self.ids.password.text.strip()

        # Basic validation
        if not username or not password:
            self.ids.error.text = "⚠ Please enter both username and password"
            return

        app = App.get_running_app()
        try:
            # Verify credentials using the database
            user = app.db.verify_user(username, password)

            if user:
                # user = (id, username, password, display_name, email, updated_at)
                app.set_user(username)

                display_name = user[3] or username
                self.ids.error.text = ""

                # Friendly toast message
                app.toast(f"👋 Welcome back, {display_name}!", color=(0.4, 1, 0.4, 1))

                # Transition to dashboard after small delay
                Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'dashboard'), 0.3)
            else:
                self.ids.error.text = "❌ Invalid username or password"
        except Exception as e:
            self.ids.error.text = f"⚠ Login failed: {e}"
            print(f"[Login Error] {e}")
