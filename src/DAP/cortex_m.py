import copy
import ctypes


"""
调试寄存器定义
"""
class DEBUG_REG:
    # 调试停机控制及状态寄存器 (Debug Halting Control and Status Register)
    # 地址: 0xE000EDF0
    DHCSR = 0xE000EDF0
    """
    DHCSR寄存器位定义:
    位段    名称           类型  复位值  描述
    31:15   KEY           W     -       调试钥匙，必须在任何写操作中把该位段写入A05F，否则忽略写操作
    25      S_RESET_ST    R     -       内核已经或即将复位，读后清零
    24      S_RETIRE_ST   R     -       在上次读取以后指令已执行完成，读后清零
    19      S_LOCKUP      R     -       1=内核进入锁定状态
    18      S_SLEEP       R     -       1=内核睡眠中
    17      S_HALT        R     -       1=内核已停机
    16      S_REGRDY      R     -       1=寄存器的访问已经完成
    15:6    保留          -     -       保留位
    5       C_SNAPSTALL   RW    0*      打断一个stalled存储器访问
    4       保留          -     -       保留位
    3       C_MASKINTS    RW    0*      调试期间关中断，只有在停机后方可设置
    2       C_STEP        RW    0*      让处理器单步执行，在C_DEBUGEN=1时有效
    1       C_HALT        RW    0*      暂停处理器，在C_DEBUGEN=1时有效
    0       C_DEBUGEN     RW    0*      使能停机模式的调试
    """

    # 调试内核寄存器选择者寄存器 (Debug Core Register Selector Register)
    # 地址: 0xE000EDF4
    DCRSR = 0xE000EDF4
    """
    DCRSR寄存器位定义:
    位段    名称           类型  复位值  描述
    16      REGWnR        W     -       1=写寄存器, 0=读寄存器
    15:5    保留          -     -       保留位
    4:0     REGSEL        W     -       寄存器选择器:
                                        00000=R0, 00001=R1, ..., 01111=R15
                                        10000=xPSR, 10001=MSP, 10010=PSP
                                        10100=特殊功能寄存器组
                                        [31:24]: CONTROL
                                        [23:16]: FAULTMASK
                                        [15:8]:  BASEPRI
                                        [7:0]:   PRIMASK
    """

    # 调试内核寄存器数据寄存器 (Debug Core Register Data Register)
    # 地址: 0xE000EDF8
    DCRDR = 0xE000EDF8
    """
    DCRDR寄存器位定义:
    位段    名称           类型  复位值  描述
    31:0    DATA          R/W   -       读回来的寄存器的值，或欲写入寄存器的值，寄存器由DCRSR选择
    """

    # 调试异常及监视器控制寄存器 (Debug Exception and Monitor Control Register)
    # 地址: 0xE000EDFC
    DEMCR = 0xE000EDFC
    """
    DEMCR寄存器位定义:
    位段    名称           类型  复位值  描述
    24      TRCENA        RW    0*      跟踪系统使能位。在使用DWT,ETM,ITM和TPIU前，必须先设置此位
    23:20   保留          -     -       保留位
    19      MON_REQ       RW    0       1=调试监视器异常不是由硬件调试事件触发，而是由软件
    18      MON_STEP      RW    0       让处理器单步执行，在MON_EN=1时有效
    17      MON_PEND      RW    0       悬起监视器异常常请求。内核将在优先级允许时响应
    16      MON_EN        RW    0       使能调试监视器异常
    15:11   保留          -     -       保留位
    10      VC_HARDERR    RW    0*      发生硬fault时停机调试
    9       VC_INTERR     RW    0*      指令/异常服务错误时停机调试
    8       VC_BUSERR     RW    0*      发生总线fault时停机调试
    7       VC_STATERR    RW    0*      发生用法fault时停机调试
    6       VC_CHKERR     RW    0*      发生用法fault使能的检查错误时停机调试（如未对齐，除数为零）
    5       VC_NOCPERR    RW    0*      发生用法fault之无处理器错误时停机调试
    4       VC_MMERR      RW    0*      发生存储器管理fault时停机调试
    3:1     保留          -     -       保留位
    0       VC_CORERESET  RW    0*      发生内核复位时停机调试
    """

