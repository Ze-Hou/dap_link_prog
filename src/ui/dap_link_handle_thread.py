import sys
import os
import copy
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from dap.dap_handle import DAPHandler
from dap.flash_algo import PraseElfFile, PrasePdscFile
from dap.cortex_m import ExecuteOperation

from PyQt5.QtCore import QThread, pyqtSignal
from enum import Enum

class DAPLinkOperation(Enum):
    RefreshDAP = "RefreshDAP"
    SelectDAP = "SelectDAP"
    ReadID = "ReadID"
    Reset = "Reset"
    Init = "Init"
    UnInit = "UnInit"
    Erase = "Erase"
    Program = "Program"
    ReadFlash = "ReadFlash"
    GetDeviceInfo = "GetDeviceInfo"
    DownloadAlgorithm = "DownloadAlgorithm"


class DAPLinkSyncData:
    sync_data: dict = {
        'operation': None,
        'suboperation': None,
        'message': '',
        'data': [],
        'status': None,
        'progress': 0,
    }

    @classmethod
    def get_sync_data(cls):
        return copy.deepcopy(cls.sync_data)

class DAPLinkHandleThread(QThread):
    dap_link_handle_sync_signal = pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        self.dap_handle = DAPHandler()
        self.sync_data = DAPLinkSyncData.get_sync_data()
        self.select_flag = False

    def run(self):
        operation = self.sync_data.get('operation', None)
        if operation is None:
            logging.error("No operation specified for DAPLinkHandleThread.")
            return

        match operation:
            case DAPLinkOperation.RefreshDAP:
                self._refresh_dap_devices()

            case DAPLinkOperation.SelectDAP:
                self._select_dap_device()

            case DAPLinkOperation.ReadID:
                self._read_id()

            case DAPLinkOperation.Reset:
                self._reset_target()

            case DAPLinkOperation.Erase:
                self._erase_target()

            case DAPLinkOperation.Program:
                pass

            case DAPLinkOperation.ReadFlash:
                self._read_flash()

            case DAPLinkOperation.GetDeviceInfo:
                self._get_device_info()

    def _refresh_dap_devices(self):
        sync_data = DAPLinkSyncData.get_sync_data()
        current_dap_devices = []
        dap_devices = self.dap_handle.get_dap_devices()
        if dap_devices is not None:
            self.dap_handle.unconfig_all_dap_devices()
            for _, dap_device in enumerate(dap_devices):
                device = dap_device.get('intf_desc', 'Unknown Device')
                serial_number = dap_device.get('serial_number', '')
                current_dap_devices.append((device, serial_number))

        sync_data['operation'] = DAPLinkOperation.RefreshDAP
        sync_data['data'] = current_dap_devices.copy()
        sync_data['status'] = True
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))

    def _select_dap_device(self):
        self.select_flag = False
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.SelectDAP
        sync_data['status'] = False
        data = self.sync_data.get('data', [])
        if data:
            device, serial_number = data[0]
            if self.dap_handle.select_dap_device_by_intf_desc_and_sn(device, serial_number):
                sync_data['status'] = True
                self.select_flag = True
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))

    def _read_id(self):
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.ReadID
        sync_data['status'] = False
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.get_target_id():
                    sync_data['data'] = [self.dap_handle.debug_id, self.dap_handle.ap_id, self.dap_handle.cpu_id].copy()
                    sync_data['status'] = True
                self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))

    def _reset_target(self):
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.Reset
        sync_data['status'] = False
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.reset_target(self.sync_data.get('message', 'software')):
                    sync_data['operation'] = DAPLinkOperation.ReadID
                    sync_data['data'] = [self.dap_handle.debug_id, self.dap_handle.ap_id, self.dap_handle.cpu_id].copy()
                    sync_data['status'] = True
                self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))

    """
    /*
    Mandatory Flash Programming Functions (Called by FlashOS):
                    int Init        (unsigned long adr,   // Initialize Flash
                                    unsigned long clk,
                                    unsigned long fnc);
                    int UnInit      (unsigned long fnc);  // De-initialize Flash
                    int EraseSector (unsigned long adr);  // Erase Sector Function
                    int ProgramPage (unsigned long adr,   // Program Page Function
                                    unsigned long sz,
                                    unsigned char *buf);

    Optional  Flash Programming Functions (Called by FlashOS):
                    int BlankCheck  (unsigned long adr,   // Blank Check
                                    unsigned long sz,
                                    unsigned char pat);
                    int EraseChip   (void);               // Erase complete Device
        unsigned long Verify      (unsigned long adr,   // Verify Function
                                    unsigned long sz,
                                    unsigned char *buf);

        - BlanckCheck  is necessary if Flash space is not mapped into CPU memory space
        - Verify       is necessary if Flash space is not mapped into CPU memory space
        - if EraseChip is not provided than EraseSector for all sectors is called
    */
    """

    def _erase_target(self):
        data = self.sync_data.get('data', [])
        settings_data = data[2]
        erase = settings_data['dap']['erase']
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.Erase
        sync_data['status'] = False
        if self._download_algorithm(copy.deepcopy(sync_data), settings_data) is False:
            return False
        if self._init(copy.deepcopy(sync_data), 1) is False:
            return False
        if self._erase_target_erase(copy.deepcopy(sync_data), erase) is False:
            return False
        if self._uninit(copy.deepcopy(sync_data), 1) is False:
            return False

    def _read_flash(self):
        data = self.sync_data.get('data', [])
        settings_data = data[2]
        if self._prase_algorithm(settings_data) is False:
            return False
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.ReadFlash
        sync_data['status'] = False
        data = self.sync_data.get('data', [])
        if len(data) != 3:
            logging.error("Read flash data error.")
            return
        read_data = data[1]
        if read_data[0] < self.prase.flash_device.DevAdr or \
            read_data[0] >= (self.prase.flash_device.DevAdr + self.prase.flash_device.szDev):
            logging.error("Read flash address out of range.")
            return False
        if read_data[1] == 0:
            logging.error("Read flash size is 0.")
            return False

        read_start_addr = read_data[0] - read_data[0] % 4
        read_end_addr = read_data[0] + read_data[1]
        if read_end_addr >= (self.prase.flash_device.DevAdr + self.prase.flash_device.szDev):
            logging.warning(f"Read flash end address out of range(end address: 0x{read_end_addr:08X}), only read to max address.")
            read_end_addr = self.prase.flash_device.DevAdr + self.prase.flash_device.szDev

        read_size = read_end_addr - read_start_addr

        buffer = []
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.read_target_flash(read_start_addr, read_size, buffer):
                    sync_data['data'] = buffer.copy()
                    sync_data['status'] = True
                self.dap_handle.unconfig_dap_device()
        print(len(buffer), "\n")
        for i in range(len(buffer)):
            print(f"0x{buffer[i]:08X}")
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))

    def _erase_target_erase(self, sync_data, erase) -> bool:
        res = False
        sync_data['suboperation'] = DAPLinkOperation.Erase
        data = self.sync_data.get('data', [])
        if len(data) == 3:
            erase_data = data[1]
            if erase_data[0] < self.prase.flash_device.DevAdr or \
                erase_data[0] >= (self.prase.flash_device.DevAdr + self.prase.flash_device.szDev):
                logging.error("Erase address out of range.")
                return False
            if erase_data[1] == 0:
                logging.error("Erase size is 0.")
                return False
        else:
            erase_data = [0, 0]
        erase_addr = erase_data[0]
        erase_size = erase_data[1]
        if erase_addr == 0 and erase_size == 0:
            pass
        else:
            sector_size = self.prase.flash_device.sectors[0].szSector
            erase_start_addr = erase_addr - erase_addr % sector_size
            erase_end_addr = erase_addr + erase_size
            if erase_end_addr >= (self.prase.flash_device.DevAdr + self.prase.flash_device.szDev):
                logging.warning(f"Erase end address out of range(end address: 0x{erase_end_addr:08X}), only erase to max address.")
                erase_end_addr = self.prase.flash_device.DevAdr + self.prase.flash_device.szDev
            # 计算需要擦除的扇区数量
            sector_num = (erase_end_addr - erase_start_addr + sector_size - 1) // sector_size
            if erase_end_addr - erase_start_addr == self.prase.flash_device.szDev:
                if self._erase_target_erase_chip(sync_data):
                    res = True
            else:
                if self._erase_target_erase_sector(sync_data, erase_start_addr, sector_num, sector_size):
                    res = True
        return res

    def _erase_target_erase_chip(self, sync_data) -> bool:
        res = False
        exec_data = ExecuteOperation()
        exec_data.r9 = self.prase.flash_algo.StaticBase
        exec_data.r13 = self.prase.flash_algo.StackPointer
        exec_data.r14 = self.prase.flash_algo.BreakPoint
        exec_data.r15 = self.prase.flash_algo.EraseChip
        exec_data.timeout = self.prase.flash_device.toErase
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.target_flash_erase(exec_data):
                    sync_data['status'] = True
                    sync_data['progress'] = 100
                    res = True
                self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        return res

    def _erase_target_erase_sector(self, sync_data, start_addr, erase_num, sector_size) -> bool:
        res = False
        exec_data = ExecuteOperation()
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                for i in range(erase_num):
                    sync_data['status'] = False
                    exec_data.r0 = start_addr + sector_size * i
                    exec_data.r9 = self.prase.flash_algo.StaticBase
                    exec_data.r13 = self.prase.flash_algo.StackPointer
                    exec_data.r14 = self.prase.flash_algo.BreakPoint
                    exec_data.r15 = self.prase.flash_algo.EraseSector
                    exec_data.timeout = self.prase.flash_device.toErase
                    if self.dap_handle.target_flash_erase(exec_data):
                        sync_data['status'] = True
                        sync_data['progress'] = int((i + 1) * 100 / erase_num)
                        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
                        if i == (erase_num - 1):
                            res = True
                    else:
                        break
                self.dap_handle.unconfig_dap_device()
        return res

    def _download_algorithm(self, sync_data, settings_data) -> bool:
        res = False
        sync_data['suboperation'] = DAPLinkOperation.DownloadAlgorithm
        sync_data['status'] = False
        verify_flag = settings_data['dap']['verify']
        if self._prase_algorithm(settings_data):
            start_addr = self.prase.flash_algo.AlgoStart
            algo = self.prase.flash_algo.AlgoBlob
            algo_size = self.prase.flash_algo.AlgoSize
            if self._check_select_dap():
                if self.dap_handle.config_dap_device():
                    if self.dap_handle.download_algorithm(start_addr, algo, algo_size, verify_flag):
                        sync_data['data'] = [self.dap_handle.debug_id, self.dap_handle.ap_id, self.dap_handle.cpu_id].copy()
                        sync_data['status'] = True
                        res = True
                    self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        self._download_algorithm_flag = True
        return res

    def _prase_algorithm(self, settings_data) -> bool:
        device = settings_data['target']['device']
        f_path = settings_data['target']['algorithm']
        self.prase = PraseElfFile(f_path, device, print_info=True)
        if self.prase.prase_flag:
            return True
        return False

    def _init(self, sync_data, fnc: int) -> bool:
        """目标初始化

        Args:
            sync_data (DAPLinkSyncData): 同步操作数据
            fnc (int): 功能代码(1 - Erase, 2 - Program, 3 - Verify)

        Returns:
            bool: true: 成功, false: 失败
        """
        res = False
        sync_data['suboperation'] = DAPLinkOperation.Init
        sync_data['status'] = False
        exec_data = ExecuteOperation()
        exec_data.r0 = self.prase.flash_device.DevAdr       # adr:  Device Base Address
        exec_data.r1 = 0                                    # clk:  Clock Frequency (Hz)
        exec_data.r2 = fnc                                  # fnc:  Function Code (1 - Erase, 2 - Program, 3 - Verify)
        exec_data.r9 = self.prase.flash_algo.StaticBase
        exec_data.r13 = self.prase.flash_algo.StackPointer
        exec_data.r14 = self.prase.flash_algo.BreakPoint
        exec_data.r15 = self.prase.flash_algo.Init
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.target_flash_init(exec_data):
                    sync_data['status'] = True
                    res = True
                self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        return res

    def _uninit(self, sync_data, fnc) -> bool:
        """目标去初始化

        Args:
            sync_data (DAPLinkSyncData): 同步操作数据
            fnc (int): 功能代码(1 - Erase, 2 - Program, 3 - Verify)

        Returns:
            bool: true: 成功, false: 失败
        """
        res = False
        sync_data['suboperation'] = DAPLinkOperation.UnInit
        sync_data['status'] = False
        exec_data = ExecuteOperation()
        exec_data.r0 = fnc                                  # fnc:  Function Code (1 - Erase, 2 - Program, 3 - Verify)
        exec_data.r9 = self.prase.flash_algo.StaticBase
        exec_data.r13 = self.prase.flash_algo.StackPointer
        exec_data.r14 = self.prase.flash_algo.BreakPoint
        exec_data.r15 = self.prase.flash_algo.UnInit
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.target_flash_uninit(exec_data):
                    sync_data['status'] = True
                    res = True
                self.dap_handle.unconfig_dap_device()
        return res

    def _check_select_dap(self) -> bool:
        if self.select_flag is False:
            data = self.sync_data.get('data', [])
            if data:
                device, serial_number = data[0]
                if self.dap_handle.select_dap_device_by_intf_desc_and_sn(device, serial_number):
                    self.select_flag = True
        else:
            print("DAP device already selected.")
            self.select_flag = False
            current_dap = self.dap_handle.get_selected_dap_device
            if current_dap is not None:
                device, serial_number = self.sync_data.get('data', [('', '')])[0]
                print("current dap:", current_dap)
                if current_dap['intf_desc'] != device or current_dap['serial_number'] != serial_number:
                    if self.dap_handle.select_dap_device_by_intf_desc_and_sn(device, serial_number):
                        self.select_flag = True
                else:
                    self.select_flag = True
        return self.select_flag

    def _get_device_info(self):
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.GetDeviceInfo
        sync_data['status'] = True
        sync_data['data'] = PrasePdscFile.get_all_device_info_from_pdsc()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))

    def get_sync_data(self, sync_data: dict):
        self.sync_data = copy.deepcopy(sync_data)
        print(self.sync_data)
