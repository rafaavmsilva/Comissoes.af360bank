import pystray
from PIL import Image
import webbrowser
import threading
from app import app
import os
import sys
import signal

def create_icon():
    # Get the directory of the current script
    if getattr(sys, 'frozen', False):
        application_path = sys._MEIPASS
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    # Try to load custom icon, fallback to generated one if not found
    icon_path = os.path.join(application_path, 'icon.png')
    if os.path.exists(icon_path):
        return Image.open(icon_path)
    else:
        # Create a simple icon as fallback
        icon = Image.new('RGB', (64, 64), color='white')
        return icon

def open_browser():
    webbrowser.open('http://127.0.0.1:5000')

def setup(icon):
    icon.visible = True
    # Open browser automatically when app starts
    open_browser()

def exit_action(icon):
    icon.visible = False
    icon.stop()
    # Send SIGTERM signal to shut down Flask gracefully
    os.kill(os.getpid(), signal.SIGTERM)

def run_flask():
    app.run(port=5000)

def main():
    # Create and start Flask thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Create system tray icon
    icon = pystray.Icon(
        'Sistema de Comissões',
        create_icon(),
        menu=pystray.Menu(
            pystray.MenuItem('Abrir', open_browser),
            pystray.MenuItem('Sair', exit_action)
        )
    )

    # Run the system tray icon
    icon.run(setup=setup)

if __name__ == '__main__':
    main()
