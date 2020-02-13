from ..common.classes import Base
from .modules import Agriculture
from .modules import DirectSocialLosses
from .modules import EssentialFacilities
from .modules import GeneralBuildingStock
from .modules import IndirectEconomicLoss
from .modules import TransportationSystems
from .modules import UDF
from .modules import UtilitySystems
from .modules import Vehicles
from .modules import WhatIf

class flood(Base):
    """
    Intialize a flood module instance
     
    Keyword arguments: \n

    """
    def __init__(self):
        super().__init__()

        self.analysis = analysis()

class analysis(): #like a second constructor for the flood class/inline class
    def __init__(self):
        
        self.agriculture = Agriculture()
        self.directSocialLosses = DirectSocialLosses()
        self.essentialFacilities = EssentialFacilities()
        self.generalBuildingStock = GeneralBuildingStock()
        self.indirectEconomicLoss = IndirectEconomicLoss()
        self.transportationSystems = TransportationSystems()
        self.UDF = UDF() #UKS - 1/14/2020 - RTC CR 34227
        self.utilitySystems = UtilitySystems()
        self.vehicles = Vehicles()
        self.whatIf = WhatIf()