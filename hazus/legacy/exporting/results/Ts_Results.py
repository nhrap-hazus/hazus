import pandas as pd
from shapely.wkt import loads
from shapely.geometry import mapping, Polygon
import fiona
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
    sql_econ_loss = """SELECT CensusBlock, SUM(ISNULL(TotalLoss, 0))
        AS EconLoss FROM %s.dbo.[tsuvResDelKTotB]
        Group by CensusBlock""" %inputs['study_region']

    sql_demographics = """SELECT CensusBlock, Population, Households FROM
        %s.dbo.[hzDemographicsB]""" %inputs['study_region']

    sql_injury = """SELECT
        cdf.CensusBlock,
        cdf.InjuryDayTotal as InjuryDayFair,
        cdf.FatalityDayTotal As FatalityDayFair,
        cdg.InjuryDayTotal As InjuryDayGood,
        cdg.FatalityDayTotal As FatalityDayGood,
        cdp.InjuryDayTotal As InjuryDayPoor,
        cdp.FatalityDayTotal As FatalityDayPoor,
        cnf.InjuryNightTotal As InjuryNightFair,
        cnf.FatalityNightTotal As FatalityNightFair,
        cng.InjuryNightTotal As InjuryNightGood,
        cng.FatalityNightTotal As FatalityNightGood,
        cnp.InjuryNightTotal As InjuryNightPoor,
        cnp.FatalityNightTotal As FatalityNightPoor
            FROM {s}.dbo.tsCasualtyDayFair as cdf
                FULL JOIN {s}.dbo.tsCasualtyDayGood as cdg
                    ON cdf.CensusBlock = cdg.CensusBlock
                FULL JOIN {s}.dbo.tsCasualtyDayPoor as cdp
                    ON cdf.CensusBlock = cdp.CensusBlock
                FULL JOIN {s}.dbo.tsCasualtyNightFair as cnf
                    ON cdf.CensusBlock = cnf.CensusBlock
                FULL JOIN {s}.dbo.tsCasualtyNightGood as cng
                    ON cdf.CensusBlock = cng.CensusBlock
                FULL JOIN {s}.dbo.tsCasualtyNightPoor as cnp
                    ON cdf.CensusBlock = cnp.CensusBlock""".format(s=inputs['study_region'])

    sql_building_damage = """SELECT CBFips As CensusBlock,
        COUNT({s}.dbo.tsHazNsiGbs.NsiID) As Total,

        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.05 THEN 1 ELSE NULL END) As Affected,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.05 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.3 THEN 1 ELSE NULL END) As Minor,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.3 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.5 THEN 1 ELSE NULL END) As Major,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.5 THEN 1 ELSE NULL END) As Destroyed,

        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont))
        <= 0.05 AND LEFT({s}.dbo.tsHazNsiGbs.NsiID, 4) = 'RES1' THEN 1 ELSE NULL END) As RES1Affect,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.05 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.3 AND LEFT({s}.dbo.tsHazNsiGbs.NsiID, 4) = 'RES1' THEN 1 ELSE NULL END) As RES1Minor,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.3 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.5 AND LEFT({s}.dbo.tsHazNsiGbs.NsiID, 4) = 'RES1' THEN 1 ELSE NULL END) As RES1Major,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.5 AND LEFT({s}.dbo.tsHazNsiGbs.NsiID, 4) = 'RES1' THEN 1 ELSE NULL END) As RES1Destroyed,

        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont))
        <= 0.05 AND LEFT({s}.dbo.tsHazNsiGbs.NsiID, 4) = 'RES2' THEN 1 ELSE NULL END) As RES2Affect,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.05 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.3 AND LEFT({s}.dbo.tsHazNsiGbs.NsiID, 4) = 'RES2' THEN 1 ELSE NULL END) As RES2Minor,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.3 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.5 AND LEFT({s}.dbo.tsHazNsiGbs.NsiID, 4) = 'RES2' THEN 1 ELSE NULL END) As RES2Major,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.5 AND LEFT({s}.dbo.tsHazNsiGbs.NsiID, 4) = 'RES2' THEN 1 ELSE NULL END) As RES2Destroyed

        FROM {s}.dbo.tsHazNsiGbs FULL JOIN {s}.dbo.tsNsiGbs
        ON {s}.dbo.tsHazNsiGbs.NsiID = {s}.dbo.tsNsiGbs.NsiID
        FULL JOIN [{s}].[dbo].[tsFRNsiGbs] ON {s}.dbo.tsNsiGbs.NsiID =
        [{s}].[dbo].[tsFRNsiGbs].NsiID
        GROUP BY CBFips""".format(s=inputs['study_region'])

    sql_building_damage_occup = """SELECT LEFT({s}.dbo.tsHazNsiGbs.NsiID, 3) As Occupancy,
        COUNT({s}.dbo.tsHazNsiGbs.NsiID) As Total,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.05 THEN 1 ELSE NULL END) As Affected,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.05 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.3 THEN 1 ELSE NULL END) As Minor,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.3 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.5 THEN 1 ELSE NULL END) As Major,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.5 THEN 1 ELSE NULL END) As Destroyed
        FROM {s}.dbo.tsHazNsiGbs FULL JOIN {s}.dbo.tsNsiGbs
        ON {s}.dbo.tsHazNsiGbs.NsiID = {s}.dbo.tsNsiGbs.NsiID
        FULL JOIN [{s}].[dbo].[tsFRNsiGbs] ON {s}.dbo.tsNsiGbs.NsiID =
        [{s}].[dbo].[tsFRNsiGbs].NsiID WHERE {s}.dbo.tsHazNsiGbs.NsiID IS NOT NULL
        GROUP BY LEFT({s}.dbo.tsHazNsiGbs.NsiID, 3)""".format(s=inputs['study_region'])

    sql_building_damage_bldg_type = """SELECT eqBldgType AS BldgType, [Description],
        COUNT({s}.dbo.tsHazNsiGbs.NsiID) As Structures,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.05 THEN 1 ELSE NULL END) As Affected,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.05 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.3 THEN 1 ELSE NULL END) As Minor,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.3 AND (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        <= 0.5 THEN 1 ELSE NULL END) As Major,
        COUNT(CASE WHEN {s}.dbo.tsHazNsiGbs.ValStruct > 0 AND {s}.dbo.tsHazNsiGbs.ValCont > 0 AND
        (BldgLoss/({s}.dbo.tsHazNsiGbs.ValStruct+{s}.dbo.tsHazNsiGbs.ValCont)) 
        > 0.5 THEN 1 ELSE NULL END) As Destroyed
        FROM {s}.dbo.tsHazNsiGbs FULL JOIN {s}.dbo.eqclBldgType
        ON {s}.dbo.tsHazNsiGbs.EqBldgTypeID = {s}.dbo.eqclBldgType.DisplayOrder
        FULL JOIN [{s}].[dbo].[tsFRNsiGbs] ON {s}.dbo.tsHazNsiGbs.NsiID = 
        [{s}].[dbo].[tsFRNsiGbs].NsiID WHERE EqBldgTypeID IS NOT NULL
        GROUP BY eqBldgType, [Description]""".format(s=inputs['study_region'])
    
    sql_county_fips = """SELECT Tract, {0}.dbo.hzCounty.CountyFips, State, {0}.dbo.hzCounty.CountyName
        FROM {0}.dbo.[hzTract] FULL JOIN {0}.dbo.hzCounty ON {0}.dbo.hzTract.CountyFips
        = {0}.dbo.hzCounty.CountyFips""".format(inputs['study_region'])

    sql_spatial = """SELECT
        tiger.CensusBlock,
        tiger.Tract, tiger.Shape.STAsText() AS Shape,
        travel.Trav_SafeUnder65,
        travel.Trav_SafeOver65
            FROM {s}.dbo.[hzCensusBlock_TIGER] as tiger
                FULL JOIN {s}.dbo.tsTravelTime as travel
                    ON tiger.CensusBlock = travel.CensusBlock""".format(s=inputs['study_region'])

    sql_hazard = """SELECT Depth, Shape.STAsText() AS Shape
        FROM %s.dbo.tsHazNsiGbs""" %inputs['study_region']

    #Group tables and queries into iterable
    hazus_results = {'econ_loss': sql_econ_loss, 'demographics': sql_demographics,
                    'injury': sql_injury, 'building_damage': sql_building_damage,
                    'building_damage_occup': sql_building_damage_occup,
                    'building_damage_bldg_type': sql_building_damage_bldg_type,
                    'county_fips': sql_county_fips,
                    'censusblock_spatial': sql_spatial,
                    'hazard': sql_hazard}

    #Read result tables from SQL Server into dataframes with Census ID as index
    hazus_results_dict = {table: pd.read_sql(query, cnxn) for table, query
    in hazus_results.items()}
    for name, dataframe in hazus_results_dict.items():
        if (name != 'building_damage_occup') and (name != 'building_damage_bldg_type'):
            try:
                dataframe.set_index('CensusBlock', append=False, inplace=True)
            except:
                pass
    
    # Convert units to real $$ bills y'all
    hazus_results_dict['econ_loss'] = hazus_results_dict['econ_loss'] * 1000

    # prepare df for building occupancy plot
    oc_dict = {
        'RES': 'Residential',
        'COM': 'Commercial',
        'IND': 'Industry',
        'AGR': 'Agriculture',
        'EDU': 'Education',
        'REL': 'Religious',
        'GOV': 'Government'
    }
    # update results with dictionary title
    occup_df = hazus_results_dict['building_damage_occup']
    for key in oc_dict.keys():
        occup_df.loc[occup_df['Occupancy'].str.contains(key), 'Occupancy'] = oc_dict[key]
    occup_df = occup_df.groupby('Occupancy').sum().reset_index()

    # format new data frame for plotting bar plot
    new_occup_df = pd.DataFrame()
    hues = ['Affected', 'Minor', 'Major', 'Destroyed']
    for hue in hues:
        hue_df = occup_df[['Occupancy', hue]]
        hue_df.columns = ['Occupancy', 'Total']
        if hue == 'NoDamage':
           hue_df['Status'] = 'No Damage'
        else:
           hue_df['Status'] = hue
        new_occup_df = new_occup_df.append(hue_df)
    # new_occup_df['Total'] = new_occup_df['Total'].astype(int)
    new_occup_df['Total'] = round(new_occup_df['Total'])

    # update results dictionary with dataframe for bar plot
    new_occup_df = new_occup_df[new_occup_df['Status'] != 'Affected']
    hazus_results_dict.update({'building_damage_occup_plot': new_occup_df})

    #Join and group results dataframes into subcounty and county dataframes
    hazus_results_dict['censusblock_spatial'] = hazus_results_dict['censusblock_spatial'].reset_index()
    name_df = hazus_results_dict['censusblock_spatial'].merge(hazus_results_dict['county_fips'], on='Tract').set_index('CensusBlock')

    agg_dict = {
        'EconLoss': 'sum',
        'Population': 'sum',
        'Households': 'sum',
        'InjuryDayFair': 'sum',
        'FatalityDayFair': 'sum',
        'InjuryDayGood': 'sum',
        'FatalityDayGood': 'sum',
        'InjuryDayPoor': 'sum',
        'FatalityDayPoor': 'sum',
        'InjuryNightFair': 'sum',
        'FatalityNightFair': 'sum',
        'FatalityNightGood': 'sum',
        'InjuryNightGood': 'sum',
        'InjuryNightPoor': 'sum',
        'FatalityNightPoor': 'sum',
        'Total': 'sum',
        'Affected': 'sum',
        'Minor': 'sum',
        'Major': 'sum',
        'Destroyed': 'sum',
        'RES1Affect': 'sum',
        'RES1Minor': 'sum',
        'RES1Major': 'sum',
        'RES1Destroyed': 'sum',
        'RES2Affect': 'sum',
        'RES2Minor': 'sum',
        'RES2Major': 'sum',
        'RES2Destroyed': 'sum',
        'Tract': 'first',
        'CountyName': 'first',
        'CountyFips': 'first',
        'State': 'first'
    }

    subcounty_results = hazus_results_dict['econ_loss'].join([hazus_results_dict['demographics'],
    hazus_results_dict['injury'], hazus_results_dict['building_damage'], name_df])
    county_results = subcounty_results.groupby(subcounty_results['CountyFips']).agg(agg_dict)

    # to keep returns consistent across modules
    damaged_facilities = ''

    # consolidates all data for validating values
    return_dict_update = {
        'subcounty_results': subcounty_results,
        'county_results': county_results,
        'damaged_facilities': damaged_facilities
    }
    return_dict = hazus_results_dict.copy()
    return_dict.update(return_dict_update)
    # validate all values
    for k, v in return_dict.items():
        return_dict[k] = setValuesValid(v)

    return hazus_results_dict, subcounty_results, county_results, damaged_facilities

