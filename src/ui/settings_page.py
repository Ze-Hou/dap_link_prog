import logging
from PyQt5.QtCore import (
    QEvent,
    Qt,
    pyqtSignal,
    QRegExp,
)
from PyQt5.QtWidgets import (
    QDialog,
    QMessageBox,
    QWhatsThis,
    QComboBox,
    QLineEdit,
    QCompleter,
)

from PyQt5.QtGui import QIcon, QRegExpValidator
from PyQt5 import uic
import copy
from src.component.run_env import RunEnv
from src.ui.dap_link_prog_icon import DAPIcon
from src.ui.dap_link_style import DAPLinkStyle
from src.ui.dap_link_handle_thread import DAPLinkHandleThread, DAPLinkSyncData, DAPLinkOperation


class SettingsData:
    dap = {
        'connect': "正常连接",    # 正常连接, 预先复位
        'reset': "自动",        # 自动, 软件复位, 硬件复位
        'erase': "扇区擦除",      # 不擦除, 扇区擦除, 全片擦除
        'verify': True,         # True, False
        'run': True,            # True, False
        'interface': "SWD",     # SWD, JTAG, 目标不允许选择，只支持SWD
        'clock': "5MHz",        # 10MHz, 5MHz, 2MHz, 1MHz, 500KHz, 200KHz, 100KHz, 50KHz, 20KHz, 10KHz
    }
    target = {
        'search_history': [],   # 最近搜索的目标
        'current_search': "",   # 当前搜索的目标
        'vendor': "",           # 目标厂商
        'family': "",           # 目标系列
        'device': "",           # 目标型号
        'algorithm': "",        # 目标算法
    }

    @classmethod
    def get_settings_data(cls):
        return {
            'dap': copy.deepcopy(cls.dap),
            'target': copy.deepcopy(cls.target),
        }


