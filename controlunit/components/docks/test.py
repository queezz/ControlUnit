from PyQt5.QtWidgets import QApplication, QWidget, QSpinBox, QHBoxLayout

class MultiDigitSpinBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spin_boxes = []
        layout = QHBoxLayout(self)
        
        for i in range(3):
            spin_box = QSpinBox()
            layout.addWidget(spin_box)
            self.spin_boxes.append(spin_box)
            
            spin_box.valueChanged.connect(self.updateValue)
        
    def updateValue(self):
        value = 0
        for i, spin_box in enumerate(self.spin_boxes):
            digit = spin_box.value()
            value += digit * pow(10, 2 - i)
        
        print(value)  # ここでは値を表示しますが、必要に応じて処理を行ってください

if __name__ == '__main__':
    app = QApplication([])
    widget = MultiDigitSpinBox()
    widget.show()
    app.exec()
