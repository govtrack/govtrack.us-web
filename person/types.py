from common import enum

class Gender(enum.Enum):
    male = enum.Item(1, 'Male', pronoun="he", pronoun_posessive="his")
    female = enum.Item(2, 'Female', pronoun="she", pronoun_posessive="her")


class RoleType(enum.Enum):
    senator = enum.Item(1, 'Senator', congress_chamber='Senate')
    representative = enum.Item(2, 'Representative', congress_chamber='House')
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


class State(enum.Enum):
    """
    For senators and representatives, the state attribute gives the USPS state abbreviation of the state or territory they represent. Besides the 50 states, this includes delegates from American Samoa (AS), District of Columbia (DC), Guam (GU), Northern Mariana Islands (MP), Puerto Rico (PR), Virgin Islands (VI), and the former (for historical data) Dakota Territory (DK), Philippines Territory/Commonwealth (PI), and Territory of Orleans (OL).
    """

    # U.S. States
    AL = enum.Item('AL', 'Alabama')
    AK = enum.Item('AK', 'Alaska')
    AZ = enum.Item('AZ', 'Arizona')
    AR = enum.Item('AR', 'Arkansas')
    CA = enum.Item('CA', 'California')
    CO = enum.Item('CO', 'Colorado')
    CT = enum.Item('CT', 'Connecticut')
    DE = enum.Item('DE', 'Delaware')
    DC = enum.Item('DC', 'District of Columbia')
    FL = enum.Item('FL', 'Florida')
    GA = enum.Item('GA', 'Georgia')
    HI = enum.Item('HI', 'Hawaii')
    ID = enum.Item('ID', 'Idaho')
    IL = enum.Item('IL', 'Illinois')
    IN = enum.Item('IN', 'Indiana')
    IA = enum.Item('IA', 'Iowa')
    KS = enum.Item('KS', 'Kansas')
    KY = enum.Item('KY', 'Kentucky')
    LA = enum.Item('LA', 'Louisiana')
    ME = enum.Item('ME', 'Maine')
    MT = enum.Item('MT', 'Montana')
    NE = enum.Item('NE', 'Nebraska')
    NV = enum.Item('NV', 'Nevada')
    NH = enum.Item('NH', 'New Hampshire')
    NJ = enum.Item('NJ', 'New Jersey')
    NM = enum.Item('NM', 'New Mexico')
    NY = enum.Item('NY', 'New York')
    NC = enum.Item('NC', 'North Carolina')
    ND = enum.Item('ND', 'North Dakota')
    OH = enum.Item('OH', 'Ohio')
    OK = enum.Item('OK', 'Oklahoma')
    OR = enum.Item('OR', 'Oregon')
    MD = enum.Item('MD', 'Maryland')
    MA = enum.Item('MA', 'Massachusetts')
    MI = enum.Item('MI', 'Michigan')
    MN = enum.Item('MN', 'Minnesota')
    MS = enum.Item('MS', 'Mississippi')
    MO = enum.Item('MO', 'Missouri')
    PA = enum.Item('PA', 'Pennsylvania')
    RI = enum.Item('RI', 'Rhode Island')
    SC = enum.Item('SC', 'South Carolina')
    SD = enum.Item('SD', 'South Dakota')
    TN = enum.Item('TN', 'Tennessee')
    TX = enum.Item('TX', 'Texas')
    UT = enum.Item('UT', 'Utah')
    VT = enum.Item('VT', 'Vermont')
    VA = enum.Item('VA', 'Virginia')
    WA = enum.Item('WA', 'Washington')
    WV = enum.Item('WV', 'West Virginia')
    WI = enum.Item('WI', 'Wisconsin')
    WY = enum.Item('WY', 'Wyoming')

    # Other
    AS = enum.Item('AS', 'American Samoa')
    GU = enum.Item('GU', 'Guam')
    MP = enum.Item('MP', 'Northern Mariana Islands')
    PR = enum.Item('PR', 'Puerto Rico')
    VI = enum.Item('VI', 'Virgin Islands')
    DK = enum.Item('DK', 'Dakota Territory')
    PI = enum.Item('PI', 'Philippines Territory/Commonwealth')
    OL = enum.Item('OL', 'Territory of Orleans')
