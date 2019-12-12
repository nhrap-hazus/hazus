import pandas as pd
import pyodbc as py
import os


def setup(inputs):
    """
    inputs dictionary
    """
    study_region = inputs['study_region']
    folder_path = inputs['output_directory']
    try:
        #Make a folder in folder_path for study_region
        if not os.path.exists(folder_path + '\\' + study_region):
            os.makedirs(folder_path + '\\' + study_region)
        #Connect to Hazus SQL Server database where scenario results are stored
        comp_name = os.environ['COMPUTERNAME']
        cnxn = py.connect('Driver=ODBC Driver 11 for SQL Server;SERVER=' +
        comp_name + '\HAZUSPLUSSRVR;DATABASE=' +
        study_region + ';UID=hazuspuser;PWD=Gohazusplus_02;MARS_Connection=Yes')
        #Get scenario hazard and date created from syHazus table
        study_regions_cnxn = py.connect('Driver=ODBC Driver 11 for SQL Server;SERVER=' +
        comp_name + '\HAZUSPLUSSRVR;DATABASE=syHazus;UID=hazuspuser;PWD=Gohazusplus_02')
        study_regions_query = """SELECT RegionName, HasEqHazard, HasFlHazard, HasHuHazard,
        HasTsHazard, Created FROM [syHazus].[dbo].[syStudyRegion]"""
        study_regions_table = pd.read_sql(study_regions_query, study_regions_cnxn)
        study_regions_table = study_regions_table.set_index('RegionName')
        # converts combine Hu & Fl to just Hu
        study_regions_table['HasFlHazard'][(study_regions_table['HasFlHazard'] == True) & (study_regions_table['HasHuHazard'] == True)] = False
        Hazards = ['Eq', 'Hu', 'Ts', 'Fl']
        modules = {}
        for hazard in Hazards:
            if study_regions_table.loc[study_region, ('Has' + hazard + 'Hazard')]:
                modules.update({'hazard': hazard})
                # modules.update({'result_module': 'results.' + hazard + '_Results'})
                modules.update({'result_module': hazard + '_Results'})
                # modules.update({'shape_module': 'shapes.' + hazard + '_Shapes'})
                modules.update({'report_module': hazard + '_Report_Generator'})

        date = study_regions_table.loc[study_region, 'Created']
        return comp_name, cnxn, date, modules
    except:
        #Make a folder in folder_path for study_region
        if not os.path.exists(folder_path + '\\' + study_region):
            os.makedirs(folder_path + '\\' + study_region)
        #Connect to Hazus SQL Server database where scenario results are stored
        comp_name = os.environ['COMPUTERNAME']
        cnxn = py.connect('Driver=ODBC Driver 11 for SQL Server;SERVER=' +
        comp_name + '\HAZUSPLUSSRVR;DATABASE=' +
        study_region + ';UID=SA;PWD=Gohazusplus_02;MARS_Connection=Yes')
        #Get scenario hazard and date created from syHazus table
        study_regions_cnxn = py.connect('Driver=ODBC Driver 11 for SQL Server;SERVER=' +
        comp_name + '\HAZUSPLUSSRVR;DATABASE=syHazus;UID=SA;PWD=Gohazusplus_02')
        study_regions_query = """SELECT RegionName, HasEqHazard, HasFlHazard, HasHuHazard,
        HasTsHazard, Created FROM [syHazus].[dbo].[syStudyRegion]"""
        study_regions_table = pd.read_sql(study_regions_query, study_regions_cnxn)
        study_regions_table = study_regions_table.set_index('RegionName')
        Hazards = ['Eq', 'Hu', 'Ts', 'Fl']
        modules = {}
        for hazard in Hazards:
            if study_regions_table.loc[study_region, ('Has' + hazard + 'Hazard')]:
                modules.update({'hazard': hazard})
                modules.update({'result_module': 'results.' + hazard + '_Results'})
                # modules.update({'shape_module': 'shapes.' + hazard + '_Shapes'})
                modules.update({'report_module': 'reports.' + hazard + '_Report_Generator'})
        date = study_regions_table.loc[study_region, 'Created']
        return comp_name, cnxn, date, modules
