from enum import IntFlag


class Status(IntFlag):
    StandingBy = 0b0000
    OBSReady = 0b0001
    OBSNotReady = 0b1110
    TeamSpeakReady = 0b0010
    TeamSpeakNotReady = 0b1101
