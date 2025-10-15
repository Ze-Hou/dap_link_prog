import sys
import os

class RunEnv:
    @staticmethod
    def parse_path(relative_path) -> str:
        return os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), relative_path)).replace("\\", "/")