#Export results dataframes to text files
def to_csv(hazus_results_dict, subcounty_results, county_results, damaged_facilities, inputs):
    tabular_df = {'building_damage_occup':
                    hazus_results_dict['building_damage_occup'],
                    'building_damage_bldg_type':
                    hazus_results_dict['building_damage_bldg_type'],
                    'censusblock_results': subcounty_results,
                    'county_results': county_results}
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
        subcounty_results['geometry'] = subcounty_results['Shape'].apply(loads)
        subcounty_results = subcounty_results.drop('Shape', axis=1)
        gdf = gpd.GeoDataFrame(subcounty_results, geometry='geometry')
        # fixes topology
        gdf['geometry'] = gdf.buffer(0)
        # nanFields = ['Trav_SafeOver65', 'Trav_SafeUnder65']
        # for field in nanFields:
        #     gdf[field] = np.where(gdf[field] == np.nan, 0, gdf[field])
        crs={'proj':'longlat', 'ellps':'WGS84', 'datum':'WGS84','no_defs':True}
        gdf.crs = crs
        # hazus_results_dict['hazard'].crs = crs
        print(time() - t0)
        # print('spatial joining hazard data')
        # t0 = time()
        # sjoin = gpd.sjoin(hazus_results_dict['hazard'], gdf, how='right', op='intersects')
        # sjoin = sjoin.reset_index()
        # sjoin = sjoin.drop(['index_right', 'index_left'], axis=1)
        # print(time() - t0)
        if inputs['opt_shp']:
            print('saving shapefile')
            t0 = time()
            gdf.to_file(inputs['output_directory'] + '/' + inputs['study_region'] + '/' + 'censusblock_results.shp', driver='ESRI Shapefile')
            print(time() - t0)
        return gdf
    else:
        sys.exit('No economic loss — unable to process study region')