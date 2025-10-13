"""
nuitka --standalone --show-progress --remove-output --mingw64 --lto=no --assume-yes-for-downloads --output-dir=E:/Py_Prj/dap_link_prog/output --main=E:/Py_Prj/dap_link_prog/main.py
"""
import sys
import os
import shutil
import subprocess
from src.ui.show_info_page import ShowAboutInfoDialog

output_dir = "output"

nuitka_cmd = [
    "python", "-m", "nuitka",
    "--standalone",                     # 创建一个包含可执行文件的文件夹
    "--remove-output",                  # 在生成模块或exe文件后移除构建目录
    "--mingw64",                        # 在 Windows 上使用 MinGW 编译
    "--assume-yes-for-downloads",       # 允许Nuitka在必要时下载外部代码
    "--include-data-dir=Fonts=Fonts",
    "--include-data-dir=packs=packs",
    "--include-data-dir=src/ui/icons=src/ui/icons",
    "--include-data-files=src/ui/*.ui=src/ui/",
    "--include-data-files=libusb-1.0.29/MinGW64/dll/*.dll=libusb-1.0.29/MinGW64/dll/",
    "--enable-plugin=pyqt5",                # 启用 PyQt5 插件
    "--output-dir=" + output_dir,           # 输出目录
    "--output-folder-name=daplinkprog",     # 输出文件夹名称
    "--output-filename=daplinkprog",        # 输出可执行文件名称
    "--windows-console-mode=disable",       # force: 控制台模式 attach: 使用现有控制台进行输出 disable: 禁用控制台
    "--windows-icon-from-ico=Link.ico",     # 图标
    "--quiet",                              # 静默模式
    "--main=main.py",                       # 主脚本
    "--report=output/report.xml",
    "--show-progress",
    "--file-version=" + ShowAboutInfoDialog.VERSION,
    "--product-version=" + ShowAboutInfoDialog.VERSION,
]

def remove_readonly(func, path, excinfo):
    os.chmod(path, 0o666)
    func(path)

if __name__ == "__main__":
    print(sys.executable)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, onerror=remove_readonly)
    os.makedirs(output_dir, exist_ok=True)
    try:
        print("清理缓存...")
        subprocess.run(["python", "-m", "nuitka", "--clean-cache=all"], check=True)
        print("缓存清理完成！")
    except subprocess.CalledProcessError as e:
        print("清理缓存失败:", e)
        sys.exit(1)
    try:
        print("开始打包...")
        subprocess.run(nuitka_cmd, check=True)
        print("打包完成！")
    except subprocess.CalledProcessError as e:
        print("打包失败:", e)