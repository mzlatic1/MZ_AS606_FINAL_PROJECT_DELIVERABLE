import importlib.util
import subprocess
import arcpy
import sys
import os


class beautifulsoup_install(ModuleNotFoundError):
    pass

class final_project_scripts_not_present(ModuleNotFoundError):
    pass

class default_resources_not_present(OSError):
    pass

class existing_weather_fcs(ValueError):
    pass


check_custom_scripts = ['mz_as606_final_project_script_generate_report', 'mz_as606_final_project_script_weather_fcs',
                        'mz_as606_final_project_script_pull_weather_info', 'mz_as606_final_project_script_city_name']
while True:
    try:
        arcpy.AddMessage('Initializing...')
        if (spec := importlib.util.find_spec('bs4')) is None: # checks if bs4 python package is installed
            raise beautifulsoup_install

        current_dir = os.path.dirname(__file__)
        scripts_dir = os.path.join(current_dir, 'scripts')
        if not os.path.exists(scripts_dir): # checks if default script folder path is present
            raise default_resources_not_present
        sys.path.append(scripts_dir)

        for script in check_custom_scripts: # checks if custom scripts are present in the scripts folder
            if (spec := importlib.util.find_spec(script)) is None:
                raise final_project_scripts_not_present
        import mz_as606_final_project_script_weather_fcs
        import mz_as606_final_project_script_generate_report

        default_aprx = os.path.join(current_dir, 'pdf_report_aprx', 'pdf_report_aprx.aprx')
        if not os.path.exists(default_aprx): # checks if PDF export APRX file is present in directory
            raise default_resources_not_present
        if not os.path.exists(os.path.join(current_dir, 'pdf_report_aprx', 'Default.gdb')): # checks if default GDB is present in directory
            raise default_resources_not_present

        input_fc = arcpy.GetParameterAsText(0)
        temp_units = arcpy.GetParameterAsText(1)
        wind_speed_units = arcpy.GetParameterAsText(2)
        out_gdb = arcpy.GetParameterAsText(3)
        pdf_path = arcpy.GetParameterAsText(4)
        enable_join_bool = arcpy.GetParameterAsText(5)
        overwrite_bool = arcpy.GetParameterAsText(6)
        
        if overwrite_bool.upper() == 'FALSE': # If false, checks to see if there are any output FCs that match the naming nomenclature of the script within the given output GDB
            out_fc_names = ['Temperature_Table_From_', 'Precipitation_Table_From_',
                            'Wind_Table_From_', 'Todays_Weather_Info_Table_From_']
            input_fc_name = arcpy.ValidateTableName(os.path.split(input_fc)[1], 'in_memory')
            for fc_name in out_fc_names:
                if len(input_fc_name) >= 129:
                    out_fc = os.path.join(out_gdb, f'{fc_name}_{input_fc_name[:129]}')
                else:
                    out_fc = os.path.join(out_gdb, f'{fc_name}_{input_fc_name}')
                if arcpy.Exists(out_fc):
                    raise existing_weather_fcs

        arcpy.env.overwriteOutput = overwrite_bool

        weather_fcs = mz_as606_final_project_script_weather_fcs.create_weather_fcs(input_fc, temp_units, wind_speed_units, out_gdb) # Generates the weather feature classes
        todays_weather_fc = sorted(weather_fcs)[-2] # retrieves the todays_weather_info feature class
        num_input_fc_rows = arcpy.GetCount_management(input_fc)[0]
        num_weather_rows = arcpy.GetCount_management(todays_weather_fc)[0]
        arcpy.AddMessage(f'Out of {num_input_fc_rows} rows from input FC, {num_weather_rows} received weather results.')

        if enable_join_bool.upper() == 'TRUE': # conducts the field join if true
            arcpy.AddMessage('Joining todays weather results to input feature class...')
            oid_from_input_fc = [f.name for f in arcpy.ListFields(input_fc) if f.type == 'OID'][0] # OID from input feature class
            join_oid_from_weather_fc = [f.name for f in arcpy.ListFields(todays_weather_fc) if f.name == 'INPUT_FC_OID'][0] # OID from todays_weather_info feature class
            fields_from_weather_fc = [f.name for f in arcpy.ListFields(todays_weather_fc) if f.type != 'OID' and f.type != 'Geometry'] # Gather all fields required for join
            arcpy.JoinField_management(input_fc, oid_from_input_fc, todays_weather_fc, join_oid_from_weather_fc, fields_from_weather_fc)

        export_pdf_instance = mz_as606_final_project_script_generate_report.run_layout(default_aprx, weather_fcs, pdf_path) # Exports PDF report of resulting weather locations
        os.remove(export_pdf_instance) # the export PDF script returns a copy of the default APRX, once the script is complete, we no longer need it so it will be deleted

        arcpy.AddMessage('Script Complete!')
        arcpy.AddMessage('The catalog paths of the resulting feature classes are as follows:')
        for w in weather_fcs:
            arcpy.AddMessage(w)
        break

    except beautifulsoup_install: # attempts to install the beautiful soup python package and throws an error if unsuccessful
        arcpy.AddWarning('Beautiful Soup Python Package not installed, attempting to install package...')
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'beautifulsoup4'])
            from bs4 import BeautifulSoup
            continue
        except:
            arcpy.AddError('Beautiful Soup Python package was unable to install, please clone your default ArcPro Python environment and install the package.\nYou can paste the following into the Python terminal as well: pip install beautifulsoup4')
            break
    except final_project_scripts_not_present: # Error is risen if the custom scripts arent found within the directory, under the scripts folder path
        arcpy.AddError(
            'One or more of the custom production scripts are missing from the final deliverable scripts folder or the scripts folder is missing completley from main deliverable folder.\nPlease redownload the zip file and try again.')
        break
    except default_resources_not_present: # Error is risen if the default APRX file or GDB is missing from the directory, under the pdf_report_aprx folder
        arcpy.AddError('The default APRX file is missing/relocated, scripts folder is missing/relocated, or default GDB is missing/relocated.\nPlease redownload the zip file and try again.')
        break
    except existing_weather_fcs: # Error is risen if user selects False for overwriting feature classes, but are present in the selected output GDB
        arcpy.AddError('The current weather feature classes exists, however, overwrite output was set to False. Please change the overwrite output to True or change the output GDB parameter and try again.')
        break
    except: # A catch all error whenever the script were to unexpectically crash, usually arises when the script is tampered with while running
        arcpy.AddError('Something unexpected occurred, please try again.')
        break
