import ctypes
from elftools.elf.elffile import ELFFile
import io
from collections import namedtuple
import xml.etree.ElementTree as ET
import logging
from pathlib import Path


class FlashDefine:
    VERS       = 1      # Interface Version 1.01
    # UNKNOWN    = 0      # Unknown
    # ONCHIP     = 1      # On-chip Flash Memory
    # EXT8BIT    = 2      # External Flash Device on 8-bit Bus
    # EXT16BIT   = 3      # External Flash Device on 16-bit Bus
    # EXT32BIT   = 4      # External Flash Device on 32-bit Bus
    # EXTSPI     = 5      # External Flash Device on SPI
    TYPE = ['UNKNOWN', 'ONCHIP', 'EXT8BIT', 'EXT16BIT', 'EXT32BIT', 'EXTSPI']

    SECTOR_NUM = 512    # Max Number of Sector Items
    PAGE_MAX   = 65536  # Max Page Size for Programming

    SECTOR_END = (0xFFFFFFFF, 0xFFFFFFFF)  # End of Sector

    FLASH_DRV_VERS = (0x0100 + VERS)  # Flash Driver Version

class FlashSectors(ctypes.LittleEndianStructure):
    _fields_ = [
        ('szSector',    ctypes.c_uint32),               # Sector Size in Bytes
        ('AddrSector',  ctypes.c_uint32),               # Address of Sector
    ]


class FlashDevice(ctypes.LittleEndianStructure):
    _fields_ = [
        ('Vers',        ctypes.c_uint16),               # Version Number and Architecture
        ('DevName',     ctypes.c_char * 128),           # Device Name and Description
        ('DevType',     ctypes.c_uint16),               # Device Type: ONCHIP, EXT8BIT, EXT16BIT, ...
        ('DevAdr',      ctypes.c_uint32),               # Default Device Start Address
        ('szDev',       ctypes.c_uint32),               # Total Size of Device
        ('szPage',      ctypes.c_uint32),               # Programming Page Size
        ('_reserved',   ctypes.c_uint32),               # Reserved for future Extension
        ('valEmpty',    ctypes.c_uint8),                # Content of Erased Memory
        ('toProg',      ctypes.c_uint32),               # Time Out of Program Page Function
        ('toErase',     ctypes.c_uint32),               # Time Out of Erase Sector Function
        ('sectors',     FlashSectors * FlashDefine.SECTOR_NUM),    # Sectors Information
    ]


class FlashAlgo(ctypes.LittleEndianStructure):
    _fields_ = [
        ('AlgoStart',           ctypes.c_uint32),               # Start Address of Algorithm
        ('AlgoSize',            ctypes.c_uint32),               # Size of Algorithm
        ('AlgoBlob',            ctypes.POINTER(ctypes.c_uint32)), # Pointer to Algorithm Blob
        ('Init',                ctypes.c_uint32),               # Pointer to Init Function
        ('UnInit',              ctypes.c_uint32),               # Pointer to UnInit Function
        ('EraseChip',           ctypes.c_uint32),               # Pointer to Erase Chip Function
        ('EraseSector',         ctypes.c_uint32),               # Pointer to Erase Sector Function
        ('ProgramPage',         ctypes.c_uint32),               # Pointer to Program Page Function
        ('StaticBase',          ctypes.c_uint32),               # Static Base Address
        ('ProgramBuffer',       ctypes.c_uint32),               # Pointer to Program Buffer
        ('ProgramBufferSize',   ctypes.c_uint32),               # Size of Program Buffer
        ('BreakPoint',          ctypes.c_uint32),               # Pointer to Breakpoint Function
        ('StackPointer',        ctypes.c_uint32),               # Stack Pointer
    ]


