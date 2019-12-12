import pandas as pd
import geopandas
import os
#       import zipfile
from time import time
import pdfrw
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from PyPDF2 import PdfFileWriter, PdfFileReader
import uuid
from matplotlib import pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
from matplotlib.colors import LinearSegmentedColormap
import shapely
from jenkspy import jenks_breaks as nb
import numpy as np
from copy import copy
import requests
from ....common import femaSetProxies

#def zip_shapefile(study_region, folder_path):
#    os.chdir(folder_path + '/' + study_region)
#    all_files = os.listdir()
#    shp_files = [x for x in all_files if x.startswith('tract_results') and not x.endswith('.csv')]
#    with zipfile.ZipFile(study_region + '_shapefile.zip', 'w') as zipf:
#        for file in shp_files:
#            zipf.write(file)

# TODO text positioning
# https://community.periscopedata.com/t/182gs1/getting-around-overlapping-data-labels-with-python
# def get_text_positions(x_data, y_data, txt_width, txt_height):
#     a = zip(y_data, x_data)
#     text_positions = y_data.copy()
#     for index, (y, x) in enumerate(a):
#         local_text_positions = [i for i in a if i[0] > (y - txt_height)
#                             and (abs(i[1] - x) < txt_width * 2) and i != (y,x)]
#         if local_text_positions:
#             sorted_ltp = sorted(local_text_positions)
#             if abs(sorted_ltp[0][0] - y) < txt_height: #True == collision
#                 differ = np.diff(sorted_ltp, axis=0)
#                 a[index] = (sorted_ltp[-1][0] + txt_height, a[index][1])
#                 text_positions[index] = sorted_ltp[-1][0] + txt_height
#                 for k, (j, m) in enumerate(differ):
#                     #j is the vertical distance between words
#                     if j > txt_height * 1.5: #if True then room to fit a word in
#                         a[index] = (sorted_ltp[k][0] + txt_height, a[index][1])
#                         text_positions[index] = sorted_ltp[k][0] + txt_height
#                         break
#     return text_positions


# def text_plotter(x_data, y_data, text_positions, axis,txt_width,txt_height):
#     for x,y,t in zip(x_data, y_data, text_positions):
#         axis.text(x - .03, 1.02*t, '%d'%int(y),rotation=0, color='blue', fontsize=13)
#         if y != t:
#             axis.arrow(x, t+20,0,y-t, color='blue',alpha=0.2, width=txt_width*0.0,
#                        head_width=.02, head_length=txt_height*0.5,
#                        zorder=0,length_includes_head=True)
        
def polygons_to_patchcollection(geoms, values=None, colormap='Set1',  facecolor=None, edgecolor=None,
                            alpha=1.0, linewidth=1.0, **kwargs):
    """ Plot a collection of Polygon geometries """
    patches = []
    idx = []

    for poly in enumerate(geoms):

        try:
            a = np.asarray(poly[1].exterior)
            if poly[1].has_z:
                poly[1] = shapely.geometry.Polygon(zip(*poly[1].exterior.xy))

            patches.append(Polygon(a))
            idx.append(poly[0])
        except:
            sub_geoms = list(poly[1])
            for sub in sub_geoms:
                    a = np.asarray(sub.exterior)
                    if sub.has_z:
                        sub = shapely.geometry.Polygon(zip(*sub.exterior.xy))
        
                    patches.append(Polygon(a))
                    idx.append(poly[0])

    patchCollection = PatchCollection(patches, facecolor=facecolor, linewidth=linewidth, edgecolor=edgecolor, alpha=alpha, **kwargs)

    # if values is not None:
    #     patchCollection.set_array(values)
    #     patchCollection.set_cmap(colormap)

    # ax.add_collection(patches, autolim=True)
    # ax.add_collection(patchCollection)
    # ax.autoscale_view()
    return patchCollection, idx

