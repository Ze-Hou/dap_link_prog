import usb.core
import usb.util
import usb.backend.libusb1

class USBDeviceInfo:
    def __init__(self, libusb_backend="./libusb-1.0.29/MinGW64/dll/libusb-1.0.dll"):
        self.backend = usb.backend.libusb1.get_backend(find_library=lambda x: libusb_backend)
        self.dap_devices = {
            'hid_devices': [],      # HID接口的DAP设备
            'vendor_devices': [],   # 厂商自定义接口的DAP设备
        }
        
    def _get_string_descriptor(self, device, index):
        """安全获取字符串描述符"""
        try:
            if index > 0:
                return usb.util.get_string(device, index)
        except Exception:
            pass
        return None
    
    def _get_device_descriptor_info(self, device):
        """获取设备描述符信息"""
        return {
            'bLength': device.bLength,
            'bDescriptorType': device.bDescriptorType,
            'bcdUSB': hex(device.bcdUSB),
            'bDeviceClass': hex(device.bDeviceClass),
            'bDeviceSubClass': hex(device.bDeviceSubClass),
            'bDeviceProtocol': hex(device.bDeviceProtocol),
            'bMaxPacketSize0': device.bMaxPacketSize0,
            'idVendor': hex(device.idVendor),
            'idProduct': hex(device.idProduct),
            'bcdDevice': hex(device.bcdDevice),
            'iManufacturer': device.iManufacturer,
            'iProduct': device.iProduct,
            'iSerialNumber': device.iSerialNumber,
            'bNumConfigurations': device.bNumConfigurations
        }
    
    def _get_configuration_descriptor_info(self, config):
        """获取配置描述符信息"""
        return {
            'bLength': config.bLength,
            'bDescriptorType': config.bDescriptorType,
            'wTotalLength': config.wTotalLength,
            'bNumInterfaces': config.bNumInterfaces,
            'bConfigurationValue': config.bConfigurationValue,
            'iConfiguration': config.iConfiguration,
            'bmAttributes': hex(config.bmAttributes),
            'bMaxPower': config.bMaxPower
        }
    
    def _get_interface_descriptor_info(self, interface):
        """获取接口描述符信息"""
        return {
            'bLength': interface.bLength,
            'bDescriptorType': interface.bDescriptorType,
            'bInterfaceNumber': interface.bInterfaceNumber,
            'bAlternateSetting': interface.bAlternateSetting,
            'bNumEndpoints': interface.bNumEndpoints,
            'bInterfaceClass': hex(interface.bInterfaceClass),
            'bInterfaceSubClass': hex(interface.bInterfaceSubClass),
            'bInterfaceProtocol': hex(interface.bInterfaceProtocol),
            'iInterface': interface.iInterface
        }
    
    def _get_endpoint_descriptor_info(self, endpoint):
        """获取端点描述符信息"""
        return {
            'bLength': endpoint.bLength,
            'bDescriptorType': endpoint.bDescriptorType,
            'bEndpointAddress': hex(endpoint.bEndpointAddress),
            'bmAttributes': hex(endpoint.bmAttributes),
            'wMaxPacketSize': endpoint.wMaxPacketSize,
            'bInterval': endpoint.bInterval
        }
    
    def _analyze_packet_size(self, max_packet_size):
        """分析包大小信息"""
        base_size = max_packet_size & 0x7FF
        additional_transactions = (max_packet_size >> 11) & 0x3
        total_max_bytes = base_size * (additional_transactions + 1)
        
        return {
            'base_size': base_size,
            'additional_transactions': additional_transactions,
            'total_max_bytes': total_max_bytes,
            'raw_value': max_packet_size
        }
    
    def _get_endpoint_info(self, endpoint):
        """获取端点完整信息"""
        endpoint_type_names = ['Control', 'Isochronous', 'Bulk', 'Interrupt']
        endpoint_type = endpoint.bmAttributes & 0x3
        
        return {
            'address': hex(endpoint.bEndpointAddress),
            'attributes': hex(endpoint.bmAttributes),
            'direction': 'IN' if endpoint.bEndpointAddress & 0x80 else 'OUT',
            'type': endpoint_type_names[endpoint_type],
            'type_code': endpoint_type,
            'max_packet_size': endpoint.wMaxPacketSize,
            'interval': endpoint.bInterval,
            'descriptor': self._get_endpoint_descriptor_info(endpoint),
            'packet_analysis': self._analyze_packet_size(endpoint.wMaxPacketSize)
        }
        
    def usb_device_info_get(self):
        """获取所有USB设备的完整注册信息"""
        devices = usb.core.find(find_all=True, backend=self.backend)
        device_list = []
        
        for device in devices:
            # 基本设备信息
            device_info = {
                # 基本标识信息
                'vendor_id': hex(device.idVendor),
                'product_id': hex(device.idProduct),
                'device_class': hex(device.bDeviceClass),
                'device_subclass': hex(device.bDeviceSubClass),
                'device_protocol': hex(device.bDeviceProtocol),
                'device_version': hex(device.bcdDevice),
                'usb_version': hex(device.bcdUSB),
                'max_packet_size': device.bMaxPacketSize0,
                'num_configurations': device.bNumConfigurations,
                
                # USB注册信息 - 字符串描述符
                'manufacturer': self._get_string_descriptor(device, device.iManufacturer),
                'product': self._get_string_descriptor(device, device.iProduct),
                'serial_number': self._get_string_descriptor(device, device.iSerialNumber),
                
                # 完整描述符信息
                'device_descriptor': self._get_device_descriptor_info(device),
                
                # 设备状态信息
                'device_state': {
                    'address': getattr(device, 'address', 'Unknown'),
                    'port_number': getattr(device, 'port_number', 'Unknown'),
                    'speed': getattr(device, 'speed', 'Unknown'),
                },
                
                # 配置信息
                'configurations': []
            }
            
            # 获取设备类别描述
            device_info['class_info'] = self._get_device_class_info(device.bDeviceClass)
            
            # 遍历所有配置
            for config in device:
                config_info = {
                    # 基本配置信息
                    'configuration_value': config.bConfigurationValue,
                    'max_power_ma': config.bMaxPower * 2,  # 转换为mA
                    'attributes': hex(config.bmAttributes),
                    'self_powered': bool(config.bmAttributes & 0x40),
                    'remote_wakeup': bool(config.bmAttributes & 0x20),
                    'num_interfaces': config.bNumInterfaces,
                    
                    # 配置字符串描述符
                    'description': self._get_string_descriptor(device, config.iConfiguration),
                    
                    # 完整配置描述符
                    'config_descriptor': self._get_configuration_descriptor_info(config),
                    
                    # 接口信息
                    'interfaces': []
                }
                
                # 遍历所有接口
                for interface in config:
                    interface_info = {
                        # 基本接口信息
                        'interface_number': interface.bInterfaceNumber,
                        'alternate_setting': interface.bAlternateSetting,
                        'interface_class': hex(interface.bInterfaceClass),
                        'interface_subclass': hex(interface.bInterfaceSubClass),
                        'interface_protocol': hex(interface.bInterfaceProtocol),
                        'num_endpoints': interface.bNumEndpoints,
                        
                        # 接口字符串描述符
                        'description': self._get_string_descriptor(device, interface.iInterface),
                        
                        # 接口类别信息
                        'class_info': self._get_interface_class_info(interface.bInterfaceClass),
                        
                        # 完整接口描述符
                        'interface_descriptor': self._get_interface_descriptor_info(interface),
                        
                        # 端点信息
                        'endpoints': []
                    }
                    
                    # 遍历所有端点
                    for endpoint in interface:
                        endpoint_info = self._get_endpoint_info(endpoint)
                        interface_info['endpoints'].append(endpoint_info)
                    
                    config_info['interfaces'].append(interface_info)
                
                device_info['configurations'].append(config_info)
            
            device_list.append(device_info)
        
        return device_list
    
    def _get_device_class_info(self, device_class):
        """获取设备类别信息"""
        class_names = {
            0x00: "Use interface class",
            0x01: "Audio",
            0x02: "Communications and CDC Control",
            0x03: "HID (Human Interface Device)",
            0x05: "Physical",
            0x06: "Image/Still Image Capture",
            0x07: "Printer",
            0x08: "Mass Storage",
            0x09: "Hub",
            0x0A: "CDC-Data",
            0x0B: "Smart Card",
            0x0D: "Content Security",
            0x0E: "Video",
            0x0F: "Personal Healthcare",
            0x10: "Audio/Video",
            0x11: "Billboard",
            0xDC: "Diagnostic",
            0xE0: "Wireless Controller",
            0xEF: "Miscellaneous",
            0xFE: "Application Specific",
            0xFF: "Vendor Specific"
        }
        return {
            'code': hex(device_class),
            'name': class_names.get(device_class, "Unknown"),
            'description': f"Device Class {hex(device_class)}"
        }
    
    def _get_interface_class_info(self, interface_class):
        """获取接口类别信息"""
        class_names = {
            0x00: "Use interface class",
            0x01: "Audio",
            0x02: "Communications and CDC Control",
            0x03: "HID (Human Interface Device)",
            0x05: "Physical",
            0x06: "Image",
            0x07: "Printer",
            0x08: "Mass Storage",
            0x09: "Hub",
            0x0A: "CDC-Data",
            0x0B: "Smart Card",
            0x0D: "Content Security",
            0x0E: "Video",
            0x0F: "Personal Healthcare",
            0x10: "Audio/Video",
            0x11: "Billboard",
            0xDC: "Diagnostic",
            0xE0: "Wireless Controller",
            0xEF: "Miscellaneous",
            0xFE: "Application Specific",
            0xFF: "Vendor Specific"
        }
        return {
            'code': hex(interface_class),
            'name': class_names.get(interface_class, "Unknown"),
            'description': f"Interface Class {hex(interface_class)}"
        }
    
    def print_device_info(self, devices=None, detail_level='summary'):
        """
        打印USB设备信息
        
        Args:
            devices: 设备列表，如果为None则重新获取
            detail_level: 详细程度 ('summary', 'detailed', 'full')
        """
        if devices is None:
            devices = self.usb_device_info_get()
        
        print(f"Found {len(devices)} USB devices")
        print("=" * 80)
        
        for i, device in enumerate(devices):
            self._print_device_summary(device, i + 1)
            
            if detail_level in ['detailed', 'full']:
                self._print_device_details(device, detail_level)
                
            print("-" * 80)
        
        return len(devices)
    
    def _print_device_summary(self, device, device_num):
        """打印设备摘要信息"""
        print(f"Device {device_num}:")
        print(f"  Vendor ID: {device['vendor_id']}")
        print(f"  Product ID: {device['product_id']}")
        print(f"  Manufacturer: {device.get('manufacturer', 'N/A')}")
        print(f"  Product: {device.get('product', 'N/A')}")
        print(f"  Serial Number: {device.get('serial_number', 'N/A')}")
        print(f"  Device Class: {device['class_info']['name']} ({device['device_class']})")
        print(f"  USB Version: {device['usb_version']}")
        print(f"  Configurations: {device['num_configurations']}")
    
    def _print_device_details(self, device, detail_level):
        """打印设备详细信息"""
        print("\n  Device Details:")
        
        # 设备状态
        state = device['device_state']
        print(f"    Device Address: {state['address']}")
        print(f"    Port Number: {state['port_number']}")
        print(f"    Speed: {state['speed']}")
        
        # 遍历配置
        for i, config in enumerate(device['configurations']):
            print(f"\n  Configuration {i + 1}:")
            print(f"    Configuration Value: {config['configuration_value']}")
            print(f"    Max Power: {config['max_power_ma']}mA")
            print(f"    Self Powered: {'Yes' if config['self_powered'] else 'No'}")
            print(f"    Remote Wakeup: {'Yes' if config['remote_wakeup'] else 'No'}")
            
            if config['description']:
                print(f"    Configuration Description: {config['description']}")
            
            # 遍历接口
            for j, interface in enumerate(config['interfaces']):
                print(f"\n    Interface {j + 1}:")
                print(f"      Interface Number: {interface['interface_number']}")
                print(f"      Interface Class: {interface['class_info']['name']} ({interface['interface_class']})")
                print(f"      Number of Endpoints: {interface['num_endpoints']}")
                
                if interface['description']:
                    print(f"      Interface Description: {interface['description']}")
                
                # 遍历端点
                if detail_level == 'full' and interface['endpoints']:
                    print("      Endpoints:")
                    for k, endpoint in enumerate(interface['endpoints']):
                        self._print_endpoint_info(endpoint, k + 1)
    
    def _print_endpoint_info(self, endpoint, endpoint_num):
        """打印端点详细信息"""
        print(f"        Endpoint {endpoint_num}:")
        print(f"          Address: {endpoint['address']}")
        print(f"          Direction: {endpoint['direction']}")
        print(f"          Type: {endpoint['type']}")
        print(f"          Max Packet Size: {endpoint['max_packet_size']}")
        print(f"          Interval: {endpoint['interval']}")
        
        # 包大小分析
        packet = endpoint['packet_analysis']
        print("          Packet Analysis:")
        print(f"            Base Size: {packet['base_size']} bytes")
        print(f"            Additional Transactions: {packet['additional_transactions']}")
        print(f"            Total Max Bytes: {packet['total_max_bytes']} bytes")
    
    def print_device_list(self, devices=None):
        """打印设备列表"""
        if devices is None:
            devices = self.usb_device_info_get()
        
        print(f"USB Device List ({len(devices)} devices found):")
        print("-" * 60)
        
        for i, device in enumerate(devices):
            product = device.get('product', 'Unknown Product')
            manufacturer = device.get('manufacturer', 'Unknown')
            print(f"{i + 1:2d}. {product} - {manufacturer}")
            print(f"    VID: {device['vendor_id']}, PID: {device['product_id']}")
            print(f"    Class: {device['class_info']['name']}")
            print()
        
        return len(devices)
    
    def find_devices_by_string(self, search_string, case_sensitive=False):
        """
        根据字符串描述符查找设备
        
        Args:
            search_string: 要搜索的字符串
            case_sensitive: 是否区分大小写，默认False
            
        Returns:
            list: 包含匹配设备的列表，每个元素包含设备信息和匹配的字段
        """
        devices = self.usb_device_info_get()
        matching_devices = []
        
        # 准备搜索字符串
        if not case_sensitive:
            search_string = search_string.lower()
        
        for device in devices:
            matches = []
            
            # 搜索产品名称
            product = device.get('product')
            if product:
                product_check = product.lower() if not case_sensitive else product
                if search_string in product_check:
                    matches.append(('product', product))
            
            # 搜索接口描述符
            for config_idx, config in enumerate(device['configurations']):
                for intf_idx, interface in enumerate(config['interfaces']):
                    intf_desc = interface.get('description')
                    if intf_desc:
                        intf_check = intf_desc.lower() if not case_sensitive else intf_desc
                        if search_string in intf_check:
                            matches.append(('interface_description', intf_desc, config_idx, intf_idx))
            
            # 如果有匹配，添加到结果中
            if matches:
                matching_devices.append({
                    'device': device,
                    'matches': matches
                })
        
        return matching_devices
    
    def find_dap_devices(self):
        """查找DAP设备并打印完整信息"""
        # 搜索包含DAP的设备
        dap_devices = self.find_devices_by_string('DAP', case_sensitive=False)
        
        if not dap_devices:
            print("No DAPdevices found in the system.")
            return []
        
        # 先清除之前的结果
        self.dap_devices = {
            'hid_devices': [],      # HID接口的DAP设备
            'vendor_devices': [],   # 厂商自定义接口的DAP设备
        }
        
        for i, match_info in enumerate(dap_devices):
            device = match_info['device']
            matches = match_info['matches']
            
            # 保存匹配的接口描述符
            for match in matches:
                if match[0] == 'interface_description':
                    config_idx, intf_idx = match[2], match[3]
                    interface = device['configurations'][config_idx]['interfaces'][intf_idx]

                    if  int(interface['interface_class'], 16) == 0x03:
                        device_info = self._save_dap_devices_info(device, interface)
                        if device_info:
                            self.dap_devices['hid_devices'].append(device_info)
                    elif int(interface['interface_class'], 16) == 0xFF:
                        device_info = self._save_dap_devices_info(device, interface)
                        if device_info:
                            self.dap_devices['vendor_devices'].append(device_info)

    def _save_dap_devices_info(self, device, interface):
        """保存DAP设备信息"""
        device_info = {
            'VID': 0x0000,
            'PID': 0x0000,
            'SN': 'None',
            'IN_EP': [],
            'OUT_EP': [],
            'intf_desc': 'None',
            'device': [],
        }
        device_ep_info = {
            'EP': 0x00,
            'MaxPacketSize': 0,
        }

        if int(interface['interface_class'], 16) == 0x03 or \
            int(interface['interface_class'], 16) == 0xFF:
            
            device_info['VID'] = int(device['vendor_id'], 16)
            device_info['PID'] = int(device['product_id'], 16)
            device_info['SN'] = device.get('serial_number', 'None')
            device_info['intf_desc'] = interface.get('description', 'None')
            
            if interface['num_endpoints'] == 2:
                for endpoint in interface['endpoints']:
                    if endpoint['direction'] == 'IN':
                        device_ep_info['EP'] = int(endpoint['address'], 16)
                        device_ep_info['MaxPacketSize'] = endpoint['max_packet_size']
                        device_info['IN_EP'] = device_ep_info.copy()
                    elif endpoint['direction'] == 'OUT':
                        device_ep_info['EP'] = int(endpoint['address'], 16)
                        device_ep_info['MaxPacketSize'] = endpoint['max_packet_size']
                        device_info['OUT_EP'] = device_ep_info.copy()

            device_info['device'] = device

            return device_info
        
        else:
            return None