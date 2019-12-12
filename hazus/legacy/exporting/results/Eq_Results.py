import pandas as pd
import pyodbc as py
import shapely
from shapely.wkt import loads
import geopandas as gpd
import numpy as np
from time import time
import sys
import json


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
    sql_econ_loss = """SELECT Tract, SUM(ISNULL(BldgLoss, 0) +
    ISNULL(ContentLoss, 0) + ISNULL(InvLoss, 0) + ISNULL(RelocLoss, 0) +
    ISNULL(IncLoss, 0) + ISNULL(RentLoss, 0) + ISNULL(WageLoss, 0)) AS EconLoss
    FROM {s}.dbo.[eqTractEconLoss]
    GROUP BY [eqTractEconLoss].Tract""".format(s=inputs['study_region'])
    
    sql_county_fips = """SELECT Tract, {s}.dbo.hzCounty.CountyFips, {s}.dbo.hzCounty.CountyName, {s}.dbo.hzCounty.State
    FROM {s}.dbo.[hzTract] FULL JOIN {s}.dbo.hzCounty ON {s}.dbo.hzTract.CountyFips
    = {s}.dbo.hzCounty.CountyFips""".format(s=inputs['study_region'])
    
    sql_demographics = """SELECT Tract, Population, Households FROM
    {s}.dbo.[hzDemographicsT]""".format(s=inputs['study_region'])
    
    sql_impact = """SELECT Tract, DebrisW AS DebrisBW, DebrisS AS DebrisCS,
    DisplacedHouseholds AS DisplHouse, ShortTermShelter AS Shelter
    FROM {s}.dbo.[eqTract]""".format(s=inputs['study_region'])
    
    sql_injury = """SELECT Tract, SUM(CASE WHEN CasTime = 'N' THEN Level1Injury 
    ELSE 0 END) AS NiteL1Inj, SUM(CASE WHEN CasTime = 'N' 
    THEN Level2Injury ELSE 0 END) AS NiteL2Inj, SUM(CASE WHEN CasTime = 'N' 
    THEN Level3Injury ELSE 0 END) AS NiteL3Inj, SUM(CASE WHEN CasTime = 'N' 
    THEN Level4Injury ELSE 0 End) AS NiteFatals, SUM(CASE WHEN CasTime = 'D' 
    THEN Level1Injury ELSE 0 END) AS DayL1Inj,  SUM(CASE WHEN CasTime = 'D' 
    THEN Level2Injury ELSE 0 END) AS DayL2Inj, SUM(CASE WHEN CasTime = 'D' 
    THEN Level3Injury ELSE 0 END) AS DayL3Inj, SUM(CASE WHEN CasTime = 'D' 
    THEN Level4Injury ELSE 0 End) AS DayFatals FROM {s}.dbo.[eqTractCasOccup] 
    WHERE CasTime IN ('N', 'D') AND InOutTot = 'Tot' GROUP BY Tract""".format(s=inputs['study_region'])
    
    sql_building_damage = """SELECT Tract, SUM(ISNULL(PDsNoneBC, 0)) As NoDamage,
    SUM(ISNULL(PDsSlightBC, 0)) AS Affected, SUM(ISNULL(PDsModerateBC, 0)) AS Minor,
    SUM(ISNULL(PDsExtensiveBC, 0)) AS Major, SUM(ISNULL(PDsCompleteBC, 0))
    AS Destroyed, SUM(CASE WHEN Occupancy = 'RES1' THEN PDsNoneBC ELSE 0 END) As RES1NoDam,
    SUM(CASE WHEN Occupancy = 'RES1' THEN PDsSlightBC ELSE 0 END) As RES1Affect,
    SUM(CASE WHEN Occupancy = 'RES1' THEN PDsModerateBC ELSE 0 END) As RES1Minor,
    SUM(CASE WHEN Occupancy = 'RES1' THEN PDsExtensiveBC ELSE 0 END) As RES1Major,
    SUM(CASE WHEN Occupancy = 'RES1' THEN PDsCompleteBC ELSE 0 END) As RES1Destr,
    SUM(CASE WHEN Occupancy = 'RES2' THEN PDsNoneBC ELSE 0 END) As RES2NoDam,
    SUM(CASE WHEN Occupancy = 'RES2' THEN PDsSlightBC ELSE 0 END) As RES2Affect,
    SUM(CASE WHEN Occupancy = 'RES2' THEN PDsModerateBC ELSE 0 END) As RES2Minor,
    SUM(CASE WHEN Occupancy = 'RES2' THEN PDsExtensiveBC ELSE 0 END) As RES2Major,
    SUM(CASE WHEN Occupancy = 'RES2' THEN PDsCompleteBC ELSE 0 END) As RES2Destr
    FROM {s}.dbo.[eqTractDmg] WHERE DmgMechType = 'STR'
    GROUP BY Tract""".format(s=inputs['study_region'])
    
    sql_building_damage_occup = """SELECT Occupancy, SUM(ISNULL(PDsNoneBC, 0))
    As NoDamage, SUM(ISNULL(PDsSlightBC, 0)) AS Affected, SUM(ISNULL(PDsModerateBC, 0))
    AS Minor, SUM(ISNULL(PDsExtensiveBC, 0)) AS Major,
    SUM(ISNULL(PDsCompleteBC, 0)) AS Destroyed FROM {s}.dbo.[eqTractDmg]
    WHERE DmgMechType = 'STR' GROUP BY Occupancy""".format(s=inputs['study_region'])
    
    sql_building_damage_bldg_type = """SELECT eqBldgType AS BldgType,
    SUM(ISNULL(PDsNoneBC, 0)) As NoDamage, SUM(ISNULL(PDsSlightBC, 0)) AS Affected,
    SUM(ISNULL(PDsModerateBC, 0)) AS Minor, SUM(ISNULL(PDsExtensiveBC, 0))
    AS Major, SUM(ISNULL(PDsCompleteBC, 0)) AS Destroyed
    FROM {s}.dbo.[eqTractDmg] WHERE DmgMechType = 'STR'
    GROUP BY eqBldgType""".format(s=inputs['study_region'])
    
    sql_spatial = """SELECT Tract, Shape.STAsText() AS Shape
    FROM {s}.dbo.[hzTract]""".format(s=inputs['study_region'])
    
    sql_hazard = """SELECT Tract, PGA from {s}.dbo.[eqTract]""".format(s=inputs['study_region'])
    
    # sql_pga_tract = """SELECT Shape.STAsText() AS Shape, ParamValue from %s.dbo.[eqSrPGA]"""%inputs['study_region']

    #Group tables and queries into iterable
    hazus_results = {'econ_loss': sql_econ_loss, 'county_fips': sql_county_fips,
                    'demographics': sql_demographics, 'impact': sql_impact,
                    'injury': sql_injury,'building_damage': sql_building_damage,
                    'building_damage_occup': sql_building_damage_occup,
                    'building_damage_bldg_type': sql_building_damage_bldg_type,
                    'tract_spatial': sql_spatial,
                    'hazard_tract': sql_hazard}

    #Read result tables from SQL Server into dataframes with Census ID as index
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

    # Join and group results dataframes into tract and county dataframes
    subcounty_results = hazus_results_dict['county_fips'].join([hazus_results_dict['econ_loss'],
    hazus_results_dict['demographics'], hazus_results_dict['impact'],
    hazus_results_dict['injury'], hazus_results_dict['building_damage'], hazus_results_dict['hazard_tract']], sort=True)
    county_results = subcounty_results.groupby('CountyFips').sum()
    county_update = subcounty_results.groupby('CountyFips').agg({
        'State': 'first',
        'CountyName': 'first'
    })
    county_results = county_results.join(county_update)

    # return hazus_results_dict, subcounty_results, county_results

    # Summarize and export damaged essential facilities
    essential_facilities = ['CareFlty', 'EmergencyCtr', 'FireStation',
                                    'PoliceStation', 'School', 'AirportFlty', 'BusFlty', 'FerryFlty',
                                    'HighwayBridge', 'HighwayTunnel', 'LightRailBridge','LightRailFlty',
                                    'LightRailTunnel', 'PortFlty', 'RailFlty', 'RailwayBridge',
                                    'RailwayTunnel', 'Runway', 'ElectricPowerFlty', 'CommunicationFlty',
                                    'NaturalGasFlty', 'OilFlty', 'PotableWaterFlty', 'WasteWaterFlty',
                                    'Dams', 'Military', 'NuclearFlty', 'HighwaySegment', 'LightRailSegment',
                                    'RailwaySegment', 'NaturalGasPl', 'OilPl', 'WasteWaterPl', 'Levees']

    damaged_facilities = pd.DataFrame()
    damaged_facilities_shp = pd.DataFrame()
    
    # TODO this needs to be recoded
    for i in essential_facilities:
        print(i)
    #    name = hazard[0:2].lower() + i
        name = 'eq' + i
        query = """SELECT * FROM {s}.dbo.""".format(s=inputs['study_region']) + name + """ WHERE EconLoss > 0"""
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
            spatial_query = """SELECT """ + columns + """, Shape.STAsText() AS Shape FROM {s}.dbo.""".format(s=inputs['study_region']) + spatial + """ WHERE """ + ids[0] + """ in ('""" + damage_ids + """')"""
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
            #Count offline essential facilities (FunctDay1 < 50) by county and add to county_results
            if 'CountyFips' not in results_df.columns:
                results_df['CountyFips'] = results_df['Tract'].str[:5]
            count_df = results_df[results_df.FunctDay1<50].groupby('CountyFips').count()
            count_df[i] = count_df['EconLoss']
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
        spatial_df = hazus_results_dict['county_fips'].join(hazus_results_dict['tract_spatial'])
        df = subcounty_results.join(spatial_df['Shape'])
        df['geometry'] = df['Shape'].apply(loads)
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
