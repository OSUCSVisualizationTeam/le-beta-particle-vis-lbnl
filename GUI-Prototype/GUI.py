# Troy Rice
# This is a prototype UI to demonstrate the wireframe structure designed in PyQt6
# Comments are to detail the steps for functionality to expand upon for the team

import sys
from datetime import date, timedelta
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QListWidget, QListWidgetItem, QGridLayout, QSizePolicy, QComboBox
from PyQt6.QtGui import QPixmap

class MainWindow(QMainWindow):
    """Main window prototype for GUI"""
    def __init__(self):
        super().__init__()
    # Set title and window geometry
        self.setWindowTitle("Visualization GUI Prototype")
        self.setGeometry(800,800,800,800)
    # Set central widget and layout to place other widgets in 
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.grid = QGridLayout()
    # Set stretch factors for rows and columns to adjust to window size
        self.grid.setRowStretch(0, 0)
        self.grid.setRowStretch(1, 1)
        for x in range(4):
            self.grid.setColumnStretch(x, 1)
        self.central_widget.setLayout(self.grid)


    # Place all widgets in the screen
        self.place_widgets()

    def place_widgets(self):
        """Places all widgets in the main window."""
    # Create Image container and populate with sample pixmap, scale that image to fit container
        image_label = QLabel(parent=self.central_widget)
        sample_image = QPixmap("GUI-Prototype\sampleImage.png")
        image_label.setPixmap(sample_image)
        image_label.setScaledContents(True)
    
    # Create combobox that contains search and other functions
        tools = QComboBox()
        tools.setMaximumHeight(50)
        tools.addItems(["Search", "Historical Data List"])

    # Create historical list that'll display data from the past, populate with 30 days previous for testing 
        historical_list = QListWidget(parent=self.central_widget)
        historical_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        historical_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        historical_list.setMinimumWidth(200)
        today = date.today()
        for x in range(30):
            historical_list.addItem(QListWidgetItem(f"{today - timedelta(days=x)}"))

    # Populate cluster data label with fake data for prototyping display
        cluster_data = QLabel(parent=self.central_widget, text="This is sample data that would be displayed for the cluster\n" \
            "Cluster Index: 123\n" \
            "Energy: 123.123keV\n" \
            "σ: 6.8\n" \
            "Full Width x: 23\n" \
            "Full Width y: 25\n" \
            "Peak xy: (983.1233)\n" \
            "Classification: Tritium Decay"
            )
    
    # Place widgets in grid layout to match UI wireframe
        self.grid.addWidget(tools, 0, 0)
        self.grid.addWidget(historical_list, 1, 0, 2, 1)
        self.grid.addWidget(image_label, 1, 2)
        self.grid.addWidget(cluster_data, 1, 3)
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    with open("GUI-Prototype\style.qss", 'r') as style:
        app.setStyleSheet(style.read())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())