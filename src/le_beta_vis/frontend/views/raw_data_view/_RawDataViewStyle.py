class _Style:
    LEFT_TOOLBAR = "background-color: #2d2d2d; border-right: 1px solid #3d3d3d;"
    STATUS_BAR = (
        "background-color: #1e1e1e; color: #cccccc;"
        " font-size: 12px; padding-left: 8px;"
    )
    RIGHT_SIDEBAR = """
        QFrame { background-color: #f0f0f0; border-left: 1px solid #ccc; }
        QWidget { background-color: #f0f0f0; }
        QTabWidget::pane {
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            border-top: none;
        }
        QTabBar::tab {
            background-color: #e0e0e0;
            color: #000000;
            padding: 6px 12px;
            border: 1px solid #ccc;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background-color: #f0f0f0;
        }
        QGroupBox { color: #000000; background-color: #f0f0f0; }
        QGroupBox::title { color: #000000; }
        QLabel { color: #000000; background: transparent; }
        QPushButton { color: #000000; }
        QComboBox { color: #000000; background-color: #ffffff; }
        QComboBox QAbstractItemView {
            color: #000000; background-color: #ffffff;
        }
        QDoubleSpinBox { color: #000000; background-color: #ffffff; }
        QListWidget {
            color: #000000;
            background-color: #f4f4f4;
            alternate-background-color: #e8e8e8;
        }
        QListWidget::item:selected { background-color: #b3d4fc; }
    """
