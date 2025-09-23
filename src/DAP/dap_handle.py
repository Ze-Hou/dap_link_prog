import usb.core
import usb.util
from usb_device.usb_device_handle import USBDeviceHandle
from .cortex_m import DEBUG_REG, SCB_REG, ROM_TABLE, ExecuteOperation
import time
import logging


"""
DAPHandler类用于处理DAP设备的连接、配置和操作。
"""
class DAPHandler:
    def __init__(self):
        self.usb_device_handle = USBDeviceHandle()
        self.dap_swj_clock = 5000000  # DAP SWJ时钟频率，默认5MHz
        self.dap_packet_size = 64  # DAP数据包大小，默认64字节
        self.dap_packet_count = 64   # DAP数据包数量，默认64个
        self.firmware_version = "Unknown"  # DAP固件版本

        """
        DAP capabilities (BYTE)
        Bit 0: SWD 串行线调试通信支持 (1=支持, 0=不支持)
        Bit 1: JTAG 通信支持 (1=支持, 0=不支持)
        Bit 2: SWO UART 支持 (1=支持, 0=不支持)
        Bit 3: SWO Manchester 支持 (1=支持, 0=不支持)
        Bit 4: 原子命令支持 (1=支持, 0=不支持)
        Bit 5: 测试域定时器支持 (1=支持, 0=不支持)
        Bit 6: SWO 流式跟踪支持 (1=支持, 0=不支持)
        """
        self.dap_caps = 0x00

        self.debug_id = "Unknown"  # 目标调试ID
        self.ap_id = "Unknown"  # 目标APID
        self.cpu_id = "Unknown"  # 目标CPUID

        self._coresight_component_table = ROM_TABLE().get_component_table()

    @property
    def get_selected_dap_device(self):
        return self.usb_device_handle.get_selected_dap_device

    def get_dap_devices(self):
        return self.usb_device_handle.get_dap_devices()

    def select_dap_device_by_index(self, device_index=0):
        return self.usb_device_handle.select_dap_device_by_index(device_index)

    def select_dap_device_by_sn(self, serial_number):
        return self.usb_device_handle.select_dap_device_by_sn(serial_number)

    def select_dap_device_by_intf_desc_and_sn(self, intf_desc, serial_number):
        return self.usb_device_handle.select_dap_device_by_intf_desc_and_sn(intf_desc, serial_number)

    def config_dap_device(self):
        return self.usb_device_handle.config_dap_device()

    def unconfig_dap_device(self):
        return self.usb_device_handle.unconfig_dap_device()

    def unconfig_all_dap_devices(self):
        return self.usb_device_handle.unconfig_all_dap_devices()

    def set_dap_swj_clock(self, clock_hz=5000000):
        if clock_hz == 0:
            clock_hz = self.dap_swj_clock
        self.dap_swj_clock = clock_hz

    def get_target_id(self) -> bool:
        if self._read_target_id() is False:
            return False

        if self._stop_dap_device() is False:
            return False

        logging.info(f"Debug ID: {self.debug_id}, AP ID: {self.ap_id}, CPU ID: {self.cpu_id}")

        return True

    def reset_target(self, reset_mode='software') -> bool:
        if self._read_target_id() is False:
            return False

        if reset_mode not in ['hardware', 'software']:
            logging.error("Invalid reset mode. Use 'hardware' or 'software'.")
            return False

        if reset_mode == 'software':
            scb_reg = SCB_REG(self._coresight_component_table['SCS_BASE'])

            if self._reset_and_halt_target() is False:
                return False
            self._write_reg(DEBUG_REG.DEMCR, 0x00000000)
            scb_aircr = self._read_reg(scb_reg.AIRCR)  # 读出AIRCR寄存器
            self._write_reg(scb_reg.AIRCR, ((0x05FA << 16) | \
                                                (scb_aircr & (0x7 << 8)) | \
                                                (0x1 << 2)))  # 软件复位

            time.sleep(0.05)  # 等待复位完成
        else:
            retry_count = 10
            while True:
                self._set_dap_swj_pin(0x00, 0x80, 0x00000000)
                time.sleep(0.05)
                self._set_dap_swj_pin(0x80, 0x80, 0x00000000)
                res = self._set_dap_swj_pin(0x00, 0x00, 0x00000000)
                time.sleep(0.05)
                retry_count -= 1
                if (res & 0x80) | (retry_count <= 0):
                    break

        if self._stop_dap_device() is False:
            return False

        return True

    def download_algorithm(self, start_addr, algorithm, algorithm_size, verify_flag: bool) -> bool:
        """
        注意使用该函数结束不会停止DAP设备。
        """
        if self._reset_and_halt_target() is False:
                return False
        if not algorithm:
            return False
        algorithm_size = (algorithm_size + 4 -1) // 4
        use_for_data_size = self.dap_packet_size - 5
        use_for_data_size = ((use_for_data_size - (use_for_data_size % 4)) & 0xFFFF) // 4
        if self._set_write_address(start_addr) is False:
            return False
        transfer_count = (algorithm_size + use_for_data_size - 1) // use_for_data_size
        start_index = 0
        end_index = 0
        verify_value = self.get_xor_value(algorithm, algorithm_size)
        buffer = usb.util.create_buffer(self.dap_packet_size)
        for _ in range(transfer_count//self.dap_packet_count):
            for _ in range(self.dap_packet_count):
                end_index = start_index + use_for_data_size
                if self._dap_transfer_block(0x00, use_for_data_size, 0x0D, algorithm[start_index:end_index]) is False:
                    return False
                start_index += use_for_data_size
            for _ in range(self.dap_packet_count):
                read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
                if read_len is None or read_len == 0:
                    return False
                if self._check_dap_transfer_block_response(buffer[1:read_len]) != self.TRANSFER_RESPONSE['OK']:
                    return False
        rest_count = transfer_count % self.dap_packet_count
        for _ in range(rest_count - 1):
            end_index = start_index + use_for_data_size
            if self._dap_transfer_block(0x00, use_for_data_size, 0x0D, algorithm[start_index:end_index]) is False:
                return False
            start_index += use_for_data_size
        end_index = start_index + (algorithm_size % use_for_data_size)
        if self._dap_transfer_block(0x00, algorithm_size % use_for_data_size, 0x0D, algorithm[start_index:end_index]) is False:
            return False
        for i in range(transfer_count):
            read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
            if read_len is None or read_len == 0:
                return False
            if self._check_dap_transfer_block_response(buffer[1:read_len]) != self.TRANSFER_RESPONSE['OK']:
                return False

        if self._check_dp_ctrl_stat_error() is False:
            return False

        if verify_flag:
            if self._verify_target_data(start_addr, algorithm_size * 4, verify_value) is False:
                logging.error("download algorithm verify error")
                return False

        if self._check_dp_ctrl_stat_error() is False:
            return False

        return True

    def target_flash_init(self, data: ExecuteOperation) -> bool:
        """
        ret: 0: success, other: failed
        """
        ret = self._execute_operation(data)
        if ret != 0:
            logging.error(f"Execute operation(flash init) failed with return code: {ret}")
            return False
        return True

    def target_flash_erase(self, data: ExecuteOperation) -> bool:
        ret = self._execute_operation(data)
        if ret != 0:
            logging.error(f"Execute operation(flash erase) failed with return code: {ret}")
            return False
        return True

    def target_flash_uninit(self, data: ExecuteOperation) -> bool:
        ret = self._execute_operation(data)
        if ret != 0:
            logging.error(f"Execute operation(flash uninit) failed with return code: {ret}")
            return False
        if self._stop_dap_device() is False:
            return False
        return True

    def read_target_flash(self, start_addr, size, read_data: list) -> bool:
        if self._read_target_id() is False:
            return False
        if self._read_target_memory(start_addr, size, read_data) is False:
            return False
        if self._stop_dap_device() is False:
            return False
        return True

    def _verify_target_data(self, start_addr, size, verify_value) -> bool:
        read_data = []
        if self._read_target_memory(start_addr, size, read_data) is False:
            return False

        if self.get_xor_value(read_data, len(read_data)) != verify_value:
            return False

        return True

    def _read_target_memory(self, start_addr, size, read_data: list) -> bool:
        read_data.clear()
        read_size = size
        size = (size + 4 - 1) // 4
        use_for_data_size = self.dap_packet_size - 4
        use_for_data_size = ((use_for_data_size - (use_for_data_size % 4)) & 0xFFFF) // 4
        if self._set_write_address(start_addr) is False:
            return False
        transfer_count = (size + use_for_data_size - 1) // use_for_data_size
        buffer = usb.util.create_buffer(self.dap_packet_size)
        for _ in range(transfer_count//self.dap_packet_count):
            for _ in range(self.dap_packet_count):
                if self._dap_transfer_block(0x00, use_for_data_size, 0x0F) is False:
                    return False
            for _ in range(self.dap_packet_count):
                read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
                if read_len is None or read_len == 0:
                    return False
                response = self._check_dap_transfer_block_response(buffer[1:read_len])
                if response != self.TRANSFER_RESPONSE['OK']:
                    return False
                for i in range(4, read_len, 4):
                    data32 = self._response_list_to_uint32_t(buffer[i:i+4])
                    read_data.append(data32)
        rest_count = transfer_count % self.dap_packet_count
        for _ in range(rest_count - 1):
            if self._dap_transfer_block(0x00, use_for_data_size, 0x0F) is False:
                return False
        if self._dap_transfer_block(0x00, size % use_for_data_size, 0x0F) is False:
            return False
        for i in range(rest_count):
            read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
            if read_len is None or read_len == 0:
                return False
            response = self._check_dap_transfer_block_response(buffer[1:read_len])
            if response != self.TRANSFER_RESPONSE['OK']:
                return False
            for j in range(4, read_len, 4):
                data32 = self._response_list_to_uint32_t(buffer[j:j+4])
                read_data.append(data32)

        if read_size % 4:
            read_data[-1] &= (0xFFFFFFFF >> ((4 - (read_size % 4)) * 8))

        return True

    @staticmethod
    def get_xor_value(data, length) -> int:
        xor_value = 0
        for i in range(length):
            xor_value ^= data[i]
        return xor_value

    def _read_target_id(self) -> bool:
        if self._steup_swj_sequence(self.dap_swj_clock) is False:
            return False

        if self.debug_id == 'Unknown':
            return False

        if self._write_dp_abort(0x1E) is False: # 清除Abort状态
            return False
        if self._write_dp_ctrl_stat(0x50000000) is False: # 设置DP控制状态寄存器
            return False
        if (self._read_dp_ctrl_stat() >> 24) & 0xF0 != 0xF0:
            return False
        if self._write_dp_ctrl_stat(0x50000F00) is False: # 设置DP控制状态寄存器
            return False
        if self._write_dp_select(0x00000000) is False:
            return False

        ap_id = self._read_ap_idr()
        self.ap_id = "Unknown"
        self.ap_id = f"0x{ap_id:08X}"

        if self._write_ap_csw(0x23000052) is False:  # 写AP CSW寄存器
            return False

        self._get_coresight_component_table()
        scb_reg = SCB_REG(self._coresight_component_table['SCS_BASE'])
        cpu_id = self._read_reg(scb_reg.CPUID)  # 读取CPUID寄存器
        self.cpu_id = 'Unknown'
        self.cpu_id = f"0x{cpu_id:08X}"

        return True

    def _reset_and_halt_target(self) -> bool:
        if self._read_target_id() is False:
            return False

        scb_reg = SCB_REG(self._coresight_component_table['SCS_BASE'])

        if self._write_reg(DEBUG_REG.DHCSR, 0xA05F0003) is False:  # 使能停机模式的调试，停机处理器
            return False
        if self._write_reg(DEBUG_REG.DEMCR, 0x00000001) is False:  # 发生内核复位时停机调试
            return False
        while True:
            scb_aircr = self._read_reg(scb_reg.AIRCR)  # 读出AIRCR寄存器
            self._write_reg(scb_reg.AIRCR, ((0x05FA << 16) | \
                                            (scb_aircr & (0x7 << 8)) | \
                                            (0x1 << 2)))  # 软件复位

            time.sleep(0.05)  # 等待复位完成
            debug_dhcsr = self._read_reg(DEBUG_REG.DHCSR)  # 读出DHCSR寄存器，确保复位后停机
            if (debug_dhcsr & 0x02030000) != 0:
                debug_dhcsr = self._read_reg(DEBUG_REG.DHCSR)
                break
        return True

    def _steup_swj_sequence(self, swj_clock=5000000) -> bool:
        self._get_dap_firmware_version()
        if self.firmware_version == 'Unknown':
            logging.error("Failed to get DAP firmware version.")
            return False

        self._get_dap_capabilities()
        if self.dap_caps == 0x00:
            logging.error("Failed to get DAP capabilities.")
            return False

        self._get_dap_packet_size()
        if self.dap_packet_size == 0:
            logging.error("Failed to get DAP packet size.")
            return False

        self._get_dap_packet_count()
        if self.dap_packet_count == 0:
            logging.error("Failed to get DAP packet count.")
            return False

        if self._connect_dap_device(0) == 0:
            logging.error("Failed to connect to DAP device.")
            return False

        if self._set_dap_swj_clock(swj_clock) is False:  # 设置SWJ时钟频率
            logging.error("Failed to set SWJ clock frequency.")
            return False

        if self._config_dap_transfer(0x00, (0xFF & 0xFFFF), (0xFF & 0xFFFF)) is False:  # 配置传输参数
            logging.error("Failed to configure DAP transfer parameters.")
            return False

        if self._config_dap_swd(0x00) is False:  # 配置SWD协议参数
            logging.error("Failed to configure SWD protocol parameters.")
            return False

        if self._set_dap_host_status('connect_on') is False:
            logging.error("Failed to set host status(connect on).")
            return False

        if self._read_debug_id() is False:  # 读取调试ID
            logging.error("Failed to read debug ID.")
            return False
        return True

    def _stop_dap_device(self) -> bool:
        if self._set_dap_host_status('connect_off') is False:
            return False

        if self._disconnect_dap_device() is False:
            return False
        return True

    def _read_debug_id(self):
        if self._send_swd_start_sequence() is False:
            return False

        response = []
        if self._dap_transfer(0x00, 0x01, [[0x02, []]], response) is False:
            return False

        # 第一个开始序列不行，使用dormant状态转换
        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            if self._send_swj_reset_sequence() is False:
                return False

            if self._send_swj_swd_to_dormant_sequence() is False:
                return False

            if self._send_swj_reset_sequence() is False:
                return False

            if self._send_swj_jtag_to_dormant_sequence() is False:
                return False

            if self._send_swj_dormant_to_swd_sequence() is False:
                return False

            if self._send_swj_reset_sequence() is False:
                return False

            if self._send_swj_idle_sequence() is False:
                return False

            response.clear()
            if self._dap_transfer(0x00, 0x01, [[0x02, []]], response) is False:
                return False

            if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
                return False

        self.debug_id = 'Unknown'
        debug_id = self._response_list_to_uint32_t(response[2:])
        self.debug_id = f"0x{debug_id:08X}"
        return True

    def _get_coresight_component_table(self):
        # 清除coresight_rom_table的每一项
        self._coresight_component_table = ROM_TABLE().get_component_table()
        for index, key in enumerate(self._coresight_component_table):
            if index == 0:
                continue
            temp = self._read_reg(self._coresight_component_table['BASE_ADDR'] + (index-1) * 4)
            if temp & 0x01 != 0:
                self._coresight_component_table[key] = \
                    ((temp & 0xFFFFFFFC) + self._coresight_component_table['BASE_ADDR']) & 0xFFFFFFFC

            elif temp == 0x00000000: # End marker
                break

    def _write_dp_abort(self, value) -> bool:
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x00, value]], response) is False:
            logging.error("Failed to write DP ABORT register, value: {value}.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to write DP ABORT register, response: 0x{response[1]:02X}")
            return False
        return True

    def _read_dp_abort(self):
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x02, []]], response) is False:
            logging.error("Failed to read DP ABORT register.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to read DP ABORT register, response: 0x{response[1]:02X}")
            return False

        return self._response_list_to_uint32_t(response[2:])

    def _write_dp_ctrl_stat(self, value) -> bool:
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x04, value]], response) is False:
            logging.error("Failed to write DP  CTRL STAT register, value: {value}.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to write DP  CTRL STAT register, response: 0x{response[1]:02X}")
            return False

        return True

    def _read_dp_ctrl_stat(self):
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x06, []]], response) is False:
            logging.error("Failed to read DP  CTRL STAT register.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to read DP CTRL STAT register, response: 0x{response[1]:02X}")
            return False

        return self._response_list_to_uint32_t(response[2:])

    def _check_dp_ctrl_stat_error(self):
        dp_status = self._read_dp_ctrl_stat()
        if (dp_status & 0x00000080) != 0 or (dp_status & 0x00000040) == 0:
            logging.error("DP read/write error")
            return False
        return True

    def _write_ap_csw(self, value) -> bool:
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x01, value]], response) is False:
            logging.error("Failed to write AP CSW register, value: {value}.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to write AP CSW register, response: 0x{response[1]:02X}")
            return False

        return True

    def _read_ap_csw(self):
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x03, []]], response) is False:
            logging.error("Failed to read AP CSW register.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to read AP CSW register, response: 0x{response[1]:02X}")
            return False

        return self._response_list_to_uint32_t(response[2:])

    def _read_ap_idr(self):
        self._write_dp_select(0x000000F0)
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x0F, []]], response) is False:
            logging.error("Failed to read AP IDR register.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to read AP IDR register, response: 0x{response[1]:02X}")
            return False

        self._write_dp_select(0x00000000)

        return self._response_list_to_uint32_t(response[2:])

    def _read_debug_interface_base_addr(self):
        self._write_dp_select(0x000000F0)
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x0B, []]], response) is False:
            logging.error("Failed to read Debug Interface Base Address.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to read Debug Interface Base Address, response: 0x{response[1]:02X}")
            return False

        self._write_dp_select(0x00000000)

        return self._response_list_to_uint32_t(response[2:])

    def _write_dp_select(self, value) -> bool:
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x08, value]], response) is False:
            logging.error("Failed to write DP select register, value: {value}.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to set DP select register, response: 0x{response[1]:02X}")
            return False

        return True

    def _set_write_address(self, addr) -> bool:
        response = []
        if self._dap_transfer(0x00, 0x01, [[0x05, addr]], response) is False:
            logging.error("Failed to set write address, address: {addr}.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to set write address, response: 0x{response[1]:02X}")
            return False
        return True

    def _write_reg(self, reg_address, value) -> bool:
        """
        写寄存器
        :param reg_address: 寄存器地址
        :param value: 要写入的值
        :return: None
        """
        response = []
        if self._dap_transfer(0x00, 0x02, [[0x05, reg_address], [0x0d, value]], response) is False:
            logging.error("Failed to write register, address: {reg_address}, value: {value}.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to write register, response: 0x{response[1]:02X}")
            return False

        return True

    def _read_reg(self, reg_address):
        """
        读寄存器
        :param reg_address: 寄存器地址
        :return: 寄存器值
        """
        response = []
        if self._dap_transfer(0x00, 0x02, [[0x05, reg_address], [0x0F, []]], response) is False:
            logging.error("Failed to read register, address: {reg_address}.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to read register, response: 0x{response[1]:02X}")
            return False

        return self._response_list_to_uint32_t(response[2:])

    def _response_list_to_uint32_t(self, response):
        """
        将DAP响应列表转换为32位无符号整数
        :param response: DAP响应列表
        :return: 32位无符号整数
        """
        value = 0
        for i, byte in enumerate(response):
            value |= (byte << (i * 8))
        return value & 0xFFFFFFFF

    def _execute_operation(self, operation: ExecuteOperation):
        """
        0x05: 写DCRSR寄存器
        0x06: 读DP-CTRL/STAT寄存器
        0x09: 写DCRDR寄存器
        0x13: 以掩码读DHCSR寄存器
        0x0B: 读DCRDR寄存器
        """
        self._execute_operation_init()
        response = []
        # 先写R0-R3寄存器
        data = [
            [0x09, operation.r0],
            [0x05, 0x00010000],
            [0x13, 0x00010000],
            [0x09, operation.r1],
            [0x05, 0x00010001],
            [0x13, 0x00010000],
            [0x09, operation.r2],
            [0x05, 0x00010002],
            [0x13, 0x00010000],
            [0x09, operation.r3],
            [0x05, 0x00010003],
            [0x13, 0x00010000],
        ]
        if self._dap_transfer(0x00, 0x0C, data, response) is False:
            logging.error("Failed to write excute operation.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to write excute operation, response: 0x{response[1]:02X}")
            return False
        # 然后写R9, R13, R14, R15寄存器
        response.clear()
        data = [
            [0x09, operation.r9],
            [0x05, 0x00010009],
            [0x13, 0x00010000],
            [0x09, operation.r13],
            [0x05, 0x0001000D],
            [0x13, 0x00010000],
            [0x09, operation.r14],
            [0x05, 0x0001000E],
            [0x13, 0x00010000],
            [0x09, operation.r15],
            [0x05, 0x0001000F],
            [0x13, 0x00010000],
        ]
        if self._dap_transfer(0x00, 0x0C, data, response) is False:
            logging.error("Failed to write excute operation.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to write excute operation, response: 0x{response[1]:02X}")
            return False
        # 最后写xpsr, DHCSR寄存器，并读取DP端口的DP-CTRL/STAT寄存器
        response.clear()
        data = [
            [0x09, operation.xpsr],
            [0x05, 0x00010010],
            [0x13, 0x00010000],
            [0x01, 0xA05F0001],
            [0x06, []],
        ]
        if self._dap_transfer(0x00, 0x05, data, response) is False:
            logging.error("Failed to write excute operation.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to write excute operation, response: 0x{response[1]:02X}")
            return False
        dp_status = self._response_list_to_uint32_t(response[2:])
        if (dp_status & 0x00000080) != 0 or (dp_status & 0x00000040) == 0:
            logging.error(f"DP status read/write error(code: 0x{dp_status:08X})")
            return False
        self._write_dp_select(0x00000000)
        timeout = operation.timeout
        while True:
            timeout -=10 # 10ms
            if timeout <= 0:
                logging.error("Execute operation timeout.")
                return False
            dhcsr_value = self._read_reg(DEBUG_REG.DHCSR)
            if (dhcsr_value & 0x00030000) == 0x00030000:
                break
            time.sleep(0.01)
        # 读取返回值
        self._execute_operation_init()
        response.clear()
        data = [
            [0x05, 0x00000000],
            [0x13, 0x00010000],
            [0x0B, []],
            [0x06, []],
        ]
        if self._dap_transfer(0x00, 0x04, data, response) is False:
            logging.error("Failed to write excute operation.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to write excute operation, response: 0x{response[1]:02X}")
            return False

        dp_status = self._response_list_to_uint32_t(response[6:])
        if (dp_status & 0x00000080) != 0 or (dp_status & 0x00000040) == 0:
            logging.error(f"DP status read/write error(code: 0x{dp_status:08X})")
            return False
        self._write_dp_select(0x00000000)
        timeout = operation.timeout
        while True:
            timeout -=1 # 1ms
            if timeout <= 0:
                logging.error("Execute operation timeout.")
                return False
            dhcsr_value = self._read_reg(DEBUG_REG.DHCSR)
            if (dhcsr_value & 0x00030000) == 0x00030000:
                break
            time.sleep(0.001)

        ret = self._response_list_to_uint32_t(response[2:6])
        return ret

    def _execute_operation_init(self):
        response = []
        data = [
            [0x20, 0x00010000],
            [0x08, 0x00000000],
            [0x05, DEBUG_REG.DHCSR],
            [0x08, 0x00000010],
        ]
        if self._dap_transfer(0x00, 0x04, data, response) is False:
            logging.error("Failed to read register, address: {reg_address}.")
            return False

        if self._check_dap_transfer_response(response) != self.TRANSFER_RESPONSE['OK']:
            logging.error(f"Failed to read register, response: 0x{response[1]:02X}")
            return False

    """
    Response Status
    """
    DAP_STATUS = {
        'OK': 0x00,  # 成功
        'ERROR': 0xFF,  # 失败
    }

    """
    Transfer Response
    """
    TRANSFER_RESPONSE = {
        'OK': 0x00,  # 传输成功
        'WAIT': 0x01,  # 等待
        'FAULT': 0x02,  # 故障
        'NO_ACK': 0x03,  # 无应答
        'ERROR': 0x04,  # 错误
        'Mismatch': 0x05,  # 值不匹配
    }

    """
    General Commands
    Information and Control commands for the CMSIS-DAP Debug Unit
    """
    # DAP_Info命令定义
    # 响应格式: [0x00, Len, Info...]
    # Len=0: 无信息, Len=1: 字节值, Len=2: 短整型, Len=4: 字值, 其他: 字符串
    INFO_COMMANDS = {
        'vid': [0x00, 0x01],                    # 厂商ID (字符串)
        'pid': [0x00, 0x02],                    # 产品ID (字符串)
        'sn': [0x00, 0x03],                     # 序列号 (字符串)
        'version': [0x00, 0x04],                # CMSIS-DAP固件版本 (字符串)
        'vendor': [0x00, 0x05],                 # 目标设备厂商 (字符串)
        'name': [0x00, 0x06],                   # 目标设备名称 (字符串)
        'caps': [0x00, 0xF0],                   # 调试单元能力 (字节)
        'timer': [0x00, 0xF1],                  # 测试域定时器 (字节)
        'swo_size': [0x00, 0xFD],               # SWO跟踪缓冲区大小 (字值)
        'packet_count': [0x00, 0xFE],           # 最大包数量 (字节)
        'packet_size': [0x00, 0xFF]             # 最大包大小 (短整型)
    }

    # DAP_HostStatus命令定义
    # 响应格式: [0x01, Status]
    # Status: 0x00=成功, 0xFF=失败
    HOST_STATUS_COMMANDS = {
        'connect_off': [0x01, 0x00, 0x00],      # 连接LED关闭
        'connect_on': [0x01, 0x00, 0x01],       # 连接LED开启
        'running_off': [0x01, 0x01, 0x00],      # 运行LED关闭
        'running_on': [0x01, 0x01, 0x01]        # 运行LED开启
    }

    # DAP_Connect命令定义
    # 响应格式: [0x02, Port]
    # Port: 0=初始化失败, 1=SWD模式已初始化, 2=JTAG模式已初始化
    CONNECT_COMMANDS = {
        'default': [0x02, 0x00],                # 默认模式连接
        'swd': [0x02, 0x01],                    # SWD模式连接
        'jtag': [0x02, 0x02]                    # JTAG模式连接
    }

    # DAP_Disconnect命令定义
    # 响应格式: [0x03, Status]
    # Status: 0x00=成功断开连接, 0xFF=断开连接失败
    DISCONNECT_COMMANDS = {
        'disconnect': [0x03]                    # 断开连接
    }

    # DAP_WriteABORT命令构建方法（需要动态参数）
    # 响应格式: [0x08, Status]
    # Status: 0x00=成功写入ABORT寄存器, 0xFF=写入失败
    def _write_abort_command(self, dap_index=0, abort_value=0x00000000):
        """
        构建DAP_WriteABORT命令
        :param dap_index: DAP索引（JTAG设备索引，SWD模式忽略）
        :param abort_value: 32位ABORT值，写入CoreSight ABORT寄存器
        :return: 命令列表
        """
        # 将32位值转换为小端序4字节
        abort_bytes = [
            abort_value & 0xFF,           # 低字节
            (abort_value >> 8) & 0xFF,
            (abort_value >> 16) & 0xFF,
            (abort_value >> 24) & 0xFF    # 高字节
        ]

        return [0x08, dap_index] + abort_bytes

    # DAP_Delay命令构建方法（需要动态参数）
    # 响应格式: [0x09, Status]
    # Status: 0x00=延迟执行成功, 0xFF=延迟执行失败
    def _delay_command(self, delay_us):
        """
        构建DAP_Delay命令
        :param delay_us: 延迟时间（微秒）
        :return: 命令列表
        """
        # 将延迟时间转换为小端序2字节（SHORT）
        delay_low = delay_us & 0xFF
        delay_high = (delay_us >> 8) & 0xFF

        return [0x09, delay_low, delay_high]

    # DAP_ResetTarget命令定义
    # 响应格式: [0x0A, Status, Execute]
    # Status: 0x00=复位成功, 0xFF=复位失败
    # Execute: 0=未实现设备特定复位序列, 1=已实现设备特定复位序列
    RESET_TARGET_COMMANDS = {
        'reset': [0x0A]                         # 复位目标设备
    }

    """
    Common SWD/JTAG Commands
    Set SWD/JTAG clock and control/monitor SWD/JTAG I/O pins
    """
    # DAP_SWJ_Pins命令构建方法（需要动态参数）
    # 响应格式: [0x10, Pin Input]
    # Pin Input: 从目标设备读取的引脚状态
    #
    # I/O引脚映射:
    # Bit 0: SWCLK/TCK
    # Bit 1: SWDIO/TMS
    # Bit 2: TDI
    # Bit 3: TDO
    # Bit 5: nTRST
    # Bit 7: nRESET
    def _swj_pins_command(self, pin_output, pin_select, pin_wait=0):
        """
        构建DAP_SWJ_Pins命令
        :param pin_output: 选定输出引脚的值
        :param pin_select: 选择哪些输出引脚将被修改
        :param pin_wait: 等待超时时间，稳定所选输出（微秒，0=不等待，最大3秒）
        :return: 命令列表
        """
        pin_output &= 0xFF  # 确保输出值为1字节
        pin_select &= 0xFF  # 确保选择值为字节
        # 将等待时间转换为小端序4字节（WORD）
        wait_bytes = [
            pin_wait & 0xFF,
            (pin_wait >> 8) & 0xFF,
            (pin_wait >> 16) & 0xFF,
            (pin_wait >> 24) & 0xFF
        ]

        return [0x10, pin_output, pin_select] + wait_bytes

    # DAP_SWJ_Clock命令构建方法（需要动态参数）
    # 响应格式: [0x11, Status]
    # Status: 0x00=时钟设置成功, 0xFF=时钟设置失败
    def _swj_clock_command(self, clock_hz):
        """
        构建DAP_SWJ_Clock命令
        :param clock_hz: SWD/JTAG时钟频率（Hz）
        :return: 命令列表
        """
        # 将时钟频率转换为小端序4字节（WORD）
        clock_bytes = [
            clock_hz & 0xFF,
            (clock_hz >> 8) & 0xFF,
            (clock_hz >> 16) & 0xFF,
            (clock_hz >> 24) & 0xFF
        ]

        return [0x11] + clock_bytes

    # DAP_SWJ_Sequence命令构建方法（需要动态参数）
    # 响应格式: [0x12, Status]
    # Status: 0x00=序列发送成功, 0xFF=序列发送失败
    def _swj_sequence_command(self, bit_count, sequence_data):
        """
        构建DAP_SWJ_Sequence命令
        :param bit_count: 序列中的位数（1-256，256编码为0）
        :param sequence_data: 序列位数据，LSB先传输
        :return: 命令列表
        """
        # 256位编码为0
        if bit_count == 256:
            bit_count = 0

        # 构建命令
        command = [0x12, bit_count]

        # 添加序列数据
        if isinstance(sequence_data, list):
            command.extend(sequence_data)
        elif isinstance(sequence_data, int):
            # 如果是单个整数，转换为字节列表
            byte_count = (bit_count + 7) // 8 if bit_count > 0 else 32  # 256位需要32字节
            for i in range(byte_count):
                command.append((sequence_data >> (i * 8)) & 0xFF)

        return command

    """
    SWD Commands
    Configure the parameters for SWD mode
    """
    # DAP_SWD_Configure命令构建方法（需要动态参数）
    # 响应格式: [0x13, Status]
    # Status: 0x00=SWD配置成功, 0xFF=SWD配置失败
    def _swd_configure_command(self, configuration=0x00):
        """
        构建DAP_SWD_Configure命令
        :param configuration: SWD协议配置字节
                            Bit 1..0: Turnaround时钟周期 (0=1周期, 1=2周期, 2=3周期, 3=4周期)
                            Bit 2: DataPhase (0=不在WAIT/FAULT时生成, 1=总是生成)
        :return: 命令列表
        """
        return [0x13, configuration]

    # DAP_SWD_Sequence命令构建方法（需要动态参数）
    # 响应格式: [0x1D, Status, SWDIO Data...]
    # Status: 0x00=序列执行成功, 0xFF=序列执行失败
    # SWDIO Data: 仅在输入模式时包含，从SWDIO引脚捕获的数据
    def _swd_sequence_command(self, sequence_count, sequence_request, sequence_data=None):
        """
        构建DAP_SWD_Sequence命令
        :param sequence_count: 序列的数量
        :param sequence_request: 序列请求列表，每个请求包含sequence_info
                                sequence_info格式：
                                Bit 5..0: TCK周期数 (1..64, 64编码为0)
                                Bit 6: 保留
                                Bit 7: 模式 (0=输出，SWDIO数据在命令中; 1=输入，SWDIO数据在响应中)
        :param sequence_data: 序列数据列表，仅在输出模式时需要
        :return: 命令列表
        """
        command = [0x1D, sequence_count]

        for i, sequence_info in enumerate(sequence_request):
            command.append(sequence_info)

            # 如果是输出模式（bit 7 = 0），添加SWDIO数据
            if (sequence_info & 0x80) == 0:
                tck_cycles = sequence_info & 0x3F
                if tck_cycles == 0:
                    tck_cycles = 64

                # 计算需要的字节数（每8个TCK周期需要1字节）
                byte_count = (tck_cycles + 7) // 8

                # 添加SWDIO数据
                if sequence_data is not None and i < len(sequence_data):
                    swdio_data = sequence_data[i]
                    if isinstance(swdio_data, int):
                        # 将整数转换为字节列表
                        for j in range(byte_count):
                            command.append((swdio_data >> (j * 8)) & 0xFF)
                    elif isinstance(swdio_data, list):
                        command.extend(swdio_data[:byte_count])

        return command

    """
    SWO Commands
    Configure the parameters for SWO mode
    """
    # DAP_SWO_Transport命令定义
    # 响应格式: [0x17, Status]
    # Status: 0x00=SWO传输模式设置成功, 0xFF=设置失败
    def _swo_transport_command(self, transport=0):
        """
        构建DAP_SWO_Transport命令
        :param transport: SWO传输模式
                         0 = None (默认)
                         1 = 通过DAP_SWO_Data命令读取跟踪数据
                         2 = 通过独立的WinUSB端点发送跟踪数据 (需要CMSIS-DAP v2配置)
        :return: 命令列表
        """
        return [0x17, transport]

    # DAP_SWO_Mode命令定义
    # 响应格式: [0x18, Status]
    # Status: 0x00=SWO模式设置成功, 0xFF=设置失败
    def _swo_mode_command(self, mode=0):
        """
        构建DAP_SWO_Mode命令
        :param mode: SWO捕获模式
                    0 = Off (默认)
                    1 = UART
                    2 = Manchester
        :return: 命令列表
        """
        return [0x18, mode]

    # DAP_SWO_Baudrate命令定义
    # 响应格式: [0x19, Baudrate]
    # Baudrate: 实际波特率或0（波特率未配置）
    def _swo_baudrate_command(self, baudrate):
        """
        构建DAP_SWO_Baudrate命令
        :param baudrate: 请求的波特率
        :return: 命令列表
        """
        # 将波特率转换为小端序4字节（WORD）
        baudrate_bytes = [
            baudrate & 0xFF,
            (baudrate >> 8) & 0xFF,
            (baudrate >> 16) & 0xFF,
            (baudrate >> 24) & 0xFF
        ]

        return [0x19] + baudrate_bytes

    # DAP_SWO_Control命令定义
    # 响应格式: [0x1A, Status]
    # Status: 0x00=SWO控制设置成功, 0xFF=设置失败
    def _swo_control_command(self, control=0):
        """
        构建DAP_SWO_Control命令
        :param control: SWO跟踪数据捕获控制
                       0 = Stop
                       1 = Start
        :return: 命令列表
        """
        return [0x1A, control]

    # DAP_SWO_Status命令定义
    # 响应格式: [0x1B, Trace Status, Trace Count]
    # Trace Status:
    #   Bit 0: Trace Capture (1=active, 0=inactive)
    #   Bit 6: Trace Stream Error
    #   Bit 7: Trace Buffer Overrun
    # Trace Count: 跟踪缓冲区中的字节数（未读取）
    SWO_STATUS_COMMAND = [0x1B]

    # DAP_SWO_ExtendedStatus命令定义
    # 响应格式: [0x1E, Trace Status, Trace Count, Index, TD_TimeStamp]
    # Trace Status:
    #   Bit 0: Trace Capture (1=active, 0=inactive)
    #   Bit 6: Trace Stream Error
    #   Bit 7: Trace Buffer Overrun
    # Trace Count: 跟踪缓冲区中的字节数（未读取）
    # Index: 下一跟踪信息的序列号
    # TD_TimeStamp: 跟踪序列的测试域定时器值
    def _swo_extended_status_command(self, control=0x07):
        """
        构建DAP_SWO_ExtendedStatus命令
        :param control: 控制字节
                       Bit 0: Trace Status (1=请求, 0=不活跃)
                       Bit 1: Trace Count (1=请求, 0=不活跃)
                       Bit 2: Index/Timestamp (1=请求, 0=不活跃)
        :return: 命令列表
        """
        return [0x1E, control]

    # DAP_SWO_Data命令定义
    # 响应格式: [0x1C, Trace Status, Trace Count, Trace Data...]
    # Trace Status:
    #   Bit 0: Trace Capture (1=active, 0=inactive)
    #   Bit 6: Trace Stream Error
    #   Bit 7: Trace Buffer Overrun
    # Trace Count: 读取的跟踪数据字节数
    # Trace Data: 读取的跟踪数据字节
    def _swo_data_command(self, trace_count):
        """
        构建DAP_SWO_Data命令
        :param trace_count: 要读取的最大跟踪数据字节数
        :return: 命令列表
        """
        # 将跟踪计数转换为小端序2字节（SHORT）
        count_bytes = [
            trace_count & 0xFF,
            (trace_count >> 8) & 0xFF
        ]

        return [0x1C] + count_bytes

    """
    JTAG Commands
    Detect and configure the JTAG device chain
    """
    # DAP_JTAG_Sequence命令构建方法（需要动态参数）
    # 响应格式: [0x14, Status, TDO Data...]
    # Status: 0x00=序列执行成功, 0xFF=序列执行失败
    # TDO Data: 从TDO捕获的数据（仅在TDO捕获启用时）
    def _jtag_sequence_command(self, sequence_count, sequence_request, sequence_data=None):
        """
        构建DAP_JTAG_Sequence命令
        :param sequence_count: 序列的数量
        :param sequence_request: 序列请求列表，每个请求包含sequence_info
                                sequence_info格式：
                                Bit 5..0: TCK周期数 (1..64, 64编码为0)
                                Bit 6: TMS值 (0或1)
                                Bit 7: TDO捕获 (0=不捕获, 1=捕获TDO数据)
        :param sequence_data: TDI数据列表
        :return: 命令列表
        """
        command = [0x14, sequence_count]

        for i, sequence_info in enumerate(sequence_request):
            command.append(sequence_info)

            # 获取TCK周期数
            tck_cycles = sequence_info & 0x3F
            if tck_cycles == 0:
                tck_cycles = 64

            # 计算需要的字节数（每8个TCK周期需要1字节）
            byte_count = (tck_cycles + 7) // 8

            # 添加TDI数据
            if sequence_data is not None and i < len(sequence_data):
                tdi_data = sequence_data[i]
                if isinstance(tdi_data, int):
                    # 将整数转换为字节列表
                    for j in range(byte_count):
                        command.append((tdi_data >> (j * 8)) & 0xFF)
                elif isinstance(tdi_data, list):
                    command.extend(tdi_data[:byte_count])

        return command

    # DAP_JTAG_Configure命令构建方法（需要动态参数）
    # 响应格式: [0x15, Status]
    # Status: 0x00=JTAG配置成功, 0xFF=配置失败
    def _jtag_configure_command(self, device_count, ir_lengths):
        """
        构建DAP_JTAG_Configure命令
        :param device_count: JTAG链中的设备数量
        :param ir_lengths: 每个设备的IR寄存器长度列表（位数）
        :return: 命令列表
        """
        command = [0x15, device_count]

        # 添加每个设备的IR长度
        for ir_length in ir_lengths:
            command.append(ir_length)

        return command

    # DAP_JTAG_IDCODE命令构建方法（需要动态参数）
    # 响应格式: [0x16, Status, ID Code]
    # Status: 0x00=IDCODE读取成功, 0xFF=读取失败
    # ID Code: 32位JTAG ID代码
    def _jtag_idcode_command(self, jtag_index):
        """
        构建DAP_JTAG_IDCODE命令
        :param jtag_index: JTAG链中选定设备的索引（从0开始）
        :return: 命令列表
        """
        return [0x16, jtag_index]

    """
    Transfer Commands
    Read and Writes to CoreSight registers
    """
    # DAP_TransferConfigure命令构建方法（需要动态参数）
    # 响应格式: [0x04, Status]
    # Status: 0x00=传输配置成功, 0xFF=配置失败
    def _transfer_configure_command(self, idle_cycles=0, wait_retry=0xFF, match_retry=0):
        """
        构建DAP_TransferConfigure命令
        :param idle_cycles: 每次传输后的额外空闲周期数
        :param wait_retry: WAIT响应后的传输重试次数
        :param match_retry: DAP_Transfer中值匹配时的重试次数
        :return: 命令列表
        """
        # 将参数转换为小端序字节
        idle_cycles_bytes = [idle_cycles & 0xFF]

        wait_retry_bytes = [
            wait_retry & 0xFF,
            (wait_retry >> 8) & 0xFF
        ]

        match_retry_bytes = [
            match_retry & 0xFF,
            (match_retry >> 8) & 0xFF
        ]

        return [0x04] + idle_cycles_bytes + wait_retry_bytes + match_retry_bytes

    # DAP_Transfer命令构建方法（需要动态参数）
    # 响应格式: [0x05, Transfer Count, Transfer Response, TD_TimeStamp, Transfer Data...]
    # Transfer Count: 执行的传输数量 (1..255)
    # Transfer Response: 来自目标设备的最后响应信息
    #   Bit 2..0: ACK值 (1=OK for SWD, OK或FAULT for JTAG; 2=WAIT; 4=FAULT; 7=NO_ACK)
    #   Bit 3: 协议错误 (SWD)
    #   Bit 4: 值不匹配 (读寄存器与值匹配)
    # TD_TimeStamp: 测试域定时器值（仅在Transfer Request bit 7: TD_TimeStamp请求设置时）
    # Transfer Data: 寄存器值或匹配值
    def _transfer_command(self, dap_index, transfer_count, transfer_sequence):
        """
        构建DAP_Transfer命令
        :param dap_index: JTAG设备的索引（SWD模式忽略）
        :param transfer_count: 传输数量 (1..255)
        :param transfer_sequence: 传输列表，每个元素是一个二维数据 (request_byte, transfer_data)
                        request_byte格式：
                        Bit 0: APnDP (0=DP, 1=AP)
                        Bit 1: RnW (0=写寄存器, 1=读寄存器)
                        Bit 2: A2寄存器地址位2
                        Bit 3: A3寄存器地址位3
                        Bit 4: 值匹配 (仅对读寄存器有效，0=正常读, 1=值匹配读)
                        Bit 5: 匹配掩码 (仅对写寄存器有效，0=正常写, 1=写匹配掩码)
                        Bit 7: TD_TimeStamp (0=无时间戳, 1=包含时间戳)
                        transfer_data: 传输数据（仅对写操作、值匹配读操作、匹配掩码写操作需要）
        :return: 命令列表
        """
        command = [0x05, dap_index, transfer_count]

        for request_byte, transfer_data in transfer_sequence:
            command.append(request_byte)

            # 检查是否需要传输数据
            rnw = (request_byte >> 1) & 1  # 读写位
            value_match = (request_byte >> 4) & 1  # 值匹配位
            match_mask = (request_byte >> 5) & 1  # 匹配掩码位

            # 对于写操作、值匹配读操作、匹配掩码写操作，需要包含数据
            if (rnw == 0) or (rnw == 1 and value_match == 1) or (rnw == 0 and match_mask == 1):
                if transfer_data is not None:
                    if isinstance(transfer_data, int):
                        # 将32位数据转换为小端序4字节
                        data_bytes = [
                            transfer_data & 0xFF,
                            (transfer_data >> 8) & 0xFF,
                            (transfer_data >> 16) & 0xFF,
                            (transfer_data >> 24) & 0xFF
                        ]
                        command.extend(data_bytes)
                    elif isinstance(transfer_data, list):
                        command.extend(transfer_data)

        return command

    # DAP_TransferBlock命令构建方法（需要动态参数）
    # 响应格式: [0x06, Transfer Count, Transfer Response, Transfer Data...]
    # Transfer Count: 执行的传输数量 (1..65535)
    # Transfer Response: 来自目标设备的最后响应信息
    #   Bit 2..0: ACK值 (1=OK for SWD, OK或FAULT for JTAG; 2=WAIT; 4=FAULT; 7=NO_ACK)
    #   Bit 3: 协议错误 (SWD)
    # Transfer Data: 寄存器值
    #   对于写寄存器传输请求：写入CoreSight寄存器的寄存器值
    #   对于读寄存器操作：不发送数据
    #   对于读寄存器传输请求：从CoreSight寄存器读取的寄存器值
    #   对于写寄存器操作：不接收数据
    def _transfer_block_command(self, dap_index, transfer_count, transfer_request, transfer_data=None):
        """
        构建DAP_TransferBlock命令
        读/写数据块到同一个CoreSight寄存器。数据块是多个32位值，
        从/到同一个CoreSight寄存器读取或写入。
        :param dap_index: JTAG设备的索引（SWD模式忽略）
        :param transfer_count: 传输数量 (1..65535)
        :param transfer_request: 传输请求字节
                               Bit 0: APnDP (0=DP, 1=AP)
                               Bit 1: RnW (0=写寄存器, 1=读寄存器)
                               Bit 2: A2寄存器地址位2
                               Bit 3: A3寄存器地址位3
        :param transfer_data: 传输数据列表（仅对写操作需要）
        :return: 命令列表
        """
        # 将传输计数转换为小端序2字节（SHORT）
        count_bytes = [
            transfer_count & 0xFF,
            (transfer_count >> 8) & 0xFF
        ]

        command = [0x06, dap_index] + count_bytes + [transfer_request]

        # 检查是否为写操作
        rnw = (transfer_request >> 1) & 1  # 读写位

        # 对于写操作，需要包含传输数据
        if rnw == 0 and transfer_data is not None:
            for data in transfer_data:
                if isinstance(data, int):
                    # 将32位数据转换为小端序4字节
                    data_bytes = [
                        data & 0xFF,
                        (data >> 8) & 0xFF,
                        (data >> 16) & 0xFF,
                        (data >> 24) & 0xFF
                    ]
                    command.extend(data_bytes)
                elif isinstance(data, list):
                    command.extend(data)

        return command

    # DAP_TransferAbort命令定义
    # 响应格式: 无响应
    # 功能: 中止当前传输。可以在DAP_Transfer或DAP_TransferBlock命令仍在进行时执行。
    # 如果没有正在进行的传输，则忽略该命令。命令本身没有响应，
    # 但中止的DAP_Transfer或DAP_TransferBlock命令将响应有关实际传输数据的信息。
    TRANSFER_ABORT_COMMAND = [0x07]

    """
    Atomic Commands
    Execute atomic commands
    """
    # DAP_ExecuteCommands命令构建方法（需要动态参数）
    # 响应格式: [0x7F, NumCmd, Command Responses...]
    # NumCmd: 执行的命令数量
    # Command Responses: 连接的命令响应
    def _execute_commands_command(self, commands):
        """
        构建DAP_ExecuteCommands命令
        在单个数据包中执行多个DAP命令。需要遵守请求和响应的数据包大小限制。
        :param commands: 要执行的命令列表，每个命令是一个字节列表
        :return: 命令列表
        """
        # 计算命令数量
        num_cmd = len(commands)

        # 构建命令
        command = [0x7F, num_cmd]

        # 连接所有命令请求
        for cmd in commands:
            if isinstance(cmd, list):
                command.extend(cmd)
            elif isinstance(cmd, int):
                command.append(cmd)

        return command

    # DAP_QueueCommands命令构建方法（需要动态参数）
    # 响应格式: [0x7E, NumCmd, Command Responses...]
    # NumCmd: 执行的命令数量
    # Command Responses: 连接的命令响应
    def _queue_commands_command(self, commands):
        """
        构建DAP_QueueCommands命令
        在多个数据包中排队多个DAP命令。排队从包含DAP_QueueCommands命令的第一个数据包开始，
        并继续包含所有后续数据包以及命令。当接收到不包含DAP_QueueCommands命令的数据包时，
        排队的命令将执行。需要遵守请求和响应的数据包大小限制。
        该命令类似于数据包级别的DAP_ExecuteCommands，但在处理之前排队多个数据包。
        :param commands: 要排队的命令列表，每个命令是一个字节列表
        :return: 命令列表
        """
        # 计算命令数量
        num_cmd = len(commands)

        # 构建命令
        command = [0x7E, num_cmd]

        # 连接所有命令请求
        for cmd in commands:
            if isinstance(cmd, list):
                command.extend(cmd)
            elif isinstance(cmd, int):
                command.append(cmd)

        return command

    def _get_dap_firmware_version(self):
        write_len = self.usb_device_handle.send_data_to_dap_device(self.INFO_COMMANDS['version'], timeout=100)
        if write_len != len(self.INFO_COMMANDS['version']):
            return False
        buffer = usb.util.create_buffer(512)

        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False
        self.firmware_version = 'Unknown'
        if buffer[1]:
            firmware_version = ''.join(chr(c) for c in buffer[2:read_len-1])
            self.firmware_version = firmware_version
        return firmware_version

    def _get_dap_capabilities(self):
        write_len = self.usb_device_handle.send_data_to_dap_device(self.INFO_COMMANDS['caps'], timeout=100)
        if write_len != len(self.INFO_COMMANDS['caps']):
            return False
        buffer = usb.util.create_buffer(512)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False
        capabilities = 0
        self.dap_caps = 0x00
        if buffer[1]:
            capabilities = buffer[2]
            # self._check_dap_capabilities(capabilities)
            self.dap_caps = capabilities
        return capabilities

    def _check_dap_capabilities(self, capability):
        if capability:
            logging.info(f"DAP Capabilities: 0x{capability:02X}")
        if capability & 0x01:
            logging.info("✓ SWD 支持")
        if capability & 0x02:
            logging.info("✓ JTAG 支持")
        if capability & 0x04:
            logging.info("✓ SWO UART 支持")
        if capability & 0x08:
            logging.info("✓ SWO Manchester 支持")
        if capability & 0x10:
            logging.info("✓ 原子命令支持")
        if capability & 0x20:
            logging.info("✓ 测试域定时器支持")
        if capability & 0x40:
            logging.info("✓ SWO 流式跟踪支持")

    def _get_dap_packet_size(self) -> int:
        write_len = self.usb_device_handle.send_data_to_dap_device(self.INFO_COMMANDS['packet_size'], timeout=100)
        if write_len != len(self.INFO_COMMANDS['packet_size']):
            return False
        buffer =usb.util.create_buffer(512)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False
        self.dap_packet_size = 0
        for i in range(buffer[1]):
            self.dap_packet_size |= buffer[i+2] << (i*8)
        return self.dap_packet_size

    def _get_dap_packet_count(self) -> int:
        write_len = self.usb_device_handle.send_data_to_dap_device(self.INFO_COMMANDS['packet_count'], timeout=100)
        if write_len != len(self.INFO_COMMANDS['packet_count']):
            return False
        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False
        self.dap_packet_count = 0
        for i in range(buffer[1]):
            self.dap_packet_count |= buffer[i+2] << (i*8)
        return self.dap_packet_count

    def _connect_dap_device(self, port=0) -> int:
        """
        连接到DAP设备
        :param port: 连接端口 (0=默认, 1=SWD, 2=JTAG)
        """
        command = self.CONNECT_COMMANDS.get('swd' if port == 1 else 'jtag' if port == 2 else 'default', None)
        if command is None:
            logging.error(f"Invalid port: {port}. Valid ports are: 0 (default), 1 (SWD), 2 (JTAG).")
            return False

        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        return buffer[1] & 0xFF

    def _disconnect_dap_device(self) -> bool:
        """
        断开DAP设备连接
        """
        command = self.DISCONNECT_COMMANDS['disconnect']
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        return buffer[1] == self.DAP_STATUS['OK']

    def _set_dap_swj_clock(self, clock_hz=0) -> bool:
        """
        设置DAP设备的时钟频率
        :param clock_hz: 时钟频率 (Hz)
        """
        if clock_hz == 0:
            clock_hz = self.dap_swj_clock

        command = self._swj_clock_command(clock_hz)
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        return buffer[1] == self.DAP_STATUS['OK']

    def _config_dap_transfer(self, idle_cycles=0, wait_retry=0xFF, match_retry=0) -> bool:
        """
        配置DAP传输参数
        :param idle_cycles: 每次传输后的额外空闲周期数
        :param wait_retry: WAIT响应后的传输重试次数
        :param match_retry: DAP_Transfer中值匹配时的重试次数
        """
        command = self._transfer_configure_command(idle_cycles, wait_retry, match_retry)
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        return buffer[1] == self.DAP_STATUS['OK']

    def _config_dap_swd(self, configuration=0x00) -> bool:
        """
        配置DAP SWD协议参数
        :param configuration: SWD协议配置字节
                              Bit 1..0: Turnaround时钟周期 (0=1周期, 1=2周期, 2=3周期, 3=4周期)
                              Bit 2: DataPhase (0=不在WAIT/FAULT时生成, 1=总是生成)
        """
        command = self._swd_configure_command(configuration)
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        return buffer[1] == self.DAP_STATUS['OK']

    def _set_dap_host_status(self, status) -> bool:
        command = self.HOST_STATUS_COMMANDS.get(status, None)
        if command is None:
            logging.error(f"Invalid host status: {status}. Valid statuses are: {list(self.HOST_STATUS_COMMANDS.keys())}.")
            return False
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        return buffer[1] == self.DAP_STATUS['OK']

    def _set_dap_swj_pin(self, pin_output=0, pin_select=0, pin_wait=0) -> int:
        """
        设置DAP SWJ引脚输出
        :param pin_output: 输出引脚状态（位掩码，0=低电平，1=高电平）
        :param pin_select: 选择哪些输出引脚将被修改
        :param pin_wait: 等待超时时间，稳定所选输出（微秒，0=不等待，最大3秒）
        """
        command = self._swj_pins_command(pin_output, pin_select, pin_wait)
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        return buffer[1] & 0xFF

    def _send_swj_sequence(self, bit_count, sequence_data) -> bool:
        """
        发送SWJ序列
        :param bit_count: 序列中的位数（1-256，256编码为0）
        :param sequence_data: 序列位数据，LSB先传输
        """
        command = self._swj_sequence_command(bit_count, sequence_data)
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        return buffer[1] == self.DAP_STATUS['OK']

    def _send_swd_start_sequence(self) -> bool:
        if self._send_swj_reset_sequence() is False:
            return False
        if self._send_swj_switch_swd_sequence() is False:
            return False
        if self._send_swj_reset_sequence() is False:
            return False

        if self._send_swj_idle_sequence() is False:
            return False

        return True

    def _send_swj_reset_sequence(self) -> bool:
        """
        发送SWJ复位序列
        在上电复位后、 DP 从 JTAG 切换到 SWD 后或者线路处于高电平超过 50 个周期后，
        SW-DP 状态机处于复位状态。
        """
        return self._send_swj_sequence(0x33, [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])

    def _send_swj_switch_swd_sequence(self) -> bool:
        """
        发送复位序列 + 0xE79E + 发送复位序列
        """
        return self._send_swj_sequence(0x10, [0x9E, 0xE7])

    def _send_swj_idle_sequence(self) -> bool:
        """
        发送SWJ空闲序列
        在复位状态后线路处于低电平至少两个周期， SW-DP 状态机处于空闲状态。
        """
        return self._send_swj_sequence(0x08, [0x00])

    def _send_swj_jtag_to_dormant_sequence(self) -> bool:
        """
        发送SWJ JTAG到休眠序列
        至少5个周期高电平 + 0x33BBBBBA
        """
        return self._send_swj_sequence(0x28, [0xFF, 0xBA, 0xBB, 0xBB, 0x33])

    def _send_swj_swd_to_dormant_sequence(self) -> bool:
        """
        发送SWJ SWD到休眠序列
        发送复位序列 + 0xE3BC
        """
        return self._send_swj_sequence(0x10, [0xBC, 0xE3])

    def _send_swj_dormant_to_swd_sequence(self) -> bool:
        """
        至少8个周期高电平 + 128-bit Selection Alert sequence + 4个周期低电平 + activation code sequence
        128-bit Selection Alert sequence = 0x19BC0EA2 E3DDAFE9 86852D95 6209F392
        activation code sequence: swd = 0xA1, jtag = 0xA0
        """
        data = [
            0xFF,
            0x92, 0xF3, 0x09, 0x62,
            0x95, 0x2D, 0x85, 0x86,
            0xE9, 0xAF, 0xDD, 0xE3,
            0xA2, 0x0E, 0xBC, 0x19,
            0xA0, 0x01,
        ]
        return self._send_swj_sequence(0x98, data)

    def _send_swj_dormant_to_jtag_sequence(self) -> bool:
        """
        至少8个周期高电平 + 128-bit Selection Alert sequence + 4个周期低电平 + activation code sequence
        128-bit Selection Alert sequence = 0x19BC0EA2 E3DDAFE9 86852D95 6209F392
        activation code sequence: swd = 0xA1, jtag = 0xA0
        """
        data = [
            0xFF,
            0x92, 0xF3, 0x09, 0x62,
            0x95, 0x2D, 0x85, 0x86,
            0xE9, 0xAF, 0xDD, 0xE3,
            0xA2, 0x0E, 0xBC, 0x19,
            0xA0, 0x00
        ]
        return self._send_swj_sequence(0x98, data)

    def _dap_transfer(self, dap_index, transfer_count, transfer_sequence, response=[]) -> bool:
        """
        执行DAP传输
        :param dap_index: JTAG设备的索引（SWD模式忽略）
        :param transfer_count: 传输数量 (1..255)
        :param transfer_request: 传输请求列表
        :param transfer_data: 传输数据列表（仅对写操作、值匹配读操作、匹配掩码写操作需要）
        """
        command = self._transfer_command(dap_index, transfer_count, transfer_sequence)
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        buffer = usb.util.create_buffer(self.dap_packet_size)
        read_len = self.usb_device_handle.receive_data_from_dap_device(buffer, timeout=100)
        if read_len is None or read_len == 0:
            return False

        # 清空并填充响应数据
        response.clear()
        response.extend(buffer[1:read_len])

        return True

    def _dap_transfer_block(self, dap_index, transfer_count, transfer_request, transfer_data=None) -> bool:
        """
        执行DAP块传输
        :param dap_index: JTAG设备的索引（SWD模式忽略）
        :param transfer_count: 传输数量 (1..65535)
        :param transfer_request: 传输请求字节
        :param transfer_data: 传输数据列表（仅对写操作需要）
        """
        command = self._transfer_block_command(dap_index, transfer_count, transfer_request, transfer_data)
        write_len = self.usb_device_handle.send_data_to_dap_device(command, timeout=100)
        if write_len != len(command):
            return False

        return True

    def _check_dap_transfer_response(self, response):
        temp = response[1] & 0x07

        match temp:
            case 1:
                return self.TRANSFER_RESPONSE['OK']
            case 2:
                return self.TRANSFER_RESPONSE['WAIT']
            case 4:
                return self.TRANSFER_RESPONSE['FAULT']
            case 7:
                return self.TRANSFER_RESPONSE['NO_ACK']

        # 检查其他位
        if response[1] & 0x08:
            return self.TRANSFER_RESPONSE['ERROR']
        if response[1] & 0x10:
            return self.TRANSFER_RESPONSE['Mismatch']

    def _check_dap_transfer_block_response(self, response):
        temp = response[2] & 0x07

        match temp:
            case 1:
                return self.TRANSFER_RESPONSE['OK']
            case 2:
                return self.TRANSFER_RESPONSE['WAIT']
            case 4:
                return self.TRANSFER_RESPONSE['FAULT']
            case 7:
                return self.TRANSFER_RESPONSE['NO_ACK']

        # 检查其他位
        if response[2] & 0x08:
            return self.TRANSFER_RESPONSE['ERROR']
