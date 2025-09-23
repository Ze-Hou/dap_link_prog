from enum import Enum

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
        return f"./src/ui/icons/{self.value}.svg"