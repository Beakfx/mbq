from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

import sys


class Mainwindow(QMainWindow):
    
    def __init__(self, *args, **kwargs):
        super(Mainwindow, self).__init__(*args, **kwargs)

        self.setWindowTitle("A New Daun")

        label = QLabel("--SINAGE--")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        

        button = QPushButton("Click There")
        button.setCheckable(True)
        button.clicked.connect(self.button_clicked)

        self.setCentralWidget(button)

    def button_clicked(self):
        print("Button clicked <--")
        

app = QApplication(sys.argv)

window = Mainwindow()
window.show()

app.exec()
