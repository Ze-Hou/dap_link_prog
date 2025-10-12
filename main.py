import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

try:
    from src.ui.dap_link_prog import DAPLinkProgUI
except ImportError:
    pass


if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    window = DAPLinkProgUI()
    window.show()
    sys.exit(app.exec_())
