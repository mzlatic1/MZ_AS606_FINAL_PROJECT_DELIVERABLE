from bs4 import BeautifulSoup
import pandas as pd
import requests
import datetime
import arcpy
import sys
import os

########################################################################################################################
### THIS SCRIPT IS USED TO SEARCH FOR THE WEATHER OF A GIVEN CITY, THE ONLY REQUIREMENT NEED TO CONDUCT THE SEARCH IS ##
### THE CITY NAME ITSELF, REGION (STATE/PROVINCE), AND COUNTRY. THERE ARE THEN FOUR MODULES FOUND WITHIN THE CLASS THAT
### TAKES THE RESULTS OF THE WEATHER INFORMATION AND GENERATES FEATURE TABLES BASED ON THE PRESENCE OF HTML ELEMENTS ###
### FOUND WITHIN THE WEATHER RESULTS. THE WEATHER_INFO CLASS PARSES THROUGH THE HTML OF A GOOGLE SEARCH AND STORES THE #
### INFORMATION AS TEXT; PRESERVING THE HTML TAGS AND ELEMENTS. THIS MAKES THE SCRIPT FREE TO USE WITHOUT LIMITATION; ##
### MANY WEATHER APIS HAVE LIMITATIONS AS TO HOW FREQUENT YOURE ABLE TO SEARCH FOR WEATHER AND MANY FREE WEATHER APIS ##
### ONLY PROVIDE, AT MOST, A FIVE DAY FORECAST. THE MZ_AS606_FINAL_PROJECT_SCRIPT_WEATHER_FCS SCRIPT USES THE ##########
### WEATHER INFO CLASS TO CHECK TO SEE IF THE SEARCHED CITY HAD NULL WEATHER RESULT. IF THE WEATHER RESULT IS POSITIVE,
### THERE ARE FOUR MODULES, IN THIS SCRIPT, THAT CREATE THE RESPECTED WEATHER FEATURE TABLES AND A EXPORT RESULTS MODULE
### THAT CARRIES OUT THE COMPUTATION NECESSARY TO EXPORT THE WEATHER RESULTS AS A FEATURE TABLE ########################
########################################################################################################################

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}


