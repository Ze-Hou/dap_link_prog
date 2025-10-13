from PyQt5.QtCore import (
    QEvent,
    Qt,
    QRegExp,
)
from PyQt5.QtWidgets import (
    QDialog,
    QMessageBox,
    QWhatsThis,
)
from PyQt5.QtGui import QIcon, QFont, QRegExpValidator
from PyQt5 import uic
from src.component.run_env import RunEnv
from src.ui.dap_link_prog_icon import DAPIcon
from src.ui.dap_link_style import DAPLinkStyle


class InputAddrSizeUIBase(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(RunEnv.parse_path("./src/ui/input_addr_size_page.ui"), self)
        self._init_ui()
        self.init_ui()

    def _init_ui(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowContextHelpButtonHint)
        self.groupBox.setStyleSheet(DAPLinkStyle.InputAddrSizePage.get_group_box_style())
        self.groupBox.setFont(QFont("consolas", 10))

        self.label_1.setFont(QFont("consolas", 10))
        self.label_2.setFont(QFont("consolas", 10))
        self.label_1.setText("起始地址:")
        self.label_2.setText("大小(字节):")

        self.lineEdit_1.setFont(QFont("consolas", 10))
        self.lineEdit_2.setFont(QFont("consolas", 10))

        self.lineEdit_1.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lineEdit_2.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        input_validator = QRegExpValidator(QRegExp("[0-9A-Fa-fxX]+"))
        self.lineEdit_1.setValidator(input_validator)
        self.lineEdit_2.setValidator(input_validator)

    def init_ui(self):
        pass

    def event(self, event):
        """
        重写 event 方法，处理帮助事件
        """
        if event.type() == QEvent.Type.EnterWhatsThisMode:
            QWhatsThis.leaveWhatsThisMode()
            help_text = (
                "在这里输入对应的擦写地址与大小\n"
                "支持十六进制(0x开头)与十进制"
            )
            QMessageBox.information(self, "帮助", help_text)
        return super().event(event)

    def accept(self):
        """
        重写 accept 方法，添加输入验证
        """
        start_addr = self.lineEdit_1.text()
        erase_size = self.lineEdit_2.text()
        if (not start_addr) or (not erase_size):
            QMessageBox.critical(self, "输入错误", "请输入正确的起始地址和大小！", QMessageBox.Ok)
            return
        try:
            # 尝试转换为数字，支持十进制和0x/0X开头的十六进制
            int(start_addr, 0)
            int(erase_size, 0)
        except Exception as e:
            QMessageBox.critical(self, "格式错误", f"输入格式错误：\n{e}", QMessageBox.Ok)
            return
        super().accept()


class EraseDialog(InputAddrSizeUIBase):
    def __init__(self, parent=None):
        super().__init__(parent)

    def init_ui(self):
        self.setWindowTitle("Erase")
        self.setWindowIcon(QIcon(DAPIcon.Erase.path()))
        self.groupBox.setTitle("擦除选项:")


class ReadFlashDialog(InputAddrSizeUIBase):
    def __init__(self, parent=None):
        super().__init__(parent)

    def init_ui(self):
        self.setWindowTitle("Read Flash")
        self.setWindowIcon(QIcon(DAPIcon.Upload.path()))
        self.groupBox.setTitle("读取选项:")