def create_plots(gdf, output_directory, breaks):
    # def find_next(array, value):
    #     array = np.asarray(array)
    #     idx = np.where((array - value) > 0 )[0][0]
    #     return array[idx]

    print('aggregating at the county level')
    t0 = time()
    # handles topology errors
    try:
        county_gdf = gdf[['CountyFips', 'Population', 'CountyName', 'State', 'geometry']].dissolve(by='CountyFips')
        population_sum = gdf.groupby(by=['CountyFips']).agg({'Population': 'sum'})['Population']
        county_gdf['Population'] = population_sum
        county_gdf['coords'] = county_gdf['geometry'].apply(lambda x: x.representative_point().coords[:][0])
    except:
        gdf['geometry'] = gdf.buffer(0)
        county_gdf = gdf[['CountyFips', 'Population', 'CountyName', 'State', 'geometry']].dissolve(by='CountyFips')
        population_sum = gdf.groupby(by=['CountyFips']).agg({'Population': 'sum'})['Population']
        county_gdf['Population'] = population_sum
        county_gdf['coords'] = county_gdf['geometry'].apply(lambda x: x.representative_point().coords[:][0])
    print(time() - t0)

    # print('simplifying geometry')
    # t0 = time()
    # gdf = gdf.drop('Shape', axis=1)
    # gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.00001,preserve_topology=True)
    # print(time() - t0)

    print('patching geometry for faster plotting')
    t0 = time()
    patches, idx = polygons_to_patchcollection(gdf.geometry)
    county_patches, idx_county = polygons_to_patchcollection(county_gdf.geometry)
    print(time() - t0)
    t0 = time()
    
    print('sorting...')
    sorted_gdf = county_gdf.sort_values(by=['Population'], ascending=False)
    poly = copy(patches)
    boundaries = copy(county_patches)
    print(time() - t0)

    print('plotting econloss')
    t0 = time()
    fig = plt.figure(figsize=(2.74, 2.46), dpi=600) 
    ax = fig.gca()
    color_vals = [gdf.iloc[[x]]['EconLoss'][0] for x in idx]
    color_array = pd.cut(color_vals, bins=(list(breaks)), labels=[x[0] + 1 for x in enumerate(list(breaks))][0:-1])
    color_array = pd.Series(pd.to_numeric(color_array)).fillna(0)
    poly.set(array=color_array, cmap='Reds')
    ax.add_collection(poly)
    boundaries.set(facecolor='None', edgecolor='#303030', linewidth=0.3, alpha=0.5)
    ax.add_collection(boundaries)
    ax.margins(x=0, y=0.1)
    ax.axis('off')
    ax.axis('scaled')
    annotated = []
    for row in range(len(sorted_gdf)):
        name = sorted_gdf.iloc[[row]]['CountyName'][0]
        if (name not in annotated) and (len(annotated) < 5):
            coords = sorted_gdf.iloc[[row]]['coords'][0]
            plt.annotate(s=name, xy=coords, horizontalalignment='center', size = 4, color='white',
            path_effects=[pe.withStroke(linewidth=1, foreground='#404040')])
            annotated.append(name)
    fig.tight_layout(pad=0, h_pad=None, w_pad=None, rect=None)
    fig.savefig(output_directory + '/' + 'econloss.png', pad_inches=0)
    print(time() - t0)
    
    # clearing the figure
    fig.clf()
    plt.clf()
    poly = copy(patches)
    boundaries = copy(county_patches)
    
    print('plotting PGA')
    t0 = time()

    hazard_colors = {
        '0': {'lowValue': 0.0, 'highValue': 0, 'color': '#ffffff'},
        '1': {'lowValue': 0.0, 'highValue': 0.0017, 'color': '#dfe6fe'},
        '2': {'lowValue': 0.0017, 'highValue': 0.0078, 'color': '#dfe6fe'},
        '3': {'lowValue': 0.0078, 'highValue': 0.014, 'color': '#82f9fb'},
        '4': {'lowValue': 0.014, 'highValue': 0.039, 'color': '#7efbdf'},
        '5': {'lowValue': 0.039, 'highValue': 0.092, 'color': '#95f879'},
        '6': {'lowValue': 0.092, 'highValue': 0.18, 'color': '#f7f835'},
        '7': {'lowValue': 0.18, 'highValue': 0.34, 'color': '#fdca2c'},
        '8': {'lowValue': 0.34, 'highValue': 0.65, 'color': '#ff701f'},
        '9': {'lowValue': 0.65, 'highValue': 1.24, 'color': '#ec2516'},
        '10': {'lowValue': 1.24, 'highValue': 2, 'color': '#c81e11'}
    }

    breaks = [hazard_colors[x]['highValue'] for x in hazard_colors][1:]
    color_vals = [gdf.iloc[[x]]['PGA'][0] for x in idx]
    color_indicies = pd.cut(color_vals, bins=([0] + list(breaks)), labels=[x[0] + 1 for x in enumerate(list(breaks))])
    color_indicies = pd.Series(pd.to_numeric(color_indicies)).fillna(0).astype(int)
    hex_array = [hazard_colors[str(x)]['color'] for x in color_indicies]

    fig = plt.figure(figsize=(2.74, 2.46), dpi=600)
    ax = fig.gca()
    ax.add_collection(poly)
    poly.set_color(hex_array)
    boundaries.set(facecolor='None', edgecolor='#303030', linewidth=0.3, alpha=0.5)
    ax.add_collection(boundaries)
    ax.margins(x=0, y=0.1)
    ax.axis('off')
    ax.axis('scaled')
    annotated = []
    for row in range(len(sorted_gdf)):
        name = sorted_gdf.iloc[[row]]['CountyName'][0]
        if (name not in annotated) and (len(annotated) < 5):
            coords = sorted_gdf.iloc[[row]]['coords'][0]
            plt.annotate(s=name, xy=coords, horizontalalignment='center', size = 4, color='white',
            path_effects=[pe.withStroke(linewidth=1,foreground='#404040')])
            annotated.append(name)
    fig.tight_layout(pad=0, h_pad=None, w_pad=None, rect=None)
    fig.savefig(output_directory + '/' + 'extent.png', pad_inches=0)
    print(time() - t0)
            
