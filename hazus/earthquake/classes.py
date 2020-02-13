from ..common.classes import Base
from .modules import AEBM
from .modules import DirectSocialLosses
from .modules import EssentialFacilities
from .modules import GeneralBuildings
from .modules import IndirectEconomicLoss
from .modules import InducedPhysicalDamage
from .modules import MilitaryInstallation
from .modules import TransportationSystems
from .modules import UserDefinedStructures
from .modules import UtilitySystems


class Earthquake(Base):
    """Intialize an earthquake module instance.
     
    Keyword arguments:
    """
    def __init__(self):
        super().__init__()

        self.analysis = Analysis()

class Analysis():
    def __init__(self):
        self.AEBM = AEBM()
        self.directSocialLosses = DirectSocialLosses()
        self.essentialFacilities = EssentialFacilities()
        self.generalBuildings = GeneralBuildings()
        self.indirectEconomicLoss = IndirectEconomicLoss()
        self.inducedPhysicalDamage = InducedPhysicalDamage()
        self.militaryInstallation = MilitaryInstallation()
        self.transportationSystems = TransportationSystems()
        self.userDefinedStructures = UserDefinedStructures()
        self.utilitySystems = UtilitySystems()
