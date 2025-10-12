import typing
import ctypes
from ctypes import wintypes
import win32con
from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtWidgets import QWidget
from functools import partial
import logging


user32 = ctypes.windll.user32
RegisterDeviceNotification = user32.RegisterDeviceNotificationW
UnregisterDeviceNotification = user32.UnregisterDeviceNotification


class GUID(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8)
    ]

class DEV_BROADCAST_DEVICEINTERFACE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("dbcc_size", wintypes.DWORD),
        ("dbcc_devicetype", wintypes.DWORD),
        ("dbcc_reserved", wintypes.DWORD),
        ("dbcc_classguid", GUID),
        ("dbcc_name", ctypes.c_wchar * 512)
    ]


class DEV_BROADCAST_HDR(ctypes.Structure):
    _fields_ = [
        ("dbch_size", wintypes.DWORD),
        ("dbch_devicetype", wintypes.DWORD),
        ("dbch_reserved", wintypes.DWORD)
    ]

GUID_DEVINTERFACE_USB_DEVICE = \
    GUID(0xA5DCBF10, 0x6530, 0x11D2, (ctypes.c_ubyte * 8)(0x90, 0x1F, 0x00, 0xC0, 0x4F, 0xB9, 0x51, 0xED))

EVENT_TYPE_GENERIC = 'windows_generic_MSG'

class USBDeviceMonitor(QWidget):
    usb_changed_signal = pyqtSignal()
    def __init__(self, handle_func=None):
        super().__init__()
        self.handle = handle_func
        self.usb_changed_info = {
            'flag': False,
            'type': None,
            'name': [],
            'dir' : False, # True: insert, False: remove
        }
        self.hNotify = []
        self.usb_changed_signal.connect(self._usb_changes_handle)  # type: ignore
        self.start()

    def start(self):
        for guid in [GUID_DEVINTERFACE_USB_DEVICE]:
            dbh = DEV_BROADCAST_DEVICEINTERFACE()
            dbh.dbcc_size = ctypes.sizeof(DEV_BROADCAST_DEVICEINTERFACE)
            dbh.dbcc_devicetype = win32con.DBT_DEVTYP_DEVICEINTERFACE
            dbh.dbcc_classguid = guid
            hNotify = RegisterDeviceNotification(int(self.winId()),
                                                 ctypes.byref(dbh),
                                                 win32con.DEVICE_NOTIFY_WINDOW_HANDLE)
            self.hNotify.append(hNotify)
            if hNotify == win32con.NULL:
                logging.error('RegisterDeviceNotification failed')

    def stop(self):
        for h in self.hNotify:
            if h != win32con.NULL:
                logging.info('UnRegisterDeviceNotification')
                UnregisterDeviceNotification(h)
            else:
                logging.error('the notify handler is NULL')
        self.hNotify.clear()

    def nativeEvent(self, eventType, message) -> typing.Tuple[bool, int]:
        if eventType == EVENT_TYPE_GENERIC:
            msg: wintypes.MSG = wintypes.MSG.from_address(message.__int__())
            if msg.message == win32con.WM_DEVICECHANGE:
                if msg.wParam == win32con.DBT_DEVICEARRIVAL:
                    hdr: DEV_BROADCAST_HDR = DEV_BROADCAST_HDR.from_address(msg.lParam)
                    if hdr.dbch_devicetype == win32con.DBT_DEVTYP_DEVICEINTERFACE:
                        d: DEV_BROADCAST_DEVICEINTERFACE = DEV_BROADCAST_DEVICEINTERFACE.from_address(msg.lParam)
                        self._set_usb_changed_info(d.dbcc_devicetype, d.dbcc_name, True)
                        self.usb_changed_signal.emit() # type: ignore
                elif msg.wParam == win32con.DBT_DEVICEREMOVECOMPLETE:
                    hdr: DEV_BROADCAST_HDR = DEV_BROADCAST_HDR.from_address(msg.lParam)
                    if hdr.dbch_devicetype == win32con.DBT_DEVTYP_DEVICEINTERFACE:
                        d: DEV_BROADCAST_DEVICEINTERFACE = DEV_BROADCAST_DEVICEINTERFACE.from_address(msg.lParam)
                        self._set_usb_changed_info(d.dbcc_devicetype, d.dbcc_name, False)
                        self.usb_changed_signal.emit() # type: ignore

        return super().nativeEvent(eventType, message)

    def _set_usb_changed_info(self, type, name: str, dir: bool):
        self.usb_changed_info['flag'] = True
        self.usb_changed_info['type'] = type
        self.usb_changed_info['name'].append(name)
        self.usb_changed_info['dir'] = dir

    def _reset_usb_changed_info(self):
        self.usb_changed_info['flag'] = False
        self.usb_changed_info['type'] = None
        self.usb_changed_info['name'].clear()
        self.usb_changed_info['dir'] = False

    def _usb_changes_handle(self):
        if self.handle is not None:
                QTimer.singleShot(500, partial(self.handle))