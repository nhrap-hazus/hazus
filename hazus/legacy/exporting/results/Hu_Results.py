import pandas as pd
import pyodbc as py
import shapely
from shapely.wkt import loads
import geopandas as gpd
import numpy as np
from time import time
import sys
import json

# df = damaged_facilities_shp.copy()
# col = 'Kitchen'

def read_sql(comp_name, cnxn, inputs):
    # removes all infinite and nulls values
    def setValuesValid(df):
        if type(df) == pd.DataFrame:
            cols = df.columns
            for col in cols:
                try:
                    dtypes = df[col].apply(type).unique()
                    if (col != 'geometry') & (str not in dtypes):
                        # sets null values to 0
                        df[col][df[col].isnull()] = 0
                        if (np.bool in dtypes) or (np.bool_ in dtypes):
                            df[col] = df[col].astype(int)
                        # ensure values are finite
                        df.replace([np.inf, -np.inf], 0)
                except:
                    print('ERR ------- ' + col)
        return df

    #Select results from SQL Server Hazus study region database
    sql_econ_loss = """SELECT TRACT as Tract, SUM(CASE WHEN GenBldgOrGenOcc 
        IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND') THEN TotLoss ELSE 0 END) AS EconLoss
        FROM %s.dbo.[huSummaryLoss] GROUP BY [huSummaryLoss].TRACT""" %inputs['study_region']

    sql_county_fips = """SELECT Tract, {s}.dbo.hzCounty.CountyFips, {s}.dbo.hzCounty.CountyName,
        {s}.dbo.hzCounty.State FROM {s}.dbo.[hzTract] FULL JOIN {s}.dbo.hzCounty ON {s}.dbo.hzTract.CountyFips
        = {s}.dbo.hzCounty.CountyFips""".format(s=inputs['study_region'])
    
    sql_demographics = """SELECT Tract, Population, Households FROM
        %s.dbo.[hzDemographicsT]""" %inputs['study_region']

    sql_impact = """SELECT {s}.dbo.[huDebrisResultsT].Tract,SUM(ISNULL(BRICKANDWOOD, 0))
        AS DebrisBW, SUM(ISNULL(CONCRETEANDSTEEL, 0)) AS DebrisCS, SUM(ISNULL(Tree, 0)) AS DebrisTree, 
        (SUM(ISNULL(Tree, 0))*TreeCollectionFactor) AS ElgDebTree, SUM(ISNULL(DISPLACEDHOUSEHOLDS, 0)) AS DisplHouse, 
        SUM(ISNULL(SHORTTERMSHELTERNEEDS, 0)) AS Shelter FROM {s}.dbo.[huShelterResultsT] 
        LEFT JOIN {s}.dbo.[huDebrisResultsT] ON {s}.dbo.[huShelterResultsT].Tract = 
        {s}.dbo.[huDebrisResultsT].TRACT LEFT JOIN {s}.dbo.[huTreeParameters] ON 
        {s}.dbo.[huShelterResultsT].TRACT = {s}.dbo.[huTreeParameters].Tract
        GROUP BY {s}.dbo.[huDebrisResultsT].Tract, {s}.dbo.[huTreeParameters].TreeCollectionFactor""" .format(s=inputs['study_region'])

    sql_building_damage = """SELECT TRACT as Tract, 
        SUM(CASE WHEN GenBldgOrGenOcc IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND') THEN NonDamage ELSE 0 END)
        AS NoDamage, SUM(CASE WHEN GenBldgOrGenOcc IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND') THEN MinDamage ELSE 0 END)
        AS Affected, SUM(CASE WHEN GenBldgOrGenOcc IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND') THEN ModDamage ELSE 0 END)
        AS Minor, SUM(CASE WHEN GenBldgOrGenOcc IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND') THEN SevDamage ELSE 0 END)
        AS Major, SUM(CASE WHEN GenBldgOrGenOcc IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND') THEN ComDamage ELSE 0 END)
        AS Destroyed, SUM(CASE WHEN GenBldgOrGenOcc = 'RES' THEN NonDamage ELSE 0 END)
        AS RESNoDam, SUM(CASE WHEN GenBldgOrGenOcc = 'RES' THEN MinDamage ELSE 0 END)
        AS RESAffect, SUM(CASE WHEN GenBldgOrGenOcc = 'RES' THEN ModDamage ELSE 0 END)
        AS RESMinor, SUM(CASE WHEN GenBldgOrGenOcc = 'RES' THEN SevDamage ELSE 0 END)
        AS RESMajor, SUM(CASE WHEN GenBldgOrGenOcc = 'RES' THEN ComDamage ELSE 0 END)
        AS RESDestr FROM %s.dbo.[huSummaryDamage] GROUP BY Tract""" %inputs['study_region']

    sql_building_damage_occup = """SELECT GenBldgOrGenOcc AS Occupancy,
        SUM(ISNULL(NonDamage, 0)) As NoDamage, SUM(ISNULL(MinDamage, 0)) AS Affected,
        SUM(ISNULL(ModDamage, 0)) AS Minor, SUM(ISNULL(SevDamage, 0)) AS Major,
        SUM(ISNULL(ComDamage, 0)) AS Destroyed FROM %s.dbo.[huSummaryDamage]
        WHERE GenBldgOrGenOcc IN('COM', 'AGR', 'GOV', 'EDU', 'REL','RES', 'IND')
        GROUP BY GenBldgOrGenOcc""" %inputs['study_region']

    # sql_building_damage_occup = """SELECT Occupancy, SUM(Total) AS Total, SUM(At_Least_Minor) AS Affected,
    # SUM(MINOR) as Minor, SUM(At_Least_Severe) as MajorAndDestroyed
    # from %s.[dbo].[huOccResultsT] group by Occupancy order by Occupancy""" %inputs['study_region']

    sql_building_damage_bldg_type = """SELECT GenBldgOrGenOcc AS Occupancy,
        SUM(ISNULL(NonDamage, 0)) As NoDamage, SUM(ISNULL(MinDamage, 0)) AS Affected,
        SUM(ISNULL(ModDamage, 0)) AS Minor, SUM(ISNULL(SevDamage, 0)) AS Major,
        SUM(ISNULL(ComDamage, 0)) AS Destroyed FROM %s.dbo.[huSummaryDamage]
        WHERE GenBldgOrGenOcc IN('CONCRETE', 'MASONRY', 'STEEL', 'WOOD', 'MH')
        GROUP BY GenBldgOrGenOcc""" %inputs['study_region']

    sql_spatial = """SELECT Tract, Shape.STAsText() AS Shape
        FROM %s.dbo.[hzTract]""" %inputs['study_region']

    sql_scenario = """SELECT CurrentScenario, ScenarioType
        FROM {s}.[dbo].[huTemplateScenario]""".format(s=inputs['study_region'])

    #Group tables and queries into iterable
    hazus_results = {'econ_loss': sql_econ_loss , 'county_fips': sql_county_fips,
                    'demographics': sql_demographics, 'impact': sql_impact,
                    'building_damage': sql_building_damage,
                    'building_damage_occup': sql_building_damage_occup,
                    'building_damage_bldg_type': sql_building_damage_bldg_type,
                    'tract_spatial': sql_spatial,
                    'scenario': sql_scenario}

    #Read result tables from SQL Server into dataframes with Census ID as index
    try:
        hazus_results_dict = {table: pd.read_sql(query, cnxn) for table, query
        in hazus_results.items()}
        for name, dataframe in hazus_results_dict.iteritems():
            if (name != 'building_damage_occup') and (name != 'building_damage_bldg_type'):
                try:
                    dataframe.set_index('Tract', append=False, inplace=True)
                except:
                    pass
    except:
        hazus_results_dict = {table: pd.read_sql(query, cnxn) for table, query
        in hazus_results.items()}
        for name, dataframe in hazus_results_dict.items():
            if (name != 'building_damage_occup') and (name != 'building_damage_bldg_type'):
                try:
                    dataframe.set_index('Tract', append=False, inplace=True)
                except:
                    pass
                
    # Convert units to real $$ bills y'all
    hazus_results_dict['econ_loss'] = hazus_results_dict['econ_loss'] * 1000
    # Convert units to tons
    debris_cols = ['DebrisBW', 'DebrisCS']
    for debris_col in debris_cols:
        hazus_results_dict['impact'][debris_col] = hazus_results_dict['impact'][debris_col] * 1000

    # strip leading and trailing spaces on occupancy type
    hazus_results_dict['building_damage_occup']['Occupancy'] = hazus_results_dict['building_damage_occup']['Occupancy'].apply(lambda x: x.strip())

    def prepDamagedEssentialFacilities(damaged_facilities):
        replacements = {
            'MINOR': 'Affected',
            'MODERATE': 'Minor',
            'SEVERE': 'Major',
            'COMPLETE': 'Destroyed'
        }
        for replace in replacements.items():
            damaged_facilities.columns = [x.replace(replace[0], replace[1]) if x == replace[0] else x for x in damaged_facilities.columns]
        damaged_facilities['MajorAndDestroyed'] = damaged_facilities['Major'] + damaged_facilities['Destroyed']
        return damaged_facilities
    
    def prepBuildingDamageOccup(building_damage_occup):
        # TODO call out single family & mobile home (RES1 & RES2)
        hrd_bdo = building_damage_occup
        # hrd_bdo = hazus_results_dict['building_damage_occup']
        # summarize building damage by occupancy type
        oc_dict = {
            'COM': 'Commercial',
            'IND': 'Industry',
            'AGR': 'Agriculture',
            'EDU': 'Education',
            'REL': 'Religious',
            'GOV': 'Government',
            'RES': 'Residential'
        }
        occupancy_categories = ['COM', 'IND', 'AGR', 'EDU', 'REL', 'GOV', 'RES']
        # occup_df = hrd_bdo[(hrd_bdo.Occupancy == 'RES1') | (hrd_bdo.Occupancy == 'RES2')].sum().to_frame().T
        # occup_df['Occupancy'] = 'Single Family\n & Mobile Home'
        occup_df = pd.DataFrame()
        for cat in occupancy_categories:
            df = hrd_bdo[hrd_bdo.Occupancy.str.contains(cat)].sum().to_frame().T
            df['Occupancy'] = oc_dict[cat]
            occup_df = occup_df.append(df)
        
        # map fields to hues
        occup_df['Affected'] = occup_df['Affected']
        occup_df['Minor'] = occup_df['Minor']
        occup_df['MajorAndDestroyed'] = occup_df['Major'] + occup_df['Destroyed']
        return occup_df

    def prepBarPlot(df, summarize_field):
        summarized = df.groupby(summarize_field).sum()
        summarized['MajorAndDestroyed'] = summarized['Major'] + summarized['Destroyed']
        summarized = summarized.reset_index()
        hues = ['Affected', 'Minor', 'MajorAndDestroyed']
        new_df = pd.DataFrame()
        for hue in hues:
            hue_df = summarized[[summarize_field, hue]]
            hue_df.columns = ['Type', 'Total']
            if hue == 'MajorAndDestroyed':
                hue_df['Status'] = 'Major & Destroyed'
            else:
                hue_df['Status'] = hue
            new_df = new_df.append(hue_df)
        new_df['Total'] = (new_df['Total'] + 0.5).apply(int)
        return new_df

    # new_occup_df = pd.DataFrame()
    # hues = ['Affected', 'Minor', 'MajorAndDestroyed']
    # for hue in hues:
    #     hue_df = occup_df[['Occupancy', hue]]
    #     hue_df.columns = ['Occupancy', 'Total']
    #     if hue == 'MajorAndDestroyed':
    #         hue_df['Status'] = 'Major & Destroyed'
    #     else:
    #         hue_df['Status'] = hue
    #     new_occup_df = new_occup_df.append(hue_df)
    # new_occup_df['Total'] = new_occup_df['Total'].astype(int)

    # # add new occupancy by building type dataframe to results
    # hazus_results_dict.update({'building_damage_occup_df': new_occup_df})

    # Pull windspeeds
    database_study_region = hazus_results_dict['scenario']['CurrentScenario'][0]
    database_scenario_type = hazus_results_dict['scenario']['ScenarioType'][0]
    if database_scenario_type == 'Deterministic':
        query = """SELECT Tract, PEAKGUST
        FROM [syHazus].[dbo].[huDetermWindSpeedResults]
        WHERE huScenarioName = '""" + database_study_region + "'"
        windspeeds = pd.read_sql(query, cnxn)
        if len(windspeeds) == 0:
            query = """SELECT Tract, PEAKGUST
            FROM %s.[dbo].[hv_huDeterminsticWindSpeedResults]
            WHERE huScenarioName = '""" % inputs['study_region'] + database_study_region + "'" 
            windspeeds = pd.read_sql(query, cnxn)
    elif database_scenario_type == 'Historic':
        query = """SELECT Tract, PEAKGUST
        FROM [syHazus].[dbo].[huDetermWindSpeedResults]
        WHERE huScenarioName = '""" + database_study_region + "'"
        windspeeds = pd.read_sql(query, cnxn)
        if len(windspeeds) == 0:
            query = """SELECT Tract, PEAKGUST
            FROM %s.[dbo].[hv_huHistoricWindSpeedT]
            WHERE huScenarioName = '""" % inputs['study_region'] + database_study_region + "'"
    elif database_scenario_type == 'Probabilistic':
        query = """SELECT Tract , f1000yr as PEAKGUST
            FROM %s.[dbo].[huHazardMapWindSpeed]""" %inputs['study_region']
        windspeeds = pd.read_sql(query, cnxn)
    else:
        print('Unable to select windspeeds from SQL')
    windspeeds = windspeeds.set_index('Tract')

    # TODO remove SQL query and join for NaN damage columns in subcounty    
    #Join and group results dataframes into subcounty and county dataframes
    subcounty_results = hazus_results_dict['county_fips'].join([hazus_results_dict['econ_loss'],
    hazus_results_dict['demographics'], hazus_results_dict['impact'],
    hazus_results_dict['building_damage'], windspeeds])

    try:
        subcounty_results = subcounty_results.drop(['TRACT_x', 'TRACT_y'], axis=1)
    except:
        pass
    subcounty_results = subcounty_results[pd.notna(subcounty_results['EconLoss'])]
    county_results = subcounty_results.groupby(subcounty_results['CountyFips']).agg({
        'EconLoss': 'sum',
        'Population': 'sum',
        'Households': 'sum',
        'DebrisBW': 'sum',
        'DebrisCS': 'sum',
        'DebrisTree': 'sum',
        'ElgDebTree': 'sum',
        'DisplHouse': 'sum',
        'Shelter': 'sum',
        'NoDamage': 'sum',
        'Affected': 'sum',
        'Minor': 'sum',
        'Major': 'sum',
        'Destroyed': 'sum',
        'RESNoDam': 'sum',
        'RESAffect': 'sum',
        'RESMinor': 'sum',
        'RESMajor': 'sum',
        'RESDestr': 'sum',
        'CountyFips': 'first',
        'CountyName': 'first',
        'State': 'first'
    })
    
    #Summarize and export damaged essential facilities
    essential_facilities = ['CareFlty', 'EmergencyCtr', 'FireStation',
                            'PoliceStation', 'School']

    damaged_facilities = pd.DataFrame()
    damaged_facilities_shp = pd.DataFrame()
    
    for i in essential_facilities:
        print(i)
    #    name = hazard[0:2].lower() + 'Results' + i
        name = 'hu' + 'Results' + i
        if i == 'EmergencyCtr':
            # name = hazard[0:2].lower() + 'Results' + 'EmergCtr'
            name = 'hu' + 'Results' + 'EmergCtr'
        query = """SELECT * FROM %s.dbo.""" %inputs['study_region'] + name + """ WHERE MINOR > 0"""
        df = pd.read_sql(query, cnxn)
        ids = [id for id in df.columns if 'Id' in id]
        df = df.set_index(ids[0])
        df['Fac_Type'] = str(i)
        damaged_facilities = damaged_facilities.append(df)
        #Only export records from spatial table that correspond to records with economic loss in damage table
        if len(df.index) > 0:
            damage_ids = "', '".join(list(df.index))
            spatial = 'hz' + i
            columns_query = """SELECT COLUMN_NAME FROM """ + inputs['study_region'] + """.information_schema.columns
            WHERE TABLE_NAME = '""" + spatial + """' AND columns.COLUMN_NAME NOT IN('Shape')"""
            columns_df = pd.read_sql(columns_query, cnxn)
            columns = ",".join(list(columns_df.COLUMN_NAME))
            spatial_query = """SELECT """ + columns + """, Shape.STAsText() AS Shape FROM %s.dbo.""" %inputs['study_region'] + spatial + """ WHERE """ + ids[0] + """ in ('""" + damage_ids + """')"""
            spatial_df = pd.read_sql(spatial_query, cnxn)
            ids = [id for id in spatial_df.columns if 'Id' in id]
            spatial_df = spatial_df.set_index(ids[0])
            results_df = spatial_df.join(df, on = ids[0], how = 'inner')
            #remove boolean data so gpd can parse to file
            # results_df = setValuesValid(results_df)
            # results_df.replace(True, 1, inplace=True)
            # results_df.replace(False, 0, inplace=True)
            # for result in results_df.columns:
            #     typeof = type(results_df[result].iloc[0])
            #     if (typeof == np.bool_) | (typeof == np.bool):
            #         results_df[result] = results_df[result].astype(int)
            #         results_df[result] = np.where(np.isnan(results_df[result]), 0, 1)
            #append essential facility layer to dataframe to turn to shp
            damaged_facilities_shp = damaged_facilities_shp.append(results_df)
            #Count offline essential facilities by county and add to county_results
            results_df['CountyFips'] = results_df['Tract'].str[:5]
            count_df = results_df[results_df.LossOfUse>0].groupby('CountyFips').count()
            # TODO set to econloss
            # count_df[i] = count_df['EconLoss']
            count_df[i] = count_df['Name']
            # remove duplicate columns
            for col in count_df.columns:
                if col in list(county_results.columns):
                    count_df = count_df.drop(col, axis=1)
            county_results = county_results.join(count_df[i])

    # consolidates all data for validating values
    return_dict_update = {
        'subcounty_results': subcounty_results,
        'county_results': county_results,
        'damaged_facilities': damaged_facilities,
        'damaged_facilities_shp': damaged_facilities_shp
    }
    return_dict = hazus_results_dict.copy()
    return_dict.update(return_dict_update)
    # validate all values
    for k, v in return_dict.items():
        return_dict[k] = setValuesValid(v)

    if inputs['opt_shp']:
        try:
            damaged_facilities_shp['geometry'] = damaged_facilities_shp['Shape'].apply(loads)
            gdf = gpd.GeoDataFrame(damaged_facilities_shp, geometry = 'geometry')
            crs={'proj':'longlat', 'ellps':'WGS84', 'datum':'WGS84','no_defs':True}
            gdf.crs = crs
            geom_types = gdf['geometry'].apply(type).unique()
            if len(geom_types) > 1:
                for geom_type in geom_types:
                    gdf_new = gdf[gdf['geometry'].apply(type) == geom_type]
                    gdf_new.to_file(inputs['output_directory'] + '/' + inputs['study_region'] + '/damaged_facilities_' + str(geom_type).split('.')[2] + '.shp', driver='ESRI Shapefile')
            else:
                gdf.to_file(inputs['output_directory'] + '/' + inputs['study_region'] + '/damaged_facilities' + '.shp', driver='ESRI Shapefile')
        except:
            print('No damaged essential facility spatial data available')
    
    damaged_facilities.rename(columns={'MINOR': 'Affected',
                                                 'MODERATE': 'Minor',
                                                 'SEVERE': 'Major',
                                                 'COMPLETE': 'Destroyed'},
                                        inplace=True)
    
    damaged_facilities_shp.rename(columns={'MINOR': 'Affected',
                                                 'MODERATE': 'Minor',
                                                 'SEVERE': 'Major',
                                                 'COMPLETE': 'Destroyed'},
                                        inplace=True)
    
    _building_damage_occup = prepBuildingDamageOccup(hazus_results_dict['building_damage_occup'])
    _damaged_facilities = prepDamagedEssentialFacilities(damaged_facilities)
    _bdo_barPlotDf = prepBarPlot(_building_damage_occup, 'Occupancy')
    _def_barPlotDf = prepBarPlot(_damaged_facilities, 'Fac_Type')
    hazus_results_dict.update({'building_damage_occup_plot': _bdo_barPlotDf})
    hazus_results_dict.update({'damaged_facilities_plot': _def_barPlotDf})

    return hazus_results_dict, subcounty_results, county_results, damaged_facilities

