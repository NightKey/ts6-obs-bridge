from enum import Enum


class UserStatus(Enum):
    Quiet = "quiet"
    Speaking = "speaking"
    Muted = "muted"
    Left = "left"

    def __eq__(self, other):
        if not isinstance(other, UserStatus): return False
        return self.name == other.name

    def __ne__(self, other):
        return not self == other

    @staticmethod
    def from_string(string: str) -> 'UserStatus':
        if string  ==  "quiet": return UserStatus.Quiet
        if string  ==  "speaking": return UserStatus.Speaking
        if string  ==  "muted": return UserStatus.Muted
        if string  ==  "left": return UserStatus.Left
        raise NotImplemented
