import dearpygui.dearpygui as dpg
import os, shutil
import sys
import subprocess
from .state_manager import AppStateManager, open_lang_file

# Callback functions for interactions
# Show relevant selection warning
def on_combo_change(state_manager: AppStateManager):
    current_language = state_manager.lang_settings.get_curr_lang()
    loc = open_lang_file(current_language)
    lang_mappings = loc["lang_mappings"]
    ocr_mappings =  loc["ocr_mappings"]

    selected_ocr = dpg.get_value("ocr_dropdown")
    selected_source_lang = dpg.get_value("source_lang_dropdown")
    
    if dpg.get_value("stop_gpt_ocr_warning_checkbox") == False:
        if selected_ocr: 
            # If the OCR is the "Default" Option
            if ocr_mappings[selected_ocr] == "Default": 
                # if it is among the languages that use GPT-4-Vision as the default
                if lang_mappings[selected_source_lang] in ["Russian", "French", "German", "Dutch", "Spanish", "Italian"]:
                    # Show Warning
                    dpg.configure_item("gpt_for_ocr_warning", show=True)

def show_error_mac(exception):
    applescript_command = f'''
    display dialog "{exception}.\\n\\nLast progress at {dpg.get_value('progress_bar_text')}" ¬
    with title "Error" buttons {{"OK"}} default button "OK" with icon stop
    '''
    subprocess.run(["osascript", "-e", applescript_command], check=True)

default_mac_dialog_path = os.path.expanduser('~/Desktop')
def open_file_dialog_mac(file_types, multiple=False, cmd = "Select", apath=default_mac_dialog_path):
    empty_list = "{"+"}"
    # Extract extensions from the file_types
    file_types = file_types[0]
    prompt, extensions = file_types
    # Split the extensions string and remove the asterisks
    extensions_list = extensions.replace("*.", "").split()
    # Format the extensions for AppleScript
    file_types_str = "{" + ", ".join('"' + ext + '"' for ext in extensions_list) + "}"
    multiple_selections = "true" if multiple else "false"
    
    ascript = f'''
    -- apath - default path for dialogs to open to
    -- cmd   - "Select", "Save"
    -- fileTypes - list of allowed file extensions
    -- allowMultiple - boolean to allow multiple file selections

    set apath to POSIX file "{apath}" as alias
    set action to "{cmd}" as text
    set fileTypes to {file_types_str}
    set allowMultiple to {multiple_selections}
    set selectedFiles to {empty_list}
    set fpath to ""

    try
        -- Check if the action is to select files
        if action contains "Select" then
            -- Handle multiple file selections
            if allowMultiple then
                set fpaths to choose file with prompt "Select files:" default location apath of type fileTypes with multiple selections allowed and showing package contents without invisibles
                -- Loop through the selected files to convert them to POSIX paths
                repeat with aFile in fpaths
                    set end of selectedFiles to POSIX path of aFile
                end repeat
                -- Combine the POSIX paths into a single string to return
                set AppleScript's text item delimiters to ", "
                set fpath to selectedFiles as text
                set AppleScript's text item delimiters to ""
            else
                -- Handle single file selection
                set fpath to POSIX path of (choose file with prompt "Select a file:" default location apath of type fileTypes without invisibles and showing package contents)
            end if
        else if action contains "Save" then
            set fpath to POSIX path of (choose file name default location apath)
        end if
    on error number -128
        -- Handle user cancel action
        return "Cancel"
    end try

    -- Return the selected file path(s) or indicate cancellation
    if fpath is not "" then
        return fpath
    else
        return "Cancel"
    end if
    '''
    try:
        proc = subprocess.check_output(['osascript', '-e', ascript])
        out = proc.decode('utf-8').strip()
        if 'Cancel' in out:  # User pressed Cancel button
            return [] if multiple else ""
        return out.split(", ") if multiple else out
    except subprocess.CalledProcessError as e:
        print(f'Python error: [{e.returncode}]\n{e.output.decode("utf-8")}\n')

def open_file_dialog_tkinter(filetypes, multiple=True):
    from tkinter import filedialog
    if multiple:
        return filedialog.askopenfilenames(filetypes=filetypes)
    else:
        return filedialog.askopenfilename(filetypes=filetypes)

def get_file_dialog_function():
    oper_system = sys.platform
    if oper_system == 'darwin':
        return open_file_dialog_mac
    elif oper_system.startswith('linux'):
        return open_file_dialog_tkinter
    elif oper_system == 'win32':
        return open_file_dialog_tkinter

def import_images(state_manager: AppStateManager):
    file_dialog_function = get_file_dialog_function()
    filetypes = [("Image files", "*.png *.jpg *.jpeg *.webp *.bmp")]
    file_paths = file_dialog_function(filetypes, multiple=True)
    if file_paths:
        state_manager.user_data.set_data("file_paths", file_paths)
        dpg.configure_item("import_confirmed", show=True)
    else:
        dpg.configure_item("import_not_confirmed", show=True)

def import_cbr_et_al(state_manager: AppStateManager):
    file_dialog_function = get_file_dialog_function()
    filetypes = [("Comic Book Archive files", "*.cbr *.cbz *.cb7 *.cbt")]
    file_path = file_dialog_function(filetypes, multiple=False)
    if file_path:
        state_manager.user_data.set_data("file_paths", file_path)
        dpg.configure_item("import_confirmed", show=True)
    else:
        dpg.configure_item("import_not_confirmed", show=True)

def import_ebook(state_manager: AppStateManager):
    file_dialog_function = get_file_dialog_function()
    filetypes = [("Ebook", "*.pdf *.epub")]
    file_path = file_dialog_function(filetypes, multiple=False)
    if file_path:
        state_manager.user_data.set_data("file_paths", file_path)
        dpg.configure_item("import_confirmed", show=True)
    else:
        dpg.configure_item("import_not_confirmed", show=True)

def set_font_list(font_folder_path, combobox_id):
    font_files = [f for f in os.listdir(font_folder_path) if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
    dpg.configure_item(combobox_id, items=font_files)

def import_font(sender, app_data, user_data):
    file_dialog_function = get_file_dialog_function()
    filetypes = [("Font files", "*.ttf *.ttc *.otf *.woff *.woff2")]
    file_path = file_dialog_function(filetypes, multiple=False)
    if file_path:
        font_folder_path = os.path.join(os.getcwd(), "fonts")
        if not os.path.exists(font_folder_path):
            os.makedirs(font_folder_path)
        shutil.copy(file_path, font_folder_path)
        set_font_list(font_folder_path, user_data)
        # Set the value of the combobox to the newly imported font filename
        filename = os.path.basename(file_path)
        dpg.set_value(user_data, filename)
        dpg.configure_item("import_confirmed", show=True)
    else:
        dpg.configure_item("import_not_confirmed", show=True)