def write_fillable_pdf(input_pdf_path, output_pdf_path, out_path, data_dict):
    ANNOT_KEY = '/Annots'
    ANNOT_FIELD_KEY = '/T'
    ANNOT_VAL_KEY = '/V'
    ANNOT_RECT_KEY = '/Rect'
    SUBTYPE_KEY = '/Subtype'
    WIDGET_SUBTYPE_KEY = '/Widget'
    try:
        template_pdf = pdfrw.PdfReader(input_pdf_path)
    except:
        try:
            template_path = out_path + 'template.pdf'
            req = requests.get(input_pdf_path, timeout=4)
            with open(template_path, 'wb') as f:
                f.write(req.content)
            template_pdf = pdfrw.PdfReader(template_path)
        except:
            femaSetProxies()
            template_path = out_path + 'template.pdf'
            req = requests.get(input_pdf_path, timeout=4)
            with open(template_path, 'wb') as f:
                f.write(req.content)
            template_pdf = pdfrw.PdfReader(template_path)
    try:
        template_pdf.Root.AcroForm.update(pdfrw.PdfDict(NeedAppearances=pdfrw.PdfObject('true')))
    except:
        pass
    annotations = template_pdf.pages[0][ANNOT_KEY]
    for annotation in annotations:
        if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
            if annotation[ANNOT_FIELD_KEY]:
                key = annotation[ANNOT_FIELD_KEY][1:-1]
                if key in data_dict.keys():
                    annotation.update(
                        pdfrw.PdfDict(V='{}'.format(data_dict[key]))
                    )
    pdfrw.PdfWriter().write(output_pdf_path, template_pdf)

def write_pdf_with_appearances(data_pdf_path, map_pdf_path, output_pdf_path):
    data_pdf = pdfrw.PdfReader(data_pdf_path)
    map_pdf = pdfrw.PdfReader(map_pdf_path)
    map_pdf.Root.AcroForm = data_pdf.Root.AcroForm
    pdfrw.PdfWriter().write(output_pdf_path, map_pdf)

