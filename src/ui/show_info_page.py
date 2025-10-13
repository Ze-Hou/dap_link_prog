from PyQt5.QtCore import (
    QEvent,
    Qt,
)
from PyQt5.QtWidgets import (
    QDialog,
    QMessageBox,
    QWhatsThis,
)
from PyQt5.QtGui import QFont
from PyQt5 import uic
from src.component.run_env import RunEnv
from src.ui.dap_link_style import DAPLinkStyle


class ShowInfoUIBase(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(RunEnv.parse_path("./src/ui/show_info_page.ui"), self)
        self._init_ui()
        self.init_ui()

    def _init_ui(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowContextHelpButtonHint)
        self.textBrowser.setStyleSheet(DAPLinkStyle.ShowInfoPage.get_text_browser_style())
        self.textBrowser.setGraphicsEffect(DAPLinkStyle.ShowInfoPage.get_text_browser_shadow_effect())

    def init_ui(self):
        pass

    def add_info(self, info, color, bold=False):
        if bold:
            self.textBrowser.setFontWeight(QFont.Weight.Bold)
        else:
            self.textBrowser.setFontWeight(QFont.Weight.Normal)
        self.textBrowser.setTextColor(color)
        self.textBrowser.append(info)

    def event(self, event):
        """
        重写 event 方法，处理帮助事件
        """
        if event.type() == QEvent.Type.EnterWhatsThisMode:
            QWhatsThis.leaveWhatsThisMode()
            help_text = (
                "信息浏览对话框"
            )
            QMessageBox.information(self, "帮助", help_text)
        return super().event(event)


class ShowAboutInfoDialog(ShowInfoUIBase):
    VERSION = "0.0"
    def init_ui(self):
        self.setWindowTitle("关于")
        """
        注意保留原作者信息
        """
        about_info = {
            'author': "Author: Ze-Hou",
            'email': "Email: 2179603549@qq.com",
            'license': "License: GPL-3.0",
            'tiltle': "Version History:",
            'content': '',
        }
        about_info['content'] = f"V{self.VERSION} 2025.10.12\n" \
                                "   初始版本\n" \
                                "       - 支持基本的daplink编程功能\n" \
                                "       - 支持WinUSB与HID设备\n" \
                                "       - 支持hex bin文件烧录\n"
        self.add_info(about_info['author'], Qt.GlobalColor.darkGreen, bold=True)
        self.add_info(about_info['email'], Qt.GlobalColor.darkGreen, bold=True)
        self.add_info(about_info['license'], Qt.GlobalColor.darkGreen, bold=True)
        self.add_info(about_info['tiltle'], Qt.GlobalColor.darkGreen, bold=True)
        self.add_info(about_info['content'], Qt.GlobalColor.black)