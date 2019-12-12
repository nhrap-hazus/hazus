
# main class
class DirectPhysicalDamage():
    def __init__(self):
        self.buildingsAndFacilities = BuildingsAndFacilities()

# helper classes
class BuildingsAndFacilities():
    def __init__(self):
        self.essentialFacilities = EssentialFacilities()

    def generalBuildings(self):
        pass

    def userDefinedBuildings(self):
        pass

class EssentialFacilities():
    def __init__(self):
        pass

    def medicalCare(self):
        pass

    def fireStations(self):
        pass

    def policeStations(self):
        pass

    def emergencyCenters(self):
        pass

    def schools(self):
        pass

