import arcpy
import os

########################################################################################################################
### THE MAIN PURPOSE OF THIS SCRIPT IS TO CREATE A COPY OF THE DEFAULT APRX FILE, THEN UPDATES THE CONNECTION OF THE ###
### FEATURE CLASSES PRESENT IN THE COPIED APRX TO ULTIMATELY EXPORT A PDF REPORT OF ALL LOCATIONS, VIA MAP SERIES, FROM
### THE RECENTLY EXPORTED WEATHER FEATURE CLASSES. THE MZ_AS607_FINAL_PROJECT_SCRIPT_WEATHER_FCS PYTHON SCRIPT RETURNS #
### A LIST CONTAINING ALL OF THE WEATHER FEATURE CLASSES THAT WERE CREATED FROM THE INPUT FEATURE CLASS IN WHICH THIS ##
### SCRIPT USES TO UPDATE CONNECTIONS FOUND WITHIN THE COPIED DEFAULT APRX AND EXPORTS THE PDF REPORT ##################
########################################################################################################################


def run_layout(default_aprx, weather_fcs: list, pdf_path):
    arcpy.SetProgressor('default', 'Loading...')
    arcpy.AddMessage('Prepping PDF Export...')
    folder_path = os.path.split(default_aprx)[0]
    arcpy.mp.ArcGISProject(default_aprx).saveACopy(os.path.join(folder_path, 'EXPORTING_PDF_REPORT.aprx'))
    current_aprx = arcpy.mp.ArcGISProject(os.path.join(folder_path, 'EXPORTING_PDF_REPORT.aprx'))

    default_map = current_aprx.listMaps('default_map')[0]
    layers = default_map.listLayers()
    index = 0
    temp_choice = []
    wind_choice = []
    for lyr in layers:
        if not lyr.isBasemapLayer:
            desc = arcpy.da.Describe(sorted(weather_fcs)[index])

            new_connection_info = { # Retrieving connection info from recently created weather feature classes
                'dataset': desc['name'],
                'workspace_factory': 'File Geodatabase',
                'connection_info': {
                    'database': desc['path']
                }
            }
            current_connection_info = lyr.connectionProperties
            default_map.updateConnectionProperties(current_connection_info, new_connection_info)
            if 'temp' in desc['name'].lower(): # Lines 32 - 36 retrieves the units found within the temperature feature class
                with arcpy.da.SearchCursor(desc['catalogPath'], 'Temp_Unit') as SC:
                    for row in SC:
                        temp_choice.append(row[0])
                        break
            elif 'wind' in desc['name'].lower(): # Lines 37 - 41 retrieves the units found within the wind speed feature class
                with arcpy.da.SearchCursor(desc['catalogPath'], 'Speed_Measurement') as SC:
                    for row in SC:
                        wind_choice.append(row[0])
                        break
            else:
                pass
        index += 1

    arcpy.AddMessage('Exporting PDF Report...')
    layout = current_aprx.listLayouts('default_layout')[0]
    for temp_and_wind_text in layout.listElements('TEXT_ELEMENT'): # Identifies the text element containing the units for the temperature and wind speed graphs
        if 'Temp' in temp_and_wind_text.name:
            temp_and_wind_text.text = f'({temp_choice[0][0]})' # Changes current temp value with value found in temperature feature class
        elif 'Wind' in temp_and_wind_text.name:
            temp_and_wind_text.text = f'({wind_choice[0]})' # Changes current wind speed value with value found in wind speed feature class
        else:
            continue
    current_aprx.save()
    arcpy.SetProgressor('default', 'Exporting...')
    map_series = layout.mapSeries # Identified map series element to be exported as a PDF
    map_series.exportToPDF(pdf_path)
    del current_aprx

    return os.path.join(folder_path, 'EXPORTING_PDF_REPORT.aprx') # Returns the path of the copied default APRX file
