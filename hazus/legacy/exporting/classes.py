from .Setup_Connection import setup
from importlib import import_module
import os
from ...common import Logger

class Exporting():
    """ Export class for Hazus legacy. Can export CSVs, Shapefiles, PDF Reports, and Jsondatetime A combination of a date and a time. |
    Use hazus.legacy.createExportObj() to create a base object for keyword arguments |
    Exporting method logic follows: setup, getData, toCSV, toShapefile, toReport
    
    Keyword arguments:
        exportObj: dictionary -- {
            study_region: str -- name of the Hazus study region (HPR name) |
            output_directory: str -- directory location for the outputs
            ?title: str -- title on the report |
            ?meta: str -- sub-title on the report (ex: Shakemap v5) |
        }
    """
    def __init__(self, exportObj):
        self.exportObj = exportObj
        try: 
            exportObj['title']
        except:
            self.exportObj['title'] = self.exportObj['study_region']
        try: 
            exportObj['meta']
        except:
            self.exportObj['meta'] = ''
        self.logger = Logger()
    
    def setup(self):
        """Establishes the connection to SQL Server
        """
        self.comp_name, self.cnxn, self.date, self.modules = setup(self.exportObj)
        self.exportObj.update({'created': self.date})
        self.result_module = import_module('.'+self.modules['result_module'], package='hazus.legacy.exporting.results')

    def getData(self):
        """Queries and parses the data from SQL Server, preparing it for exporting
        """
        self.hazus_results_dict, self.subcounty_results, self.county_results, self.damaged_essential_facilities = self.result_module.read_sql(self.comp_name, self.cnxn, self.exportObj)
    
    def toCSV(self):
        """Exports the study region data to CSVs
        """
        self.result_module.to_csv(self.hazus_results_dict, self.subcounty_results, self.county_results, self.damaged_essential_facilities, self.exportObj)

    def toShapefile(self):
        """Exports the study region data to Shapefile(s)
        """
        self.gdf = self.result_module.to_shp(self.exportObj, self.hazus_results_dict, self.subcounty_results)
    
    def toReport(self):
        """Exports the study region data to a one-page PDF report
        """
        try:
            len(self.gdf)
        except:
            self.toShapefile()
        self.report_module = import_module('.'+self.modules['report_module'], package='hazus.legacy.exporting.reports')
        self.report_module.generate_report(self.gdf, self.hazus_results_dict, self.subcounty_results, self.county_results, self.exportObj)
