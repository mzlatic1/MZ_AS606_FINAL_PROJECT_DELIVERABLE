import mz_as606_final_project_script_pull_weather_info
import mz_as606_final_project_script_city_name
import arcpy
import sys
import os

########################################################################################################################
### THIS SCRIPT USES THE MZ_AS606_FINAL_PROJECT_SCRIPT_PULL_WEATHER_INFO AND THE MZ_AS607_FINAL_PROJECT_SCRIPT_CITY_NAME
### PYTHON SCRIPTS TO GENERATE FOUR WEATHER FEATURE CLASSES THAT ILLUSTRATE TEMPERATURE, PRECIPITATION, WIND SPEED, AND
### THE WEATHER FOR TODAY IN THE LOCAL AREA OF THE SEARCHED WEATHER LOCATION.THE MZ_AS606_FINAL_PROJECT_SCRIPT_CITY_NAME
### SCRIPT IS USED FIRST TO TAKE THE INPUT FEATURE CLASS AND REVERSE GEOCODE THE LOCATIONS TO OUTPUT A DICTIONARY WITH #
### CITY NAME AND COORDINATES, FOR EACH FEATURE, IN WHICH THE REVERSE GEOCODE FOUND A CITY LOCATION. ###################
### THE MZ_AS606_FINAL_PROJECT_SCRIPT_PULL_WEATHER_INFO SCRIPT IS THEN USED TO CONDUCT THE WEATHER SEARCH TO SEE IF THE
### GENERATED CITY NAME MATCHES A WEATHER RESULT. IF A CITY NAME RETURNS A POSITIVE RESULT, A FEATURE TABLE IS CREATED #
### FOR THAT PARTICULAR CITY. THIS PARTICULAR SCRIPT, THEN TAKES THE OUTPUT OF THE TWO MENTIONED SCRIPTS AND CREATES A #
### MASTER DICTIONARY TO STORE ALL OF THE CITY NAMES WITH POSITIVE WEATHER RESULTS TO ULTIMATELY MERGE ALL FEATURE #####
### TABLES BASED ON CATEGORY (IE ALL TEMPERATURE TABLES ARE MERGED, ETC.) THEN LATER EXPORTS EACH TABLE AS A FEATURE ###
### CLASS. THIS SCRIPT OUTPUTS A LIST CONTAINING THE FOUR FEATURE CLASSES THAT CAN BE USED FOR SUBSEQUENT SCRIPTS ######
########################################################################################################################


