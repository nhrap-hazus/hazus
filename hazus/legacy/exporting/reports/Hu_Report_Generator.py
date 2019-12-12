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
import matplotlib.ticker as ticker
import seaborn as sns
import shapely
from jenkspy import jenks_breaks as nb
import numpy as np
from copy import copy
from stat import S_IREAD, S_IRGRP, S_IROTH
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

    patchCollection = PatchCollection(patches, facecolor=facecolor, linewidth=linewidth, edgecolor=edgecolor, alpha=alpha, match_original=True, **kwargs)

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
    # gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.001,preserve_topology=True)
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
    # fig = plt.figure(figsize=(2.74, 2.46), dpi=600) 
    fig = plt.figure(figsize=(2.74, 2.36), dpi=600) 
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
    
    print('plotting windspeeds')
    mod = 1.25
    hazard_colors = {
        '0': {'lowValue': 0.0, 'highValue': 39*mod, 'color': '#ffffff'},
        '1': {'lowValue': 40, 'highValue': 58*mod, 'color': '#82f9fb'},
        '2': {'lowValue': 59*mod, 'highValue': 73*mod, 'color': '#7efbdf'},
        '3': {'lowValue': 74*mod, 'highValue': 95*mod, 'color': '#95f879'},
        '4': {'lowValue': 96*mod, 'highValue': 110*mod, 'color': '#f7f835'},
        '5': {'lowValue': 111*mod, 'highValue': 129*mod, 'color': '#fdca2c'},
        '6': {'lowValue': 130*mod, 'highValue': 156*mod, 'color': '#ff701f'},
        '7': {'lowValue': 157*mod, 'highValue': 179*mod, 'color': '#ec2516'},
        '8': {'lowValue': 180*mod, 'highValue': 300*mod, 'color': '#c81e11'}
    }

    breaks = [hazard_colors[x]['highValue'] for x in hazard_colors][1:]
    color_vals = [gdf.iloc[[x]]['PEAKGUST'][0] for x in idx]
    color_indicies = pd.cut(color_vals, bins=([0] + list(breaks)), labels=[x[0] + 1 for x in enumerate(list(breaks))])
    color_indicies = pd.Series(pd.to_numeric(color_indicies)).fillna(0).astype(int)
    hex_array = [hazard_colors[str(x)]['color'] for x in color_indicies]

    t0 = time()
    fig = plt.figure(figsize=(2.74, 2.3), dpi=600) 
    # fig = plt.figure(figsize=(2.74, 2.46), dpi=600) 
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

def create_occupancy_plot(df, output_directory):
    print('plotting occupancy bar graph')
    t0 = time()
    df['Occupancy'] = df['Type']
    color_dict = dict(zip(df.Status.unique(), ['#549534', '#f3de2c', '#bf2f37']))
    # plt.figure(figsize=(4.2,1.8))
    plt.figure(figsize=(4.2,1.9))
    ax = sns.barplot(x='Occupancy', y='Total', hue='Status', data=df, palette=color_dict)
    # ax.set_title('Building Damage by Occupancy', fontsize=8)
    ax.set_xlabel('')
    plt.box(on=None)
    plt.legend(title='', fontsize=6)
    plt.xticks(fontsize=5)
    plt.yticks(fontsize=5)
    fmt = '{x:,.0f}'
    tick = ticker.StrMethodFormatter(fmt)
    ax.yaxis.set_major_formatter(tick) 
    plt.ylabel('Total Buildings', fontsize=6)
    plt.tight_layout(pad=0.1, h_pad=None, w_pad=None, rect=None)
    plt.subplots_adjust(top=0.85)
    for p in ax.patches:
        ax.annotate('{:,}'.format(int(p.get_height() + 0.5)), (p.get_x() + p.get_width() / 2., p.get_height()),
        ha = 'center', va = 'center', xytext = (0, 10), textcoords = 'offset points', rotation=90,
        fontsize=6, color='dimgrey')
    plt.savefig(output_directory + '/' + 'occup.png', pad_inches=0, dpi=400)
    print(time() - t0)

