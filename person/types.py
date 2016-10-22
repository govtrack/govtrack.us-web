from common import enum

class Gender(enum.Enum):
    male = enum.Item(1, 'Male', pronoun="he", pronoun_object="him", pronoun_posessive="his")
    female = enum.Item(2, 'Female', pronoun="she", pronoun_object="her", pronoun_posessive="her")


class RoleType(enum.Enum):
    senator = enum.Item(1, 'Senator', congress_chamber='Senate', congress_chamber_other="House", congress_chamber_long="Senate")
    representative = enum.Item(2, 'Representative', congress_chamber='House', congress_chamber_other="Senate", congress_chamber_long="House of Representatives")
    president = enum.Item(3, 'President')
    vicepresident = enum.Item(4, 'Vice President')


class SenatorClass(enum.Enum):
    class1 = enum.Item(1, 'Class 1')
    class2 = enum.Item(2, 'Class 2')
    class3 = enum.Item(3, 'Class 3')

class SenatorRank(enum.Enum):
    # the order is used by order_by on the district maps page
    senior = enum.Item(1, 'Senior')
    junior = enum.Item(2, 'Junior')

