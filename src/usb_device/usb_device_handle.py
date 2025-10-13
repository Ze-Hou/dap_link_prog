import usb.core
import usb.util
from src.usb_device.usb_device_info import USBDeviceInfo
import logging

class USBDeviceHandle(USBDeviceInfo):
    def __init__(self):
        super().__init__()
        self.dap_devices_list = []
        self.select_dap_device_index = 0xFF

    def clean_dap_devices_list(self):
        self.dap_devices_list.clear()

    def clean_selected_dap_device(self):
        self.select_dap_device_index = 0xFF

    @property
    def get_selected_dap_device(self):
        if self.select_dap_device_index < len(self.dap_devices_list):
            return self.dap_devices_list[self.select_dap_device_index]
        return None

    def get_dap_devices(self):
        self.clean_dap_devices_list()
        self.clean_selected_dap_device()
        self.clean_dap_devices()
        dap_devices = self.find_dap_devices().copy()
        devices = dap_devices.get('dap', [])
        if devices:
            for device in devices:
                if 'HID' in device:
                    for hid_device in device['HID']:
                        self.dap_devices_list.append(hid_device)
                if 'WinUSB' in device:
                    for winusb_device in device['WinUSB']:
                        self.dap_devices_list.append(winusb_device)
            # 打印获取的DAP设备信息
            self.print_dap_devices(self.dap_devices_list)

            return self.dap_devices_list
        return None

    def print_dap_devices(self, dap_devices):
        if dap_devices:
            for i, dap_device in enumerate(dap_devices):
                logging.info(f"index: {i} VID: 0x{dap_device['vid']:04X} PID: 0x{dap_device['pid']:04X} "
                             f"{dap_device['intf_desc']} SN: {dap_device['serial_number']}")

    def select_dap_device_by_index(self, index):
        if index < len(self.dap_devices_list):
            self.select_dap_device_index = index
            self._print_selected_dap_device()
            return True

        return False

    def select_dap_device_by_sn(self, serial_number):
        match_index = []
        for i, dap_device in enumerate(self.dap_devices_list):
            if dap_device['serial_number'] == serial_number:
                match_index.append(i)

        if len(match_index) > 1:
            for i in match_index:
                if "WinUSB".lower() in self.dap_devices_list[i]['intf_desc'].lower():
                    self.select_dap_device_index = i
                    self._print_selected_dap_device()
                    return True
        elif len(match_index) == 1:
            self.select_dap_device_index = match_index[0]
            self._print_selected_dap_device()
            return True

        return False

    def select_dap_device_by_intf_desc_and_sn(self, intf_desc, serial_number):
        for i, dap_device in enumerate(self.dap_devices_list):
            if dap_device['intf_desc'] == intf_desc and dap_device['serial_number'] == serial_number:
                self.select_dap_device_index = i
                self._print_selected_dap_device()
                return True

        return False

    def _print_selected_dap_device(self):
        if self.select_dap_device_index < len(self.dap_devices_list):
            dap_device = self.dap_devices_list[self.select_dap_device_index]
            logging.info(f"Selected Device - index: {self.select_dap_device_index} VID: 0x{dap_device['vid']:04X} PID: 0x{dap_device['pid']:04X} "
                         f"{dap_device['intf_desc']} SN: {dap_device['serial_number']}")
        else:
            logging.error("No device selected or index out of range.")

    def config_dap_device(self):
        if self.select_dap_device_index == 0xFF:
            logging.error("No DAP device selected.")
            return False
        dap_device = self.dap_devices_list[self.select_dap_device_index]
        if self._check_dap_device_is_configured(dap_device) is False:
            if self._config_dap_device(dap_device) is False:
                return False
        self.reset_dap_device(dap_device)
        self.clean_in_ep()
        return True

    def unconfig_dap_device(self):
        if self.select_dap_device_index == 0xFF:
            logging.error("No DAP device selected.")
            return False
        dap_device = self.dap_devices_list[self.select_dap_device_index]
        if self._check_dap_device_is_configured(dap_device) is True:
            try:
                usb.util.release_interface(dap_device['device'], dap_device['interface'])
                usb.util.dispose_resources(dap_device['device'])
            except Exception:
                return False
        return True

    def unconfig_all_dap_devices(self):
        for dap_device in self.dap_devices_list:
            if self._check_dap_device_is_configured(dap_device) is True:
                try:
                    usb.util.release_interface(dap_device['device'], dap_device['interface'])
                    usb.util.dispose_resources(dap_device['device'])
                except Exception:
                    return False
        return True

    def _check_dap_device_is_configured(self, dap_device):
        dev = dap_device.get('device', None)
        cfg = dap_device.get('cfg_value', None)
        if dev:
            try:
                current_cfg = usb.control.get_configuration(dev)
                if current_cfg == cfg:
                    return True
            except Exception:
                return False

        return False

    def _config_dap_device(self, dap_device):
        dev = dap_device.get('device', None)
        cfg = dap_device.get('cfg_value', None)
        if dev and cfg is not None:
            try:
                dev.set_configuration(cfg)

                if self._check_dap_device_is_configured(dap_device):
                    return True
            except Exception:
                return False

        return False

    def reset_dap_device(self, dap_device):
        dap_device = self.get_selected_dap_device
        if dap_device is None:
            return False
        dev = dap_device.get('device', None)
        if dev:
            try:
                dev.reset()
                return True
            except Exception:
                return False

        return False

    def send_data_to_dap_device(self, data, timeout=10):
        dap_device = self.get_selected_dap_device
        if dap_device is None:
            return False
        dev = dap_device.get('device', None)
        if dev is None:
            return False

        out_ep = dap_device.get('out_ep', None)
        if out_ep is None:
            return False
        try:
            temp_data = data[:]
            if self._is_hid_device(dap_device):
                packet_size = dap_device.get('out_ep_packet_size')
                if packet_size is not None:
                    if len(temp_data) > packet_size:
                        temp_data = temp_data[:packet_size]
                    else:
                        temp_data.extend([0x00] * (packet_size - len(temp_data)))

            write_len = dev.write(out_ep, temp_data, timeout=timeout)
            if self._is_hid_device(dap_device):
                write_len = len(data)
            return write_len
        except Exception:
            return False

    def receive_data_from_dap_device(self, buffer, timeout=10):
        dap_device = self.get_selected_dap_device
        if dap_device is None:
            return None
        dev = dap_device.get('device', None)
        if dev is None:
            return None

        in_ep = dap_device.get('in_ep', None)
        if in_ep is None:
            return None

        try:
            read_len = dev.read(in_ep, buffer, timeout=timeout)
            if self._is_hid_device(dap_device):
                read_len = self._get_hid_receive_buffer_length(buffer)
            return read_len
        except Exception:
            return None

    def _is_hid_device(self, device):
        if device.get('interface_class', None) == 'HID':
            return True
        return False

    def _get_hid_receive_buffer_length(self, buffer):
        """获取HID接收缓冲区的有效长度，即最后一个非零字节的位置+1"""
        return next((i for i in range(len(buffer) - 1, -1, -1) if buffer[i] != 0), -1) + 1

    def clean_in_ep(self):
        dap_device = self.get_selected_dap_device
        if dap_device is None:
            return False
        packet_size = dap_device.get('out_ep_packet_size')
        buffer =usb.util.create_buffer(packet_size)
        while True:
            res = self.receive_data_from_dap_device(buffer)
            if res is None or res == 0:
                break


