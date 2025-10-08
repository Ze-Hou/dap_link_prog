from PyQt5.QtCore import (
    QEvent,
    Qt,
)
from PyQt5.QtWidgets import (
    QDialog,
    QMessageBox,
    QWhatsThis,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt5 import uic
from enum import Enum

from dap_link_style import DAPLinkStyle

class DataTableFormat(Enum):
    """
    显示格式的位数
    """
    BIT_BYTE = "byte"
    BIT_WORD = "word"
    BIT_DWORD = "dword"
    BIT_QWORD = "qword"
    ColumnCount = 16 # 每行显示的字节数

class DataTableUIBase(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_format_bit = DataTableFormat.BIT_BYTE
        self.column_count = DataTableFormat.ColumnCount.value
        self.ascii_column_header = ''.join(f"{i:X}" for i in range(self.column_count))
        self.table_data = {
            'data': [],
            'addr': 0x0,
            'size': 0,
            'show_rows': 64,
            'load_rows' : 5,
        }
        self.table_load_data = {
            'data': [],
            'addr': 0x0,
            'size': 0,
        }

        uic.loadUi("./src/ui/data_table_page.ui", self)
        self._init_ui()
        self.init_ui()

    def _init_ui(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowContextHelpButtonHint)
        self.tableWidget.setStyleSheet(DAPLinkStyle.DateTablePage.get_table_widget_style())
        # 行高根据内容自适应调整，禁止用户调整行高
        self.tableWidget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        # 列宽根据内容自适应调整，禁止用户调整列宽
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tableWidget.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tableWidget.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pushButton.setText(self.current_format_bit.value)
        self.pushButton.clicked.connect(self._on_format_button_clicked)

        self.label_1.setText("起始地址:")
        self.label_3.setText("数据大小:")
        self.set_table_data([], 0, 0)

    def init_ui(self):
        pass

    def set_table_data(self, data: list, start_addr: int, size: int):
        byte_data = []
        for item in data:
            byte_data.append(item & 0xFF)
            byte_data.append((item >> 8) & 0xFF)
            byte_data.append((item >> 16) & 0xFF)
            byte_data.append((item >> 24) & 0xFF)
        data = byte_data[:size]
        self.table_data['data'] = data
        self.table_data['addr'] = start_addr
        self.table_data['size'] = size
        self.label_2.setText(f"0x{self.table_data['addr']:08X}")
        self.label_4.setText(f"{self.table_data['size']} bytes")

        if self.table_data['size'] >= self.table_data['show_rows'] * self.column_count:
            self.table_load_data['data'] = self.table_data['data'][:self.table_data['show_rows'] * self.column_count]
            self.table_load_data['addr'] = self.table_data['addr']
            self.table_load_data['size'] = self.table_data['show_rows'] * self.column_count
        else:
            self.table_load_data['data'] = self.table_data['data']
            self.table_load_data['addr'] = self.table_data['addr']
            self.table_load_data['size'] = self.table_data['size']
        self._load_table_data()

    def _load_table_data(self):
        self._set_table_format()

    def _set_table_format(self):
        self.tableWidget.clear()
        match self.current_format_bit:
            case DataTableFormat.BIT_BYTE:
                self._set_table_format_byte()

            case DataTableFormat.BIT_WORD:
                self._set_table_format_word()

            case DataTableFormat.BIT_DWORD:
                self._set_table_format_dword()

            case DataTableFormat.BIT_QWORD:
                self._set_table_format_qword()

    def _set_table_format_byte(self):
        column_count = self.column_count + 1 # X列数据 + 1列ascii
        self.tableWidget.setColumnCount(column_count)
        column_headers = [f"{i:02X}" for i in range(self.column_count)] + [self.ascii_column_header]
        self.tableWidget.setHorizontalHeaderLabels(column_headers)
        if self.table_load_data['size'] == 0:
            self.tableWidget.setRowCount(1)
            start_addr = self.table_load_data['addr']
            row_header = [f"{start_addr:08X}"]
            self.tableWidget.setVerticalHeaderLabels(row_header)
            return
        row_count = (self.table_load_data['size'] + self.column_count - 1) // self.column_count
        self.tableWidget.setRowCount(row_count)
        row_headers = [f"{(self.table_load_data['addr'] + i*self.column_count):08X}" for i in range(row_count)]
        self.tableWidget.setVerticalHeaderLabels(row_headers)
        for row in range(row_count):
            if (row + 1) * self.column_count <= self.table_load_data['size']:
                row_bytes = self.table_load_data['data'][row*self.column_count:(row+1)*self.column_count]
                ascii_str = self._data_to_ascii(row_bytes)
                for col in range(column_count - 1):
                    item = self.tableWidget.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, col, item)
                        self.tableWidget.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"{row_bytes[col]:02X}")
            else:
                row_bytes = self.table_load_data['data'][row*self.column_count:]
                ascii_str = self._data_to_ascii(row_bytes)
                for col in range(len(row_bytes)):
                    item = self.tableWidget.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, col, item)
                        self.tableWidget.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"{row_bytes[col]:02X}")
            item = self.tableWidget.item(row, column_count - 1)
            if item is None:
                item = QTableWidgetItem()
                self.tableWidget.setItem(row, column_count - 1, item)
                self.tableWidget.item(row, column_count - 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setText(ascii_str)

    def _set_table_format_word(self):
        column_count = self.column_count // 2 + 1 # X//2列数据 + 1列ascii
        self.tableWidget.setColumnCount(column_count)
        column_headers = [f"{i*2:04X}" for i in range(self.column_count // 2)] + [self.ascii_column_header]
        self.tableWidget.setHorizontalHeaderLabels(column_headers)
        if self.table_load_data['size'] == 0:
            self.tableWidget.setRowCount(1)
            start_addr = self.table_load_data['addr']
            row_header = [f"{start_addr:08X}"]
            self.tableWidget.setVerticalHeaderLabels(row_header)
            return
        row_count = (self.table_load_data['size'] + self.column_count - 1) // self.column_count
        self.tableWidget.setRowCount(row_count)
        row_headers = [f"{(self.table_load_data['addr'] + i*self.column_count):08X}" for i in range(row_count)]
        self.tableWidget.setVerticalHeaderLabels(row_headers)
        for row in range(row_count):
            if (row + 1) * self.column_count <= self.table_load_data['size']:
                row_bytes = self.table_load_data['data'][row*self.column_count:(row+1)*self.column_count]
                ascii_str = self._data_to_ascii(row_bytes)
                for col in range(column_count - 1):
                    word = row_bytes[col*2] | (row_bytes[col*2 + 1] << 8)
                    item = self.tableWidget.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, col, item)
                        self.tableWidget.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"{word:04X}")
            else:
                row_bytes = self.table_load_data['data'][row*self.column_count:]
                ascii_str = self._data_to_ascii(row_bytes)
                for col in range(len(row_bytes) // 2):
                    word = row_bytes[col*2] | (row_bytes[col*2 + 1] << 8)
                    item = self.tableWidget.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, col, item)
                        self.tableWidget.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"{word:04X}")
                if len(row_bytes) % 2 != 0:
                    word = row_bytes[-1]
                    item = self.tableWidget.item(row, len(row_bytes) // 2)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, len(row_bytes) // 2, item)
                        self.tableWidget.item(row, len(row_bytes) // 2).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"\u25A1\u25A1{word:02X}")
            item = self.tableWidget.item(row, column_count - 1)
            if item is None:
                item = QTableWidgetItem()
                self.tableWidget.setItem(row, column_count - 1, item)
                self.tableWidget.item(row, column_count - 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setText(ascii_str)

    def _set_table_format_dword(self):
        column_count = self.column_count // 4 + 1 # X//4列数据 + 1列ascii
        self.tableWidget.setColumnCount(column_count)
        column_headers = [f"{i*4:08X}" for i in range(self.column_count // 4)] + [self.ascii_column_header]
        self.tableWidget.setHorizontalHeaderLabels(column_headers)
        if self.table_load_data['size'] == 0:
            self.tableWidget.setRowCount(1)
            start_addr = self.table_load_data['addr']
            row_header = [f"{start_addr:08X}"]
            self.tableWidget.setVerticalHeaderLabels(row_header)
            return
        row_count = (self.table_load_data['size'] + self.column_count - 1) // self.column_count
        self.tableWidget.setRowCount(row_count)
        row_headers = [f"{(self.table_load_data['addr'] + i*self.column_count):08X}" for i in range(row_count)]
        self.tableWidget.setVerticalHeaderLabels(row_headers)
        for row in range(row_count):
            if (row + 1) * self.column_count <= self.table_load_data['size']:
                row_bytes = self.table_load_data['data'][row*self.column_count:(row+1)*self.column_count]
                ascii_str = self._data_to_ascii(row_bytes)
                for col in range(column_count - 1):
                    dword = (row_bytes[col*4] |
                             (row_bytes[col*4 + 1] << 8)  |
                             (row_bytes[col*4 + 2] << 16) |
                             (row_bytes[col*4 + 3] << 24))
                    item = self.tableWidget.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, col, item)
                        self.tableWidget.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"{dword:08X}")
            else:
                row_bytes = self.table_load_data['data'][row*self.column_count:]
                ascii_str = self._data_to_ascii(row_bytes)
                for col in range(len(row_bytes) // 4):
                    dword = (row_bytes[col*4] |
                             (row_bytes[col*4 + 1] << 8)  |
                             (row_bytes[col*4 + 2] << 16) |
                             (row_bytes[col*4 + 3] << 24))
                    item = self.tableWidget.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, col, item)
                        self.tableWidget.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"{dword:08X}")
                if len(row_bytes) % 4 != 0:
                    rem = len(row_bytes) % 4
                    dword = 0
                    for i in range(rem):
                        dword |= row_bytes[-rem + i] << (i * 8)
                    item = self.tableWidget.item(row, len(row_bytes) // 4)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, len(row_bytes) // 4, item)
                        self.tableWidget.item(row, len(row_bytes) // 4).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    dword_str = ''.join("\u25A1" for _ in range((4 - rem)*2)) + f"{dword:0{rem*2}X}"
                    item.setText(dword_str)
            item = self.tableWidget.item(row, column_count - 1)
            if item is None:
                item = QTableWidgetItem()
                self.tableWidget.setItem(row, column_count - 1, item)
                self.tableWidget.item(row, column_count - 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setText(ascii_str)

    def _set_table_format_qword(self):
        column_count = self.column_count // 8 + 1 # X//8列数据 + 1列ascii
        self.tableWidget.setColumnCount(column_count)
        column_headers = [f"{i*8:016X}" for i in range(self.column_count // 8)] + [self.ascii_column_header]
        self.tableWidget.setHorizontalHeaderLabels(column_headers)
        if self.table_load_data['size'] == 0:
            self.tableWidget.setRowCount(1)
            start_addr = self.table_load_data['addr']
            row_header = [f"{start_addr:08X}"]
            self.tableWidget.setVerticalHeaderLabels(row_header)
            return
        row_count = (self.table_load_data['size'] + self.column_count - 1) // self.column_count
        self.tableWidget.setRowCount(row_count)
        row_headers = [f"{(self.table_load_data['addr'] + i*self.column_count):08X}" for i in range(row_count)]
        self.tableWidget.setVerticalHeaderLabels(row_headers)
        for row in range(row_count):
            if (row + 1) * self.column_count <= self.table_load_data['size']:
                row_bytes = self.table_load_data['data'][row*self.column_count:(row+1)*self.column_count]
                ascii_str = self._data_to_ascii(row_bytes)
                for col in range(column_count - 1):
                    qword = (row_bytes[col*8] |
                             (row_bytes[col*8 + 1] << 8)  |
                             (row_bytes[col*8 + 2] << 16) |
                             (row_bytes[col*8 + 3] << 24) |
                             (row_bytes[col*8 + 4] << 32) |
                             (row_bytes[col*8 + 5] << 40) |
                             (row_bytes[col*8 + 6] << 48) |
                             (row_bytes[col*8 + 7] << 56))
                    item = self.tableWidget.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, col, item)
                        self.tableWidget.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"{qword:016X}")
            else:
                row_bytes = self.table_load_data['data'][row*self.column_count:]
                ascii_str = self._data_to_ascii(row_bytes)
                for col in range(len(row_bytes) // 8):
                    qword = (row_bytes[col*8] |
                             (row_bytes[col*8 + 1] << 8)  |
                             (row_bytes[col*8 + 2] << 16) |
                             (row_bytes[col*8 + 3] << 24) |
                             (row_bytes[col*8 + 4] << 32) |
                             (row_bytes[col*8 + 5] << 40) |
                             (row_bytes[col*8 + 6] << 48) |
                             (row_bytes[col*8 + 7] << 56))
                    item = self.tableWidget.item(row, col)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, col, item)
                        self.tableWidget.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setText(f"{qword:016X}")
                if len(row_bytes) % 8 != 0:
                    rem = len(row_bytes) % 8
                    qword = 0
                    for i in range(rem):
                        qword |= row_bytes[-rem + i] << (i * 8)
                    item = self.tableWidget.item(row, len(row_bytes) // 8)
                    if item is None:
                        item = QTableWidgetItem()
                        self.tableWidget.setItem(row, len(row_bytes) // 8, item)
                        self.tableWidget.item(row, len(row_bytes) // 8).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    qword_str = ''.join("\u25A1" for _ in range((8 - rem)*2)) + f"{qword:0{rem*2}X}"
                    item.setText(qword_str)
            item = self.tableWidget.item(row, column_count - 1)
            if item is None:
                item = QTableWidgetItem()
                self.tableWidget.setItem(row, column_count - 1, item)
                self.tableWidget.item(row, column_count - 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setText(ascii_str)

    def _data_to_ascii(self, data):
        # 对于不足一行的数据，在数据后追加空格，以实现ascii列对齐
        if len(data) != self.column_count:
            data = data + [0x20] * (self.column_count - len(data))
        return ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)

    def event(self, event):
        """
        重写 event 方法，处理帮助事件
        """
        if event.type() == QEvent.Type.EnterWhatsThisMode:
            QWhatsThis.leaveWhatsThisMode()
            help_text = (
                "二进制数据查看，支持16进制查看,\n"
                "可按钮设置显示格式(8/16/32/64位)"
            )
            QMessageBox.information(self, "帮助", help_text)
        return super().event(event)

    def wheelEvent(self, event):
        """鼠标滚轮事件处理"""
        temp = self.table_data['size'] - self.table_data['show_rows'] * self.column_count
        if temp <= 0:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta > 0:
            if self.table_load_data['addr'] > self.table_data['addr']:
                temp = self.table_load_data['addr'] - self.table_data['addr']
                if temp >= self.table_data['load_rows'] * self.column_count:
                    self.table_load_data['addr'] -= self.table_data['load_rows'] * self.column_count
                    self.table_load_data['size'] = self.table_data['show_rows'] * self.column_count
                    self.table_load_data['data'] = self.table_data['data'][
                        (self.table_load_data['addr'] - self.table_data['addr']):
                        (self.table_load_data['addr'] - self.table_data['addr'] + self.table_load_data['size'])
                    ]
                else:
                    self.table_load_data['addr'] = self.table_data['addr']
                    self.table_load_data['size'] = self.table_data['show_rows'] * self.column_count
                    self.table_load_data['data'] = self.table_data['data'][:self.table_load_data['size']]
                self._load_table_data()
        elif delta < 0:
            temp = self.table_load_data['addr'] + self.table_load_data['size'] - \
                   self.table_data['addr']
            if temp < self.table_data['size']:
                temp = self.table_load_data['addr'] + self.table_load_data['size'] + \
                        self.table_data['load_rows'] * self.column_count - self.table_data['addr']
                if temp <= self.table_data['size']:
                    self.table_load_data['addr'] += self.table_data['load_rows'] * self.column_count
                    self.table_load_data['size'] = self.table_data['show_rows'] * self.column_count
                    self.table_load_data['data'] = self.table_data['data'][
                        (self.table_load_data['addr'] - self.table_data['addr']):
                        (self.table_load_data['addr'] - self.table_data['addr'] + self.table_load_data['size'])
                    ]
                else:
                    self.table_load_data['addr'] += self.table_data['load_rows'] * self.column_count
                    self.table_load_data['size'] = self.table_data['size'] - (self.table_load_data['addr'] - self.table_data['addr'])
                    self.table_load_data['data'] = self.table_data['data'][
                        (self.table_load_data['addr'] - self.table_data['addr']):
                        (self.table_data['size'])
                    ]
                self._load_table_data()
        super().wheelEvent(event)

    def _on_format_button_clicked(self):
        match self.current_format_bit:
            case DataTableFormat.BIT_BYTE:
                self.current_format_bit = DataTableFormat.BIT_WORD

            case DataTableFormat.BIT_WORD:
                self.current_format_bit = DataTableFormat.BIT_DWORD

            case DataTableFormat.BIT_DWORD:
                self.current_format_bit = DataTableFormat.BIT_QWORD

            case DataTableFormat.BIT_QWORD:
                self.current_format_bit = DataTableFormat.BIT_BYTE

        self.pushButton.setText(self.current_format_bit.value)
        self._set_table_format()


class FlashDataTableDialog(DataTableUIBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Flash Data Table")


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    dig = FlashDataTableDialog()
    dig.show()
    sys.exit(app.exec_())