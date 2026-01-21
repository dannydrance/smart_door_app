# metrics.py
from kivy.metrics import dp, sp
from kivy.core.window import Window

class ScreenMetrics:
    """Helper class for responsive UI scaling"""
    
    @staticmethod
    def get_scale_factor():
        """Returns a scale factor based on screen width"""
        width = Window.width
        if width >= 1200:  # Large tablets
            return 1.4
        elif width >= 800:  # Medium tablets
            return 1.2
        elif width >= 600:  # Small tablets
            return 1.1
        else:  # Phones
            return 1.0
    
    @staticmethod
    def scaled_sp(size):
        """Scale font size based on screen"""
        return sp(size * ScreenMetrics.get_scale_factor())
    
    @staticmethod
    def scaled_dp(size):
        """Scale dimension based on screen"""
        return dp(size * ScreenMetrics.get_scale_factor())

# Convenience functions
def rsp(size):
    """Responsive sp (for fonts)"""
    return ScreenMetrics.scaled_sp(size)

def rdp(size):
    """Responsive dp (for dimensions)"""
    return ScreenMetrics.scaled_dp(size)