
import sys
import os

# Add the src directory to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from PySide6.QtWidgets import QApplication
from le_beta_vis.frontend.MainWindow import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # In the future, we would load a QTranslator here:
    # translator = QTranslator()
    # if translator.load(QLocale.system(), "app", "_", "translations"):
    #     app.installTranslator(translator)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
