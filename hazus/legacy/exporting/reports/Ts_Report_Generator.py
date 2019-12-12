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
import matplotlib.ticker as ticker
from mpl_toolkits.axes_grid1 import make_axes_locatable
import seaborn as sns
import shapely
from jenkspy import jenks_breaks as nb
import numpy as np
import rasterio as rio
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

def create_plots(gdf, hazard_gdf, out_path, breaks):
    # TODO create hazard map unrestricted by tracts
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
    fig.savefig(out_path + '/' + 'econloss.png', pad_inches=0)
    print(time() - t0)
    
    # clearing the figure
    fig.clf()
    plt.clf()
    poly = copy(patches)
    boundaries = copy(county_patches)

    # gradient gen: https://pinetools.com/gradient-generator
    time_colors = {
        '0': {'lowValue': 0.0, 'highValue': 15, 'color': '#f9e852'},
        '1': {'lowValue': 15, 'highValue': 30, 'color': '#f0cb49'},
        '2': {'lowValue': 30, 'highValue': 45, 'color': '#e7af40'},
        '3': {'lowValue': 45, 'highValue': 60, 'color': '#de9337'},
        '4': {'lowValue': 60, 'highValue': 75, 'color': '#d5762e'},
        '5': {'lowValue': 75, 'highValue': 90, 'color': '#cc5a25'},
        '6': {'lowValue': 90, 'highValue': 120, 'color': '#c33e1c'},
        '7': {'lowValue': 120, 'highValue': 300, 'color': '#bb2214'}
    }

    breaks = [time_colors[x]['highValue'] for x in time_colors][1:]
    color_vals = [gdf.iloc[[x]]['Trav_SafeOver65'][0] for x in idx]
    color_indicies = pd.cut(color_vals, bins=([0] + list(breaks)), labels=[x[0] + 1 for x in enumerate(list(breaks))])
    color_indicies = pd.Series(pd.to_numeric(color_indicies)).fillna(0)
    color_indicies = color_indicies.apply(int).apply(str)
    hex_array = [time_colors[x]['color'] for x in color_indicies]

    t0 = time()
    fig = plt.figure(figsize=(2.74, 1.5), dpi=600) 
    ax = fig.gca()
    ax.add_collection(poly)
    poly.set_color(hex_array)
    boundaries.set(facecolor='None', edgecolor='#303030', linewidth=0.3, alpha=0.5)
    ax.add_collection(boundaries)
    # ax.margins(x=0, y=0.1) # reduces x whitespace
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
    fig.savefig(out_path + '/' + 'timetravel.png', pad_inches=0)
    print(time() - t0)
    
    # clearing the figure
    fig.clf()
    plt.clf()
    poly = copy(patches)
    boundaries = copy(county_patches)
    
    print('plotting hazard')
    study_region = out_path.split('/')[-2]
    hazard_path = '/'.join(['C:/HazusData/Regions', study_region, 'maxdg_ft'])
    ras = rio.open(hazard_path)
    band = ras.read(1)
    band = np.where(band < 0, 0, band)
    band = np.where(band > 60, 0, band)
    # extent = gpd.read_file('/'.join(hazard_path.split('/')[0:-1]) + '/DepthPolyDiss.shp')

    # bounds = county_gdf.bounds
    # xmin, xmax, ymin, ymax = np.min(bounds.minx), np.max(bounds.maxx), np.min(bounds.miny), np.max(bounds.miny)

    t0 = time()
    fig.clf()
    plt.clf()
    fig = plt.figure(figsize=(2.74, 2.46), dpi=600) 
    ax = fig.gca()
    # ax.add_collection(poly)
    # poly.set_color(hex_array)
    # from mpl_toolkits.basemap import Basemap
    # m = Basemap(llcrnrx=xmin,llcrnry=ymin,urcrnrx=xmax,urcrnry=ymax, resolution = 'c', epsg=4326)
    # m.bluemarble()
    # m.shadedrelief()
    img = ax.imshow(band, cmap='Blues')
    # extent.plot()
    # boundaries.set(facecolor='None', edgecolor='#303030', linewidth=0.3, alpha=0.7)
    # ax.add_collection(boundaries)
    # ax.margins(x=0, y=0.1) # reduces x whitespace
    ax.axis('off')
    ax.axis('scaled')
    # annotated = []
    # for row in range(len(sorted_gdf)):
    #     name = sorted_gdf.iloc[[row]]['CountyName'][0]
    #     if (name not in annotated) and (len(annotated) < 5):
    #         coords = sorted_gdf.iloc[[row]]['coords'][0]
    #         plt.annotate(s=name, xy=coords, horizontalalignment='center', size = 0.3, color='white',
    #         path_effects=[pe.withStroke(linewidth=1,foreground='#404040')])
    #         annotated.append(name)
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("top", size="6%", pad="4%")
    cbar = plt.colorbar(img, cax=cax, orientation="horizontal")
    cax.xaxis.set_ticks_position("top")
    cbar.ax.tick_params(labelsize=4, pad=0, length=0)
    cbar.outline.set_visible(False)
    fig.tight_layout(pad=0, h_pad=None, w_pad=None, rect=None)
    # fig.savefig(out_path + '/' + 'extent.png', pad_inches=0, bbox_inches='tight', transparent="True")
    fig.savefig(out_path + '/' + 'extent.png', pad_inches=0, transparent="True")
    print(time() - t0)