class SettingsDialog(QDialog):
    settings_sync_signal = pyqtSignal(dict)
    def __init__(self, parent=None, settings_data: dict={}):
        super().__init__(parent)
        self.dap_handle_thread = DAPLinkHandleThread()
        self.dap_handle_thread.dap_link_handle_sync_signal.connect(self._handle_sync_data)
        self.settings_sync_signal.connect(self.dap_handle_thread.get_sync_data)
        self.all_device_info = []
        if not settings_data:
            self.settings_data = SettingsData.get_settings_data()
        else:
            self.settings_data = copy.deepcopy(settings_data)
        uic.loadUi(RunEnv.parse_path("./src/ui/settings_page.ui"), self)
        self._init_ui()

    def get_settings_data(self):
        self.settings_data['dap']['connect'] = self.comboBox_0_0.currentText()
        self.settings_data['dap']['reset'] = self.comboBox_0_1.currentText()
        self.settings_data['dap']['erase'] = self.comboBox_0_2.currentText()
        self.settings_data['dap']['verify'] = self.checkBox_0_0.isChecked()
        self.settings_data['dap']['run'] = self.checkBox_0_1.isChecked()
        self.settings_data['dap']['interface'] = self.comboBox_0_3.currentText()
        self.settings_data['dap']['clock'] = self.comboBox_0_4.currentText()
        self.settings_data['target']['current_search'] = self.comboBox_1_0.currentText()
        self.settings_data['target']['vendor'] = self.comboBox_1_1.currentText()
        self.settings_data['target']['family'] = self.comboBox_1_2.currentText()
        self.settings_data['target']['device'] = self.comboBox_1_3.currentText()
        self.settings_data['target']['algorithm'] = self.comboBox_1_4.currentData(Qt.ItemDataRole.UserRole)
        return copy.deepcopy(self.settings_data)

    def _init_ui(self):
        self.setWindowTitle("Settings")
        self.setWindowIcon(QIcon(DAPIcon.Settings.path()))
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowContextHelpButtonHint)

        self.listWidget.setCurrentRow(0)
        self.stackedWidget.setCurrentIndex(0)

        self.listWidget.setStyleSheet(DAPLinkStyle.SettingsPage.get_list_widget_style())
        self.stackedWidget.setStyleSheet(DAPLinkStyle.SettingsPage.get_stacked_widget_style())

        self.listWidget.currentRowChanged.connect(self.stackedWidget.setCurrentIndex)

        # page 0
        self.comboBox_0_0.activated[str].connect(self._on_comboBox_0_0_activated)
        self.comboBox_0_1.activated[str].connect(self._on_comboBox_0_1_activated)
        self.comboBox_0_2.activated[str].connect(self._on_comboBox_0_2_activated)
        self.comboBox_0_3.setEnabled(False)
        self.comboBox_0_4.activated[str].connect(self._on_comboBox_0_4_activated)
        self.checkBox_0_0.stateChanged.connect(self._on_checkBox_0_0_stateChanged)
        self.checkBox_0_1.stateChanged.connect(self._on_checkBox_0_1_stateChanged)

        # page 1
        self.comboBox_1_0.setEditable(True)
        input_validator = QRegExpValidator(QRegExp(r"[A-Za-z0-9_\-+*/\.\\]+"))
        self.comboBox_1_0.setValidator(input_validator)

        self.comboBox_1_0.editTextChanged.connect(self._on_comboBox_1_0_editTextChanged)
        self.comboBox_1_0.activated[str].connect(self._on_comboBox_1_0_activated)
        self.comboBox_1_0.lineEdit().returnPressed.connect(self._on_comboBox_1_0_confirmed)
        self.comboBox_1_1.activated[str].connect(self._on_comboBox_1_1_activated)
        self.comboBox_1_2.activated[str].connect(self._on_comboBox_1_2_activated)
        self.comboBox_1_3.activated[str].connect(self._on_comboBox_1_3_activated)
        self.comboBox_1_4.activated[str].connect(self._on_comboBox_1_4_activated)

        self._set_page_0_context()
        # 获取可用设备信息
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.GetDeviceInfo
        self.settings_sync_signal.emit(sync_data)
        self.dap_handle_thread.start()

    def event(self, event):
        """
        重写 event 方法，处理帮助事件
        """
        if event.type() == QEvent.Type.EnterWhatsThisMode:
            QWhatsThis.leaveWhatsThisMode()
            help_text = (
                "设置各种参数"
            )
            QMessageBox.information(self, "帮助", help_text)
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            widget = self.focusWidget()
            if isinstance(widget, (QComboBox, QLineEdit)):
                event.ignore()
                return
        super().keyPressEvent(event)

    # 槽函数
    def _on_comboBox_0_0_activated(self, text):
        self.settings_data['dap']['connect'] = text

    def _on_comboBox_0_1_activated(self, text):
        self.settings_data['dap']['reset'] = text

    def _on_comboBox_0_2_activated(self, text):
        self.settings_data['dap']['erase'] = text

    def _on_comboBox_0_4_activated(self, text):
        self.settings_data['dap']['clock'] = text

    def _on_checkBox_0_0_stateChanged(self, state):
        if state == Qt.CheckState.Checked:
            self.settings_data['dap']['verify'] = True
        else:
            self.settings_data['dap']['verify'] = False

    def _on_checkBox_0_1_stateChanged(self, state):
        if state == Qt.CheckState.Checked:
            self.settings_data['dap']['run'] = True
        else:
            self.settings_data['dap']['run'] = False

    def _on_comboBox_1_0_editTextChanged(self, text):
        if text:
            self._add_item_to_combobox_by_serach(text)

    def _on_comboBox_1_0_activated(self, text):
        if self.comboBox_1_0.completer().popup().isVisible() is False:
            self.comboBox_1_0.completer().complete()

        self._add_item_to_combobox_by_serach(text)
        self.settings_data['target']['current_search'] = text

    def _on_comboBox_1_0_confirmed(self):
        text = self.comboBox_1_0.currentText()
        self.settings_data['target']['current_search'] = text
        if text:
            self._add_item_to_combobox_by_serach(text)
            if text not in self.settings_data['target']['search_history']:
                if len(self.settings_data['target']['search_history']) >= 20:
                    self.settings_data['target']['search_history'].pop(0)
                self.settings_data['target']['search_history'].append(text)

    def _on_comboBox_1_1_activated(self, text):
        self._filter_family_by_vendor(text)
        self._on_comboBox_1_2_activated(self.comboBox_1_2.currentText())
        self.settings_data['target']['vendor'] = text

    def _on_comboBox_1_2_activated(self, text):
        self._filter_device_by_family(text)
        self._on_comboBox_1_3_activated(self.comboBox_1_3.currentText())
        self.settings_data['target']['family'] = text

    def _on_comboBox_1_3_activated(self, text):
        self._filter_algorithm_by_device(text)
        self._on_comboBox_1_4_activated(self.comboBox_1_4.currentText())
        self.settings_data['target']['device'] = text

    def _on_comboBox_1_4_activated(self, text):
        self.settings_data['target']['algorithm'] = self.comboBox_1_4.currentData(Qt.ItemDataRole.UserRole)

    def _handle_sync_data(self, sync_data: dict):
        operation = sync_data.get('operation')
        if not operation:
            logging.error("no operation specified in sync data.")
            return
        if sync_data['status'] is not True:
            logging.error(f"{operation.value} failed.")
            return

        match operation:
            case DAPLinkOperation.GetDeviceInfo:
                self._get_device_info(sync_data)

    def _get_device_info(self, sync_data: dict):
        device = []
        self.all_device_info = sync_data.get('data', [])
        for info in self.all_device_info:
            device.append(info['device'])

        completer = QCompleter(device, self.comboBox_1_0)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # 不区分大小写
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.comboBox_1_0.setCompleter(completer)

        self._add_item_to_combobox_by_serach(self.settings_data['target']['current_search'])
        self._set_page_1_context()

    def _add_item_to_combobox_by_serach(self, filter: str=""):
        self.comboBox_1_1.clear()
        alread_add_vendor = []
        device_flag = False
        if filter:
            for info in self.all_device_info:
                if filter.lower() in info['device'].lower():
                    device_flag = True
                    break
            if device_flag is False:
                self.comboBox_1_2.clear()
                self.comboBox_1_3.clear()
                self.comboBox_1_4.clear()
                return

        # 添加所有厂商
        for info in self.all_device_info:
            if info['vendor'] not in alread_add_vendor:
                alread_add_vendor.append(info['vendor'])
                self.comboBox_1_1.addItem(info['vendor'])

        current_vendor = self.comboBox_1_1.currentText()
        for info in self.all_device_info:
            if filter.lower() in info['device'].lower():
                if info['vendor'] != current_vendor:
                    self.comboBox_1_1.setCurrentText(info['vendor'])
                    current_vendor = info['vendor']
                    break
                else:
                    break
        self._filter_family_by_vendor(current_vendor, filter)
        current_family = self.comboBox_1_2.currentText()
        self._filter_device_by_family(current_family, filter)
        current_device = self.comboBox_1_3.currentText()
        self._filter_algorithm_by_device(current_device)

    def _filter_family_by_vendor(self, vendor: str, filter: str=""):
        self.comboBox_1_2.clear()
        aleardy_add_family = []
        if filter:
            for info in self.all_device_info:
                if info['vendor'] == vendor:
                    if filter.lower() in info['device'].lower():
                        if info['family'] not in aleardy_add_family:
                            aleardy_add_family.append(info['family'])
                            self.comboBox_1_2.addItem(info['family'])
        else:
            for info in self.all_device_info:
                if info['vendor'] == vendor:
                    if info['family'] not in aleardy_add_family:
                        aleardy_add_family.append(info['family'])
                        self.comboBox_1_2.addItem(info['family'])

    def _filter_device_by_family(self, family: str, filter: str=""):
        self.comboBox_1_3.clear()
        already_add_device = []
        if filter:
            for info in self.all_device_info:
                if info['family'] == family:
                    if filter.lower() in info['device'].lower():
                        if info['device'] not in already_add_device:
                            already_add_device.append(info['device'])
                            self.comboBox_1_3.addItem(info['device'])
        else:
            for info in self.all_device_info:
                if info['family'] == family:
                    if info['device'] not in already_add_device:
                        already_add_device.append(info['device'])
                        self.comboBox_1_3.addItem(info['device'])

    def _filter_algorithm_by_device(self, device: str):
        self.comboBox_1_4.clear()
        already_add_algorithm = []
        for info in self.all_device_info:
            if info['device'] == device:
                for algo in info['algorithm']:
                    if algo[0] not in already_add_algorithm:
                        already_add_algorithm.append(algo[0])
                        self.comboBox_1_4.addItem(algo[0], algo[1])

        for i in range(self.comboBox_1_4.count()):
            flm_path = self.comboBox_1_4.itemData(i, Qt.ItemDataRole.UserRole)
            self.comboBox_1_4.setItemData(i, flm_path, Qt.ItemDataRole.ToolTipRole)

    def _set_page_0_context(self):
        self.comboBox_0_0.setCurrentText(self.settings_data['dap']['connect'])
        self.comboBox_0_1.setCurrentText(self.settings_data['dap']['reset'])
        self.comboBox_0_2.setCurrentText(self.settings_data['dap']['erase'])
        self.checkBox_0_0.setChecked(self.settings_data['dap']['verify'])
        self.checkBox_0_1.setChecked(self.settings_data['dap']['run'])
        self.comboBox_0_4.setCurrentText(self.settings_data['dap']['clock'])

    def _set_page_1_context(self):
        if self.settings_data['target']['search_history']:
            self.comboBox_1_0.addItems(self.settings_data['target']['search_history'])
            self.comboBox_1_0.setCurrentText(self.settings_data['target']['current_search'])
        if self.settings_data['target']['vendor']:
            self.comboBox_1_1.setCurrentText(self.settings_data['target']['vendor'])
        self._filter_family_by_vendor(self.comboBox_1_1.currentText())
        if self.settings_data['target']['family']:
            self.comboBox_1_2.setCurrentText(self.settings_data['target']['family'])
        self._filter_device_by_family(self.comboBox_1_2.currentText())
        if self.settings_data['target']['device']:
            self.comboBox_1_3.setCurrentText(self.settings_data['target']['device'])
        self._filter_algorithm_by_device(self.comboBox_1_3.currentText())
        if self.settings_data['target']['algorithm']:
            self.comboBox_1_4.setCurrentText(self.settings_data['target']['algorithm'])

