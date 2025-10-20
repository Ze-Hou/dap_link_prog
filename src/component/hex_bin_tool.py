from typing import Optional
import logging
import copy


class HexBinTool:
    def __init__(self):
        self.parse_data_info = {
            'data': [],
            'addr': [],
            'size': [],
            'count': 0,
            'type': '',
        }
    """
    hex 文件格式：
        :LLAAAATT[DD...]CC
        :：每行以冒号开头
        LL：数据长度（1字节，2个十六进制字符）
        AAAA：数据地址（2字节，4个十六进制字符）
        TT：记录类型（1字节，2个十六进制字符）
            00 - 数据记录
            01 - 文件结束记录
            02 - 扩展段地址记录
            03 - 起始段地址记录
            04 - 扩展线性地址记录
            05 - 起始线性地址记录
        DD：数据（LL字节，2*LL个十六进制字符）
        CC：校验和（1字节，2个十六进制字符），计算方法为：取LL、AAAA、TT及DD各字节之和的二进制补码的最低字节
    """
    HEX_TYPE_DATA = 0
    HEX_TYPE_EOF = 1
    HEX_TYPE_EXT_SEG_ADDRESS = 2
    HEX_TYPE_START_SEG_ADDRESS = 3
    HEX_TYPE_EXT_LINEAR_ADDRESS = 4
    HEX_TYPE_START_LINEAR_ADDRESS = 5

    def get_parse_data_info(self):
        return copy.deepcopy(self.parse_data_info)

    def hex_to_bin_from_file(self, fpath: str) -> Optional[dict]:
        data = self._get_data_from_file(fpath)
        if data is None:
            logging.error(f"Failed to read file: {fpath}")
            return None
        lines = data.splitlines()
        ret = self.get_parse_data_info()
        base_addr = 0
        segment_addr = 0
        next_addr = -1
        count = -1
        for line in lines:
            if line[0] != ord(':'):
                logging.error("Invalid hex file format")
                return None
            type = int(line[7:9], 16)
            if type == self.HEX_TYPE_DATA:
                length = int(line[1:3], 16)
                addr = int(line[3:7], 16) + base_addr + segment_addr
                if addr != next_addr or next_addr == -1:
                    ret['data'].append(bytearray())
                    ret['addr'].append(addr)
                    ret['size'].append(0)
                    ret['count'] += 1
                next_addr = addr + length
                # 处理数据
                data = bytes.fromhex(line[9:9 + length * 2].decode('utf-8'))
                checksum = length + (addr >> 8) + (addr & 0xFF) + type
                checksum += sum(data)
                if (256 - checksum) & 0xFF != int(line[-2:], 16):
                    logging.error(f"Checksum error at address {hex(addr)}")
                    return None
                ret['data'][count].extend(data)
                ret['size'][count] += length
            elif type == self.HEX_TYPE_EOF:
                ret['type'] = 'hex'
                return ret
            elif type == self.HEX_TYPE_EXT_SEG_ADDRESS:
                segment_addr = int(line[9:13], 16) << 4
            elif type == self.HEX_TYPE_EXT_LINEAR_ADDRESS:
                base_addr = int(line[9:13], 16) << 16

        return None

    def bin_from_from_file(self, fpath: str) -> Optional[dict]:
        data = self._get_data_from_file(fpath)
        if data is None:
            logging.error(f"Failed to read file: {fpath}")
            return None
        ret = self.get_parse_data_info()
        ret['data'].append(data)
        ret['addr'].append(0)
        ret['size'].append(len(data))
        ret['count'] = 1
        ret['type'] = 'bin'

        return ret

    def check_data_to_align_4(self, parse_data: Optional[dict]) -> Optional[dict]:
        if parse_data is None:
            return None
        ret = parse_data
        for i in range(ret['count']):
            if ret['size'][i] % 4 != 0:
                logging.warning(f"data size at index {i} is not aligned to 4 bytes, padding with 0xFF.")
                padding = 4 - (ret['size'][i] % 4)
                ret['data'][i].extend(b'\xFF' * padding)
                ret['size'][i] += padding

        return ret

    def bytes_to_dword(self, bytes, size, format = 'little') -> Optional[list]:
        if size % 4 != 0:
            logging.error("Size must be a multiple of 4.")
            return None
        dword = []
        byteorder = 'little' if format == 'little' else 'big'
        for i in range(size // 4):
            dword.append(int.from_bytes(bytes[i*4:(i+1)*4], byteorder=byteorder))

        return dword

    def print_hex_to_bin_info(self, parse_data: Optional[dict]):
        if parse_data is None:
            return
        logging.info(f"total {parse_data['count']} data segments found.")
        logging.info(f"address: {', '.join([hex(a) for a in parse_data['addr']])}")
        logging.info(f"sizes(bytes): {', '.join([str(s) for s in parse_data['size']])}")

    def print_hex_to_bin_data(self, parse_data: Optional[dict]):
        if parse_data is None:
            return
        self.print_hex_to_bin_info(parse_data)
        for i in range(parse_data['count']):
            for j in range(parse_data['size'][i] // 16):
                logging.info(
                    f"{hex(parse_data['addr'][i] + j * 16).zfill(8)}: " +
                    ' '.join([hex(b)[2:].zfill(2) for b in parse_data['data'][i][j * 16:(j + 1) * 16]])
                )
            if parse_data['size'][i] % 16 != 0:
                logging.info(
                    f"{hex(parse_data['addr'][i] + (parse_data['size'][i] // 16) * 16).zfill(8)}: " +
                    ' '.join([hex(b)[2:].zfill(2) for b in parse_data['data'][i][(parse_data['size'][i] // 16) * 16:]])
                )

    def _get_data_from_file(self, fpath: str) -> Optional[bytes]:
        try:
            with open(fpath, 'rb') as f:
                data = f.read()  # 返回类型为 bytes
                return data
        except FileNotFoundError:
            logging.error(f"file (path: {fpath}) not found")
            return None