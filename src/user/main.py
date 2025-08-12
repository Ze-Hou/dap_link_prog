import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from usb_device.usb_device_info import USBDeviceInfo

if __name__ == "__main__":
    # 创建USB设备信息对象
    usb_info = USBDeviceInfo()
    
    usb_info.find_dap_devices()
    print("=== HID DAP Devices ===")
    for i, device in enumerate(usb_info.dap_devices['hid_devices']):
        print(f"HID Device {i+1}:")
        print(f"  VID: 0x{device['VID']:04X}")
        print(f"  PID: 0x{device['PID']:04X}")
        print(f"  SN: {device['SN']}")
        print(f"  Interface: {device['intf_desc']}")
        if device['IN_EP']:
            print(f"  IN EP: 0x{device['IN_EP']['EP']:02X}")
        if device['OUT_EP']:
            print(f"  OUT EP: 0x{device['OUT_EP']['EP']:02X}")
        print()
    
    print("=== Vendor Specific DAP Devices ===")
    for i, device in enumerate(usb_info.dap_devices['vendor_devices']):
        print(f"Vendor Device {i+1}:")
        print(f"  VID: 0x{device['VID']:04X}")
        print(f"  PID: 0x{device['PID']:04X}")
        print(f"  SN: {device['SN']}")
        print(f"  Interface: {device['intf_desc']}")
        if device['IN_EP']:
            print(f"  IN EP: 0x{device['IN_EP']['EP']:02X}")
        if device['OUT_EP']:
            print(f"  OUT EP: 0x{device['OUT_EP']['EP']:02X}")
        print()
    
    print(f"Total HID devices: {len(usb_info.dap_devices['hid_devices'])}")
    print(f"Total Vendor devices: {len(usb_info.dap_devices['vendor_devices'])}")
    
    print("\n完成！")
    