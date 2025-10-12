import usb.core
import usb.util
import usb.backend.libusb1
from typing import Optional, Dict, Any, Union
import logging

class USBDeviceInfo:
    def __init__(self, libusb_backend="./libusb-1.0.29/MinGW64/dll/libusb-1.0.dll"):
        self.backend = usb.backend.libusb1.get_backend(find_library=lambda x: libusb_backend)
        # 定义一个空字典保存DAP设备信息
        self.dap_devices = {
            'dap': [],
        }

    def clean_dap_devices(self):
        self.dap_devices['dap'].clear()

    def usb_devices_info_get(self):
        # 查找所有USB设备
        devices = usb.core.find(find_all=True, backend=self.backend)
        device_list = []
        if devices:
            for device in devices:
                device_list.append(device)

        return device_list

    def find_dap_devices(self, desc='DAP'):
        desc = desc.lower()
        devices = self.usb_devices_info_get()

        for device in devices:
            try:
                temp = self._safe_get_string(device, device.iProduct)
                if isinstance(temp, str):
                    if desc in temp.lower():
                        device_class = self._save_dap_devices(device, desc)

                        if device_class:
                            self.dap_devices['dap'].append(device_class)
            except Exception:
                continue
        # self._print_dap_devices_info(self.dap_devices)
        # self.print_dap_devices(self.dap_devices)
        return self.dap_devices

    def _save_dap_devices(self, device, desc):
        device_class = {
            'HID': [],
            'WinUSB': [],
        }

        device_info: Dict[str, Optional[Union[str, int, Any]]] = {
            'vid': None,
            'pid': None,
            'manufacturer': None,
            'product': None,
            'serial_number': None,
            'intf_desc': None,
            'in_ep': None,
            'in_ep_packet_size': None,
            'out_ep': None,
            'out_ep_packet_size': None,
            'cfg_value': None,
            'interface': None,
            'interface_class': None,
            'device': None,
        }

        desc = desc.lower()

        if device:
            device_info['device'] = device
            try:
                device_info['vid'] = device.idVendor
                device_info['pid'] = device.idProduct
                device_info['manufacturer'] = self._safe_get_string(device, device.iManufacturer)
                device_info['product'] = self._safe_get_string(device, device.iProduct)
                device_info['serial_number'] = self._safe_get_string(device, device.iSerialNumber)

                for cfg in device:
                    for intf in cfg:
                        temp = self._safe_get_string(device, intf.iInterface)
                        if isinstance(temp, str):
                            if desc in temp.lower() and \
                                (intf.bInterfaceClass == 0x3 or intf.bInterfaceClass == 0xFF):
                                device_info['intf_desc'] = self._safe_get_string(device, intf.iInterface)
                                device_info['cfg_value'] = cfg.bConfigurationValue
                                device_info['interface'] = intf.bInterfaceNumber
                                for ep in intf:
                                    if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                                        device_info['in_ep'] = ep.bEndpointAddress
                                        device_info['in_ep_packet_size'] = ep.wMaxPacketSize
                                    elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                                        device_info['out_ep'] = ep.bEndpointAddress
                                        device_info['out_ep_packet_size'] = ep.wMaxPacketSize

                                if intf.bInterfaceClass == 0x3:  # HID class
                                    device_info['interface_class'] = 'HID'
                                    device_class['HID'].append(device_info.copy())
                                elif intf.bInterfaceClass == 0xFF:  # Vendor specific class
                                    device_info['interface_class'] = 'WinUSB'
                                    device_class['WinUSB'].append(device_info.copy())
            except Exception:
                return

        return device_class

    def _safe_get_string(self, device, index):
        if index == 0:
            return ""
        try:
            return usb.util.get_string(device, index)
        except Exception:
            return None

    def _print_dap_devices_info(self, dap_devices):
        device = dap_devices['dap']
        if device:
            for i, device_class in enumerate(device):
                logging.info('='*50)
                if device_class['HID']:
                    logging.info("HID Devices:")
                    for i, hid_device in enumerate(device_class['HID']):
                        logging.info(f"  HID device {i+1}:")
                        logging.info(f"    VID: 0x{hid_device['vid']:04X}, PID: 0x{hid_device['pid']:04X}")
                        logging.info(f"    Manufacturer: {hid_device['manufacturer']}")
                        logging.info(f"    Product: {hid_device['product']}")
                        logging.info(f"    Serial Number: {hid_device['serial_number']}")
                        logging.info(f"    Interface: {hid_device['intf_desc']}")
                        logging.info(f"    Configuration Value: {hid_device['cfg_value']}")
                        logging.info(f"    Interface Number: {hid_device['interface']}")
                        if hid_device['in_ep']:
                            logging.info(f"    IN EP: 0x{hid_device['in_ep']:02X}")
                            logging.info(f"    IN EP Max Packet Size: {hid_device['in_ep_packet_size']}")
                        if hid_device['out_ep']:
                            logging.info(f"    OUT EP: 0x{hid_device['out_ep']:02X}")
                            logging.info(f"    OUT EP Max Packet Size: {hid_device['out_ep_packet_size']}")
                if device_class['WinUSB']:
                    logging.info("WinUSB Devices:")
                    for i, winusb_device in enumerate(device_class['WinUSB']):
                        logging.info(f"  WinUSB device {i+1}:")
                        logging.info(f"    VID: 0x{winusb_device['vid']:04X}, PID: 0x{winusb_device['pid']:04X}")
                        logging.info(f"    Manufacturer: {winusb_device['manufacturer']}")
                        logging.info(f"    Product: {winusb_device['product']}")
                        logging.info(f"    Serial Number: {winusb_device['serial_number']}")
                        logging.info(f"    Interface: {winusb_device['intf_desc']}")
                        logging.info(f"    Configuration Value: {winusb_device['cfg_value']}")
                        logging.info(f"    Interface Number: {winusb_device['interface']}")
                        if winusb_device['in_ep']:
                            logging.info(f"    IN EP: 0x{winusb_device['in_ep']:02X}")
                            logging.info(f"    IN EP Max Packet Size: {winusb_device['in_ep_packet_size']}")
                        if winusb_device['out_ep']:
                            logging.info(f"    OUT EP: 0x{winusb_device['out_ep']:02X}")
                            logging.info(f"    OUT EP Max Packet Size: {winusb_device['out_ep_packet_size']}")
                logging.info('='*50)

    def print_dap_devices(self, dap_devices):
        devices = dap_devices['dap']
        if devices:
            for i, device_class in enumerate(devices):
                if device_class['HID']:
                    for i, hid_device in enumerate(device_class['HID']):
                        logging.info(f"VID: 0x{hid_device['vid']:04X} PID: 0x{hid_device['pid']:04X} "
                                     f"{hid_device['intf_desc']} "
                                     f"SN: {hid_device['serial_number']}")
                if device_class['WinUSB']:
                    for i, winusb_device in enumerate(device_class['WinUSB']):
                        logging.info(f"VID: 0x{winusb_device['vid']:04X} PID: 0x{winusb_device['pid']:04X} "
                                     f"{winusb_device['intf_desc']} "
                                     f"SN: {winusb_device['serial_number']}")