def create_occupancy_plot(df, out_path):
    print('plotting occupancy bar graph')
    t0 = time()
    color_dict = dict(zip(df.Status.unique(), ['#549534', '#f3de2c', '#bf2f37']))
    plt.figure(figsize=(4.2,1.8))
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
    plt.savefig(out_path + '/' + 'occup.png', pad_inches=0, dpi=400)
    print(t0 - time())

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
        create_plots(gdf, hazus_results_dict['hazard'], out_path, breaks)
        create_occupancy_plot(hazus_results_dict['building_damage_occup_plot'], out_path)
        extentIMG = out_path + 'extent.png'
        econlossIMG = out_path + 'econloss.png'
        occupIMG = out_path + 'occup.png'
        travelIMG = out_path + 'timetravel.png'
        
        # Create the watermark from an image
        map_pdf = out_path + str(uuid.uuid1())+'.pdf'
        c = canvas.Canvas(map_pdf)
        scale = 5.96
        c.scale(1/scale, 1/scale)
        c.drawImage(extentIMG, 327*scale, 130*scale)
        c.drawImage(econlossIMG, 327*scale, 404*scale)
        c.drawImage(occupIMG, 19*scale, 556*scale)
        c.drawImage(travelIMG, 19*scale, 29*scale)
        c.save()
        
        merge_pdfs(data_pdf_path, map_pdf, map_pdf_path)
        
        removal_list = [map_pdf, extentIMG, econlossIMG, occupIMG, travelIMG]
        for item in removal_list:
            os.remove(item)
    except:
        removal_list = [map_pdf, extentIMG, econlossIMG, occupIMG, travelIMG]
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
        template = 'Ts_template' if len(county_results) > 1 else 'Ts_template2'
        
        # RES = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('RES'))]
        # COM = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('COM'))]
        # IND = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('IND'))]
        # AGR = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('AGR'))]
        # GOV = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('GOV'))]
        # REL = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('REL'))]
        # EDU = hazus_results_dict['building_damage_occup'].loc[(hazus_results_dict['building_damage_occup'].Occupancy.str.startswith('EDU'))]
        
        # join county name to county_results
        # county_results['_CountyFips'] = county_results.index
        # subcounty_results['_CountyFips'] = subcounty_results['CountyFips']
        # tract_cat = pd.concat([subcounty_results['_CountyFips'], subcounty_results['CountyName'], subcounty_results['State']], axis=1)
        # county_results = county_results.merge(tract_cat.groupby(['_CountyFips']).first(), on='_CountyFips', how='left')
        # economic loss by county
        # non fatal injuries by county
        # nonfatals = county_results.sort_values(by='NonFatal5p', ascending=False)[0:7]
        # nonfatals_total = round(sum(county_results['NonFatal5p']))
        # shelter needs by county
        # shelter_needs = county_results.sort_values(by='Shelter', ascending=False)[0:7]
        # displaced_households_total = round(sum(county_results['DisplHouse']))
        # debris
        # debris_cd_total = round(sum(county_results['DebrisCS']))
        # debris_bw_total = round(sum(county_results['DebrisBW']))
        
        #handle nans
        # nan_fields = ['InjuryDayGood', 'InjuryNightGood', 'FatalityDayGood', 'FatalityNightGood']
        # for field in nan_fields:
        #     subcounty_results[field] = np.where(np.isfinite(subcounty_results[field]), subcounty_results[field], 0)
        #     county_results[field] = np.where(np.isfinite(county_results[field]), county_results[field], 0)

        a = subcounty_results['InjuryDayGood']
        
        

        # totals
        econloss_total = sum(county_results['EconLoss'])
        nonfatals_total_day = sum([int(x + 0.5) for x in subcounty_results['InjuryDayGood']])
        nonfatals_total_night = sum([int(x + 0.5) for x in subcounty_results['InjuryNightGood']])
        fatals_total_day = sum([int(x + 0.5) for x in subcounty_results['FatalityDayGood']])
        fatals_total_night = sum([int(x + 0.5) for x in subcounty_results['FatalityNightGood']])
        injuries_total_day = nonfatals_total_day + fatals_total_day
        injuries_total_night = nonfatals_total_night + nonfatals_total_night

        # determines sorting by night or day by largest sum
        injuries_day_check = injuries_total_day > injuries_total_night
        injuries_sortby = 'InjuryDayGood' if injuries_day_check else 'InjuryNightGood'

        if len(county_results) > 1:
            # county_results['EconLoss'] = county_results['EconLoss'].astype(int)
            econloss = county_results.sort_values(by='EconLoss', ascending=False)[0:7]
            injuries = county_results.sort_values(by=injuries_sortby, ascending=False)[0:7]
            injuries['nonfatals'] = injuries['InjuryDayGood'].apply(f) + '/' + injuries['InjuryNightGood'].apply(f)
            injuries['fatals'] = injuries['FatalityDayGood'].apply(f) + '/' + injuries['FatalityNightGood'].apply(f)
        
        if len(county_results) == 1:
            econloss = subcounty_results.sort_values(by='EconLoss', ascending=False)[0:7]
            # logically sort values if fields are insignificant
            # if shelter_needs['Shelter'].iloc[0] == 0:
            #     shelter_needs = econloss.copy()
            injuries = subcounty_results.sort_values(by=injuries_sortby, ascending=False)[0:7]
            injuries['nonfatals'] = injuries['InjuryDayGood'].apply(f) + '/' + injuries['InjuryNightGood'].apply(f)
            injuries['fatals'] = injuries['FatalityDayGood'].apply(f) + '/' + injuries['FatalityNightGood'].apply(f)

            # remap field names
            econloss['State'] = [a +', ' + b for a, b in zip(econloss['CountyName'], econloss['State'])]
            econloss['CountyName'] = econloss.index
            injuries['State'] = [a +', ' + b for a, b in zip(injuries['CountyName'], injuries['State'])]
            injuries['CountyName'] = injuries.index



        # ensures all seven fields are populated
        if len(econloss) < 7:
            new_rows = 7 - len(econloss)
            for row in range(new_rows):
                new_row = pd.Series(list(map(lambda x: ' ', econloss.columns)), index=econloss.columns)
                econloss = econloss.append([new_row])
                # nonfatals = nonfatals.append([new_row])
                # shelter_needs = shelter_needs.append([new_row])
        
        t0 = time()
        print('finding normal breaks in data')
        breaks = nb(subcounty_results['EconLoss'], nb_class=5)
        print(time() - t0)
        if len(breaks) > 1:
            legend_item1 = breaks[0]
            legend_item2 = breaks[1]
            legend_item3 = breaks[2]
            legend_item4 = breaks[3]
            legend_item5 = breaks[4]
        else: 
            legend_item1 = breaks[0]
            legend_item2 = breaks[0]
            legend_item3 = breaks[0]
            legend_item4 = breaks[0]
            legend_item5 = breaks[0]
        # legend_item1 = subcounty_results.EconLoss.quantile(.2)
        # legend_item2 = subcounty_results.EconLoss.quantile(.4)
        # legend_item3 = subcounty_results.EconLoss.quantile(.6)
        # legend_item4 = subcounty_results.EconLoss.quantile(.8)
        # legend_item5 = subcounty_results.EconLoss.quantile(1)

        data_dict = {
            'title': title,
            'date': 'Hazus run ' + date + meta,
            # 'g_res': f(sum(RES['NoDamage'])),
            # 'g_com': f(sum(COM['NoDamage'])),
            # 'g_ind': f(sum(IND['NoDamage'])),
            # 'g_agr': f(sum(AGR['NoDamage'])),
            # 'g_edu': f(sum(EDU['NoDamage'])),
            # 'g_gov': f(sum(GOV['NoDamage'])),
            # 'g_rel': f(sum(REL['NoDamage'])),
            # 'y_res': f(sum(RES['Moderate'])),
            # 'y_com': f(sum(COM['Moderate'])),
            # 'y_ind': f(sum(IND['Moderate'])),
            # 'y_agr': f(sum(AGR['Moderate'])),
            # 'y_edu': f(sum(EDU['Moderate'])),
            # 'y_gov': f(sum(GOV['Moderate'])),
            # 'y_rel': f(sum(REL['Moderate'])),
            # 'r_res': f(sum(RES['Complete'])),
            # 'r_com': f(sum(COM['Complete'])),
            # 'r_ind': f(sum(IND['Complete'])),
            # 'r_agr': f(sum(AGR['Complete'])),
            # 'r_edu': f(sum(EDU['Complete'])),
            # 'r_gov': f(sum(GOV['Complete'])),
            # 'r_rel': f(sum(REL['Complete'])),
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
               'nonfatal_pop_1': f(injuries['nonfatals'].iloc[0]),
               'nonfatal_pop_2': f(injuries['nonfatals'].iloc[1]),
               'nonfatal_pop_3': f(injuries['nonfatals'].iloc[2]),
               'nonfatal_pop_4': f(injuries['nonfatals'].iloc[3]),
               'nonfatal_pop_5': f(injuries['nonfatals'].iloc[4]),
               'nonfatal_pop_6': f(injuries['nonfatals'].iloc[5]),
               'nonfatal_pop_7': f(injuries['nonfatals'].iloc[6]),
               'nonfatal_injuries_1': f(injuries['fatals'].iloc[0]),
               'nonfatal_injuries_2': f(injuries['fatals'].iloc[1]),
               'nonfatal_injuries_3': f(injuries['fatals'].iloc[2]),
               'nonfatal_injuries_4': f(injuries['fatals'].iloc[3]),
               'nonfatal_injuries_5': f(injuries['fatals'].iloc[4]),
               'nonfatal_injuries_6': f(injuries['fatals'].iloc[5]),
               'nonfatal_injuries_7': f(injuries['fatals'].iloc[6]),
            #    'shelter_county_1': str(shelter_needs['CountyName'].iloc[0]),
            #    'shelter_county_2': str(shelter_needs['CountyName'].iloc[1]),
            #    'shelter_county_3': str(shelter_needs['CountyName'].iloc[2]),
            #    'shelter_county_4': str(shelter_needs['CountyName'].iloc[3]),
            #    'shelter_county_5': str(shelter_needs['CountyName'].iloc[4]),
            #    'shelter_county_6': str(shelter_needs['CountyName'].iloc[5]),
            #    'shelter_county_7': str(shelter_needs['CountyName'].iloc[6]),
            #    'shelter_state_1': str(shelter_needs['State'].iloc[0]),
            #    'shelter_state_2': str(shelter_needs['State'].iloc[1]),
            #    'shelter_state_3': str(shelter_needs['State'].iloc[2]),
            #    'shelter_state_4': str(shelter_needs['State'].iloc[3]),
            #    'shelter_state_5': str(shelter_needs['State'].iloc[4]),
            #    'shelter_state_6': str(shelter_needs['State'].iloc[5]),
            #    'shelter_state_7': str(shelter_needs['State'].iloc[6]),
            #    'shelter_pop_1': f(shelter_needs['Population'].iloc[0]), 
            #    'shelter_pop_2': f(shelter_needs['Population'].iloc[1]),
            #    'shelter_pop_3': f(shelter_needs['Population'].iloc[2]),
            #    'shelter_pop_4': f(shelter_needs['Population'].iloc[3]),
            #    'shelter_pop_5': f(shelter_needs['Population'].iloc[4]),
            #    'shelter_pop_6': f(shelter_needs['Population'].iloc[5]),
            #    'shelter_pop_7': f(shelter_needs['Population'].iloc[6]),
            #    'shelter_house_1': f(shelter_needs['DisplHouse'].iloc[0]),
            #    'shelter_house_2': f(shelter_needs['DisplHouse'].iloc[1]),
            #    'shelter_house_3': f(shelter_needs['DisplHouse'].iloc[2]),
            #    'shelter_house_4': f(shelter_needs['DisplHouse'].iloc[3]),
            #    'shelter_house_5': f(shelter_needs['DisplHouse'].iloc[4]),
            #    'shelter_house_6': f(shelter_needs['DisplHouse'].iloc[5]),
            #    'shelter_house_7': f(shelter_needs['DisplHouse'].iloc[6]),
            #    'shelter_need_1': f(shelter_needs['Shelter'].iloc[0]),
            #    'shelter_need_2': f(shelter_needs['Shelter'].iloc[1]),
            #    'shelter_need_3': f(shelter_needs['Shelter'].iloc[2]),
            #    'shelter_need_4': f(shelter_needs['Shelter'].iloc[3]),
            #    'shelter_need_5': f(shelter_needs['Shelter'].iloc[4]),
            #    'shelter_need_6': f(shelter_needs['Shelter'].iloc[5]),
            #    'shelter_need_7': f(shelter_needs['Shelter'].iloc[6]),
                # 'debris_type_1': 'Brick, Wood, & Others',
                # 'debris_type_2': 'Concrete & Steel',
            #    'debris_tons_1': f(debris_bw_total),
            #    'debris_tons_2': f(debris_cd_total),
            'total_econloss': '$' + f(econloss_total),
               'total_injuries': f(injuries_total_day) + '/' + f(injuries_total_night),
            #    'total_shelter': f(displaced_households_total),
            #    'total_debris': f(debris_bw_total + debris_cd_total),
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
        merge_maps(hazus_results_dict, gdf, data_pdf_path, map_pdf_path, folder_path, study_region, breaks)
        output_pdf_path = out_path + study_region+'_Report.pdf'
        write_pdf_with_appearances(data_pdf_path, map_pdf_path, output_pdf_path)
        
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