def merge_maps(gdf, data_pdf_path, map_pdf_path, folder_path, study_region, breaks):
    try:
        def merge_pdfs(target, image, output):
            with open(target, 'rb') as template, open(image, 'rb') as overlay:    
                template_pdf = PdfFileReader(template).getPage(0)
                overlay_pdf = PdfFileReader(overlay).getPage(0)
                
                writer = PdfFileWriter()
                
                template_pdf.mergePage(overlay_pdf)
                # add page from input file to output document
                writer.addPage(template_pdf)
                
                with open(output, "wb") as outputStream:
                    writer.write(outputStream)

        out_path = folder_path + '/' + study_region + '/'
        create_plots(gdf, out_path, breaks)
        extentIMG = out_path + 'extent.png'
        econlossIMG = out_path + 'econloss.png'
        
        # Create the watermark from an image
        map_pdf = out_path + str(uuid.uuid1())+'.pdf'
        c = canvas.Canvas(map_pdf)
        scale = 5.96
        c.scale(1/scale, 1/scale)
        c.drawImage(extentIMG, 327*scale, 122*scale)
        c.drawImage(econlossIMG, 327*scale, 404*scale)
        c.save()
        
        merge_pdfs(data_pdf_path, map_pdf, map_pdf_path)
        
        os.remove(map_pdf)
        os.remove(extentIMG)
        os.remove(econlossIMG)
    except:
        removal_list = [map_pdf, extentIMG, econlossIMG]
        for item in removal_list:
            try:
                os.remove(item)
            except:
                pass
   