class ParseElfFile(ELFFile):
    def __init__(self, f_path: str, device:str, ram_base_addr = 0, print_info: bool = False):
        self.f_path = f_path
        self.dev = device.lower()
        self.ram_base_addr = ram_base_addr
        self.print_info = print_info
        self.data = self._get_elf_data()
        if self.data is None:
            logging.error("Failed to read ELF file.")
            self.parse_flag = False
            return
        super().__init__(io.BytesIO(self.data))
        self.flash_device = FlashDevice()
        self.flash_algo = FlashAlgo()
        self.algo_blob = None
        self.parse_flag = self._parse()

    def _parse(self) -> bool:
        symbols = dict()
        if self._get_elf_symbols(symbols):
            missing = set(self.REQUIRED_SYMBOLS) - set(symbols)
            if missing:
                logging.error(f"Missing required symbol(s): {', '.join(missing)}")
                return False

            info = symbols['FlashDevice']
            data = self._get_elf_segments_data(info.value, ctypes.sizeof(FlashDevice), \
                                               self.SEGMENT_FLAGS['PF_R'] | self.SEGMENT_FLAGS['PF_MASKPROC'])

            if data is None or len(data) < ctypes.sizeof(FlashDevice):
                logging.error("Invalid FlashDevice data segment.")
                return False

            self.flash_device = FlashDevice.from_buffer_copy(data)

            data = self._get_elf_algo_data()
            if data is None:
                logging.error("Failed to get algorithm data from ELF file.")
                return False
            self.algo_blob, algo_size, static_base = data

            ram_base_addr = self._get_ram_base_addr()
            if self.ram_base_addr != 0:
                ram_base_addr = self.ram_base_addr

            header_size = 32 # 中断halt程序大小

            self.flash_algo.AlgoStart = ram_base_addr
            self.flash_algo.AlgoSize = algo_size
            self.flash_algo.AlgoBlob = (ctypes.c_uint32 * (len(self.algo_blob)))(*self.algo_blob)

            self.flash_algo.Init = symbols['Init'].value + ram_base_addr + header_size
            self.flash_algo.UnInit = symbols['UnInit'].value + ram_base_addr + header_size
            self.flash_algo.EraseChip = symbols['EraseChip'].value + ram_base_addr + header_size
            self.flash_algo.EraseSector = symbols['EraseSector'].value + ram_base_addr + header_size
            self.flash_algo.ProgramPage = symbols['ProgramPage'].value + ram_base_addr + header_size
            self.flash_algo.StaticBase = static_base + ram_base_addr + header_size

            self.flash_algo.ProgramBuffer = ram_base_addr + (algo_size if algo_size % 4 == 0 else (algo_size + (4 - algo_size % 4)))
            self.flash_algo.ProgramBufferSize = self.flash_device.szPage

            self.flash_algo.BreakPoint = ram_base_addr + 1 # Thumb mode
            self.flash_algo.StackPointer = self.flash_algo.ProgramBuffer + self.flash_algo.ProgramBufferSize + 0x400 # 1KB stack
            if self.print_info:
                self._print_flash_device_info()
                self._print_flash_algo_info()

            return True
        return False

    def _print_flash_device_info(self):
        logging.info("FlashDevice info:")
        logging.info(f"\tversion: 0x{self.flash_device.Vers:02X}")
        logging.info(f"\tname: {self.flash_device.DevName.decode().rstrip(chr(0))}")
        type_str = FlashDefine.TYPE[self.flash_device.DevType] if 0 <= self.flash_device.DevType < len(FlashDefine.TYPE) else 'UNKNOWN'
        logging.info(f"\ttype: {type_str}")
        logging.info(f"\taddress: 0x{self.flash_device.DevAdr:08X}")
        logging.info(f"\tsize: {int(self.flash_device.szDev / 1024)} Kbytes")
        logging.info(f"\tpage size: {self.flash_device.szPage} bytes")
        logging.info(f"\terased value: 0x{self.flash_device.valEmpty:02X}")
        logging.info(f"\ttimeout program: {self.flash_device.toProg} ms")
        logging.info(f"\ttimeout erase: {self.flash_device.toErase} ms")
        logging.info("\tsectors:")
        for i in range(FlashDefine.SECTOR_NUM):
            if (self.flash_device.sectors[i].szSector == FlashDefine.SECTOR_END[0] and \
                self.flash_device.sectors[i].AddrSector == FlashDefine.SECTOR_END[1]):
                break
            logging.info(f"\t\tsize: {self.flash_device.sectors[i].szSector} bytes")
            logging.info(f"\t\taddress: 0x{self.flash_device.sectors[i].AddrSector:08X}")

    def _print_flash_algo_info(self):
        logging.info("FlashAlgo info:")
        logging.info(f"\tAlgoStart: 0x{self.flash_algo.AlgoStart:08X}")
        logging.info(f"\tAlgoSize: {self.flash_algo.AlgoSize} bytes")
        logging.info(f"\tAlgoBlob: {self.flash_algo.AlgoBlob}")
        logging.info(f"\tInit: 0x{self.flash_algo.Init:08X}")
        logging.info(f"\tUnInit: 0x{self.flash_algo.UnInit:08X}")
        logging.info(f"\tEraseChip: 0x{self.flash_algo.EraseChip:08X}")
        logging.info(f"\tEraseSector: 0x{self.flash_algo.EraseSector:08X}")
        logging.info(f"\tProgramPage: 0x{self.flash_algo.ProgramPage:08X}")
        logging.info(f"\tStaticBase: 0x{self.flash_algo.StaticBase:08X}")
        logging.info(f"\tProgramBuffer: 0x{self.flash_algo.ProgramBuffer:08X}")
        logging.info(f"\tProgramBufferSize: {self.flash_algo.ProgramBufferSize} bytes")
        logging.info(f"\tBreakPoint: 0x{self.flash_algo.BreakPoint:08X}")
        logging.info(f"\tStackPointer: 0x{self.flash_algo.StackPointer:08X}")

    def _get_elf_symbols(self, symbols: dict) -> bool:
        Symbol = namedtuple('Symbol', ('name', 'value', 'size'))

        section  = self.get_section_by_name('.symtab')
        if section is None:
            return False
        for symbol in section.iter_symbols():
            if symbol.name in self.REQUIRED_SYMBOLS + self.EXTRA_SYMBOLS:
                symbols[symbol.name] = Symbol(symbol.name, symbol.entry['st_value'], symbol.entry['st_size'])
        return True

    def _get_elf_data(self):
        try:
            with open(self.f_path, 'rb') as f:
                data = f.read()
                e_ident = data[:16] # Magic number and other info
                if not (e_ident[:4] == b'\x7fELF'):
                    logging.error("Not a valid ELF file.")
                    return None
                return data
        except Exception as e:
            logging.error(f"Error reading ELF file: {e}")
            return None

    def _get_elf_algo_data(self):
        ro_rw_zi = [None, None, None]
        # 获取elf节内的RO，RW和ZI段
        for section in self.iter_sections():
            for i, name_and_type in enumerate((('PrgCode', 'SHT_PROGBITS'),
                                               ('PrgData', 'SHT_PROGBITS'),
                                               ('PrgData', 'SHT_NOBITS'),)):
                # 检查节的名称和类型是否匹配
                if name_and_type != (section.name, section['sh_type']):
                    continue
                # 如果已经有一个同类型的节被放进去了，则抛出异常
                if ro_rw_zi[i] is not None:
                    logging.error('Duplicated section')
                    return None

                ro_rw_zi[i] = section

        s_ro, s_rw, s_zi = ro_rw_zi
        if s_rw is not None and s_zi is None:
            s_zi = {
                'sh_addr': s_rw['sh_addr'] + s_rw['sh_size'],
                'sh_size': 0
            }
        # 检查RO，RW和ZI节是否存在
        if s_ro is None:
            logging.error('RO section is missing')
            return None
        if s_rw is None:
            logging.error('RW section is missing')
            return None
        if s_zi is None:
            logging.error('ZI section is missing')
            return None
        if s_ro['sh_addr'] != 0:
            logging.error('RO section does not start at address 0')
            return None
        if s_ro['sh_addr'] + s_ro['sh_size'] != s_rw['sh_addr']:
            logging.error('RW section does not follow RO section')
            return None
        if s_rw['sh_addr'] + s_rw['sh_size'] != s_zi['sh_addr']:
            logging.error('ZI section does not follow RW section')
            return None

        read_size = s_ro['sh_size'] + s_rw['sh_size']
        algo_size = s_ro['sh_size'] + s_rw['sh_size'] + s_zi['sh_size']
        static_base = s_ro['sh_size']

        # 判断algo_size是不是4字节对齐
        if algo_size % 4 != 0:
            algo_size += 4 - (algo_size % 4)

        algo_size = algo_size + 32  # 额外加32字节的空间给中断halt程序

        data = self._get_elf_segments_data(s_ro['sh_addr'], read_size, \
                self.SEGMENT_FLAGS['PF_R'] | self.SEGMENT_FLAGS['PF_W'] | self.SEGMENT_FLAGS['PF_X'])

        if data is None or len(data) < read_size:
            logging.error("Invalid algorithm data segment.")
            return None

        algo_blob = (ctypes.c_uint8 * (algo_size))()
        algo_blob = ctypes.cast(algo_blob, ctypes.POINTER(ctypes.c_uint32))[:algo_size//4]

        # 这8个数是中断halt程序，让函数执行完后返回到这里来执行从而让CPU自动halt住
        algo_blob[0] = 0xE00ABE00
        algo_blob[1] = 0x062D780D
        algo_blob[2] = 0x24084068
        algo_blob[3] = 0xD3000040
        algo_blob[4] = 0x1E644058
        algo_blob[5] = 0x1C49D1FA
        algo_blob[6] = 0x2A001E52
        algo_blob[7] = 0x4770D1F2

        algo_blob[8:(8+read_size // 4)] = ctypes.cast(data, ctypes.POINTER(ctypes.c_uint32))[:read_size // 4]
        return algo_blob, algo_size, static_base

    def _get_elf_segments_data(self, address: int, size: int, flag):
        for segment in self.iter_segments():
            p_type = segment['p_type']
            if p_type != 'PT_LOAD':
                continue
            p_paddr = segment['p_paddr']
            p_filesz = segment['p_filesz']
            if address >= p_paddr and (address + size) <= (p_paddr + p_filesz) \
                and (segment['p_flags'] & flag):
                offset = address - p_paddr
                return segment.data()[offset:offset + size]
        return None

    def _get_ram_base_addr(self):
        # 先判断路径分隔符是不是'\\'，如果是则将其替换为'/'
        if '\\' in self.f_path:
            self.f_path = self.f_path.replace('\\', '/')
        path = self.f_path.rsplit('/', 3)
        pdsc_path =  f"{path[0]}/{path[1]}/{path[2]}/{path[1]}.{path[2]}.pdsc"
        pasc_data = ParsePdscFile.parse_pdsc_file(pdsc_path)

        ram_addr = 0

        if pasc_data:
            for dev, dev_info in pasc_data.items():
                if self.dev in dev.lower():
                    for mem, mem_info in dev_info['memories'].items():
                        if 'ram' in mem.lower():
                            if mem_info['start'] & 0x20000000:
                                ram_addr = mem_info['start']
                                break

        return ram_addr

    REQUIRED_SYMBOLS = (
        'Init',
        'UnInit',
        'EraseChip',
        'EraseSector',
        'ProgramPage',
        'FlashDevice',
    )

    EXTRA_SYMBOLS = (
        'BlankCheck',
        'EraseChip',
        'Verify',
        'Read',
    )

    SEGMENT_FLAGS = {
        'PF_X':         1 << 0,  # Execute
        'PF_W':         1 << 1,  # Write
        'PF_R':         1 << 2,  # Read
        'PF_MASKOS':    0x0ff00000,  # OS-specific
        'PF_MASKPROC':  0xf0000000,  # Processor-specific
    }


class ParsePdscFile:
    @staticmethod
    def parse_pdsc_file(pdsc_path):
        return ParsePdscFile()._parse_pdsc_file(pdsc_path)

    @staticmethod
    def get_all_device_info_from_pdsc() -> list:
        pdsc_path =  list(Path("./packs").rglob("*.pdsc"))
        if not pdsc_path:
            logging.error("No pdsc file found in ./packs")
            return []
        all_device = []
        parse = ParsePdscFile()
        for pdsc in pdsc_path:
            flm_dir = str(Path(pdsc).parent.as_posix())
            data = parse._parse_pdsc_file(pdsc)
            for dev, dev_info in data.items():
                device_info = {
                    'vendor': dev_info['from_pack']['vendor'],
                    'family': dev_info['sub_family'],
                    'device': dev[1:] if dev.startswith('-') else dev,  # 雅特力的pdsc文件中，设备名前面会有一个'-'，去掉再添加
                    'algorithm': []
                }
                for algo in dev_info['algorithms']:
                    flm = Path(algo['file_name']).name
                    flm_path = f"./{flm_dir}/{flm}"
                    device_info['algorithm'].append((flm, flm_path))
                all_device.append(device_info)
        return all_device

    def _parse_pdsc_file(self, pdsc_path):
        """解析pdsc文件，返回设备详细信息字典"""
        tree = ET.parse(pdsc_path)
        root = tree.getroot()
        parse_data = {}
        vendor = root.findtext('vendor')
        pack = root.findtext('name')
        version = None
        url = root.findtext('url')
        # 获取最新release的version
        releases = root.find('releases')
        if releases is not None:
            release = releases.find('release')
            if release is not None:
                version = release.attrib.get('version')
        for family in root.findall('.//family'):
            family_name = family.attrib.get('Dfamily')
            vendor_id = family.attrib.get('Dvendor')
            for subfamily in family.findall('subFamily'):
                subfamily_name = subfamily.attrib.get('DsubFamily')
                for device in subfamily.findall('device'):
                    dname = device.attrib.get('Dname')
                    if not dname:
                        continue
                    # memories
                    memories = {}
                    for mem in device.findall('memory'):
                        mem_name = mem.attrib.get('name', mem.attrib.get('id'))
                        if not mem_name:
                            continue
                        access = mem.attrib.get('access', 'rwx')
                        access_dict = {
                            'read': 'r' in access,
                            'write': 'w' in access,
                            'execute': 'x' in access,
                            'peripheral': False,
                            'secure': False,
                            'non_secure': False,
                            'non_secure_callable': False
                        }
                        memories[mem_name] = {
                            'p_name': None,
                            'access': access_dict,
                            'start': int(mem.attrib.get('start', '0'), 0),
                            'size': int(mem.attrib.get('size', '0'), 0),
                            'startup': mem.attrib.get('startup', '0') == '1',
                            'default': mem.attrib.get('default', '0') == '1'
                        }
                    # algorithms
                    algorithms = []
                    for algo in device.findall('algorithm'):
                        algorithms.append({
                            'file_name': algo.attrib.get('name'),
                            'start': int(algo.attrib.get('start', '0'), 0),
                            'size': int(algo.attrib.get('size', '0'), 0),
                            'default': algo.attrib.get('default', '0') == '1',
                            'ram_start': int(algo.attrib.get('RAMstart', '0'), 0) if 'RAMstart' in algo.attrib else None,
                            'ram_size': int(algo.attrib.get('RAMsize', '0'), 0) if 'RAMsize' in algo.attrib else None,
                            'style': 'Keil'
                        })
                    # processors
                    processors = []
                    for proc in family.findall('processor'):
                        processors.append({
                            'core': proc.attrib.get('Dcore', ''),
                            'fpu': proc.attrib.get('Dfpu', ''),
                            'mpu': 'Present' if proc.attrib.get('Dmpu', '0') == '1' else 'Absent',
                            'ap': {'Index': 0},
                            'dp': 0,
                            'address': None,
                            'svd': None,
                            'name': None,
                            'unit': 0,
                            'default_reset_sequence': None
                        })
                    # SVD
                    svd = None
                    debug = device.find('debug')
                    if debug is not None:
                        svd = debug.attrib.get('svd')
                    # from_pack
                    from_pack = {
                        'vendor': vendor,
                        'pack': pack,
                        'version': version,
                        'url': url
                    }
                    parse_data[dname] = {
                        'name': dname,
                        'memories': memories,
                        'algorithms': algorithms,
                        'processors': processors,
                        'from_pack': from_pack,
                        'vendor': vendor_id,
                        'family': family_name,
                        'sub_family': subfamily_name,
                        'svd': svd
                    }
        return parse_data
