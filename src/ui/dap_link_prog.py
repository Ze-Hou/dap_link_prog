import sys
import os
import logging
from PyQt5.QtCore import (
    Qt,
    QTimer,
    QTime,
    QSize,
    pyqtSignal,
)
from PyQt5.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QLabel,
    QAction,
    QWidget,
    QSizePolicy,
    QListView,
    QDialog,
)
from PyQt5.QtGui import QIcon, QFont, QFontDatabase
from PyQt5 import uic
from functools import partial

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from component.run_env import RunEnv
from ui.dap_link_prog_icon import DAPIcon
from ui.dap_link_style import DAPLinkStyle
from ui.input_addr_size_page import EraseDialog, ReadFlashDialog
from ui.settings_page import SettingsDialog, SettingsData
from ui.data_table_page import FlashDataTableDialog
from ui.show_info_page import ShowAboutInfoDialog
from ui.dap_link_handle_thread import DAPLinkHandleThread, DAPLinkOperation, DAPLinkSyncData
from usb_device.usb_device_monitor import USBDeviceMonitor

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


class DAPLinkProgUI(QMainWindow):
    dap_link_prog_sync_signal = pyqtSignal(dict)
    log_signal = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        fonts_dir = RunEnv.parse_path("Fonts")
        for fname in os.listdir(fonts_dir):
            if fname.lower().endswith(('.ttf')):
                font_path = os.path.join(fonts_dir, fname)
                font_id = QFontDatabase.addApplicationFont(font_path)
                QFontDatabase.applicationFontFamilies(font_id)

        self.usb_monitor = USBDeviceMonitor(self._refresh_dap_devices) # 创建USB设备监测器

        self.dap_handle_thread = DAPLinkHandleThread()
        self.dap_handle_thread.dap_link_handle_sync_signal.connect(self._handle_sync_data)
        self.dap_link_prog_sync_signal.connect(self.dap_handle_thread.get_sync_data)

        self.log_text_max_lines = LoggingHandler.Max_Lines
        self.log_text_trim_lines = LoggingHandler.Trim_Lines
        self.log_signal.connect(self._handle_log)

        self.settings_data = SettingsData.get_settings_data()

        # 加载 UI 文件
        uic.loadUi(RunEnv.parse_path("./src/ui/main_page.ui"), self)
        self.show()
        self._init_ui()

        self.last_window_flags = self.windowHandle().flags()

    def _init_ui(self):
        # 主窗口
        self._init_mainwindow()
        # 菜单栏
        self._init_menu_bar()
        # 工具栏
        self._init_tool_bar()
        # 状态栏
        self._init_status_bar()
        # DAP设备框
        self._init_dap_device_box()

        self._init_target_info_box()

        self._init_status_info_box()

        self._init_log_text_display_area()

    def _init_mainwindow(self):
        self.setWindowIcon(QIcon(DAPIcon.Link.path()))
        self.setWindowTitle("dap link prog")

    def _init_menu_bar(self):
        self.actionOpen.triggered.connect(self._open_file)
        about_action = QAction("About", self)
        about_action.triggered.connect(self._about)
        self.menuBar().addAction(about_action)
        self.menuBar().setStyleSheet(DAPLinkStyle.MainPage.get_menu_bar_style())

    def _init_tool_bar(self):
        tool_bar = self.toolBar
        tool_bar.setWindowTitle("工具栏")
        tool_bar.setFloatable(True)  # 允许悬浮
        tool_bar.setMovable(True)    # 允许拖动
        self.toolBar.topLevelChanged.connect(self._is_toolbar_floating)

        folder_open = QAction(QIcon(DAPIcon.FolderOpen.path()), '', tool_bar)
        folder_open.setToolTip("打开文件")
        tool_bar.addAction(folder_open)
        folder_open.triggered.connect(self._open_file)

        tool_bar.addSeparator() # 添加分隔符

        id = QAction(QIcon(DAPIcon.Id.path()), '', tool_bar)
        id.setToolTip("读取目标ID")
        tool_bar.addAction(id)
        id.triggered.connect(self._read_id)

        reset = QAction(QIcon(DAPIcon.Reset.path()), '', tool_bar)
        reset.setToolTip("复位目标")
        tool_bar.addAction(reset)
        reset.triggered.connect(self._reset_target)

        tool_bar.addSeparator() # 添加分隔符

        erase = QAction(QIcon(DAPIcon.Erase.path()), '', tool_bar)
        erase.setToolTip("擦除目标")
        tool_bar.addAction(erase)
        erase.triggered.connect(self._erase_target)

        tool_bar.addSeparator() # 添加分隔符

        upload = QAction(QIcon(DAPIcon.Upload.path()), '', tool_bar)
        upload.setToolTip("读取")
        tool_bar.addAction(upload)
        upload.triggered.connect(self._read_target_flash)

        download = QAction(QIcon(DAPIcon.Download.path()), '', tool_bar)
        download.setToolTip("烧录")
        tool_bar.addAction(download)
        download.triggered.connect(self._download_target_flash)

        tool_bar.addSeparator() # 添加分隔符
        settings = QAction(QIcon(DAPIcon.Settings.path()), '', tool_bar)
        settings.setToolTip("设置")
        tool_bar.addAction(settings)
        settings.triggered.connect(self._settings_dialog)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tool_bar.addWidget(spacer)
        tool_bar.addSeparator() # 添加分隔符
        # pin.svg
        pin = QAction(QIcon(DAPIcon.Pin.path()), '', tool_bar)
        pin.setToolTip("置顶窗口")
        tool_bar.addAction(pin)
        # 设置pin状态切换的槽函数
        pin.triggered.connect(partial(self._toggle_always_on_top, pin))

    def _init_status_bar(self):
        # 时间
        time_label = QLabel()
        time_label.setFont(QFont("方正舒体", 12))
        self.statusBar().addPermanentWidget(time_label)
        # 创建一个定时器刷新时间显示
        timer = QTimer(self)
        timer.timeout.connect(partial(self._update_time, time_label))
        timer.start(1000)
        self._update_time(time_label)

        self.statusBar().setStyleSheet(DAPLinkStyle.MainPage.get_status_bar_style())

    def _init_dap_device_box(self):
        self.dap_device_Box.setTitle("设备:")
        self.dap_device_Box.setStyleSheet(DAPLinkStyle.MainPage.get_group_box_style())
        self.dap_device_Box.setFont(QFont("方正舒体", 14, QFont.Bold))
        self.refresh_pushButton.setIcon(QIcon(DAPIcon.Sync.path()))
        self.refresh_pushButton.setIconSize(QSize(24, 24))
        # 设置按钮点击时颜色变化
        self.refresh_pushButton.setStyleSheet(DAPLinkStyle.MainPage.get_refresh_button_style())
        self.refresh_pushButton.clicked.connect(self._refresh_dap_devices)

        self.dap_comboBox.setView(QListView())
        self.dap_comboBox.setStyleSheet(DAPLinkStyle.MainPage.get_combo_box_style())

        self.dap_comboBox.view().window().setWindowFlags(Qt.WindowType(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint))
        self.dap_comboBox.view().window().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.dap_comboBox.setToolTip("请插入DAP设备或刷新设备")
        self.dap_comboBox.activated.connect(self._dap_comboBox_activated)

    def _init_target_info_box(self):
        self.target_info_Box.setTitle("目标信息:")
        self.target_info_Box.setStyleSheet(DAPLinkStyle.MainPage.get_group_box_style())
        self.target_info_Box.setFont(QFont("方正舒体", 12, QFont.Bold))
        self.label_1.setFont(QFont("方正舒体", 8))
        self.label_2.setFont(QFont("方正舒体", 8))
        self.label_3.setFont(QFont("方正舒体", 8))
        self.label_4.setFont(QFont("方正舒体", 10))
        self.label_5.setFont(QFont("方正舒体", 10))
        self.label_6.setFont(QFont("方正舒体", 10))

        self.label_1.setText("DBG ID:")
        self.label_2.setText("AP ID:")
        self.label_3.setText("CPU ID:")
        self.label_4.setText("null")
        self.label_5.setText("null")
        self.label_6.setText("null")

    def _init_status_info_box(self):
        self.status_info_Box.setTitle("状态信息")
        self.status_info_Box.setStyleSheet(DAPLinkStyle.MainPage.get_group_box_style())
        self.status_info_Box.setFont(QFont("方正舒体", 12, QFont.Bold))
        self.label_7.setFont(QFont("方正舒体", 12))
        self.label_8.setFont(QFont("方正舒体", 12))
        self.label_9.setFont(QFont("方正舒体", 12))

        self.label_7.setText("file:")
        self.label_8.setText("null")
        self.label_8.setToolTip("null")
        self.label_9.setText("null:") # 当前执行的操作

        self.progressBar.setStyleSheet(DAPLinkStyle.MainPage.get_progress_bar_style())
        self.progressBar.setValue(0)

    def _init_log_text_display_area(self):
        self.log_textBrowser.setStyleSheet(DAPLinkStyle.MainPage.get_text_browser_style())
        self.log_textBrowser.setGraphicsEffect(DAPLinkStyle.MainPage.get_text_browser_shadow_effect())
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger().addHandler(LoggingHandler(self.log_signal))

    """
    槽函数
    """
    def _open_file(self):
        fpath, filter_str = QFileDialog.getOpenFileName(self, "Open File", '', "program file (*.bin *.hex);;All files (*.*)")
        if fpath:
            if '\\' in fpath:
                fpath = fpath.replace('\\', '/')
            file_type = fpath.split('.')[-1]
            if file_type in ['bin', 'hex']:
                sync_data = DAPLinkSyncData.get_sync_data()
                sync_data['operation'] = DAPLinkOperation.SelectProgFile
                sync_data['data'] = [fpath, file_type]
                self.dap_link_prog_sync_signal.emit(sync_data)
                self.dap_handle_thread.start()
            else:
                self.label_8.setText("null")
                self.label_8.setToolTip("null")
                logging.error("unsupported file type: %s" % file_type)
                return

    def _about(self):
        print("about")
        about = ShowAboutInfoDialog(self)
        about.exec_()

    def _is_toolbar_floating(self, floating):
        action = self.toolBar.actions()[-1]
        if floating:
            current_flags = self.windowHandle().flags()
            self.last_window_flags = current_flags
            if (current_flags & Qt.WindowType.WindowStaysOnTopHint) == Qt.WindowType.WindowStaysOnTopHint:
                update_flags = current_flags & ~Qt.WindowType.WindowStaysOnTopHint
                self.windowHandle().setFlags(Qt.WindowType(update_flags))
            action.setIcon(QIcon(DAPIcon.Pin.path()))
            action.setToolTip("置顶工具栏")
        else:
            if (self.last_window_flags & Qt.WindowType.WindowStaysOnTopHint) == Qt.WindowType.WindowStaysOnTopHint:
                action.setIcon(QIcon(DAPIcon.PinOff.path()))
                action.setToolTip("取消置顶窗口")
            else:
                action.setIcon(QIcon(DAPIcon.Pin.path()))
                action.setToolTip("置顶窗口")
            self.windowHandle().setFlags(self.last_window_flags)

    def _read_id(self):
        if self._check_thread_is_running():
            return

        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.ReadID
        sync_data['data'] = [self._get_current_dap_device()]
        self.dap_link_prog_sync_signal.emit(sync_data)
        self.dap_handle_thread.start()

    def _reset_target(self):
        if self._check_thread_is_running():
            return

        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.Reset
        sync_data['data'] = [self._get_current_dap_device(), self.settings_data]
        self.dap_link_prog_sync_signal.emit(sync_data)
        self.dap_handle_thread.start()

    def _erase_target(self):
        if self._check_thread_is_running():
            return
        erase_config = EraseDialog(self)
        res = erase_config.exec_()

        if res == QDialog.Accepted:
            start_addr = int(erase_config.lineEdit_1.text(), 0)
            erase_size = int(erase_config.lineEdit_2.text(), 0)
            sync_data = DAPLinkSyncData.get_sync_data()
            sync_data['operation'] = DAPLinkOperation.Erase
            sync_data['data'] = [(self._get_current_dap_device()), (start_addr, erase_size), self.settings_data]
            self._set_progress_value(0, "E:")
            self.dap_link_prog_sync_signal.emit(sync_data)
            self.dap_handle_thread.start()
        elif res == QDialog.Rejected:
            pass

    def _read_target_flash(self):
        if self._check_thread_is_running():
            return
        read_flash_config = ReadFlashDialog(self)
        res = read_flash_config.exec_()

        if res == QDialog.Accepted:
            start_addr = int(read_flash_config.lineEdit_1.text(), 0)
            read_size = int(read_flash_config.lineEdit_2.text(), 0)
            sync_data = DAPLinkSyncData.get_sync_data()
            sync_data['operation'] = DAPLinkOperation.ReadFlash
            sync_data['data'] = [(self._get_current_dap_device()), (start_addr, read_size), self.settings_data]
            self._set_progress_value(0, "R:")
            self.dap_link_prog_sync_signal.emit(sync_data)
            self.dap_handle_thread.start()
        elif res == QDialog.Rejected:
            pass

    def _download_target_flash(self):
        if self._check_thread_is_running():
            return
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.Program
        sync_data['data'] = [(self._get_current_dap_device()), self.settings_data]
        self._set_progress_value(0, "P:")
        self.dap_link_prog_sync_signal.emit(sync_data)
        self.dap_handle_thread.start()

    def _check_thread_is_running(self) -> bool:
        if self.dap_handle_thread.isRunning():
            logging.warning("a operation in progress, please wait...")
            return True
        return False

    def _settings_dialog(self):
        settings_dialog = SettingsDialog(parent=self, settings_data=self.settings_data)
        res = settings_dialog.exec_()
        if res == QDialog.Accepted:
            self.settings_data = settings_dialog.get_settings_data()
        elif res == QDialog.Rejected:
            pass

    def _update_time(self, time_label):
        current_time = QTime.currentTime().toString("HH:mm:ss")
        time_label.setText(current_time)

    def _toggle_always_on_top(self, action):
        if self.toolBar.isFloating():
            current_flags = self.toolBar.window().windowHandle().flags()
            if (current_flags & Qt.WindowType.WindowStaysOnTopHint) == Qt.WindowType.WindowStaysOnTopHint:
                update_flags = current_flags & ~Qt.WindowType.WindowStaysOnTopHint & ~Qt.WindowType.WindowDoesNotAcceptFocus
                action.setIcon(QIcon(DAPIcon.Pin.path()))
                action.setToolTip("置顶工具栏")
            else:
                update_flags = current_flags | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
                action.setIcon(QIcon(DAPIcon.PinOff.path()))
                action.setToolTip("取消置顶工具栏")
            self.toolBar.window().windowHandle().setFlags(update_flags)
        else:
            current_flags = self.windowHandle().flags()
            if (current_flags & Qt.WindowType.WindowStaysOnTopHint) == Qt.WindowType.WindowStaysOnTopHint:
                update_flags = current_flags & ~Qt.WindowType.WindowStaysOnTopHint
                action.setIcon(QIcon(DAPIcon.Pin.path()))  # 取消置顶时的图标
                action.setToolTip("置顶窗口")
            else:
                update_flags = current_flags | Qt.WindowType.WindowStaysOnTopHint
                action.setIcon(QIcon(DAPIcon.PinOff.path()))  # 置顶时的图标
                action.setToolTip("取消置顶窗口")
            self.windowHandle().setFlags(update_flags)

    def _refresh_dap_devices(self):
        if self.dap_handle_thread.isRunning():
            logging.warning("dap device refresh in progress, please wait...")
            return
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.RefreshDAP
        self.dap_link_prog_sync_signal.emit(sync_data)
        self.dap_handle_thread.start()

    def _dap_comboBox_activated(self, index):
        if self.dap_handle_thread.isRunning():
            logging.warning("read id operation in progress, please wait...")
            return
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.SelectDAP
        sync_data['data'] = [self._get_current_dap_device()]
        self.dap_link_prog_sync_signal.emit(sync_data)
        self.dap_handle_thread.start()

    def _get_current_dap_device(self):
        device = self.dap_comboBox.currentText()
        serial_number = self.dap_comboBox.currentData(Qt.ItemDataRole.UserRole)
        if device and serial_number:
            return (device, serial_number)
        logging.error("no dap device selected.")
        return (None, None)

    def _handle_sync_data(self, sync_data: dict):
        operation = sync_data.get('operation')
        suboperation = sync_data.get('suboperation')
        if not operation:
            logging.error("no operation specified in sync data.")
            return
        if sync_data['status'] is not True:
            # 操作失败时清空显示的ID信息
            self.label_4.setText("null")
            self.label_5.setText("null")
            self.label_6.setText("null")
            if suboperation:
                logging.error(f"{operation.value}.{suboperation.value} failed.")
            else:
                logging.error(f"{operation.value} failed.")
            return
        if suboperation:
            self.statusBar().showMessage(f"{operation.value}.{suboperation.value} successful", 500)
        else:
            self.statusBar().showMessage(f"{operation.value} successful", 500)
        match operation:
            case DAPLinkOperation.RefreshDAP:
                self._handle_sync_data_refresh_dap(sync_data)

            case DAPLinkOperation.SelectDAP:
                self._handle_sync_data_select_dap(sync_data)

            case DAPLinkOperation.ReadID:
                self._handle_sync_data_read_id(sync_data)

            case DAPLinkOperation.Reset:
                self._handle_sync_data_reset_target(sync_data)

            case DAPLinkOperation.Erase:
                self._handle_sync_data_erase_target(sync_data)

            case DAPLinkOperation.Program:
                self._handle_sync_data_program_target(sync_data)

            case DAPLinkOperation.ReadFlash:
                self._handle_sync_data_read_flash(sync_data)

            case DAPLinkOperation.SelectProgFile:
                self._handle_sync_data_select_prog_file(sync_data)

    def _handle_sync_data_refresh_dap(self, sync_data: dict):
        item_count = self.dap_comboBox.count()
        last_dap_devices = [self.dap_comboBox.itemText(i) for i in range(item_count)]
        item_data = [self.dap_comboBox.itemData(i, Qt.ItemDataRole.UserRole) for i in range(item_count)]
        current_dap_devices = sync_data.get('data', [])
        if current_dap_devices:
            for i, (device, serial_number) in enumerate(current_dap_devices):
                # 先判断当前device在不在last_dap_devices里
                if device in last_dap_devices:
                    if serial_number in item_data:
                        continue
                    else:
                        self.dap_comboBox.addItem(device, serial_number)
                else:
                    self.dap_comboBox.addItem(device, serial_number)
        else:
            self.dap_comboBox.clear()

        # 移除已经拔掉的设备
        item_count = self.dap_comboBox.count()
        for i, (device, serial_number) in enumerate(zip(last_dap_devices, item_data)):
            if (device, serial_number) not in current_dap_devices:
                for i in range(item_count):
                    temp_device = self.dap_comboBox.itemText(i)
                    temp_serial_number = self.dap_comboBox.itemData(i, Qt.ItemDataRole.UserRole)
                    if temp_device == device and temp_serial_number == serial_number:
                        self.dap_comboBox.removeItem(i)
                        break
        if self.dap_comboBox.count() > 0:
            self.dap_comboBox.setToolTip(f"{self.dap_comboBox.currentText()} {self.dap_comboBox.currentData(Qt.ItemDataRole.UserRole)}")
        else:
            self.dap_comboBox.setToolTip("请插入DAP设备或刷新设备")

        item_count = self.dap_comboBox.count()
        for i in range(item_count):
            device = self.dap_comboBox.itemText(i)
            serial_number = self.dap_comboBox.itemData(i, Qt.ItemDataRole.UserRole)
            self.dap_comboBox.setItemData(i, f"{device} {serial_number}", Qt.ItemDataRole.ToolTipRole)

        QTimer.singleShot(1000, partial(self._dap_comboBox_activated, None))

    def _handle_sync_data_select_dap(self, sync_data: dict):
        pass

    def _handle_sync_data_read_id(self, sync_data: dict):
        data = sync_data.get('data', [])
        if data and len(data) == 3:
            debug_id, ap_id, cpu_id = data
            self.label_4.setText(f"{debug_id}")
            self.label_5.setText(f"{ap_id}")
            self.label_6.setText(f"{cpu_id}")
        else:
            self.label_4.setText("error")
            self.label_5.setText("error")
            self.label_6.setText("error")
            logging.error("Invalid data received for ReadID operation.")

    def _handle_sync_data_reset_target(self, sync_data: dict):
        reset_mode = sync_data.get('message', 'unknown')
        logging.info(f"target reset mode: {reset_mode}")
        self._handle_sync_data_read_id(sync_data)

    def _handle_sync_data_erase_target(self, sync_data: dict):
        suboperation = sync_data.get('suboperation')
        if not suboperation:
            logging.error("no suboperation in sync data for Erase operation.")
            return
        self._handle_sync_data_suboperation(sync_data)

    def _handle_sync_data_program_target(self, sync_data: dict):
        suboperation = sync_data.get('suboperation')
        if not suboperation:
            logging.error("no suboperation in sync data for Download operation.")
            return
        self._handle_sync_data_suboperation(sync_data)

    def _handle_sync_data_read_flash(self, sync_data: dict):
        self._handle_sync_data_progress(sync_data, "R:")
        data = sync_data.get('data', [])
        flash_data = data[0]
        addr = data[1]
        size = data[2]
        flash_data_table_dialog = FlashDataTableDialog(self)
        flash_data_table_dialog.set_table_data(flash_data, addr, size)
        res = flash_data_table_dialog.exec_()
        if res == QDialog.Accepted:
            logging.info("flash data table dialog accepted.")
        elif res == QDialog.Rejected:
            logging.info("flash data table dialog rejected.")

    def _handle_sync_data_select_prog_file(self, sync_data: dict):
        data = sync_data.get('data', [])
        if data and len(data) == 2:
            fpath, file_type = data
            file_name = fpath.split('/')[-1]
            self.label_8.setText(f"{file_name}")
            self.label_8.setToolTip(f"{fpath}")
        else:
            self.label_8.setText("null")
            self.label_8.setToolTip("null")
            logging.error("Invalid data received for SelectProgFile operation.")

    def _handle_sync_data_suboperation(self, sync_data: dict):
        operation = sync_data.get('operation')
        suboperation = sync_data.get('suboperation')
        if operation is None or suboperation is None:
            logging.error("operation or suboperation is None in sync data.")
            return
        logging.info(f"{operation.value}.{suboperation.value} completed.")
        match suboperation:
            case DAPLinkOperation.DownloadAlgorithm:
                self._handle_sync_data_read_id(sync_data)

            case DAPLinkOperation.Init:
                pass

            case DAPLinkOperation.UnInit:
                pass

            case DAPLinkOperation.Erase:
                self._handle_sync_data_progress(sync_data, "E:")

            case DAPLinkOperation.Program:
                self._handle_sync_data_progress(sync_data, "P:")

            case DAPLinkOperation.Reset:
                self._handle_sync_data_reset_target(sync_data)

    def _handle_sync_data_progress(self, sync_data: dict, operation: str):
        progress = sync_data.get('progress', 0)
        self._set_progress_value(progress, operation)

    def _set_progress_value(self, value: int, operation: str = "null:"):
        if isinstance(value, int) and 0 <= value <= 100:
            self.label_9.setText(operation)
            self.progressBar.setValue(value)
        else:
            self.label_9.setText("null:")
            logging.error("Invalid progress value received.")

    def _handle_log(self, msg: str, level: int):
        if level >= logging.ERROR:
            self.log_textBrowser.setTextColor(Qt.GlobalColor.red)
        else:
            self.log_textBrowser.setTextColor(Qt.GlobalColor.black)
        self.log_textBrowser.append(msg)
        # 超过阈值时清理最前面的内容
        doc = self.log_textBrowser.document()
        if doc.blockCount() > self.log_text_max_lines:
            # 计算要删除的字符数（前N行）
            block = doc.firstBlock()
            remove_chars = 0
            for _ in range(self.log_text_trim_lines):
                remove_chars += block.length()
                block = block.next()
            cursor = self.log_textBrowser.textCursor()
            cursor.setPosition(0)
            cursor.setPosition(remove_chars, cursor.KeepAnchor)
            cursor.removeSelectedText()


class LoggingHandler(logging.Handler):
    Max_Lines = 1024
    Trim_Lines = 768
    def __init__(self, log_signal):
        super().__init__()
        self.setLevel(logging.INFO)
        self.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        self.log_signal = log_signal

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg, record.levelno)
