import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow
import config


def load_stylesheet(app: QApplication):
    stylesheet_path = config.STYLESHEET_PATH
    
    if os.path.exists(stylesheet_path):
        with open(stylesheet_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: Stylesheet not found at {stylesheet_path}")


def main():
    """Ana fonksiyon"""
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--ignore-gpu-blocklist --enable-webgl --enable-accelerated-2d-canvas --disable-background-networking"
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Ground Station")
    
    load_stylesheet(app)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

