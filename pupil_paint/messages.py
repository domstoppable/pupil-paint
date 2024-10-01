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

@dataclass
class SwatchesMsg:
    colors: list

@dataclass
class DrawMsg:
    host: str
    color: tuple
    enabled: bool

@dataclass
class CalculateScoreMsg:
    pass

@dataclass
class UpdatedScoresMsg:
    scores: dict
