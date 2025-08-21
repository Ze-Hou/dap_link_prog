import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from DAP.dap_handle import DAPHandler

dap_handle = DAPHandler()

dap_handle.get_dap_devices()
dap_handle.select_dap_device_by_index(0)
dap_handle.config_dap_device()
dap_handle.reset_target('hardware')