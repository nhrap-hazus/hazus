from ..common.classes import Base
from .modules import GeneralBuildingStock
from .modules import UserDefinedFacilities

class Tsunami(Base):
    """
    Intialize a tsunami module instance
     
    Keyword arguments: \n

    """
    def __init__(self):
        super().__init__()

        self.analysis = Analysis()

class Analysis():
    def __init__(self):
        self.generalBuildingStock = GeneralBuildingStock()
        self.userDefinedFacilities = UserDefinedFacilities()