def create_essential_facilities_plot(df, output_directory):
    print('plotting essential facilities bar graph')
    t0 = time()
    df['Facility'] = df['Type']
    color_dict = dict(zip(df.Status.unique(), ['#549534', '#f3de2c', '#bf2f37']))
    plt.figure(figsize=(4.2,2))
    ax = sns.barplot(x='Facility', y='Total', hue='Status', data=df, palette=color_dict)
    # ax.set_title('Damaged Essential Facilties', fontsize=8)
    ax.set_xlabel('')
    plt.box(on=None)
    plt.legend(title='', fontsize=6)
    plt.xticks(fontsize=5)
    plt.yticks(fontsize=5)
    fmt = '{x:,.0f}'
    tick = ticker.StrMethodFormatter(fmt)
    ax.yaxis.set_major_formatter(tick) 
    plt.ylabel('Total Facilities', fontsize=6)
    plt.tight_layout(pad=0.1, h_pad=None, w_pad=None, rect=None)
    plt.subplots_adjust(top=0.85)
    for p in ax.patches:
        ax.annotate('{:,}'.format(int(p.get_height() + 0.5)), (p.get_x() + p.get_width() / 2., p.get_height()),
        ha = 'center', va = 'center', xytext = (0, 10), textcoords = 'offset points', rotation=90,
        fontsize=6, color='dimgrey')
    plt.savefig(output_directory + '/' + 'ef.png', pad_inches=0, dpi=400)
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