def generate_report(gdf, hazus_results_dict, subcounty_results, county_results, inputs):
    study_region = inputs['study_region']
    folder_path = inputs['output_directory']
    date = inputs['created']
    date = str(date.month) + '/' + str(date.day) + '/' + str(date.year)
    title = study_region if inputs['title'] == '' else inputs['title']
    meta = '' if inputs['meta'] == '' else ' | ' + inputs['meta']

    try:
        out_path = folder_path + '/' + study_region + '/'
        def f(number, digits=0):
            try:
                f_str = str("{:,}".format(round(number, digits)))
                if ('.' in f_str) and (digits==0):
                    f_str = f_str.split('.')[0]
                if (number > 1000) and (number < 1000000):
                    split = f_str.split(',')
                    f_str = split[0] + '.' + split[1][0:-1] + ' K'
                if (number > 1000000) and (number < 1000000000):
                    split = f_str.split(',')
                    f_str = split[0] + '.' + split[1][0:-1] + ' M'
                if (number > 1000000000) and (number < 1000000000000):
                    split = f_str.split(',')
                    f_str = split[0] + '.' + split[1][0:-1] + ' B'
                return f_str
            except:
                return str(number)
        
        # declare template based on number of counties affected
        template = 'Eq_template' if len(county_results) > 1 else 'Eq_template2'
        
        RES = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('RES'))]
        COM = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('COM'))]
        IND = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('IND'))]
        AGR = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('AGR'))]
        GOV = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('GOV'))]
        REL = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('REL'))]
        EDU = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('EDU'))]
        
        # join county name to county_results
        county_results['_CountyFips'] = county_results.index
        subcounty_results['_CountyFips'] = subcounty_results['CountyFips']
        tract_cat = pd.concat([subcounty_results['_CountyFips'], subcounty_results['CountyName'], subcounty_results['State']], axis=1)
        # county_results = county_results.merge(tract_cat.groupby(['_CountyFips']).first(), on='_CountyFips', how='left')

        # add fields for night and day
        subcounty_results['InjuriesNite'] = subcounty_results['NiteL1Inj'] + subcounty_results['NiteL2Inj'] + subcounty_results['NiteL3Inj']
        subcounty_results['InjuriesDay'] = subcounty_results['DayL1Inj'] + subcounty_results['DayL2Inj'] + subcounty_results['DayL3Inj']
        county_results['InjuriesNite'] = county_results['NiteL1Inj'] + county_results['NiteL2Inj'] + county_results['NiteL3Inj']
        county_results['InjuriesDay'] = county_results['DayL1Inj'] + county_results['DayL2Inj'] + county_results['DayL3Inj']

        # totals
        econloss_total = sum(county_results['EconLoss'])
        nonfatals_total_day = sum([int(x + 0.5) for x in subcounty_results['InjuriesDay']])
        nonfatals_total_nite = sum([int(x + 0.5) for x in subcounty_results['InjuriesNite']])
        fatals_total_day = sum([int(x + 0.5) for x in subcounty_results['DayFatals']])
        fatals_total_nite = sum([int(x + 0.5) for x in subcounty_results['NiteFatals']])
        injuries_total_day = nonfatals_total_day + fatals_total_day
        injuries_total_nite = nonfatals_total_nite + nonfatals_total_nite
        displaced_households_total = round(sum(county_results['DisplHouse']))
        debris_cs_total = round(sum(county_results['DebrisCS']))
        debris_bw_total = round(sum(county_results['DebrisBW']))

        # night/day total handling
        injuries_day_check = injuries_total_day > injuries_total_nite
        injuries_sortby = 'InjuriesDay' if injuries_day_check else 'InjuriesNite'
        # day_nf_check = 1 if nonfatals_total_day > nonfatals_total_nite else 0 # day nonfatal check
        # day_f_check = 1 if fatals_total_day > fatals_total_nite else 0 # day fatal check
        # nonfatals_total = nonfatals_total_day if day_nf_check else nonfatals_total_nite
        # fatals_total = fatals_total_day if day_f_check else fatals_total_nite
        # injuries_total = nonfatals_total + fatals_total

        # sort counties by impact
        if len(county_results) > 1:
            # county_results['EconLoss'] = county_results['EconLoss'].astype(int)
            econloss = county_results.sort_values(by='EconLoss', ascending=False)[0:7]
            injuries = county_results.sort_values(by=injuries_sortby, ascending=False)[0:7]
            injuries['nonfatals'] = injuries['InjuriesDay'].apply(f) + '/' + injuries['InjuriesNite'].apply(f)
            injuries['fatals'] = injuries['DayFatals'].apply(f) + '/' + injuries['NiteFatals'].apply(f)
            # nonfatals_nite = county_results.sort_values(by=injuries_sortby, ascending=False)[0:7]
            # nonfatals_day = county_results.sort_values(by=injuries_sortby, ascending=False)[0:7]
            # injuries = nonfatals_day if day_nf_check else nonfatals_nite
            # injuries['nonfatals'] = nonfatals_day['InjuriesDay'] if day_nf_check else nonfatals_nite['InjuriesNite']
            # injuries['fatals'] = nonfatals_day['DayFatals'] if day_nf_check else nonfatals_nite['NiteFatals']
            shelter_needs = county_results.sort_values(by='DisplHouse', ascending=False)[0:7]

        # sort tracts by impact
        if len(county_results) == 1:
            econloss = subcounty_results.sort_values(by='EconLoss', ascending=False)[0:7]
            shelter_needs = subcounty_results.sort_values(by='DisplHouse', ascending=False)[0:7]
            # non fatal day/night handling
            injuries = subcounty_results.sort_values(by=injuries_sortby, ascending=False)[0:7]
            injuries['nonfatals'] = injuries['InjuriesDay'].apply(f) + '/' + injuries['InjuriesNite'].apply(f)
            injuries['fatals'] = injuries['DayFatals'].apply(f) + '/' + injuries['NiteFatals'].apply(f)
            # nonfatals_nite = subcounty_results.sort_values(by='InjuriesNite', ascending=False)[0:7]
            # nonfatals_day = subcounty_results.sort_values(by='InjuriesDay', ascending=False)[0:7]
            # injuries = nonfatals_day if day_nf_check else nonfatals_nite
            # injuries['nonfatals'] = nonfatals_day['InjuriesDay'] if day_nf_check else nonfatals_nite['InjuriesNite']
            # fatals day/night handling
            # injuries['fatals'] = nonfatals_day['DayFatals'] if day_nf_check else nonfatals_nite['NiteFatals']
            # logically sort values if fields are insignificant
            if shelter_needs['DisplHouse'][0] == 0:
                shelter_needs = econloss.copy()
            if (injuries['nonfatals'][0] == 0) & (injuries['fatals'][0] == 0):
                injuries = econloss.copy()
                
            # remap field names
            econloss['State'] = [a +', ' + b for a, b in zip(econloss['CountyName'], econloss['State'])]
            econloss['CountyName'] = econloss.index
            shelter_needs['State'] = [a +', ' + b for a, b in zip(shelter_needs['CountyName'], shelter_needs['State'])]
            shelter_needs['CountyName'] = shelter_needs.index
            injuries['State'] = [a +', ' + b for a, b in zip(injuries['CountyName'], injuries['State'])]
            injuries['CountyName'] = injuries.index
        
        # floats to int - better here than in results due to rounding
        # injuries['nonfatals'] = [int(x + 0.5) for x in injuries['nonfatals']]
        # injuries['fatals'] = [int(x + 0.5) for x in injuries['fatals']]
        # floatFields = ['InjuriesDay', 'InjuriesNite', 'DayFatals', 'NiteFatals']
        # for field in floatFields:
        #     injuries[field] = [int(x + 0.5) for x in injuries[field]]

        if len(econloss) < 7:
            new_rows = 7 - len(econloss)
            for row in range(new_rows):
                new_row = pd.Series(list(map(lambda x: ' ', econloss.columns)), index=econloss.columns)
                econloss = econloss.append([new_row])
                shelter_needs = shelter_needs.append([new_row])
                new_row = pd.Series(list(map(lambda x: ' ', injuries.columns)), index=injuries.columns)
                injuries = injuries.append([new_row])
                
        t0 = time()
        print('finding normal breaks in data')
        breaks = nb(subcounty_results['EconLoss'], nb_class=5)
        print(time() - t0)
        legend_item1 = breaks[0]
        legend_item2 = breaks[1]
        legend_item3 = breaks[2]
        legend_item4 = breaks[3]
        legend_item5 = breaks[4]

        data_dict = {
            'title': title,
            'date': 'Hazus run ' + date + meta,
            'g_res': f(sum(RES['Minor'])),
            'g_com': f(sum(COM['Minor'])),
            'g_ind': f(sum(IND['Minor'])),
            'g_agr': f(sum(AGR['Minor'])),
            'g_edu': f(sum(EDU['Minor'])),
            'g_gov': f(sum(GOV['Minor'])),
            'g_rel': f(sum(REL['Minor'])),
            'y_res': f(sum(RES['Major'])),
            'y_com': f(sum(COM['Major'])),
            'y_ind': f(sum(IND['Major'])),
            'y_agr': f(sum(AGR['Major'])),
            'y_edu': f(sum(EDU['Major'])),
            'y_gov': f(sum(GOV['Major'])),
            'y_rel': f(sum(REL['Major'])),
            'r_res': f(sum(RES['Destroyed'])),
            'r_com': f(sum(COM['Destroyed'])),
            'r_ind': f(sum(IND['Destroyed'])),
            'r_agr': f(sum(AGR['Destroyed'])),
            'r_edu': f(sum(EDU['Destroyed'])),
            'r_gov': f(sum(GOV['Destroyed'])),
            'r_rel': f(sum(REL['Destroyed'])),
            'econloss_county_1': str(econloss['CountyName'].iloc[0]),
            'econloss_county_2': str(econloss['CountyName'].iloc[1]),
            'econloss_county_3': str(econloss['CountyName'].iloc[2]),
            'econloss_county_4': str(econloss['CountyName'].iloc[3]),
            'econloss_county_5': str(econloss['CountyName'].iloc[4]),
            'econloss_county_6': str(econloss['CountyName'].iloc[5]),
            'econloss_county_7': str(econloss['CountyName'].iloc[6]),
            'econloss_state_1': str(econloss['State'].iloc[0]),
            'econloss_state_2': str(econloss['State'].iloc[1]),
            'econloss_state_3': str(econloss['State'].iloc[2]),
            'econloss_state_4': str(econloss['State'].iloc[3]),
            'econloss_state_5': str(econloss['State'].iloc[4]),
            'econloss_state_6': str(econloss['State'].iloc[5]),
            'econloss_state_7': str(econloss['State'].iloc[6]),
            'econloss_total_1': '$' + f(econloss['EconLoss'].iloc[0], 2) if len(f(econloss['EconLoss'].iloc[0], 2)) > 1 else '',
            'econloss_total_2': '$' + f(econloss['EconLoss'].iloc[1], 2) if len(f(econloss['EconLoss'].iloc[1], 2)) > 1 else '',
            'econloss_total_3': '$' + f(econloss['EconLoss'].iloc[2], 2) if len(f(econloss['EconLoss'].iloc[2], 2)) > 1 else '',
            'econloss_total_4': '$' + f(econloss['EconLoss'].iloc[3], 2) if len(f(econloss['EconLoss'].iloc[3], 2)) > 1 else '',
            'econloss_total_5': '$' + f(econloss['EconLoss'].iloc[4], 2) if len(f(econloss['EconLoss'].iloc[4], 2)) > 1 else '',
            'econloss_total_6': '$' + f(econloss['EconLoss'].iloc[5], 2) if len(f(econloss['EconLoss'].iloc[5], 2)) > 1 else '',
            'econloss_total_7': '$' + f(econloss['EconLoss'].iloc[6], 2) if len(f(econloss['EconLoss'].iloc[6], 2)) > 1 else '',
            'nonfatal_county_1': str(injuries['CountyName'].iloc[0]),
            'nonfatal_county_2': str(injuries['CountyName'].iloc[1]),
            'nonfatal_county_3': str(injuries['CountyName'].iloc[2]),
            'nonfatal_county_4': str(injuries['CountyName'].iloc[3]),
            'nonfatal_county_5': str(injuries['CountyName'].iloc[4]),
            'nonfatal_county_6': str(injuries['CountyName'].iloc[5]),
            'nonfatal_county_7': str(injuries['CountyName'].iloc[6]),
            'nonfatal_state_1': str(injuries['State'].iloc[0]),
            'nonfatal_state_2': str(injuries['State'].iloc[1]),
            'nonfatal_state_3': str(injuries['State'].iloc[2]),
            'nonfatal_state_4': str(injuries['State'].iloc[3]),
            'nonfatal_state_5': str(injuries['State'].iloc[4]),
            'nonfatal_state_6': str(injuries['State'].iloc[5]),
            'nonfatal_state_7': str(injuries['State'].iloc[6]),
            'nonfatal_pop_1': injuries['nonfatals'].iloc[0],
            'nonfatal_pop_2': injuries['nonfatals'].iloc[1],
            'nonfatal_pop_3': injuries['nonfatals'].iloc[2],
            'nonfatal_pop_4': injuries['nonfatals'].iloc[3],
            'nonfatal_pop_5': injuries['nonfatals'].iloc[4],
            'nonfatal_pop_6': injuries['nonfatals'].iloc[5],
            'nonfatal_pop_7': injuries['nonfatals'].iloc[6],
            'nonfatal_injuries_1': injuries['fatals'].iloc[0],
            'nonfatal_injuries_2': injuries['fatals'].iloc[1],
            'nonfatal_injuries_3': injuries['fatals'].iloc[2],
            'nonfatal_injuries_4': injuries['fatals'].iloc[3],
            'nonfatal_injuries_5': injuries['fatals'].iloc[4],
            'nonfatal_injuries_6': injuries['fatals'].iloc[5],
            'nonfatal_injuries_7': injuries['fatals'].iloc[6],
            'shelter_county_1': str(shelter_needs['CountyName'].iloc[0]),
            'shelter_county_2': str(shelter_needs['CountyName'].iloc[1]),
            'shelter_county_3': str(shelter_needs['CountyName'].iloc[2]),
            'shelter_county_4': str(shelter_needs['CountyName'].iloc[3]),
            'shelter_county_5': str(shelter_needs['CountyName'].iloc[4]),
            'shelter_county_6': str(shelter_needs['CountyName'].iloc[5]),
            'shelter_county_7': str(shelter_needs['CountyName'].iloc[6]),
            'shelter_state_1': str(shelter_needs['State'].iloc[0]),
            'shelter_state_2': str(shelter_needs['State'].iloc[1]),
            'shelter_state_3': str(shelter_needs['State'].iloc[2]),
            'shelter_state_4': str(shelter_needs['State'].iloc[3]),
            'shelter_state_5': str(shelter_needs['State'].iloc[4]),
            'shelter_state_6': str(shelter_needs['State'].iloc[5]),
            'shelter_state_7': str(shelter_needs['State'].iloc[6]),
            # 'shelter_pop_1': f(shelter_needs['Households'].iloc[0]), 
            # 'shelter_pop_2': f(shelter_needs['Households'].iloc[1]),
            # 'shelter_pop_3': f(shelter_needs['Households'].iloc[2]),
            # 'shelter_pop_4': f(shelter_needs['Households'].iloc[3]),
            # 'shelter_pop_5': f(shelter_needs['Households'].iloc[4]),
            # 'shelter_pop_6': f(shelter_needs['Households'].iloc[5]),
            # 'shelter_pop_7': f(shelter_needs['Households'].iloc[6]),
            'shelter_house_1': f(shelter_needs['DisplHouse'].iloc[0]),
            'shelter_house_2': f(shelter_needs['DisplHouse'].iloc[1]),
            'shelter_house_3': f(shelter_needs['DisplHouse'].iloc[2]),
            'shelter_house_4': f(shelter_needs['DisplHouse'].iloc[3]),
            'shelter_house_5': f(shelter_needs['DisplHouse'].iloc[4]),
            'shelter_house_6': f(shelter_needs['DisplHouse'].iloc[5]),
            'shelter_house_7': f(shelter_needs['DisplHouse'].iloc[6]),
            'shelter_need_1': f(shelter_needs['Shelter'].iloc[0]),
            'shelter_need_2': f(shelter_needs['Shelter'].iloc[1]),
            'shelter_need_3': f(shelter_needs['Shelter'].iloc[2]),
            'shelter_need_4': f(shelter_needs['Shelter'].iloc[3]),
            'shelter_need_5': f(shelter_needs['Shelter'].iloc[4]),
            'shelter_need_6': f(shelter_needs['Shelter'].iloc[5]),
            'shelter_need_7': f(shelter_needs['Shelter'].iloc[6]),
            'debris_type_1': 'Brick, Wood, & Others',
            'debris_type_2': 'Concrete & Steel',
            'debris_tons_1': f(debris_bw_total),
            'debris_tons_2': f(debris_cs_total),
            'total_econloss': '$' + f(econloss_total),
            'total_injuries': f(injuries_total_day)+'/'+f(injuries_total_nite),
            'total_shelter': f(displaced_households_total),
            'total_debris': f(debris_bw_total + debris_cs_total),
            'legend_1': '$' + f(legend_item1) + '-' + f(legend_item2),
            'legend_2': '$' + f(legend_item2) + '-' + f(legend_item3),
            'legend_3': '$' + f(legend_item3) + '-' + f(legend_item4),
            'legend_4': '$' + f(legend_item4) + '-' + f(legend_item5)
        }

        data_pdf_path = out_path + str(uuid.uuid1())+'.pdf'
        try:
            template_pdf_path = 'src/assets/templates/' + template + '.pdf'
            write_fillable_pdf(template_pdf_path, data_pdf_path, out_path, data_dict)
        except:
            template_pdf_path = 'https://fema-nhrap.s3.amazonaws.com/Utilities/hazus-export-utility/templates/' + template + '.pdf'
            write_fillable_pdf(template_pdf_path, data_pdf_path, out_path, data_dict)
        
        map_pdf_path = out_path + str(uuid.uuid1())+'.pdf'
        merge_maps(gdf, data_pdf_path, map_pdf_path, folder_path, study_region, breaks)
        output_pdf_path = out_path + study_region+'_Report.pdf'
        write_pdf_with_appearances(data_pdf_path, map_pdf_path, output_pdf_path)
        
        removal_list = [data_pdf_path, map_pdf_path, out_path+'template.pdf']
        for item in removal_list:
            try:
                os.remove(item)
            except:
                pass
    except:
        removal_list = [data_pdf_path, map_pdf_path, out_path+template.pdf]
        for item in removal_list:
            try:
                os.remove(item)
            except:
                pass