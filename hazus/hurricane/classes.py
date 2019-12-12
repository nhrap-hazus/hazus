from ..common.classes import Base
from .modules import DirectEconomicLoss
from .modules import DirectPhysicalDamage
from .modules import DirectSocialLoss
from .modules import InducedPhysicalDamage


class Hurricane(Base):
    """
    Intialize a hurricane module instance
     
    Keyword arguments: \n
    
    """
    def __init__(self):
        super().__init__()

        self.analysis = Analysis()

class Analysis():
    def __init__(self):
        self.directEconomicLoss = DirectEconomicLoss()
        self.directPhysicalDamage = DirectPhysicalDamage()
        self.directSocialLoss = DirectSocialLoss()
        self.inducedPhysicalDamage = InducedPhysicalDamage()