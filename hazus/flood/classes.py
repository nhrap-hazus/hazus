from ..common.classes import Base
from .modules import Agriculture
from .modules import DirectSocialLosses
from .modules import EssentialFacilities
from .modules import GeneralBuildingStock
from .modules import IndirectEconomicLoss
from .modules import TransportationSystems
from .modules import UserDefinedStructures
from .modules import UtilitySystems
from .modules import Vehicles
from .modules import WhatIf

class Flood(Base):
    """
    Intialize a flood module instance
     
    Keyword arguments: \n

    """
    def __init__(self):
        super().__init__()

        self.analysis = Analysis()

class Analysis():
    def __init__(self):
        
        self.agriculture = Agriculture()
        self.directSocialLosses = DirectSocialLosses()
        self.essentialFacilities = EssentialFacilities()
        self.generalBuildingStock = GeneralBuildingStock()
        self.indirectEconomicLoss = IndirectEconomicLoss()
        self.transportationSystems = TransportationSystems()
        self.userDefinedStructures = UserDefinedStructures()
        self.utilitySystems = UtilitySystems()
        self.vehicles = Vehicles()
        self.whatIf = WhatIf()