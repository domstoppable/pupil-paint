from dataclasses import dataclass


@dataclass
class ClientIdentifyMsg:
    host: str

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