def create_weather_fcs(input_fc, temp_units, wind_speed_units, output_gdb):
    arcpy.env.workspace = 'in_memory'

    city_info = mz_as606_final_project_script_city_name.get_city_names(input_fc) # Searches city info for each feature found within feature class

    fc_blueprint = {'temp_tables': [], 'precip_tables': [], 'wind_tables': [], 'todays_tables': []}
    # The dictionary above will host all of the resulting features that had a positive city name result and a positive weather result
    null_weather_result = [] # All city names with a null weather result are stored in a list to output as a warning message
    arcpy.AddMessage('Generating Weather Feature Classes...')
    arcpy.SetProgressor('default', 'Searching for weather info for each city')
    total_rows_to_process = int(arcpy.GetCount_management(input_fc)[0]) - (int(arcpy.GetCount_management(input_fc)[0]) - len(city_info))
    num = 1
    for city_name in city_info:
        arcpy.SetProgressorLabel(f'Processing {num} out of {total_rows_to_process}: "{city_name.replace("+", ", ")}"')
        weather_info = mz_as606_final_project_script_pull_weather_info.weather_info(city_name) # Searches the city name and outputs an object containing the results
        if len(weather_info.f_or_c) == 0 or weather_info.city.count('+') < 3: # Checks if weather_info object contains positive weather results
            null_weather_result.append(city_info[city_name]['orig_oid'])
            num += 1
            continue

        # If the weather_info object returns a positive weather result, it is then used to develop the master dictionary by storing the results of the exported feature table

        fc_blueprint[city_name] = {} # Create a dictionary, within the master dictionary, containing the results for the respected city
        fc_blueprint[city_name]['coord_info'] = city_info[city_name]['location']
        validate_city_name = arcpy.ValidateTableName(city_name, 'in_memory')
        fc_blueprint[city_name]['tables'] = []

        temp_info = weather_info.find_temp(temp_units, f'Temperature_Table_{validate_city_name}') # stores temperature information as feature table
        fc_blueprint[city_name]['tables'].append(temp_info) # stores results in city dictionary found within master dictionary
        fc_blueprint['temp_tables'].append(temp_info) # stores results in master dictionary

        precip_info = weather_info.find_rain(f'Precipitation_Table_{validate_city_name}') # stores precipitation information as feature table
        fc_blueprint[city_name]['tables'].append(precip_info) # stores results in city dictionary found within master dictionary
        fc_blueprint['precip_tables'].append(precip_info) # stores results in master dictionary

        wind_info = weather_info.find_wind(wind_speed_units, f'Wind_Speed_Table_{validate_city_name}') # stores wind information as feature table
        fc_blueprint[city_name]['tables'].append(wind_info) # stores results in city dictionary found within master dictionary
        fc_blueprint['wind_tables'].append(wind_info) # stores results in master dictionary

        todays_info = weather_info.find_todays_info(temp_units, f'Todays_Weather_Info_{validate_city_name}') # stores todays weather information as feature table
        fc_blueprint[city_name]['tables'].append(todays_info) # stores results in city dictionary found within master dictionary
        fc_blueprint['todays_tables'].append(todays_info) # stores results in master dictionary

        for table in fc_blueprint[city_name]['tables']: # Adds in object ID from input feature class that matched this cities weather results
            arcpy.CalculateField_management(table, 'INPUT_FC_OID', f"{city_info[city_name]['orig_oid']}", 'PYTHON3', '', 'LONG')
        num += 1

    if len(fc_blueprint) == 4: # If all features found within input feature class had either a null city result or weather result, the script will fail and exit
        arcpy.AddError('None of the input features resulted in a weather result, please use a different feature class and try again.')
        sys.exit(1)

    if len(null_weather_result) > 0: # Identifies to the user which features, found within the input feature class, had a null weather result
        oids = ', '.join(str(oid) for oid in null_weather_result)
        arcpy.AddWarning(f'The following OIDs from input FC had a null weather search result and will be excluded from final result: {oids}')

    arcpy.ResetProgressor()
    arcpy.AddMessage('Generating Coordinates...')
    arcpy.SetProgressor('step', 'Processing...', 0, len(fc_blueprint), 1)
    for blueprint_info in fc_blueprint: # Generates coordinates for each feature table
        if '_tables' not in blueprint_info:
            for tables in fc_blueprint[blueprint_info]['tables']: # first looks at a given city
                long_lat_fields = ['Longitude', 'Latitude'] # adds in the long and lat fields (lines 84 - 85)
                for long_lat in long_lat_fields:
                    arcpy.AddField_management(tables, long_lat, 'DOUBLE')
                coordinates = fc_blueprint[blueprint_info]['coord_info'] # then looks at the coordinates for the given city
                with arcpy.da.UpdateCursor(tables, long_lat_fields) as UC: # adds then in via update cursor
                    for row in UC:
                        row[0] = coordinates[0]
                        row[1] = coordinates[1]
                        UC.updateRow(row)
        arcpy.SetProgressorPosition()

    arcpy.ResetProgressor()
    keys = ['temp_tables', 'precip_tables', 'wind_tables', 'todays_tables']
    out_fc_names = ['Temperature_Table_From_', 'Precipitation_Table_From_',
                    'Wind_Table_From_', 'Todays_Weather_Info_Table_From_']
    wgs84 = arcpy.SpatialReference(4326)
    index = 0
    weather_fcs = []
    arcpy.AddMessage('Exporting Feature Classes...')
    while index != len(keys):
        key = keys[index]

        merged_table = arcpy.Merge_management(fc_blueprint[key], key) # goes into master dictionary to select all tables that is currently being iterated for
        input_fc_name = arcpy.ValidateTableName(os.path.split(input_fc)[1], 'in_memory')
        if len(input_fc_name) >= 129: # checks to see if proposed output feature class name is too long
            out_fc = os.path.join(output_gdb, f'{out_fc_names[index]}_{input_fc_name[:129]}')
        else:
            out_fc = os.path.join(output_gdb, f'{out_fc_names[index]}_{input_fc_name}')
        fc_export = arcpy.XYTableToPoint_management(merged_table, out_fc, 'Longitude', 'Latitude', '', wgs84) # generates feature class from long/lat fields
        weather_fcs.append(fc_export[0])
        index += 1
    arcpy.SetProgressorLabel('Processing...')
    arcpy.ResetProgressor()

    return weather_fcs
