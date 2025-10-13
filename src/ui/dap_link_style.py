from PyQt5.QtCore import (
    Qt,
)
from PyQt5.QtWidgets import (
    QGraphicsDropShadowEffect
)
from src.ui.dap_link_prog_icon import DAPIcon


class DAPLinkStyle:
    class MainPage:
        @staticmethod
        def get_menu_bar_style():
            return (
                """
                QMenuBar {
                    font: bold 12pt "方正舒体";
                    color: #222222;
                    background: #f7fafc;
                    border: none;

                }
                QMenuBar::item:selected {
                    background: #d0d7e2;
                    color: #0077cc;
                }
                QMenu {
                    font: 10pt "方正舒体";
                    color: #222222;
                    background: #f7fafc;
                    border: none;
                    padding: 0px;
                }
                QMenu::item:selected {
                    background: #d0d7e2;
                    color: #0077cc;
                }
                """
            )

        @staticmethod
        def get_status_bar_style():
            return (
                """
                QStatusBar {
                    border: none;
                    font: 12pt "方正舒体";
                    background-color: gainsboro;
                }
                """
            )

        @staticmethod
        def get_group_box_style():
            return (
                """
                QGroupBox {
                    border: 2px solid #a0a0a0;    /* 线宽2px，颜色#a0a0a0 */
                    border-radius: 6px;           /* 圆角可选 */
                    margin-top: 2ex;              /* 标题与上边距 */
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px 0 3px;
                }
                """
            )

        @staticmethod
        def get_refresh_button_style():
            return (
                """
                QPushButton {
                    background-color: #d0d7e2;
                    border-radius: 12px;
                }
                QPushButton:pressed {
                    background-color: #a0b0c0;
                }
                """
            )

        @staticmethod
        def get_combo_box_style():
            return (
                f"""
                QComboBox {{
                    font: 12pt "方正舒体";
                    border: 1px solid #a0a0a0;
                    border-radius: 6px;
                    padding: 2px 10px 2px 10px;
                    background-color: #f8f8ff;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 15px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url({DAPIcon.ChevronDown.path()});
                    width: 12px;
                    height: 12px;
                }}
                QComboBox::down-arrow:on {{
                    image: url({DAPIcon.ChevronUp.path()});
                    width: 12px;
                    height: 12px;
                }}
                QComboBox QAbstractItemView {{
                    font: 11pt "方正舒体";
                    border: 1px solid #a0a0a0;
                    border-radius: 6px;
                    background: #ffffff;
                    outline: none;
                }}
                QComboBox QAbstractItemView::item {{
                    padding: 0px 0px;
                    border-radius: 4px;
                }}
                QComboBox QAbstractItemView::item:selected {{
                    background: #d0d7e2;
                    color: #0077cc;
                    padding: 0px 10px;
                }}
                """
            )

        @staticmethod
        def get_progress_bar_style():
            return (
                """
                QProgressBar {
                    border: 1px solid #a0a0a0;
                    border-radius: 6px;
                    background-color: #f7fafc;
                    height: 12px;
                    text-align: right;
                    font: 8pt "方正舒体";
                    color: #333;
                }
                QProgressBar::chunk {
                    border-radius: 5px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                stop:0 #6ec1e4, stop:1 #b4ecb4);
                    margin: 0.5px;
                }
                """
            )
        @staticmethod
        def get_text_browser_style():
            return (
                """
                QTextBrowser {
                    border: 1px solid #a0a0a0;
                    border-radius: 6px;
                    background: #f8f8ff;
                    font: 10pt "consolas";
                    color: #000000;
                }
                QTextBrowser:focus {
                    outline: none;
                    border: 1px solid #a0a0a0;
                }
                /* 滚动条整体 */
                QScrollBar:vertical {
                    background: #f0f0f0;
                    width: 4px;
                    margin: 5px 0px 5px 0px;
                    border-radius: 2px;
                }
                /* 滚动条滑块 */
                QScrollBar::handle:vertical {
                    background: gainsboro;
                    min-height: 24px;
                    border-radius: 2px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #6ec1e4;
                }
                /* 上下按钮隐藏 */
                QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
                    height: 0px;
                    background: none;
                    border: none;
                }
                /* 滚动条两端空白 */
                QScrollBar::sub-page:vertical, QScrollBar::add-page:vertical {
                    background: none;
                }
                """
            )

        @staticmethod
        def get_text_browser_shadow_effect():
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(12)
            shadow.setOffset(2, 2)
            shadow.setColor(Qt.GlobalColor.gray)
            return shadow


    class InputAddrSizePage:
        @staticmethod
        def get_group_box_style():
            return (
                """
                QGroupBox {
                    border: 2px solid #a0a0a0;    /* 线宽2px，颜色#a0a0a0 */
                    border-radius: 6px;           /* 圆角可选 */
                    margin-top: 2ex;              /* 标题与上边距 */
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px 0 3px;
                }
                """
            )

    class SettingsPage:
        @staticmethod
        def get_group_box_style():
            return (
                """
                QGroupBox {
                    border: 2px solid #a0a0a0;    /* 线宽2px，颜色#a0a0a0 */
                    border-radius: 6px;           /* 圆角可选 */
                    margin-top: 2ex;              /* 标题与上边距 */
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px 0 3px;
                }
                """
            )

        @staticmethod
        def get_list_widget_style():
            return (
                """
                QListWidget {
                    color: #000000;
                    background: #f0f0f0;
                    border: 1px solid #a0a0a0;
                    border-radius: 6px;
                }
                QListWidget:focus {
                    outline: none;
                    border: 1px solid #a0a0a0;
                }
                QListWidget::item {
                    color: #000000;
                    border-radius: 6px;
                    padding: 0px 0px;
                    border: none;
                }
                QListWidget::item:selected {
                    background: #d0d7e2;
                    border: 1px solid #0077cc;
                }
                QListWidget::item:focus {
                    outline: none;
                }
                /* 滚动条整体 */
                QScrollBar:vertical {
                    background: #f0f0f0;
                    width: 4px;
                    margin: 5px 0px 5px 0px;
                    border-radius: 2px;
                }
                /* 滚动条滑块 */
                QScrollBar::handle:vertical {
                    background: gainsboro;
                    min-height: 24px;
                    border-radius: 2px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #6ec1e4;
                }
                /* 上下按钮隐藏 */
                QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
                    height: 0px;
                    background: none;
                    border: none;
                }
                /* 滚动条两端空白 */
                QScrollBar::sub-page:vertical, QScrollBar::add-page:vertical {
                    background: none;
                }
                """
            )

        @staticmethod
        def get_stacked_widget_style():
            return (
                """
                QStackedWidget {
                    border: 1px solid #a0a0a0;
                    border-radius: 6px;
                    background: #ffffff;
                }
                """
            )

    class DateTablePage:
        @staticmethod
        def get_table_widget_style():
            return (
                """
                QTableWidget {
                    background: #F8F9FA;
                    border: none;
                    gridline-color: #E0E0E0;
                    font: 10pt "consolas";
                }
                QTableWidget:focus {
                    outline: none;
                    border: none;
                }
                QHeaderView::section {
                    background: #F3F4F6;
                    font: 10pt "consolas";
                    color: #444;
                    padding: 0px;
                    border: none;
                    border-bottom: 1px solid #E0E0E0;
                }
                QTableWidget::item {
                    font: 10pt "consolas";
                    padding: 0px;
                    border: none;
                    text-align: center;
                }
                QTableWidget::item:selected {
                    background: #D0EBFF;
                    color: #222;
                }
                QTableWidget::item:focus {
                    outline: none;
                    border: 1px solid #a0a0a0;
                }
                """
            )

    class ShowInfoPage:
        @staticmethod
        def get_text_browser_style():
            return (
                """
                QTextBrowser {
                    border: 1px solid #a0a0a0;
                    border-radius: 6px;
                    background: #f8f8ff;
                    font: 10pt "consolas";
                    color: #000000;
                }
                QTextBrowser:focus {
                    outline: none;
                    border: 1px solid #a0a0a0;
                }
                /* 滚动条整体 */
                QScrollBar:vertical {
                    background: #f0f0f0;
                    width: 4px;
                    margin: 5px 0px 5px 0px;
                    border-radius: 2px;
                }
                /* 滚动条滑块 */
                QScrollBar::handle:vertical {
                    background: gainsboro;
                    min-height: 24px;
                    border-radius: 2px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #6ec1e4;
                }
                /* 上下按钮隐藏 */
                QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
                    height: 0px;
                    background: none;
                    border: none;
                }
                /* 滚动条两端空白 */
                QScrollBar::sub-page:vertical, QScrollBar::add-page:vertical {
                    background: none;
                }
                """
            )

        @staticmethod
        def get_text_browser_shadow_effect():
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(12)
            shadow.setOffset(2, 2)
            shadow.setColor(Qt.GlobalColor.gray)
            return shadow