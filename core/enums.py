"""
Exchange and Segment Enums matching Phoenix Core definitions.
"""

from enum import IntEnum


class Exchange(IntEnum):
    NONE = 0
    NSE = 1
    BSE = 2
    MCX = 3
    END = 4


class Segment(IntEnum):
    NONE = 0
    CM = 1
    FO = 2
    CD = 3
    CO = 4
    SLB = 5
    END = 6
