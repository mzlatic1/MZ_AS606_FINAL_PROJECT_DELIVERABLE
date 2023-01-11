import os
import arcpy
from arcgis.gis import GIS
from arcgis.geocoding import Geocoder
from arcgis.geocoding import reverse_geocode

########################################################################################################################
### THIS SCRIPT UTILIZES THE REVERSE_GEOCODE FUNCTION TO FIND THE CITY, REGION (IE PROVINCE/STATE), AND COUNTRY OF A ###
### GIVEN FEATURE FOUND WITHIN A FEATURE CLASS. SINCE WE CAN ASSUME THIS SCRIPT WILL ONLY RUN ON ARCGIS PRO, IT WILL ###
### UTILIZE THE LOGIN CREDENTIALS THAT ARE ALREADY INITIALIZED IN PRO. IT IS CURRENTLY UNKNOWN IF THIS SCRIPT CONSUMES #
### CREDITS, ACCORDING TO ESRI'S WEBSITE, IT SHOULD CONSUME 40 CREDITS FOR EVERY 1000 ROWS; HOWEVER, WHEN RUNNING THE ##
### SCRIPT, NO CREDITS ARE CONSUMED. NONETHELESS, THIS SCRIPT ITERATES THROUGH EACH FEATURE OF A GIVEN FEATURE CLASS ###
### AND RETRIVES ESSENTIAL CITY INFORMATION IN THE FORM OF A DICTIONARY, AS WELL AS, STORES THE RESPECTED OBJECTID FOR #
### EACH FEATURE BEING SUCCESSFULLY RAN THROUGH THE REVERSE GEOCODE FUNCTION ###########################################
########################################################################################################################


def get_city_names(input_fc):
    default_path = os.path.split(os.path.dirname(__file__))[0]
    default_gdb = os.path.join(default_path, 'pdf_report_aprx', 'Default.gdb') # Locates the default GDB in the event of line 27 holding true
    gis = GIS('Pro') # Logs into AGOL
    credit_start = gis.users.me.availableCredits # Identifies how many credits are present before the iteration begins on line 42
    geocoder = Geocoder('https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer', gis=gis) # connects to the world geocode server to allow the reverse_geocode function to run

    wgs84 = arcpy.SpatialReference(4326) # WGS84 wkt spatial reference object

    if arcpy.da.Describe(input_fc)['spatialReference'].name != wgs84.name: # checks if the input feature class is projected in WGS84
        oid_st_num = [row[0] for row in arcpy.da.SearchCursor(input_fc, ['OID@'])][0] # pulls the first objectid in input feature class
        if oid_st_num == 0: # checks to see if objectid starts at 0, if it does, it will need to be subtracted by one as project tool is outputting to GDB (objectid will start at 1)
            fix_oid = 1
        else:
            fix_oid = 0
        prj_fc = arcpy.Project_management(input_fc, os.path.join(default_gdb, 'INPUT_FC_PROJECTED'), wgs84) # the Project geoprocessing tool cant output in memory
    else:
        prj_fc = input_fc
        fix_oid = 0

    arcpy.SetProgressor('step', 'Gathering City Information From Input FC...', 0, int(arcpy.GetCount_management(input_fc)[0]), 1)

    city_names = {'invalid_coord': []} # master dictionary to store all successful and null city identification results
    dup_city_name = 0 # If two or more features have the same city result, only the first feature's object id will be used
    with arcpy.da.SearchCursor(prj_fc, ['OID@', 'SHAPE@X', 'SHAPE@Y']) as SC:
        for row in SC:
            coordinates = {'x': row[1], 'y': row[2]} # stores coordinates in a dictionary as this is preferred for the reverse_geocode function
            try: # tests feature to see if the search result is successful or null
                city_info = reverse_geocode(location=coordinates, geocoder=geocoder)
                address = city_info['address'] # pulls the city name, region, and country information
                1 / len(address['City']) # tests if city result present
                1 / len(address['Region']) # tests if region result present
                1 / len(address['CntryName']) # tests if country result present
            except:
                city_names['invalid_coord'].append(row[0])
                continue
            location = city_info['location'] # pulls the coordinate information of where the geocoder identified the positive result
            prep_address = f'{address["City"]}+{address["Region"]}+{address["CntryName"]}' # preps the address information for the mz_as606_final_project_script_pull_weather_info
            if prep_address not in city_names: # checks to see if the city name key already exists
                city_names[prep_address] = {} # creates a new dictionary storing the respected city information
                city_names[prep_address]['location'] = [location['x'], location['y']]
                city_names[prep_address]['orig_oid'] = int(row[0]) - fix_oid # accommodates if input feature had its respected objectid start at 0
            else:
                dup_city_name += 1
            arcpy.SetProgressorPosition()

    credit_end = gis.users.me.availableCredits # retrieves how much credits the user has after the iteration is complete
    arcpy.ResetProgressor()
    arcpy.AddMessage(f'There was {credit_end - credit_start} credits consumed.') # lines 67 - 72 prompts the user of all features that are excluded from the final results
    if len(city_names['invalid_coord']) > 0:
        oid_str = ', '.join(str(oid) for oid in city_names['invalid_coord'])
        arcpy.AddWarning(f'Null location search for the following OIDs from Input FC and will be excluded from weather search: {oid_str}')
    del city_names['invalid_coord']
    if dup_city_name > 0:
        arcpy.AddWarning(f'{dup_city_name} features were excluded due to matching city address with other features.')
    if arcpy.da.Describe(prj_fc)['catalogPath'] != arcpy.da.Describe(input_fc)['catalogPath']:
        arcpy.Delete_management(prj_fc) # deletes the projected feature class as its now no longer needed

    return city_names # returns the master dictionary containing the successful city location results
