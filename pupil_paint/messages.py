from dataclasses import dataclass


@dataclass
class ClientStatusMsg:
    host: str
    status: str

@dataclass
class GazePointMsg:
    host: str
    x: float
    y: float

@dataclass
class QuitMsg:
    pass

@dataclass
class DebugMsg:
    text: str
