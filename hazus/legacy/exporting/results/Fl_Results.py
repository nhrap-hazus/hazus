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

    def setSubcountyQuery(returnPeriod, studyRegion):
        sql_subcounty_results = """
        SELECT 
            Sdemo.CensusBlock,
            Sdemo.Tract,
            Sdemo.CountyFips,
            ISNULL(Sdemo.Population, 0) AS Population,
            ISNULL(Sdemo.Households, 0) AS Households,
            Scounty.CountyName,
            Scounty.State,
            ISNULL(Seconloss.TotalLoss, 0) AS TotalLoss,
            ISNULL(Seconloss.BldgLoss, 0) AS BldgLoss,
            ISNULL(Seconloss.ContLoss, 0) AS ContLoss,
            ISNULL(Sdebris.Debris, 0) AS Debris,
            ISNULL(Sdisplaced.DisplacedPop, 0) AS DisplPop,
            ISNULL(Sdisplaced.ShortTermNeeds, 0) AS Shelter,
            Sshape.Shape
                FROM
        (
            (SELECT 
                CensusBlock,
                LEFT(CensusBlock, 5) AS CountyFips,
                LEFT(CensusBlock, 11) AS Tract,
                Population,
                Households
                    FROM {s}.dbo.[hzDemographicsB]) Sdemo
            FULL JOIN
            (SELECT 
                CountyFips, 
                CountyName, 
                State 
                    FROM {s}.dbo.[hzCounty]) Scounty
            ON Scounty.CountyFips = Sdemo.CountyFips
            FULL JOIN
            (SELECT 
                CensusBlock,
                SUM(TotalLoss) * 1000 AS TotalLoss,
                SUM(BuildingLoss) * 1000 AS BldgLoss,
                SUM(ContentsLoss) * 1000 AS ContLoss
                    FROM {s}.dbo.[flFRGBSEcLossByTotal]
                WHERE ReturnPeriodId = {r}
                group by CensusBlock) Seconloss
            ON Seconloss.CensusBlock = Sdemo.CensusBlock
            FULL JOIN
            (SELECT
                CensusBlock,
                TotalTons * 1000 AS Debris
                    FROM {s}.dbo.[flFRDebris]
                WHERE ReturnPeriodId = {r}) Sdebris
            ON Sdebris.CensusBlock = Sdemo.CensusBlock
            FULL JOIN
            (SELECT 
                CensusBlock,
                DisplacedPop,
                ShortTermNeeds
                    FROM {s}.dbo.flFRShelter
                WHERE ReturnPeriodId = {r}) Sdisplaced
            ON Sdisplaced.CensusBlock = Sdemo.CensusBlock
            FULL JOIN
            (SELECT 
                CensusBlock,
                Shape.STAsText() AS Shape
                    FROM {s}.dbo.hzCensusBlock_TIGER) Sshape
            ON Sshape.CensusBlock = Sdemo.CensusBlock
        )
        """.format(s=studyRegion, r=returnPeriod)
        return sql_subcounty_results
    
    sql_econ_loss_occup = """SELECT SOccup AS Occupancy, SUM(ISNULL(TotalLoss, 0))
    AS TotalLoss, SUM(ISNULL(BuildingLoss, 0)) AS BldgLoss,
    SUM(ISNULL(ContentsLoss, 0)) AS ContLoss
    FROM %s.dbo.[flFRGBSEcLossBySOccup] GROUP BY SOccup""" %inputs['study_region']

    sql_econ_loss_bldg_type = """SELECT BldgType, SUM(ISNULL(TotalLoss, 0)) AS TotalLoss,
    SUM(ISNULL(BuildingLoss, 0)) AS BldgLoss, SUM(ISNULL(ContentsLoss, 0)) AS ContLoss
    FROM %s.dbo.[flFRGBSEcLossByGBldgType] GROUP BY BldgType""" %inputs['study_region']

    sql_scenarios = """SELECT [StudyCaseName] FROM %s.[dbo].[flStudyCase]""" %inputs['study_region']

    #Group tables and queries into iterable
    hazus_results = {'econ_loss_occup': sql_econ_loss_occup,
                    'econ_loss_bldg_type': sql_econ_loss_bldg_type,
                    'scenarios': sql_scenarios}

    #Read result tables from SQL Server into dataframes
    hazus_results_dict = {table: pd.read_sql(query, cnxn) for table, query
    in hazus_results.items()}

    returnPeriods = ['100', '500', '50', '25', '10']
    returnPeriodFound = 0
    for returnPeriod in returnPeriods:
        if returnPeriodFound == 0:
            try:
                query = setSubcountyQuery(returnPeriod, inputs['study_region'])
                sql_subcounty_results = pd.read_sql(query, cnxn)
                hazus_results_dict.update({'subcounty_results': sql_subcounty_results})
                returnPeriodFound += 1
            except:
                pass


    def prepBuildingDamageOccup(econ_loss_occup):
        hrd_elo = econ_loss_occup
        # summarize building damage by occupancy type
        oc_dict = {
            'RES': 'Residential',
            'COM': 'Commercial',
            'IND': 'Industry',
            'AGR': 'Agriculture',
            'EDU': 'Education',
            'REL': 'Religious',
            'GOV': 'Government'
        }
        hrd_elo['Occupancy'] = hrd_elo['Occupancy'].apply(lambda x: x.strip())
        for key in oc_dict:
            hrd_elo['Occupancy'][hrd_elo['Occupancy'].str.contains(key)] = oc_dict[key]
        replacements = {
            'BldgLoss': 'Building',
            'ContLoss': 'Content',
            'TotalLoss': 'Total'
        }
        for replace in replacements.items():
            hrd_elo.columns = [x.replace(replace[0], replace[1]) if x == replace[0] else x for x in hrd_elo.columns]
        return hrd_elo

    def prepEconLossByType(econ_loss_bldg_type):
        hrd_elbt = econ_loss_bldg_type
        # hrd_elbt = hazus_results_dict['econ_loss_bldg_type']
        hrd_elbt['BldgType'][hrd_elbt['BldgType'] == 'ManufHousing'] = 'Manufactured'
        replacements = {
            'BldgType': 'Type',
            'BldgLoss': 'Building',
            'ContLoss': 'Content',
            'TotalLoss': 'Total'
        }
        for replace in replacements.items():
            hrd_elbt.columns = [x.replace(replace[0], replace[1]) if x == replace[0] else x for x in hrd_elbt.columns]
        return hrd_elbt


    def prepBarPlot(df, summarize_field, hues):
        summarized = df.groupby(summarize_field).sum()
        summarized = summarized.reset_index()
        new_df = pd.DataFrame()
        for hue in hues:
            hue_df = summarized[[summarize_field, hue]]
            hue_df.columns = ['Type', 'Total']
            hue_df['Status'] = hue
            new_df = new_df.append(hue_df)
        new_df['Total'] = (new_df['Total'] + 0.5).apply(int)
        return new_df
    
    econ_loss_occup = prepBuildingDamageOccup(hazus_results_dict['econ_loss_occup'])
    econ_loss_bldg_type = prepEconLossByType(hazus_results_dict['econ_loss_bldg_type'])
    hues = ['Building', 'Content', 'Total']
    econ_loss_occup_plot = prepBarPlot(econ_loss_occup, 'Occupancy', hues)
    econ_loss_bldg_type_plot = prepBarPlot(econ_loss_bldg_type, 'Type', hues)
    econ_loss_occup_plot['Occupancy'] = econ_loss_occup_plot['Type']
    
    # add new occupancy by building type dataframe to results
    hazus_results_dict.update({'econ_loss_occup_plot': econ_loss_occup_plot})
    hazus_results_dict.update({'econ_loss_bldg_type_plot': econ_loss_bldg_type_plot})
    
    #Summarize and export damaged essential facilities
    essential_facilities = ['CareFlty', 'EmergencyCtr', 'FireStation',
                            'PoliceStation', 'School', 'HighwayBridge', 
                            'LightRailBridge', 'RailwayBridge', 'ElectricPowerFlty',
                            'NaturalGasFlty', 'OilFlty', 'PotableWaterFlty', 
                            'PotableWaterPl', 'WasteWaterFlty']

    damaged_facilities = pd.DataFrame()
    damaged_facilities_shp = pd.DataFrame()
    
    for i in essential_facilities:
        print(i)
        name = 'fl' + 'FR' + i
        query = """SELECT * FROM %s.dbo.""" %inputs['study_region'] + name
        df = pd.read_sql(query, cnxn)
        dmg_column = [column for column in df.columns if 'Dmg' in column or 'Damage' in column]
        dmg_query = """SELECT * FROM %s.dbo.""" %inputs['study_region'] + name + """ WHERE """ + dmg_column[0] + """ > 0"""
        df = pd.read_sql(dmg_query, cnxn)
        if i == 'EmergencyCtr':
            ID = 'EocId'
        else:
            ID = i + 'Id'
        df = df.set_index(ID)
        df['Fac_Type'] = str(i)
        damaged_facilities = damaged_facilities.append(df)
        # Only export records from spatial table that correspond to records with economic loss in damage table
        if len(df.index) > 0:
            damage_ids = "', '".join(list(df.index))
            spatial = 'hz' + i
            columns_query = """SELECT COLUMN_NAME FROM """ + inputs['study_region'] + """.information_schema.columns
            WHERE TABLE_NAME = '""" + spatial + """' AND columns.COLUMN_NAME NOT IN('Shape')"""
            columns_df = pd.read_sql(columns_query, cnxn)
            columns = ",".join(list(columns_df.COLUMN_NAME))
            spatial_query = """SELECT """ + columns + """, Shape.STAsText() AS Shape FROM %s.dbo.""" %inputs['study_region'] + spatial + """ WHERE """ + ID + """ in ('""" + damage_ids + """')"""
            spatial_df = pd.read_sql(spatial_query, cnxn)
            ids = [id for id in spatial_df.columns if 'Id' in id]
            spatial_df = spatial_df.set_index(ids[0])
            results_df = spatial_df.join(df, on = ids[0], how = 'inner')
            damaged_facilities_shp = damaged_facilities_shp.append(results_df)
            #Count offline essential facilities inside subcounty geometries and add to subcounty_results
            results_df['geometry'] = results_df['Shape'].apply(loads)
            damaged_facilities_gdf = gpd.GeoDataFrame(results_df, geometry = 'geometry')
            hazus_results_dict['subcounty_results']['geometry'] = hazus_results_dict['subcounty_results']['Shape'].apply(loads)
            subcounty_gdf = gpd.GeoDataFrame(hazus_results_dict['subcounty_results'], 
                                             geometry='geometry')
            crs={'proj':'longlat', 'ellps':'WGS84', 'datum':'WGS84','no_defs':True}
            damaged_facilities_gdf.crs, subcounty_gdf.crs = (crs, crs)
            dfsjoin = gpd.sjoin(damaged_facilities_gdf, subcounty_gdf)
            count_df = dfsjoin[dfsjoin.Functionality<1].groupby('CensusBlock').count()
            count_df[i] = count_df['Functionality']
            hazus_results_dict['subcounty_results'] = hazus_results_dict['subcounty_results'].join(count_df[i], on='CensusBlock')
            hazus_results_dict['subcounty_results'].drop('geometry', axis=1, inplace=True)

    # consolidates all data for validating values
    return_dict_update = {
        'subcounty_results': hazus_results_dict['subcounty_results'],
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

    subcounty_results = hazus_results_dict['subcounty_results']
    county_results = subcounty_results.groupby('CountyFips').agg({
        'Population': 'sum',
        'Households': 'sum',
        'CountyName': 'first',
        'State': 'first',
        'TotalLoss': 'sum',
        'BldgLoss': 'sum',
        'ContLoss': 'sum',
        'Debris': 'sum',
        'DisplPop': 'sum',
        'Shelter': 'sum',
    })

    return hazus_results_dict, subcounty_results, county_results, damaged_facilities

#Export results dataframes to text files
def to_csv(hazus_results_dict, subcounty_results, county_results, damaged_facilities, inputs):
    tabular_df = {'econ_loss_occup':hazus_results_dict['econ_loss_occup'],
                  'econ_loss_bldg_type':hazus_results_dict['econ_loss_bldg_type'],
                  'censusblock_results': hazus_results_dict['subcounty_results'],
                  'damaged_facilities': damaged_facilities}
    json_output = {}
    for name, dataframe in tabular_df.items():
        if (not dataframe.empty) and (len(dataframe) > 0):
            path = inputs['output_directory'] + '\\' + inputs['study_region'] + '\\' + name + '.csv'
            if inputs['opt_csv']:
                Cols = [x for x in dataframe.columns if x not in ['Shape']]
                dataframe.to_csv(path, columns=Cols)
            if inputs['opt_json']:
                dataframe = dataframe.replace({pd.np.nan: 'null'})
                dictionary = dataframe.to_dict()
                json_output.update({name: dictionary})
    if inputs['opt_json']:
        with open(inputs['output_directory'] + '/' + inputs['study_region'] + '/' + inputs['study_region'] + '.json', 'w') as j:
            json.dump(json_output, j)

#Create shapefile of subcounty results
def to_shp(inputs, hazus_results_dict, subcounty_results):
    if hazus_results_dict['subcounty_results']['TotalLoss'].sum() > 0:
        print('creating geodataframe')
        t0 = time()
        df = hazus_results_dict['subcounty_results']
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
            gdf.to_file(inputs['output_directory'] + '/' + inputs['study_region'] + '/' + 'censusblock_results.shp', driver='ESRI Shapefile')
            print(time() - t0)
        return gdf
    else:
        sys.exit('No economic loss — unable to process study region')
