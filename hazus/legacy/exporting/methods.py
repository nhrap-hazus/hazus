from .Setup_Connection import setup
from importlib import import_module
import os
from ...common import Logger

def initLogger(output_directory, study_region):
    path = output_directory + '/' + study_region
    if not os.path.exists(path):
        os.mkdir(path)
    logger = Logger()
    logger.create(path)
    return logger

def createExportObj():
    """Creates a dictionary to be used in the hazus.legacy.export method and hazus.legacy.Exporting class

    Returns:
        exportObj: dict -- opt fields are boolean and decide options for exports. The rest of the fields are strings.
    """
    exportObj = {
        'opt_csv': 1,
        'opt_shp': 1,
        'opt_report': 1,
        'opt_json': 1,
        'study_region': '',
        'title': '',
        'meta': '',
        'output_directory': ''
    }
    return exportObj

def export(exportObj):
    """ Exports data from Hazus legacy. Can export CSVs, Shapefiles, PDF Reports, and Json |
    Use hazus.legacy.createExportObj() to create a base object for keyword arguments |
    
    Keyword arguments:
        exportObj: dictionary -- {
            opt_csv: boolean -- export CSVs,
            opt_shp: boolean -- export Shapefile(s),
            opt_report: boolean -- export report,
            opt_json: boolean -- export Json,
            study_region: str -- name of the Hazus study region (HPR name),
            ?title: str -- title on the report,
            ?meta: str -- sub-title on the report (ex: Shakemap v5),
            output_directory: str -- directory location for the outputs
        }
    """

    logger = initLogger(exportObj['output_directory'], exportObj['study_region'])
    logger.log('Establishing connection to SQL Server')
    comp_name, cnxn, date, modules = setup(exportObj)
    logger.log('Connection established and modules identified')
    exportObj.update({'created': date})
    logger.log('Importing result module')
    result_module = import_module('.'+modules['result_module'], package='hazus.legacy.exporting.results')
    logger.log('Result module imported')
    logger.log('Fetching data from SQL Server')
    hazus_results_dict, subcounty_results, county_results, damaged_essential_facilities = result_module.read_sql(comp_name, cnxn, exportObj)
    logger.log('SQL quiries returned and data parsed')
    if exportObj['opt_csv']:
        logger.log('Exporting CSVs')
        result_module.to_csv(hazus_results_dict, subcounty_results, county_results, damaged_essential_facilities, exportObj)
        logger.log('CSVs saved')
    if exportObj['opt_shp']:
        logger.log('Exporting Shapefile(s)')
        gdf = result_module.to_shp(exportObj, hazus_results_dict, subcounty_results)
        logger.log('Shapefile(s) saved')
    if exportObj['opt_report']:
        try:
            len(gdf)
        except:
            logger.log('Creating gdf for report')
            gdf = result_module.to_shp(exportObj, hazus_results_dict, subcounty_results)
            logger.log('Gdf created')
        logger.log('Importing report module')
        report_module = import_module('.'+modules['report_module'], package='hazus.legacy.exporting.reports')
        logger.log('Report module imported')
        logger.log('Creating and exporting report')
        report_module.generate_report(gdf, hazus_results_dict, subcounty_results, county_results, exportObj)
        logger.destroy()