#Export results dataframes to text files
def to_csv(hazus_results_dict, subcounty_results, county_results, damaged_facilities, inputs):
    tabular_df = {'building_damage_occup':
                    hazus_results_dict['building_damage_occup'],
                    'building_damage_bldg_type':
                    hazus_results_dict['building_damage_bldg_type'],
                    'tract_results': subcounty_results,
                    'county_results': county_results,
                    'damaged_facilities': damaged_facilities}
    json_output = {}
    for name, dataframe in tabular_df.items():
        if (not dataframe.empty) and (len(dataframe) > 0):
            path = inputs['output_directory'] + '\\' + inputs['study_region'] + '\\' + name + '.csv'
            if inputs['opt_csv']:
                dataframe.to_csv(path)
            if inputs['opt_json']:
                dataframe = dataframe.replace({pd.np.nan: 'null'})
                dictionary = dataframe.to_dict()
                json_output.update({name: dictionary})
    if inputs['opt_json']:
        with open(inputs['output_directory'] + '/' + inputs['study_region'] + '/' + inputs['study_region'] + '.json', 'w') as j:
            json.dump(json_output, j)

#Create shapefile of tract results table
def to_shp(inputs, hazus_results_dict, subcounty_results):
    if len(hazus_results_dict['econ_loss']) > 0:
        print('creating geodataframe')
        t0 = time()
        df = subcounty_results.join(hazus_results_dict['tract_spatial'])
        if not df.empty:
            df['geometry'] = df['Shape'].apply(loads)
            df = df.drop('Shape', axis=1)
            gdf = gpd.GeoDataFrame(df, geometry='geometry')
            # fixes topology
            gdf['geometry'] = gdf.buffer(0)
            crs={'proj':'longlat', 'ellps':'WGS84', 'datum':'WGS84','no_defs':True}
            gdf.crs = crs
            print(time() - t0)
            if inputs['opt_shp']:
                print('saving shapefile')
                t0 = time()
                gdf.to_file(inputs['output_directory'] + '/' + inputs['study_region'] + '/' + 'tract_results.shp', driver='ESRI Shapefile')
                print(time() - t0)
            return gdf
    else:
        sys.exit('No economic loss — unable to process study region')