"""
ROM Table
"""
class ROM_TABLE:
    component = {
        'BASE_ADDR': 0xE00FF000,
        'SCS_BASE':  0x00000000,
        'DWT_BASE':  0x00000000,
        'FPB_BASE':  0x00000000,
        'ITM_BASE':  0x00000000,
        'TPIU_BASE': 0x00000000,
        'ETM_BASE':  0x00000000,
    }

    def get_component_table(self):
        return copy.deepcopy(self.component)


"""
系统控制块寄存器定义
"""
class SCB_REG:
    def __init__(self, scs_base=0xE000E000):
        # SCS基地址加上0x0D00偏移，确保4字节地址对齐
        self.base_address = (scs_base + 0x0D00) & 0xFFFFFFFC

    @property
    def CPUID(self):
        return self.base_address + 0x000  # CPUID基地址寄存器

    @property
    def ICSR(self):
        return self.base_address + 0x004  # 中断控制及状态寄存器

    @property
    def VTOR(self):
        return self.base_address + 0x008  # 向量表偏移寄存器

    @property
    def AIRCR(self):
        return self.base_address + 0x00C  # 应用中断及复位控制寄存器

    @property
    def SCR(self):
        return self.base_address + 0x010  # 系统控制寄存器

    @property
    def CCR(self):
        return self.base_address + 0x014  # 配置控制寄存器

    @property
    def SHPR1(self):
        return self.base_address + 0x018  # 系统处理器优先级寄存器1

    @property
    def SHPR2(self):
        return self.base_address + 0x01C  # 系统处理器优先级寄存器2

    @property
    def SHPR3(self):
        return self.base_address + 0x020  # 系统处理器优先级寄存器3

    @property
    def SHCSR(self):
        return self.base_address + 0x024  # 系统处理器控制及状态寄存器

    @property
    def CFSR(self):
        return self.base_address + 0x028  # 可配置故障状态寄存器

    @property
    def HFSR(self):
        return self.base_address + 0x02C  # 硬故障状态寄存器

    @property
    def DFSR(self):
        return self.base_address + 0x030  # 调试故障状态寄存器

    @property
    def MMFAR(self):
        return self.base_address + 0x034  # 存储器管理故障地址寄存器

    @property
    def BFAR(self):
        return self.base_address + 0x038  # 总线故障地址寄存器

    @property
    def AFSR(self):
        return self.base_address + 0x03C  # 辅助故障状态寄存器


class ExecuteOperation(ctypes.LittleEndianStructure):
    _fields_ = [
        ('r0',      ctypes.c_uint32),           # R0 argument 1
        ('r1',      ctypes.c_uint32),           # R1 argument 2
        ('r2',      ctypes.c_uint32),           # R2 argument 3
        ('r3',      ctypes.c_uint32),           # R3 argument 4
        ('r9',      ctypes.c_uint32),           # R9 static base pointer
        ('r13',     ctypes.c_uint32),           # R13 stack pointer
        ('r14',     ctypes.c_uint32),           # R14 link register
        ('r15',     ctypes.c_uint32),           # R15 program counter
        ('xpsr',    ctypes.c_uint32),           # Program status register
        ('timeout', ctypes.c_uint32),           # Timeout value in milliseconds
    ]
    def __init__(self):
        self.r0 = 0
        self.r1 = 0
        self.r2 = 0
        self.r3 = 0
        self.r9 = 0
        self.r13 = 0
        self.r14 = 0
        self.r15 = 0
        self.xpsr = 0x01000000      # 例如 Thumb 状态位
        self.timeout = 100          # 默认超时时间100ms