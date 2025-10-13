import time
import copy
import logging
import ctypes
from PyQt5.QtCore import QThread, pyqtSignal
from enum import Enum
from src.dap.dap_handle import DAPHandler
from src.dap.flash_algo import ParseElfFile, ParsePdscFile
from src.dap.cortex_m import ExecuteOperation
from src.component.hex_bin_tool import HexBinTool


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
    SelectProgFile = "SelectProgFile"


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
        self.hex_bin_tool = HexBinTool()
        self.sync_data = DAPLinkSyncData.get_sync_data()
        self.sync_data_flag = False
        self.select_flag = False
        self.prog_file = {
            'path': '',
            'type': '',  # 'bin', 'hex'
        }
        self.parse_algorithm_flag = {
            'device': '',
            'path': '',
        }

    def run(self):
        time_out = 0
        while not self.sync_data_flag:
            self.msleep(1)
            time_out += 1
            if time_out > 2000:
                logging.error("DAPLinkHandleThread wait sync_data_flag timeout.")
                return
        self.sync_data_flag = False
        operation = self.sync_data.get('operation', None)
        if operation is None:
            logging.error("No operation specified for DAPLinkHandleThread.")
            return
        res = False
        start_time = time.time()
        match operation:
            case DAPLinkOperation.RefreshDAP:
                res = self._refresh_dap_devices()

            case DAPLinkOperation.SelectDAP:
                res = self._select_dap_device()

            case DAPLinkOperation.ReadID:
                res = self._read_id()

            case DAPLinkOperation.Reset:
                res = self._reset_target()

            case DAPLinkOperation.Erase:
                res = self._erase_target()

            case DAPLinkOperation.Program:
                res = self._program_target()

            case DAPLinkOperation.ReadFlash:
                res = self._read_flash()

            case DAPLinkOperation.GetDeviceInfo:
                res = self._get_device_info()

            case DAPLinkOperation.SelectProgFile:
                res = self._select_prog_file()
        if not res:
            logging.error(f"DAPLinkHandleThread operation {operation} failed.")
        else:
            end_time = time.time()
            logging.info(f"DAPLinkHandleThread operation {operation} completed in {end_time - start_time:.2f} seconds.")

    def _refresh_dap_devices(self) -> bool:
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
        return True

    def _select_dap_device(self) -> bool:
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
        return True

    def _read_id(self) -> bool:
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
        return True

    def _reset_target(self) -> bool:
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.Reset
        sync_data['status'] = False
        data = self.sync_data.get('data', [])
        settings_data = data[1]
        if self._reset(copy.deepcopy(sync_data), settings_data) is False:
            logging.error("Reset target error.")
            return False
        return True

    def _erase_target(self) -> bool:
        data = self.sync_data.get('data', [])
        settings_data = data[2]
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.Erase
        sync_data['status'] = False
        if self.dap_handle.target_flash_operation_init() is False:
            return False
        if self._download_algorithm(copy.deepcopy(sync_data), settings_data) is False:
            return False
        if self._init(copy.deepcopy(sync_data), 1) is False:
            return False
        erase_data = data[1]
        if erase_data[0] < self.parse.flash_device.DevAdr or \
                erase_data[0] >= (self.parse.flash_device.DevAdr + self.parse.flash_device.szDev):
                logging.error("Erase address out of range.")
                return False
        if erase_data[1] == 0:
            logging.error("Erase size is 0.")
            return False
        if self._erase_target_erase_auto(copy.deepcopy(sync_data), erase_data[0], erase_data[1]) is False:
            return False
        if self._uninit(copy.deepcopy(sync_data), 1) is False:
            return False
        if self.dap_handle.target_flash_operation_uninit() is False:
            return False
        return True

    def _program_target(self) -> bool:
        if self.prog_file['path'] == '' or self.prog_file['type'] == '' \
            or self.prog_file['type'] not in ['bin', 'hex']:
            logging.error("no program file selected or file type error.")
            return False
        data = self.sync_data.get('data', [])
        settings_data = data[1]
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.Program
        sync_data['status'] = False
        prog_info = self.hex_bin_tool.get_parse_data_info()
        if self.prog_file['type'] == 'bin':
            bin_data = self.hex_bin_tool.bin_from_from_file(self.prog_file['path'])
            bin_data = self.hex_bin_tool.check_data_to_align_4(bin_data)
            if bin_data is None:
                logging.error("Failed to parse bin file.")
                return False
            prog_info = bin_data
        elif self.prog_file['type'] == 'hex':
            hex_data = self.hex_bin_tool.hex_to_bin_from_file(self.prog_file['path'])
            hex_data = self.hex_bin_tool.check_data_to_align_4(hex_data)
            if hex_data is None:
                logging.error("Failed to parse hex file.")
                return False
            prog_info = hex_data

        start_time = time.time()
        if self.dap_handle.target_flash_operation_init() is False:
            return False
        if self._download_algorithm(copy.deepcopy(sync_data), settings_data) is False:
            return False

        if prog_info['type'] == 'bin':
            if prog_info['count'] != 1:
                logging.error("Bin file should contain only one data segment.")
                return False
            prog_info['addr'][0] = self.parse.flash_device.DevAdr
            logging.info(f"set bin file program start address to 0x{prog_info['addr'][0]:08X}")

        if settings_data['dap']['erase'] == "不擦除":
            # 检查目标下载区域是否存在非0xFF数据
            if self._check_select_dap():
                if self.dap_handle.config_dap_device():
                    for i in range(prog_info['count']):
                        buffer = []
                        if self.dap_handle.read_target_flash(prog_info['addr'][i], prog_info['size'][i], buffer):
                            for b in buffer:
                                if b != 0xFFFFFFFF:
                                    logging.error("Target flash is not empty, please erase flash before programming.")
                                    self.dap_handle.unconfig_dap_device()
                                    return False
                        else:
                            logging.error("Failed to read target flash for verification.")
                            self.dap_handle.unconfig_dap_device()
                            return False
                    self.dap_handle.unconfig_dap_device()

        elif settings_data['dap']['erase'] in ["扇区擦除", "全片擦除"]:
            if self._init(copy.deepcopy(sync_data), 1) is False:
                return False
            if settings_data['dap']['erase'] == "扇区擦除":
                for i in range(prog_info['count']):
                    prog_addr = prog_info['addr'][i]
                    prog_size = prog_info['size'][i]
                    if self._erase_target_erase_auto(copy.deepcopy(sync_data), prog_info['addr'][0], prog_info['size'][0]) is False:
                        return False
            elif settings_data['dap']['erase'] == "全片擦除":
                if self._erase_target_erase_chip(copy.deepcopy(sync_data)) is False:
                    return False
            if self._uninit(copy.deepcopy(sync_data), 1) is False:
                return False

        if self._init(copy.deepcopy(sync_data), 2) is False:
            return False

        total_size = 0
        for i in range(prog_info['count']):
            prog_addr = prog_info['addr'][i]
            prog_size = prog_info['size'][i]
            prog_data = prog_info['data'][i]
            total_size += prog_size
            if prog_size == 0:
                continue
            if self._program(copy.deepcopy(sync_data), prog_addr, prog_size, prog_data) is False:
                return False

        if self._uninit(copy.deepcopy(sync_data), 2) is False:
            return False

        if settings_data['dap']['verify'] is True:
            logging.info("start program verify...")
            for i in range(prog_info['count']):
                prog_addr = prog_info['addr'][i]
                prog_size = prog_info['size'][i]
                prog_data = prog_info['data'][i]
                if prog_size == 0:
                    continue
                verify_data = self.hex_bin_tool.bytes_to_dword(prog_data, prog_size, format='little')
                if verify_data is None:
                    logging.error("program verify data error.")
                    return False
                verify_value = self.dap_handle.get_xor_value(verify_data, len(verify_data))
                if self.dap_handle.verify_target_data(prog_addr, prog_size, verify_value) is False:
                    logging.error("program verify error.")
                    return False
            logging.info("program verify success.")

        if self.dap_handle.target_flash_operation_uninit() is False:
            return False

        if settings_data['dap']['run'] is True:
            if self._reset(copy.deepcopy(sync_data), settings_data) is False:
                logging.error("Reset target after program error.")
                return False
        end_time = time.time()
        take_time = end_time - start_time
        logging.info(f"program takes {(take_time * 1000):.2f}ms. speed: {total_size / 1024 / take_time:.2f} KB/s")
        return True

    def _read_flash(self) -> bool:
        data = self.sync_data.get('data', [])
        if len(data) != 3:
            logging.error("Read flash data error.")
            return False
        settings_data = data[2]
        if self._parse_algorithm(settings_data) is False:
            return False
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.ReadFlash
        sync_data['status'] = False
        read_data = data[1]
        read_start_addr = read_data[0] - read_data[0] % 4
        read_end_addr = read_data[0] + read_data[1]
        if read_start_addr < self.parse.flash_device.DevAdr or \
            read_start_addr >= (self.parse.flash_device.DevAdr + self.parse.flash_device.szDev):
            logging.error("Read flash address out of range.")
            return False
        if read_data[1] == 0:
            logging.error("Read flash size is 0.")
            return False

        if read_end_addr >= (self.parse.flash_device.DevAdr + self.parse.flash_device.szDev):
            logging.warning(f"Read flash end address out of range(end address: 0x{read_end_addr:08X}), only read to max address.")
            read_end_addr = self.parse.flash_device.DevAdr + self.parse.flash_device.szDev

        read_size = read_end_addr - read_start_addr
        real_read_size = read_size if read_size % 4 == 0 else (read_size + (4 - read_size % 4))
        buffer = []
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.read_target_flash(read_start_addr, real_read_size, buffer):
                    sync_data['data'] = [buffer.copy(), read_start_addr, read_size]
                    sync_data['status'] = True
                    sync_data['progress'] = 100
                self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        return True

    def _reset(self, sync_data, settings_data) -> bool:
        reset_mode = settings_data['dap']['reset']
        if reset_mode == "自动":
            reset_mode = 'software'
        elif reset_mode == "软件复位":
            reset_mode = 'software'
        elif reset_mode == "硬件复位":
            reset_mode = 'hardware'
        else:
            reset_mode = 'software'
        sync_data['suboperation'] = DAPLinkOperation.Reset
        sync_data['status'] = False
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.reset_target(reset_mode):
                    sync_data['data'] = [self.dap_handle.debug_id, self.dap_handle.ap_id, self.dap_handle.cpu_id].copy()
                    sync_data['message'] = reset_mode
                    sync_data['status'] = True
                self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        return True

    def _erase_target_erase_auto(self, sync_data, erase_addr, erase_size) -> bool:
        res = False
        sync_data['suboperation'] = DAPLinkOperation.Erase
        if erase_addr != 0 and erase_size != 0:
            sector_size = self.parse.flash_device.sectors[0].szSector
            erase_start_addr = erase_addr - erase_addr % sector_size
            erase_end_addr = erase_addr + erase_size
            if erase_end_addr >= (self.parse.flash_device.DevAdr + self.parse.flash_device.szDev):
                logging.warning(f"Erase end address out of range(end address: 0x{erase_end_addr:08X}), only erase to max address.")
                erase_end_addr = self.parse.flash_device.DevAdr + self.parse.flash_device.szDev
            # 计算需要擦除的扇区数量
            sector_num = (erase_end_addr - erase_start_addr + sector_size - 1) // sector_size
            if erase_end_addr - erase_start_addr == self.parse.flash_device.szDev:
                if self._erase_target_erase_chip(sync_data):
                    res = True
            else:
                if self._erase_target_erase_sector(sync_data, erase_start_addr, sector_num, sector_size):
                    res = True
        return res

    def _erase_target_erase_chip(self, sync_data) -> bool:
        res = False
        sync_data['suboperation'] = DAPLinkOperation.Erase
        exec_data = ExecuteOperation()
        exec_data.r9 = self.parse.flash_algo.StaticBase
        exec_data.r13 = self.parse.flash_algo.StackPointer
        exec_data.r14 = self.parse.flash_algo.BreakPoint
        exec_data.r15 = self.parse.flash_algo.EraseChip
        exec_data.timeout = self.parse.flash_device.toErase
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
                    exec_data.r9 = self.parse.flash_algo.StaticBase
                    exec_data.r13 = self.parse.flash_algo.StackPointer
                    exec_data.r14 = self.parse.flash_algo.BreakPoint
                    exec_data.r15 = self.parse.flash_algo.EraseSector
                    exec_data.timeout = self.parse.flash_device.toErase
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

    def _program(self, sync_data, start_addr, prog_size, data) -> bool:
        res = False
        sync_data['suboperation'] = DAPLinkOperation.Program
        sync_data['status'] = False
        if start_addr % 4 != 0 or prog_size % 4 != 0:
            logging.error("Program address or size is not aligned to 4 bytes.")
            return False
        if start_addr < self.parse.flash_device.DevAdr or \
            start_addr >= (self.parse.flash_device.DevAdr + self.parse.flash_device.szDev):
            logging.error("Program address out of range.")
            return False
        if prog_size == 0:
            logging.error("Program size is 0.")
            return False
        if prog_size + start_addr > (self.parse.flash_device.DevAdr + self.parse.flash_device.szDev):
            logging.error("Program size out of range.")
            return False

        page_size = self.parse.flash_algo.ProgramBufferSize
        if page_size % 4 != 0:
            logging.error("Flash page size is not aligned to 4 bytes.")
            return False

        exec_data = ExecuteOperation()
        exec_data.r2 = self.parse.flash_algo.ProgramBuffer
        exec_data.r9 = self.parse.flash_algo.StaticBase
        exec_data.r13 = self.parse.flash_algo.StackPointer
        exec_data.r14 = self.parse.flash_algo.BreakPoint
        exec_data.r15 = self.parse.flash_algo.ProgramPage
        exec_data.timeout = self.parse.flash_device.toProg
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                for i in range(prog_size // page_size):
                    sync_data['status'] = False
                    data_offset = i * page_size
                    temp = data[data_offset : data_offset + page_size]
                    write_data = self.hex_bin_tool.bytes_to_dword(temp, page_size)
                    if write_data is None:
                        return False
                    if self.dap_handle.download_data_to_prog_ram(self.parse.flash_algo.ProgramBuffer, write_data, page_size):
                        exec_data.r0 = start_addr + i * page_size
                        exec_data.r1 = page_size
                        if self.dap_handle.target_flash_program(exec_data):
                            sync_data['status'] = True
                            sync_data['progress'] = int((i + 1) * 100 / ((prog_size + page_size - 1) // page_size))
                            self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
                            if i == (prog_size // page_size - 1):
                                res = True
                        else:
                            return False
                    else:
                        return False
                rest_size = prog_size % page_size
                if rest_size != 0:
                    res = False
                    sync_data['status'] = False
                    data_offset = (prog_size // page_size) * page_size
                    temp = data[data_offset : prog_size]
                    write_data = self.hex_bin_tool.bytes_to_dword(temp, rest_size)
                    if write_data is None:
                        return False
                    if self.dap_handle.download_data_to_prog_ram(self.parse.flash_algo.ProgramBuffer, write_data, prog_size % page_size):
                        exec_data.r0 = start_addr + (prog_size // page_size) * page_size
                        exec_data.r1 = prog_size % page_size
                        if self.dap_handle.target_flash_program(exec_data):
                            sync_data['status'] = True
                            sync_data['progress'] = 100
                            res = True
                            self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
                self.dap_handle.unconfig_dap_device()
        return res

    def _download_algorithm(self, sync_data, settings_data) -> bool:
        res = False
        sync_data['suboperation'] = DAPLinkOperation.DownloadAlgorithm
        sync_data['status'] = False
        verify_flag = settings_data['dap']['verify']
        if self._parse_algorithm(settings_data):
            start_addr = self.parse.flash_algo.AlgoStart
            algo = self.parse.flash_algo.AlgoBlob
            algo_size = self.parse.flash_algo.AlgoSize
            algo_list = ctypes.cast(algo, ctypes.POINTER(ctypes.c_uint32))[:algo_size//4]
            if self._check_select_dap():
                if self.dap_handle.config_dap_device():
                    if self.dap_handle.download_algorithm(start_addr, algo_list, algo_size, verify_flag):
                        sync_data['data'] = [self.dap_handle.debug_id, self.dap_handle.ap_id, self.dap_handle.cpu_id].copy()
                        sync_data['status'] = True
                        res = True
                    self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        return res

    def _parse_algorithm(self, settings_data) -> bool:
        device = settings_data['target']['device']
        f_path = settings_data['target']['algorithm']
        if not device or not f_path:
            logging.error("No device or algorithm file specified.")
            return False
        if device == self.parse_algorithm_flag['device'] and \
            f_path == self.parse_algorithm_flag['path']:
            return True
        self.parse = ParseElfFile(f_path, device, print_info=True)
        if self.parse.parse_flag:
            self.parse_algorithm_flag['device'] = device
            self.parse_algorithm_flag['path'] = f_path
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
        exec_data.r0 = self.parse.flash_device.DevAdr       # adr:  Device Base Address
        exec_data.r1 = 0                                    # clk:  Clock Frequency (Hz)
        exec_data.r2 = fnc                                  # fnc:  Function Code (1 - Erase, 2 - Program, 3 - Verify)
        exec_data.r9 = self.parse.flash_algo.StaticBase
        exec_data.r13 = self.parse.flash_algo.StackPointer
        exec_data.r14 = self.parse.flash_algo.BreakPoint
        exec_data.r15 = self.parse.flash_algo.Init
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
        exec_data.r9 = self.parse.flash_algo.StaticBase
        exec_data.r13 = self.parse.flash_algo.StackPointer
        exec_data.r14 = self.parse.flash_algo.BreakPoint
        exec_data.r15 = self.parse.flash_algo.UnInit
        if self._check_select_dap():
            if self.dap_handle.config_dap_device():
                if self.dap_handle.target_flash_uninit(exec_data):
                    sync_data['status'] = True
                    res = True
                self.dap_handle.unconfig_dap_device()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        return res

    def _check_select_dap(self) -> bool:
        if self.select_flag is False:
            data = self.sync_data.get('data', [])
            if data:
                device, serial_number = data[0]
                if self.dap_handle.select_dap_device_by_intf_desc_and_sn(device, serial_number):
                    self.select_flag = True
        else:
            self.select_flag = False
            current_dap = self.dap_handle.get_selected_dap_device
            if current_dap is not None:
                device, serial_number = self.sync_data.get('data', [('', '')])[0]
                if current_dap['intf_desc'] != device or current_dap['serial_number'] != serial_number:
                    if self.dap_handle.select_dap_device_by_intf_desc_and_sn(device, serial_number):
                        self.select_flag = True
                else:
                    self.select_flag = True
        return self.select_flag

    def _get_device_info(self) -> bool:
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.GetDeviceInfo
        sync_data['status'] = True
        sync_data['data'] = ParsePdscFile.get_all_device_info_from_pdsc()
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        return True

    def _select_prog_file(self) -> bool:
        sync_data = DAPLinkSyncData.get_sync_data()
        sync_data['operation'] = DAPLinkOperation.SelectProgFile
        sync_data['status'] = False
        data = self.sync_data.get('data', [])
        if data and len(data) == 2:
            self.prog_file['path'] = data[0]
            self.prog_file['type'] = data[1]
            sync_data['data'] = data.copy()
            sync_data['status'] = True
        self.dap_link_handle_sync_signal.emit(copy.deepcopy(sync_data))
        return True

    def get_sync_data(self, sync_data: dict):
        self.sync_data = copy.deepcopy(sync_data)
        self.sync_data_flag = True