def merge_maps(hazus_results_dict, gdf, data_pdf_path, map_pdf_path, folder_path, study_region, breaks):
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
        create_occupancy_plot(hazus_results_dict['building_damage_occup_plot'], out_path)
        create_essential_facilities_plot(hazus_results_dict['damaged_facilities_plot'], out_path)
        extentIMG = out_path + 'extent.png'
        econlossIMG = out_path + 'econloss.png'
        occupIMG = out_path + 'occup.png'
        efIMG = out_path + 'ef.png'
        
        # Create the watermark from an image
        map_pdf = out_path + str(uuid.uuid1())+'.pdf'
        c = canvas.Canvas(map_pdf)
        # scale = 4.75
        # c.scale(1/scale, 1/scale)
        # c.drawImage(occupIMG, 18*scale, 552*scale)
        scale = 5.96
        c.scale(1/scale, 1/scale)
        c.drawImage(extentIMG, 327*scale, 146*scale)
        c.drawImage(econlossIMG, 327*scale, 414*scale)
        c.drawImage(occupIMG, 19*scale, 546*scale)
        c.drawImage(efIMG, 19*scale, 215*scale)
        c.save()
        
        merge_pdfs(data_pdf_path, map_pdf, map_pdf_path)
        
        removal_list = [map_pdf, extentIMG, econlossIMG, occupIMG, efIMG]
        for item in removal_list:
                os.remove(item)
    except:
        removal_list = [map_pdf, extentIMG, econlossIMG, occupIMG]
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
        template = 'Hu_template' if len(county_results) > 1 else 'Hu_template2'

        # join county name to county_results
        county_results['_CountyFips'] = county_results.index
        subcounty_results['_CountyFips'] = subcounty_results['CountyFips']

        # sort counties by impact
        if len(county_results) > 1:
            # set a common value for grouping
            # hazus_results_dict['building_damage_occup']['common'] = 0

            # RES = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('RES'))]
            # COM = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('COM'))].groupby('common').sum()
            # IND = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('IND'))].groupby('common').sum()
            # AGR = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('AGR'))].groupby('common').sum()
            # GOV = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('GOV'))].groupby('common').sum()
            # REL = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('REL'))].groupby('common').sum()
            # EDU = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('EDU'))].groupby('common').sum()

            # SingleFamilyAndMobile = RES[(RES.Occupancy == 'RES1')]
            # SingleFamilyAndMobile = RES[(RES.Occupancy == 'RES1') | (RES.Occupancy == 'RES2')]
            
            # tract_cat = pd.concat([subcounty_results['_CountyFips'], subcounty_results['CountyName'], subcounty_results['State']], axis=1)
            # county_results['EconLoss'] = round(county_results['EconLoss'].astype(int)
            # economic loss by county
            econloss = county_results.sort_values(by='EconLoss', ascending=False)[0:7]
            # non fatal injuries by county
            # nonfatals = county_results.sort_values(by='NonFatal5p', ascending=False)[0:7]
            # nonfatals_total = round(sum(county_results['NonFatal5p']))
            # shelter needs by county
            shelter_needs = county_results.sort_values(by='DisplHouse', ascending=False)[0:7]
        
        # sort tracts by impact
        if len(county_results) == 1:
            econloss = subcounty_results.sort_values(by='EconLoss', ascending=False)[0:7]
            shelter_needs = subcounty_results.sort_values(by='DisplHouse', ascending=False)[0:7]
            # logically sort values if fields are insignificant
            if shelter_needs['DisplHouse'][0] == 0:
                shelter_needs = econloss.copy()
                
            # remap field names
            econloss['State'] = [a +', ' + b for a, b in zip(econloss['CountyName'], econloss['State'])]
            econloss['CountyName'] = econloss.index
            shelter_needs['State'] = [a +', ' + b for a, b in zip(shelter_needs['CountyName'], shelter_needs['State'])]
            shelter_needs['CountyName'] = shelter_needs.index

        
        # totals
        econloss_total = sum(county_results['EconLoss'])
        displaced_households_total = round(sum(county_results['DisplHouse']))
        debris_cs = round(sum(county_results['DebrisCS']))
        debris_bw = round(sum(county_results['DebrisBW']))
        debris_t = round(sum(county_results['DebrisTree']))
        debris_et = round(sum(county_results['ElgDebTree']))
        debris_total = debris_cs + debris_bw + debris_t + debris_et
        # debris_bw_total = round(sum(county_results['Debris']))
        # debris_cs_total = round(sum(county_results['Debris']))
        
        # ensures all seven fields are populated
        if len(econloss) < 7:
            new_rows = 7 - len(econloss)
            for row in range(new_rows):
                new_row = pd.Series(list(map(lambda x: ' ', econloss.columns)), index=econloss.columns)
                econloss = econloss.append([new_row])
                # nonfatals = nonfatals.append([new_row])
                shelter_needs = shelter_needs.append([new_row])
        t0 = time()
        print('finding normal breaks in data')
        breaks = nb(subcounty_results['EconLoss'], nb_class=5)
        print(time() - t0)
        legend_item1 = breaks[0]
        legend_item2 = breaks[1]
        legend_item3 = breaks[2]
        legend_item4 = breaks[3]
        legend_item5 = breaks[4]
        # legend_item1 = subcounty_results.EconLoss.quantile(.2)
        # legend_item2 = subcounty_results.EconLoss.quantile(.4)
        # legend_item3 = subcounty_results.EconLoss.quantile(.6)
        # legend_item4 = subcounty_results.EconLoss.quantile(.8)
        # legend_item5 = subcounty_results.EconLoss.quantile(1)

        data_dict = {
            'title': title,
            'date': 'Hazus run ' + date + meta,
            # 'g_res': f(sum(SingleFamilyAndMobile['Affected'])),
            # 'g_com': f(sum(COM['Affected'])),
            # 'g_ind': f(sum(IND['Affected'])),
            # 'g_agr': f(sum(AGR['Affected'])),
            # 'g_edu': f(sum(EDU['Affected'])),
            # 'g_gov': f(sum(GOV['Affected'])),
            # 'g_rel': f(sum(REL['Affected'])),
            # 'y_res': f(sum(SingleFamilyAndMobile['Minor'])),
            # 'y_com': f(sum(COM['Minor'])),
            # 'y_ind': f(sum(IND['Minor'])),
            # 'y_agr': f(sum(AGR['Minor'])),
            # 'y_edu': f(sum(EDU['Minor'])),
            # 'y_gov': f(sum(GOV['Minor'])),
            # 'y_rel': f(sum(REL['Minor'])),
            # 'r_res': f(sum(SingleFamilyAndMobile['MajorAndDestroyed'])),
            # 'r_com': f(sum(COM['MajorAndDestroyed'])),
            # 'r_ind': f(sum(IND['MajorAndDestroyed'])),
            # 'r_agr': f(sum(AGR['MajorAndDestroyed'])),
            # 'r_edu': f(sum(EDU['MajorAndDestroyed'])),
            # 'r_gov': f(sum(GOV['MajorAndDestroyed'])),
            # 'r_rel': f(sum(REL['MajorAndDestroyed'])),
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
            #    'nonfatal_county_1': str(nonfatals['CountyName'].iloc[0]),
            #    'nonfatal_county_2': str(nonfatals['CountyName'].iloc[1]),
            #    'nonfatal_county_3': str(nonfatals['CountyName'].iloc[2]),
            #    'nonfatal_county_4': str(nonfatals['CountyName'].iloc[3]),
            #    'nonfatal_county_5': str(nonfatals['CountyName'].iloc[4]),
            #    'nonfatal_county_6': str(nonfatals['CountyName'].iloc[5]),
            #    'nonfatal_county_7': str(nonfatals['CountyName'].iloc[6]),
            #    'nonfatal_state_1': str(nonfatals['State'].iloc[0]),
            #    'nonfatal_state_2': str(nonfatals['State'].iloc[1]),
            #    'nonfatal_state_3': str(nonfatals['State'].iloc[2]),
            #    'nonfatal_state_4': str(nonfatals['State'].iloc[3]),
            #    'nonfatal_state_5': str(nonfatals['State'].iloc[4]),
            #    'nonfatal_state_6': str(nonfatals['State'].iloc[5]),
            #    'nonfatal_state_7': str(nonfatals['State'].iloc[6]),
            #    'nonfatal_pop_1': f(nonfatals['Population'].iloc[0]),
            #    'nonfatal_pop_2': f(nonfatals['Population'].iloc[1]),
            #    'nonfatal_pop_3': f(nonfatals['Population'].iloc[2]),
            #    'nonfatal_pop_4': f(nonfatals['Population'].iloc[3]),
            #    'nonfatal_pop_5': f(nonfatals['Population'].iloc[4]),
            #    'nonfatal_pop_6': f(nonfatals['Population'].iloc[5]),
            #    'nonfatal_pop_7': f(nonfatals['Population'].iloc[6]),
            #    'nonfatal_injuries_1': f(nonfatals['NonFatal5p'].iloc[0]),
            #    'nonfatal_injuries_2': f(nonfatals['NonFatal5p'].iloc[1]),
            #    'nonfatal_injuries_3': f(nonfatals['NonFatal5p'].iloc[2]),
            #    'nonfatal_injuries_4': f(nonfatals['NonFatal5p'].iloc[3]),
            #    'nonfatal_injuries_5': f(nonfatals['NonFatal5p'].iloc[4]),
            #    'nonfatal_injuries_6': f(nonfatals['NonFatal5p'].iloc[5]),
            #    'nonfatal_injuries_7': f(nonfatals['NonFatal5p'].iloc[6]),
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
            'shelter_pop_1': f(shelter_needs['Population'].iloc[0]),
            'shelter_pop_2': f(shelter_needs['Population'].iloc[1]),
            'shelter_pop_3': f(shelter_needs['Population'].iloc[2]),
            'shelter_pop_4': f(shelter_needs['Population'].iloc[3]),
            'shelter_pop_5': f(shelter_needs['Population'].iloc[4]),
            'shelter_pop_6': f(shelter_needs['Population'].iloc[5]),
            'shelter_pop_7': f(shelter_needs['Population'].iloc[6]),
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
            'debris_type_3': 'Tree',
            'debris_type_4': 'Eligible Tree',
            'debris_tons_1': f(debris_bw),
            'debris_tons_2': f(debris_cs),
            'debris_tons_3': f(debris_t),
            'debris_tons_4': f(debris_et),
            'total_econloss': '$' + f(econloss_total),
            #    'total_injuries': f(nonfatals_total),
            'total_shelter': f(displaced_households_total),
            'total_debris': f(debris_total),
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
        map_pdf_path = out_path + str(uuid.uuid1()) + '.pdf'
        merge_maps(hazus_results_dict, gdf, data_pdf_path, map_pdf_path, folder_path, study_region, breaks)
        output_pdf_path = out_path + study_region+'_Report.pdf'
        write_pdf_with_appearances(data_pdf_path, map_pdf_path, output_pdf_path)

        # make pdf uneditable
        os.chmod(output_pdf_path, S_IREAD|S_IRGRP|S_IROTH)
        
        removal_list = [data_pdf_path, map_pdf_path, out_path+'template.pdf']
        for item in removal_list:
            try:
                os.remove(item)
            except:
                pass
    except:
        removal_list = [data_pdf_path, map_pdf_path]
        for item in removal_list:
            try:
                os.remove(item)
            except:
                pass