class weather_info(object):
    def __init__(self, city):
        self.city = city.replace(" ", "+") + '+weather' # preps city name for search
        self.res = requests.get(
            f'https://www.google.com/search?q={self.city}&oq={self.city}&aqs=chrome.0.35i39l2j0l4j46j69i60.6128j1j7&sourceid=chrome&ie=UTF-8', # web url that hosts weather information
            headers=headers)
        self.soup = BeautifulSoup(self.res.text, 'html.parser') # searches for city weather
        self.todays_date = datetime.datetime.now()
        self.xl_export_folder = os.path.join(os.path.split(os.path.dirname(__file__))[0], 'weather_info_xl_processing')

        self.f = 'Fahrenheit'
        self.c = 'Celsius'
        ### Determines if F or C is selected first or if there are no results present (ie len(self.f_or_c) == 0) ###
        wob_t = self.soup.select('.wob_t')
        f_or_c = ''
        for wob in wob_t:
            if 'F' in wob.get_text():
                f_or_c += self.f
                break
            elif 'C' in wob.get_text():
                f_or_c += self.c
                break
            else:
                continue
        self.f_or_c = f_or_c

    def export_results(self, results: list, columns: dict, method_type, out_table): # internal method to export results of weather info
        df = pd.DataFrame(results) # weather results are in the form of a list
        df.rename(columns=columns, inplace=True)
        df.insert(0, 'City Name', self.city[:-8].replace('+', ' '), True)
        prep_city_name = ''.join(str(c) for c in list(self.city) if c.isalnum()) # removes special characters
        xl_export = os.path.join(self.xl_export_folder, '{}.xlsx'.format(f"Processing_{method_type}_Info_for_{prep_city_name}"[:45]))
        if len(xl_export) > 217:
            arcpy.AddError('File path in which the script is running is too long, please paste the script package in another folder and try again.')
            sys.exit(1)
        df.index.names = ['Sequence'] # renaming index column
        df.to_excel(xl_export, index=True)
        final_result = arcpy.ExcelToTable_conversion(xl_export, out_table)
        if os.path.exists(xl_export):
            os.remove(xl_export) # removes temporary excel output as its now no longer needed
        return final_result # returns path of feature table catalog path

    def find_temp(self, temp_choice, out_table):
        soup = self.soup # weather results
        f_or_c = self.f_or_c

        ### Scrapes Temperature Info based on User Selection and Default Selection ###
        weather_seq = soup.select('[data-wob-di]') # selects parent element containing temperature information
        temp_info = {}
        for weather in weather_seq:
            text_parse = [txt for txt in weather.stripped_strings] # pulls text elements from parent div element
            weekday = text_parse[0]
            temps = [int(temp) for temp in text_parse[1:] if temp.replace('-', '').isnumeric()] # searches for temperature in the form of integers
            if f_or_c == self.f: # checks if default temperature unit present matches the temperature unit select by user, if not, switches accordingly
                if temp_choice == self.f:
                    temp_info[weekday] = temps[::2] # creates a dictionary that adds weekday and temperature information
                    unit = self.f # unit variable used instead of temp_choice variable due to QA/QC
                else:
                    temp_info[weekday] = temps[1::2]
                    unit = self.c
            else:
                if temp_choice == self.c:
                    temp_info[weekday] = temps[::2]
                    unit = self.c
                else:
                    temp_info[weekday] = temps[1::2]
                    unit = self.f

        fix_temp_info = [] # temp results are currently stored as a dictionary, to export as a Pandas dataframe, its converted into a list
        for result in temp_info.keys():
            fix_temp_info.append([result])
            for w in temp_info[result]: # searches by weekday and adds the temperatures at the end of each list item
                fix_temp_info[-1].append(w)
        temp_results = fix_temp_info[1:] + [fix_temp_info[0]] # Last day of the week appears at the end of the list, this reorganizes it
        for t in temp_results: # adds in the temp unit
            t.append(unit)
        columns = {0: 'Weekday', 1: 'High', 2: 'Low', 3: 'Temp Unit'} # column dictionary needed to change dataframe column names

        return self.export_results(temp_results, columns, 'Temp', out_table) # runs internal module to output the list into a feature table

    def find_rain(self, out_table):
        soup = self.soup # weather results
        todays_date = self.todays_date

        ### Scrapping Precipitation info from Parent Div Element ###
        precip_info = []
        parent_element = soup.select('#wob_pg')[0] # searches for parent element containing precipitation information (only element with this id)
        for precip in parent_element.select('.wob_hw'): # further narrows down the search to pull each record one-at-a-time (other parent elements also contain .wob_hw class elements as well)
            child = precip.select('[aria-label]')[0] # selects precipitation string
            attribute_info = child.get_attribute_list('aria-label')[0].split(' ') # splits string to remove redundant string components
            precip_info.append([int(attribute_info[0].replace('%', '')), attribute_info[1], # appends the integer, weekday, time as a string, and the timestamp of when the prediction were to happen
                                ' '.join(a for a in attribute_info[2:]), todays_date])
            todays_date = todays_date + datetime.timedelta(hours=1) # increment the time for each iteration to match the prediction time interval
        columns = {0: 'Percent Chance of Rain', 1: 'Weekday', 2: 'String Time', 3: 'Datetime'} # column dictionary needed to change dataframe column names

        return self.export_results(precip_info, columns, 'Precip', out_table) # runs internal module to output the list in to a feature table

    def find_wind(self, speed_unit, out_table):
        soup = self.soup # weather results
        todays_date = self.todays_date

        parent_wind = soup.select('#wob_wg')[0] # selects parent element containing the wind speed results (only element with this id)
        wind_children = parent_wind.select('.wob_hw') # further narrows down the search (other parent elements also contain .wob_hw class elements as well)
        wind_results = []
        for wind_info in wind_children:
            wind = [txt for txt in wind_info.stripped_strings] # retrieves text elements
            for w in wind:
                if speed_unit in w: # iterates through and appends the wind integer, wind speed unit, and a timestamp on when the prediction were to occur
                    wind_results.append([int(w.split(' ')[0]), w.split(' ')[1], todays_date])
            todays_date = todays_date + datetime.timedelta(hours=1) # ensures date increments matches the increments indicated on the parent element
        columns = {0: 'Numeric Value', 1: 'Speed Measurement', 2: 'Datetime'} # column dictionary needed to change dataframe column names

        return self.export_results(wind_results, columns, 'Wind', out_table) # runs internal module to output the list in to a feature table

    def find_todays_info(self, temp_choice, out_table):
        soup = self.soup # weather results
        f_or_c = self.f_or_c # pulls temperature selection of weather results, not what the user selected

        name = soup.select('#wob_loc')[0].get_text() # retrieves the text from city local time
        weekday_time = soup.select('#wob_dts')[0].get_text() # retrieves the weekday and time of upcoming hour
        sky_info = soup.select('#wob_dc')[0].get_text() # retrieves the current sky information

        if f_or_c == self.f: # determines is user selection matches the default temperature unit and otherwise switches if they're different
            if temp_choice == self.f: # identifies what the user selected for temperature units
                temp = soup.select('#wob_tm')[0].get_text() + ' F' # pulls text info if default temp matches user temp
            else:
                temp = soup.select('#wob_ttm')[0].get_text() + ' C' # pulls text info if default temp doesnt match user temp
        else:
            if temp_choice == self.c:
                temp = soup.select('#wob_tm')[0].get_text() + ' C'
            else:
                temp = soup.select('#wob_ttm')[0].get_text() + ' F'

        result_from_today = [name, weekday_time, sky_info, temp]                # Due to the nature of how this method
        column_names = ['City Name', 'Local Time in Area', 'Sky Info', 'Temp']  # pulled the needed text information,
        todays_info = pd.DataFrame()                                            # the export_result() internal method
        index = 0                                                               # wasnt viable and this resulted in
        while index != len(result_from_today):                                  # duplicating some code to accommodate
            todays_info[column_names[index]] = [result_from_today[index]]       # these differences. Lines 163 - 170
            index += 1
        prep_city_name = ''.join(str(c) for c in list(self.city) if c.isalnum()) # removes special characters
        xl_export = os.path.join(self.xl_export_folder, '{}.xlsx'.format(f"Processing_Todays_Info_for_{prep_city_name}"[:45]))
        if len(xl_export) > 217:
            arcpy.AddError('File path in which the script is running is too long, please paste the script package in another folder and try again.')
            sys.exit(1)
        todays_info.to_excel(xl_export, index=False)

        final_result = arcpy.ExcelToTable_conversion(xl_export, out_table)
        if os.path.exists(xl_export):
            os.remove(xl_export) # removes temporary excel output as its now no longer needed

        return final_result # returns the catalog path of the todays_weather_info feature table
