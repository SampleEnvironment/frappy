from frappy.gui.qt import QToolButton, QFrame, QWidget, QGridLayout, QSizePolicy, QVBoxLayout, Qt

class CollapsibleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.button = QToolButton()
        self.widget = QWidget()
        self.widgetContainer = QWidget()

        self.button.setArrowType(Qt.RightArrow)
        self.button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.button.setStyleSheet("QToolButton { border: none; }")
        self.button.setCheckable(True)
        self.button.toggled.connect(self._collapse)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        l = QVBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(self.widget)
        self.widgetContainer.setLayout(l)
        self.widgetContainer.setMaximumHeight(0)

        layout = QGridLayout()
        layout.addWidget(self.button, 0, 0, Qt.AlignLeft)
        layout.addWidget(line, 0, 1, 1, 1)
        layout.addWidget(self.widgetContainer, 1, 0, -1, -1)
        layout.setContentsMargins(0, 6, 0, 0)
        self.setLayout(layout)

    def _collapse(self, expand):
        if expand:
            self.button.setArrowType(Qt.DownArrow)
            self.widgetContainer.setMaximumHeight(self.widget.maximumHeight())
        else:
            self.button.setArrowType(Qt.RightArrow)
            self.widgetContainer.setMaximumHeight(0)
            self.setMaximumHeight(self.button.maximumHeight())

    def replaceWidget(self, widget):
        layout = self.widgetContainer.layout()
        layout.removeWidget(self.widget)
        self.widget = widget
        layout.addWidget(self.widget)

    def setTitle(self, title):
        self.button.setText(title)

    def getWidget(self):
        return self.widget
