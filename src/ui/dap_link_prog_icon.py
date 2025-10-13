from enum import Enum
from src.component.run_env import RunEnv


class DAPIcon(Enum):
    Download = "ArrowDownload"
    Upload = "ArrowUpload"
    Erase = "Eraser"
    FolderOpen = "FolderOpen"
    Link = "Link"
    LockClose = "LockClosed"
    LockOpen = "LockOpen"
    Pin = "Pin"
    PinOff = "PinOff"
    Settings = "Settings"
    CheckMark = "TextGrammarCheckmark"
    Sync = "ArrowSync"
    Id = "Id"
    Reset = "ArrowReset"
    ChevronDown = "ChevronDown"
    ChevronUp = "ChevronUp"

    def path(self) -> str:
        return RunEnv.parse_path(f"./src/ui/icons/{self.value}.svg")