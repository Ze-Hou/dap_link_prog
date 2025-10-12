import sys
import os


class RunEnv:
    @staticmethod
    def parse_path(relative_path):
        abs_path = os.path.abspath(relative_path)
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                abs_path = os.path.join(meipass, relative_path)
        return abs_path.replace("\\", "/")
