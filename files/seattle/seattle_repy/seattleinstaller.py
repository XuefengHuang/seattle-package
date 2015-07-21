"""
<Program Name>
  seattleinstaller.py

<Started>
  February 10, 2009
    Amended June 11, 2009
    Amended July 30, 2009
    Amended September 9, 2009

<Author>
  Carter Butaud
    Amended by Zachary Boka

<Purpose>
  Installs seattle on any supported system. This means setting up the computer
  to run seattle at startup, generating node keys, customizing configuration
  files, and starting seattle running (not necessarily in that order, except
  that seattle must always be started running last).
"""

# Let's make sure the version of python is supported.
import checkpythonversion
checkpythonversion.ensure_python_version_is_supported()

import os
import shutil
import platform
import sys
import getopt
import tempfile
import time
import getpass


# Python should do this by default, but doesn't on Windows CE.
sys.path.append(os.getcwd())
import servicelogger
import nonportable
import createnodekeys
import repy_constants
import persist # Armon: Need to modify the NM config file
import benchmark_resources
# Anthony - traceback is imported so that benchmarking can be logged
# before the vessel state has been created (servicelogger does not work
# without the v2 directory).
import traceback 


SILENT_MODE = False
KEYBITSIZE = 1024
DISABLE_STARTUP_SCRIPT = False
OS = nonportable.ostype
SUPPORTED_OSES = ["Windows", "WindowsCE", "Linux", "Darwin"]
# Supported Windows Versions: XP, Vista, 7
# NOTE:
#   To support newer versions of Windows (or when changing the Python version 
#   included with the Windows installer package), ammend the function 
#   get_filepath_of_win_startup_folder_with_link_to_seattle() below.

RESOURCE_PERCENTAGE = 10
# Armon: DISABLE_INSTALL: Special flag for testing purposes that can be
#        accessed from the command-line argument "--onlynetwork". All
#        pre-install actions are performed, but the actual install is disabled.
DISABLE_INSTALL = False
# Specify the directory containing all seattle files.
SEATTLE_FILES_DIR = os.path.realpath(".")

# Import subprocess if not in WindowsCE
subprocess = None
if OS != "WindowsCE":
  import subprocess

# Import windows_api if in Windows or WindowsCE
windows_api = None
if OS == "WindowsCE":
  import windows_api

# Import _winreg if in Windows or WindowsCE
_winreg = None
if OS == "Windows" or OS == "WindowsCE":
  import _winreg


IS_ANDROID = False



class CronAccessibilityFilesPermissionDeniedError(Exception):
  pass

class CronAccessibilityFilesNotFoundError(Exception):
  pass

class CannotDetermineCronStatusError(Exception):
  pass

class DetectUserError(Exception):
  pass

class UnsupportedOSError(Exception):
  pass

class AlreadyInstalledError(Exception):
  pass




def _output(text):
  """
  For internal use.
  If the program is not in silent mode, prints the input text.
  """
  if not SILENT_MODE:
    print text




def find_substring_in_a_file_line(search_absolute_filepath,substring):
  """
  <Purpose>
    Determine if the given substring exists in at least one line in the given
    file by opening a file object for the file in search_absolute_filepath.

  <Arguments>
    search_absolute_filepath:
      The absolute file path to the file that will be searched for the given
      substring.

    substring:
      The substring that will be searched for in file named by
      search_absolute_filepath.

  <Exceptions>
    IOError if the supplied file path does not exist.

  <Side Effects>
    None.

  <Return>
    True if the substring is found in at least one line in the file specified
    by search_absolute_filepath,
    False otherwise.
  """

  file_obj = open(search_absolute_filepath,"r")
  for line in file_obj:
    if substring in line:
      file_obj.close()
      return True

  file_obj.close
  return False




def preprocess_file(absolute_filepath, substitute_dict, comment="#"):
  """
  <Purpose>
    Looks through the given file and makes all substitutions indicated in lines
    the do not begin with a comment.

  <Arguments>
    absolute_filepath:
      The absolute path to the file that should be preprocessed.
    substitute_dict:
      Map of words to be substituted to their replacements, e.g.,
      {"word1_in_file": "replacement1", "word2_in_file": "replacement2"}
    comment:
      A string which indicates commented lines; lines that start with this will
      be ignored, but lines that contain this symbol somewhere else in the line 
      will be preprocessed up to the first instance of the symbol. Defaults to
      "#". To preprocess all lines in a file, set as the empty string.

  <Exceptions>
    IOError on bad file names.
  
  <Side Effects>
    None.

  <Returns>
    None.
  """
  edited_lines = []
  base_fileobj = open(absolute_filepath, "r")

  for fileline in base_fileobj:
    commentedOutString = ""

    if comment == "" or not fileline.startswith(comment):
      # Substitute the replacement string into the file line.

      # First, test whether there is an in-line comment.
      if comment != "" and comment in fileline:
        splitLine = fileline.split(comment,1)
        fileline = splitLine[0]
        commentedOutString = comment + splitLine[1]

      for substitute in substitute_dict:
        fileline = fileline.replace(substitute, substitute_dict[substitute])

    edited_lines.append(fileline + commentedOutString)

  base_fileobj.close()

  # Now, write those modified lines to the actual starter file location.
  final_fileobj = open(absolute_filepath, "w")
  final_fileobj.writelines(edited_lines)
  final_fileobj.close()




def get_filepath_of_win_startup_folder_with_link_to_seattle():
  """
  <Purpose>
    Gets what the full filepath would be to a link to the seattle starter script
    in the Windows startup folder.  Also tests whether or not that filepath
    exists (i.e., whether or not there is currently a link in the startup folder
    to run seattle at boot).
  
  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSException if the operating system is not Windows or WindowsCE.
    IOError may be thrown if an error occurs while accessing a file.

  <Side Effects>
    None.

  <Returns>
    A tuple is returned with the first value being the filepath to the link in
    the startup folder that will run seattle at boot.  The second value is a
    boolean value: True indicates the link currently exists in the startup
    folder, and False if it does not.
  """
  if OS == "WindowsCE":
    startup_path = "\\Windows\\Startup" + os.sep \
        + get_starter_shortucut_file_name()
    return (startup_path, os.path.exists(startup_path))

  elif OS != "Windows":
    raise UnsupportedOSError("The startup folder only exists on Windows.")


  # The startup_path is the same for Vista and Windows 7.
  #
  # As discussed per ticket #1059, different Python versions return
  # different names for Windows 7 (see also http://bugs.python.org/issue7863).
  # Testing on Windows 7 Professional, 64 bits, German localization, 
  # platform.release() returns
  #   "Vista" for Python versions 2.5.2 and 2.5.4,
  #   "post2008Server" for versions 2.6.2 to 2.6.5, and
  #   "7" for versions 2.6.6 and 2.7.0 to 2.7.3.
  # Please adapt this once new Python/Windows versions become available.

  release = platform.release()
  if release == "Vista" or release == "post2008Server" or release == "7":
    startup_path = os.environ.get("HOMEDRIVE") + os.environ.get("HOMEPATH") \
        + "\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs" \
        + "\\Startup" + os.sep + get_starter_shortcut_file_name()
    return (startup_path, os.path.exists(startup_path))

  elif release == "XP":
    startup_path = os.environ.get("HOMEDRIVE") + os.environ.get("HOMEPATH") \
        + "\\Start Menu\\Programs\\Startup" + os.sep \
        + get_starter_shortcut_file_name()
    return (startup_path, os.path.exists(startup_path))


  else:
    raise UnsupportedOSError("""
Sorry, we couldn't detect your Windows version.
Please contact the Seattle development team at

   seattle-devel@googlegroups.com
   
to resolve this issue. Version details:
Python version: """ + str(platform.python_version()) + 
"\nPlatform arch: " + str(platform.architecture()) + 
"\nPlatform release: " + str(platform.release()) + 
"\nPlatform version string: " + str(platform.version()))



def get_starter_file_name():
  """
  <Purpose>
    Returns the name of the starter file on the current operating system.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the operating system requested is not supported.

  <Side Effects>
    None.

  <Returns>
    A string containing the name of the starter file.
  """

  if OS == "Windows":
    return "start_seattle.bat"
  elif OS == "WindowsCE":
    return "start_seattle.py"
  elif OS == "Linux" or OS == "Darwin":
    return "start_seattle.sh"
  else:
    raise UnsupportedOSError("This operating system is not supported. " \
                               + "Currently, only the following operating " \
                               + "systems are supported: " + SUPPORTED_OSES)
                            




def get_starter_shortcut_file_name():
  """
  <Purpose>
    Returns the name of the starter shortcut file on the current operating
    system.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the operating system requested is not supported.

  <Side Effects>
    None.

  <Returns>
    A string containing the name of the starter shortcut file.
  """

  if OS == "Windows":
    return "start_seattle_shortcut.bat"
  else:
    raise UnsupportedOSError("Only the Windows installer contains a shortcut " \
                               + "for the seattle starter batch file.")




def get_stopper_file_name():
  """
  <Purpose>
    Returns the name of the stopper file on the current operating system.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the operating system requested is not supported.

  <Side Effects>
    None.

  <Returns>
    A string containing the name of the stopper file.  Returns an empty string
    if the supported operating system does not contain a stopper file.
  """

  if OS == "Windows":
    return "stop_seattle.bat"
  elif OS == "WindowsCE":
    return ""
  elif OS == "Linux" or OS == "Darwin":
    return "stop_seattle.sh"
  else:
    raise UnsupportedOSError("This operating system is not supported. " \
                               + "Currently, only the following operating " \
                               + "systems are supported: " + SUPPORTED_OSES)




def get_uninstaller_file_name():
  """
  <Purpose>
    Returns the name of the uninstaller file on the current operating
    system.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the operating system requested is not supported.

  <Side Effects>
    None.

  <Returns>
    The name of the uninstaller file.
  """
  if OS == "Windows":
    return "uninstall.bat"
  elif OS == "WindowsCE":
    return "uninstall.py"
  elif OS == "Linux" or OS == "Darwin":
    return "uninstall.sh"
  else:
    raise UnsupportedOSError("This operating system is not supported. " \
                               + "Currently, only the following operating " \
                               + "systems are supported: " + SUPPORTED_OSES)




def search_value_in_win_registry_key(opened_key,seeking_value_name):
  """
  <Purpose>
    Searches a given key to see if a given value exists for that key.

  <Arguments>
    opened_key:
      An already opened key that will be searched for the given value.  For a
      key to be opened, it must have had either the _winreg.OpenKey(...) or
      _winreg.CreateKey(...) function performed on it.

    seeking_value_name:
      A string containing the name of the value to search for within the
      opened_key.

  <Exceptions>
    UnsupportedOSError if the operating system is not Windows or WindowsCE.
    WindowsError if opened_key has not yet been opened.

  <Side Effects>
    None.

  <Returns>
    True if seeking_value_name is found within opened_key.
    False otherwise.
  """
  if OS != "Windows" and OS != "WindowsCE":
    raise UnsupportedOSError("This operating system must be Windows or " \
                               + "WindowsCE in order to manipulate registry " \
                               + "keys.")

  # Test to make sure that opened_key was actually opened by obtaining
  # information about that key.
  # Raises a WindowsError if opened_key has not been opened.
  # subkeycount: the number of subkeys opened_key contains. (not used).
  # valuescount: the number of values opened_key has.
  # modification_info: long integer stating when the key was last modified.
  #                    (not used)
  subkeycount, valuescount, modification_info = _winreg.QueryInfoKey(opened_key)
  if valuescount == 0:
    return False


  try:
    value_data,value_type = _winreg.QueryValueEx(opened_key,seeking_value_name)
    # No exception was raised, so seeking_value_name was found.
    return True
  except WindowsError:
    return False




def remove_seattle_from_win_startup_folder():
  """
  <Purpose>
    Removes the seattle startup script from the Windows startup folder if it
    exists.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the os is not supported (i.e., a Windows machine).
    IOError may be raised if an error occurs during file and filepath
      manipulation.

  <Side Effects>
    Removes the seattle startup script from the Windows startup folder if it
    exists.

  <Returns>
    True if the function removed the link to the startup script, meaning it
         previously existed.
    False otherwise, meaning that a link to the startup script did not
    previously exist.
  """
  if OS != "Windows" and OS != "WindowsCE":
    raise UnsupportedOSError("This must be a Windows operating system to " \
                               + "access the startup folder.")

  # Getting the startup path in order to see if a link to seattle has been
  # installed there.
  full_startup_file_path,file_path_exists = \
      get_filepath_of_win_startup_folder_with_link_to_seattle()
  if file_path_exists:
    os.remove(full_startup_file_path)
    return True
  else:
    return False




def add_seattle_to_win_startup_folder():
  """
  <Purpose>
    Add the seattle startup script to the Windows startup folder.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the os is not supported (i.e., a Windows machine).
    IOError may be raised if an error occurs during file and filepath
      manipulation.

  <Side Effects>
    Adds the seattle startup script to the Windows startup folder.

  <Returns>
    None.
  """
  if OS != "Windows" and OS != "WindowsCE":
    raise UnsupportedOSError("This must be a Windows operating system to " \
                               + "access the startup folder.")

  # Getting the startup path in order to copy the startup file there which will
  # make seattle start when the user logs in.
  full_startup_file_path,file_path_exists = \
      get_filepath_of_win_startup_folder_with_link_to_seattle()
  if file_path_exists:
    raise AlreadyInstalledError("seattle was already installed in the " \
                                  + "startup folder.")
  else:
    shutil.copy(SEATTLE_FILES_DIR + os.sep + get_starter_shortcut_file_name(),
                full_startup_file_path)




def add_to_win_registry_Local_Machine_key():
  """
  <Purpose>
    Adds seattle to the Windows registry key Local_Machine which runs programs
    at machine startup (regardless of which user logs in).

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the os is not supported (i.e., a Windows machine).
    AlreadyInstalledError if seattle has already been installed on the system.

  <Side Effects>
    Adds a value named "seattle", which contains the absolute file path to the
    seattle starter script, to the startup registry key.

  <Returns>
    True if succeeded in adding seattle to the registry,
    False otherwise.
  """

  if OS != "Windows" and OS != "WindowsCE":
    raise UnsupportedOSError("This machine must be running Windows in order " \
                               + "to access the Windows registry.")

  # The following entire try: block attempts to add seattle to the Windows
  # registry to run seattle at machine startup regardless of user login.
  try:
    # The startup key must first be opened before any operations, including
    # searching its values, may be performed on it.

    # ARGUMENTS:
    # _winreg.HKEY_LOCAL_MACHINE: specifies the key containing the subkey used
    #                             to run programs at machine startup
    #                             (independent of user login).
    # "Software\\Microsoft\\Windows\\CurrentVersion\\Run": specifies the subkey
    #                                                      that runs programs on
    #                                                      machine startup.
    # 0: a reserved integer that must be zero.
    # _winreg.KEY_ALL_ACCESS: an integer that acts as an access map that
    #                         describes desired security access for this key.
    #                         In this case, we want all access to the key so it
    #                         can be modified. (Default: _winreg.KEY_READ)
    startup_key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                            "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                            0, _winreg.KEY_ALL_ACCESS)
  except WindowsError:
    return False

  else:
    # The key was successfully opened.  Now check to see if seattle was
    # previously installed in this key. *Note that the key should be closed in
    # this else: block when it is no longer needed.
    if search_value_in_win_registry_key(startup_key, "seattle"):
      # Close the key before raising AlreadyInstalledError.
      _winreg.CloseKey(startup_key)
      raise AlreadyInstalledError("seattle is already installed in the " \
                                    + "Windows registry startup key.")

    try:
      # seattle has not been detected in the registry from a previous
      # installation, so attempting to add the value now.
      
      # _winreg.SetValueEx(...) creates the value "seattle", if it does not
      #                         already exist, and simultaneously adds the given
      #                         data to the value.
      # ARGUMENTS:
      # startup_key: the opened subkey that runs programs on startup.
      # "seattle": the name of the new value to be created under startup_key 
      #            that will make seattle run at machine startup.
      # 0: A reserved value that can be anything, though zero is always passed
      #    to the API according to python documentation for this function.
      # _winreg.REG_SZ: Specifies the integer constant REG_SZ which indicates
      #                 that the type of the data to be stored in the value is a
      #                 null-terminated string.
      # SEATTLE_FILES_DIR + os.sep + get_starter_file_name(): The data of the
      #                                               new value being created
      #                                               containing the full path
      #                                               to seattle's startup
      #                                               script.
      _winreg.SetValueEx(startup_key, "seattle", 0, _winreg.REG_SZ,
                       SEATTLE_FILES_DIR + os.sep + get_starter_file_name())
      servicelogger.log(" seattle was successfully added to the Windows " \
                          + "registry key to run at startup: " \
                          + "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows" \
                          + "\\CurrentVersion\\Run")
      # Close the key before returning.
      _winreg.CloseKey(startup_key)
      return True

      
    except WindowsError:
      # Close the key before falling through the try: block.
      _winreg.CloseKey(startup_key)
      return False






def add_to_win_registry_Current_User_key():
  """
  <Purpose>
    Sets up seattle to run at user login on this Windows machine.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the os is not supported (i.e., a Windows machine).
    AlreadyInstalledError if seattle has already been installed on the system.

  <Side Effects>
    Adds a value named "seattle", which contains the absolute file path to the
    seattle starter script, to the user login registry key.

  <Returns>
    True if succeeded in adding seattle to the registry,
    False otherwise.
  """
  if OS != "Windows" and OS != "WindowsCE":
    raise UnsupportedOSError("This machine must be running Windows in order " \
                               + "to access the Windows registry.")

  # The following entire try: block attempts to add seattle to the Windows
  # registry to run seattle at user login.
  try:
    # The startup key must first be opened before any operations, including
    # searching its values, may be performed on it.

    # ARGUMENTS:
    # _winreg.HKEY_CURRENT_MACHINE: specifies the key containing the subkey used
    #                             to run programs at user login.
    # "Software\\Microsoft\\Windows\\CurrentVersion\\Run": specifies the subkey
    #                                                      that runs programs on
    #                                                      user login.
    # 0: a reserved integer that must be zero.
    # _winreg.KEY_ALL_ACCESS: an integer that acts as an access map that
    #                         describes desired security access for this key.
    #                         In this case, we want all access to the key so it
    #                         can be modified. (Default: _winreg.KEY_READ)
    startup_key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                            "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                            0, _winreg.KEY_ALL_ACCESS)
  except WindowsError:
    return False

  else:
    # The key was successfully opened.  Now check to see if seattle was
    # previously installed in this key. *Note that the key should be closed in
    # this else: block when it is no longer needed.
    if search_value_in_win_registry_key(startup_key, "seattle"):
      # Close the key before raising AlreadyInstalledError.
      _winreg.CloseKey(startup_key)
      raise AlreadyInstalledError("seattle is already installed in the " \
                                    + "Windows registry startup key.")

    try:
      # seattle has not been detected in the registry from a previous
      # installation, so attempting to add the value now.
      
      # _winreg.SetValueEx(...) creates the value "seattle", if it does not
      #                         already exist, and simultaneously adds the given
      #                         data to the value.
      # ARGUMENTS:
      # startup_key: the opened subkey that runs programs on user login.
      # "seattle": the name of the new value to be created under startup_key 
      #            that will make seattle run at user login.
      # 0: A reserved value that can be anything, though zero is always passed
      #    to the API according to python documentation for this function.
      # _winreg.REG_SZ: Specifies the integer constant REG_SZ which indicates
      #                 that the type of the data to be stored in the value is a
      #                 null-terminated string.
      # SEATTLE_FILES_DIR + os.sep + get_starter_file_name(): The data of the
      #                                               new value being created
      #                                               containing the full path
      #                                               to seattle's startup
      #                                               script.
      _winreg.SetValueEx(startup_key, "seattle", 0, _winreg.REG_SZ,
                       SEATTLE_FILES_DIR + os.sep + get_starter_file_name())
      servicelogger.log(" seattle was successfully added to the Windows " \
                          + "registry key to run at user login: " \
                          + "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows" \
                          + "\\CurrentVersion\\Run")
      # Close the key before returning.
      _winreg.CloseKey(startup_key)
      return True
      
    except WindowsError:
      # Close the key before falling through the try: block.
      _winreg.CloseKey(startup_key)
      return False





def setup_win_startup():
  """
  <Purpose>
    Sets up seattle to run at startup on this Windows machine. First, this means
    adding a value, with absolute file path to the seattle starter script, to
    the machine startup and user login registry keys (HKEY_LOCAL_MACHINE and 
    HKEY_CURRENT_USER) which will run seattle at startup regardless of which
    user logs in and when the current user logs in (in the case where a machine
    is not shut down between users logging in and out). Second, if that fails,
    this method attempts to add a link to the Windows startup folder which will
    only run seattle when this user logs in.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the os is not supported (i.e., a Windows machine).
    AlreadyInstalledError if seattle has already been installed on the system.
    IOError may be raised if an error occurs during file and filepath
      manipulation in one of the sub-functions called by this method.

  <Side Effects>
    Adds a value named "seattle", which contains the absolute file path to the
    seattle starter script, to the startup registry key, or adds seattle to the
    startup folder if adding to the registry key fails.

    If an entry is successfully made to the registry key and a pre-existing link
    to seattle exists in the startup folder, the entry in the startup folder is
    removed.

  <Returns>
    None.
  """

  # Check to make sure the OS is supported
  if OS != "Windows" and OS != "WindowsCE":
    raise UnsupportedOSError("This operating system must be Windows or " \
                               + "WindowsCE in order to modify a registry " \
                               + "or startup folder.")

  try:
    added_to_CU_key = add_to_win_registry_Current_User_key()
    added_to_LM_key = add_to_win_registry_Local_Machine_key()
  except Exception,e:
    # Fall through try: block to setup seattle in the startup folder.
    _output("seattle could not be installed in the Windows registry for the " \
              + "following reason: " + str(e))
    servicelogger.log(" seattle was NOT setup in the Windows registry " \
                        + "for the following reason: " + str(e))
  else:
    if added_to_CU_key or added_to_CU_key:
      # Succeeded in adding seattle to the registry key, so now remove seattle
      # from the startup folder if there is currently a link there from a
      # previous installation.
      if remove_seattle_from_win_startup_folder():
        _output("seattle was detected in the startup folder.")
        _output("Now that seattle has been successfully added to the " \
                  + "Windows registry key, the link to run seattle has been " \
                  + "deleted from the startup folder.")
        servicelogger.log(" A link to the seattle starter file from a " \
                            + "previous installation was removed from the " \
                            + "startup folder during the current installation.")
        # Since seattle was successfully installed in the registry, the job of
        # this function is finished.
      return

    else:
      _output("This user does not have permission to access the user registry.")
      
    



  # Reaching this point means modifying the registry key failed, so add seattle
  # to the startup folder.
  _output("Attempting to add seattle to the startup folder as an " \
            + "alternative method for running seattle at startup.")
  add_seattle_to_win_startup_folder()
  servicelogger.log(" A link to the seattle starter script was installed in " \
                      + "the Windows startup folder rather than in the " \
                      + "registry.")




def test_cron_is_running():
  """
  <Purpose>
    Try to find out if cron is installed and running on this system. This is not
    a straight-forward process because many operating systems install cron in
    different locations.  Further, not all the current known locations of
    where cron may be installed will allow for the status (whether or not cron
    is actually running) to be checked. As a result, the most general method of
    trying to find if cron is running is performed first (grep the list of
    current processes looking for cron), then if that fails, the following list
    of possible cron file locations where the cron status can be checked are
    searched. If all else fails, a CannotDetermineCronStatusError is raised.

    Current list of possible cron locations where the status of cron can be
    checked:

      DEBIAN AND UBUNTU: /etc/init.d/cron
      DEBIAN AND UBUNTU: /etc/init.d/crond
      FREEBSD and others?: /etc/rc.d/cron
      unknown: /etc/rc.d/init.d/cron


  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if this is not a Linux or Mac box.
    CannotDetermineCronStatusError if cron is installed but it cannot be
      determined whether or not it is running.

  <Side Effects>
    None.
   
  <Return>
    True if cron is running on this machine,
    False otherwise.
  """

  if not OS == "Linux" and not OS == "Darwin":
    raise UnsupportedOSError("This must be a Linux or Macintosh machine to " \
                               + "test if cron is running.")

  # First, try the most general way of seeing if cron is running.

  # Due to the pipes in the subprocess.Popen command, it makes more sense to
  # send the command as one string rather than breaking up the cammand into
  # three separate subprocess.Popen processes and piping the output of one into
  # the input of the next.
  grep_cron_stdout,grep_cron_stderr = \
      subprocess.Popen("ps -ef | grep cron | grep -v grep",shell=True,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE).communicate()

  if "cron" in grep_cron_stdout:
    return (True,None)
  else:
    grep_crond_stdout,grep_crond_stderr = \
        subprocess.Popen("ps -ef | grep crond | grep -v grep",shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).communicate()
    if "crond" in grep_crond_stdout:
      return (True,None)




  # Reaching this point means cron was not detected using the most general
  # method.  Cron may still be running or installed, but may not be easily
  # accessible.  For example, FreeBSD seems to have some trouble running the
  # command "ps -ef | grep cron | grep -v grep".

  # Try to get the status of cron if possible.

  # Depending on the system and distribution, the cron file that allows the cron
  # status to be checked could appear in a variety of places.
  cron_file_paths_list = ["/etc/init.d/cron","/etc/init.d/crond",
                          "/etc/rc.d/init.d/cron","/etc/rc.d/cron"]

  cron_status_path = None
  for possible_cron_path in cron_file_paths_list:
    # Test if possible_cron_path exists and is executable.
    if os.access(possible_cron_path,os.X_OK):
      cron_status_path = possible_cron_path
      break

  if cron_status_path == None:
    # Not able to detect cron on this machine. Because the cron_file_paths_list
    # may be incomplete, this function cannot return false but must instead
    # raise a CannotDetermineCronStatusError.
    raise CannotDetermineCronStatusError("Cannot determine if cron is " \
                                           + "installed, and thus cannot " \
                                           + "test if cron is running.")

  else:
    # Try to get the status of cron from the found cron_status_path.
    try:
      cron_status_stdout,cron_status_stderr = \
          subprocess.Popen([cron_status_path,"status"],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE).communicate()
    except Exception:
      raise CannotDetermineCronStatusError("User cannot access the cron " \
                                             + "status.")
    else:
      # Because there will be various outputs depending on the OS and whether
      # or not cron is installed, many conditions are needed to attempt to
      # capture the cron status.
      if not cron_status_stdout and not cron_status_stderr:
        # If there is no output, then the status cannot be determined.
        raise CannotDetermineCronStatusError("No output produced from the " \
                                               + "cron status command.")
      elif "not running" in cron_status_stdout:
        # If "not running" appears in the stdout output, return False.
        return (False,cron_status_path)
      elif cron_status_stdout and not cron_status_stderr:
        # After those tests, if there is stdout output and no stderr output,
        # return True to indicate that cron is running.
        return (True,cron_status_path)
      else:
        # For any other unpredicted conditions, raise a
        # CannotDetermineCronStatusError
        raise CannotDetermineCronStatusError("The output produced by the " \
                                               + "cron status command could " \
                                               + "not be interpreted.")




def test_cron_accessibility():
  """
  <Purpose>
    Find out if the user has access to use cron by examining the allow and deny
    files for cron.  Depending on the operating system, these files may be
    located in various locations.  Below is a list of probable locations
    depending on the system (this list may not be complete).

	DEBIAN:	 /etc/cron.allow
	SuSE:	 /var/spool/cron/allow
	MAC:	 /usr/lib/cron/cron.allow
	UNIX?:	 /etc/cron.d/cron.allow
	BSD:	 /var/cron/allow

    Because there are so many options, this function searches for any of these
    files on the system.  If any of them exist, then we have found the location
    of the accessibility files on this machine.  If this function cannot find
    any of these files, then we assume the accessibility files do not exist on
    this machine, meaning that the user may or may not have access to cron
    depending on the system on its specifications with cron (this cannot be
    determined by us, so a CronAccessibilityFilesNotFoundError is raised).

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if this not a Linux or Mac box.
    CronAccessibilityFilesNotFoundError if the allow or deny files cannot be
      found on this system.
    DectectUserError if cron accessibility files are found but the user name
      cannot be determined.
    CronAccessibilityFilesPermissionDeniedError when the cron accessibility
      files are found but the user does not have permission to read them.

  <Side Effects>
    None.

  <Return>
    True if the user has access to use cron,
    False otherwise.
  """

  if not OS == "Linux" and not OS == "Darwin":
    raise UnsupportedOSError("This must be a Linux or Macintosh machine to " \
                               + "test if cron is running.")

  cron_allow_path = None
  cron_deny_path = None
  cron_accessibility_paths = [("/etc/cron.allow","/etc/cron.deny"),
                              ("/var/spool/cron/allow","/var/spool/cron/deny"),
                              ("/usr/lib/cron/cron.allow",
                               "/usr/lib/cron/cron.allow"),
                              ("/etc/cron.d/cron.allow",
                               "/etc/cron.d/cron.deny"),
                              ("/var/cron/allow","/var/cron/deny")]

  # Try to figure out the location of the cron accessibility files.
  for (possible_allow_path,possible_deny_path) in cron_accessibility_paths:
    if os.path.exists(possible_allow_path) \
          or os.path.exists(possible_deny_path):
      cron_allow_path = possible_allow_path
      cron_deny_path = possible_deny_path
      break

  
  if cron_allow_path == None and cron_deny_path == None:
    # The cron accessibility files do not exist.
    raise CronAccessibilityFilesNotFoundError("Unable to detect existing " \
                                                + "cron.allow and " \
                                                + "cron.deny files.")
  else:
    try:
      # Get the user name.
      user_name = getpass.getuser()
    except Exception,e:
      # The user name cannot be determined, and thus the cron.allow and/or the
      # cron.deny files cannot be checked to see if the username appears in
      # them.
      raise DetectUserError("At least one of the cron accessibility files " \
                              + "were found, but they could not be searched " \
                              + "because the user name could not be " \
                              + "determined.")

    # If cron.allow exists, then the user MUST be listed therein in order to use
    # cron.
    if os.path.exists(cron_allow_path):
      try:
        found_in_allow = find_substring_in_a_file_line(cron_allow_path,
                                                       user_name)
      except Exception,e:
        raise CronAccessibilityFilesPermissionDeniedError(cron_allow_path)
      else:
        return (found_in_allow,None)

    # If cron.deny exists AND cron.allow does not exist, then the user must NOT
    # be listed therein in order to use cron.
    elif os.path.exists(cron_deny_path):
      try:
        found_in_deny = find_substring_in_a_file_line(cron_deny_path,user_name)
      except Exception,e:
        raise CronAccessibilityFilesPermissionDeniedError(cron_deny_path)
      else:
        return (not found_in_deny,cron_deny_path)
      
      


def find_mount_point_of_seattle_dir():
  """
  <Purpose>
    Find the mount point of the directory in which seattle is currently being
    installed.

  <Arguments>
    None.

  <Excpetions>
    None.

  <Side Effects>
    None.

  <Return>
    The mount point for the directory in which seattle is currently being
    installed.
  """

  potential_mount_point = SEATTLE_FILES_DIR

  # To prevent a potential, yet unlikely, infinite loop from occuring, exit the
  # while loop if the current potential mount point is the same as
  # os.path.dirname(potential_mount_point).
  while not os.path.ismount(potential_mount_point) \
        and potential_mount_point != os.path.dirname(potential_mount_point):
    potential_mount_point = os.path.dirname(potential_mount_point)

  return potential_mount_point
      



def add_seattle_to_crontab():
  """
  <Purpose>
    Adds an entry to the crontab to run seattle automatically at boot.

    HIGH-LEVEL DESCRIPTION OF CRONTAB ENTRY FUNCTIONALITY:
      Check if the seattle start script exists: if so, start seattle.
      Else if the mount point for the seattle directory isn't mounted, sit in
      a 60 second sleep loop until the mount point has been mounted, then start
      start seattle.
      Otherwise, the seattle start script has been removed, so remove the
      seattle crontab entry.

      *NOTE: Further functionality to check if the seattle start script has been
             deleted once the mount point is detected was NOT added to the
             crontab entry because it is already highly unlikely that cron will
             be started before the directory is mounted.  NFS appears to make
             all directories appear mounted to the OS at all times.

  <Arguments>
    None.

  <Exceptions>
    OSError if cron is not installed on this system.

  <Side Effects>
    Adds an entry to the crontab.

  <Returns>
    True if an entry for seattle was successfully added to the crontab,
    False otherwise.
  """
  # Check to see if the crontab has already been modified to run seattle.
  crontab_contents_stdout,crontab_contents_stderr = \
      subprocess.Popen(["crontab", "-l"], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE).communicate()
  if get_starter_file_name() in crontab_contents_stdout:
    raise AlreadyInstalledError("An entry for seattle was already detected " \
                                  + "in the crontab.")
    

  # Since seattle is not already installed, modify crontab to run seattle at
  # boot.

  # First, get the service vessel where standard error produced from cron will
  # be written.
  service_vessel = servicelogger.get_servicevessel()

  # Next, find the mount point which will be included in the seattle crontab
  # entry in case the user installs on a network filesystem.  This way the
  # seattle entry will not automatically erroneously remove itself if the user's
  # filesystem has not yet been mounted.
  mount_point = find_mount_point_of_seattle_dir()


  # The crontab entry automatically removes itself in the event that the seattle
  # directory no longer exists (the user removed it without uninstalling). In
  # this case, the crontab entry must use mktemp to create a file with
  # secure permissions in which to store the modified crontab contents while the
  # seattle entry is being removed from crontab. This prevents a malicious
  # program on another user account from changing the modified crontab contents
  # before it is read back into crontab.
  #   The mktemp command is different accross platforms, so we create a temp
  #   file using the '-t' option so mkfile is consistent for our purposes across
  #   platforms.  On regular linux systems, the "XXXXX" in "tempcrontab.XXXXX"
  #   will be replaced by randomly chosen characters/numbers.  On Mac and BSD,
  #   the "XXXXX" remain part of the file name, and a randomly chosen string of
  #   characters/numbers are appended to the file name. In both cases, a
  #   randomly generated file with secure permissions is created on the stop.
  cron_line_entry = '@reboot if [ -e "' + SEATTLE_FILES_DIR + os.sep \
      + get_starter_file_name() + '" ]; then "' + SEATTLE_FILES_DIR + os.sep \
      + get_starter_file_name() + '" >> "' + SEATTLE_FILES_DIR + os.sep \
      + service_vessel + '/cronlog.txt" 2>&1; elif [ "`mount | ' \
      + 'grep -e \'[ ]' + mount_point + '[/]*[ ]\'`" = "" ]; then ' \
      + 'while [ "`mount | grep -e \'[ ]' + mount_point + '[/]*[ ]\'`" = ""]; '\
      + 'do sleep 60s; done && "' + SEATTLE_FILES_DIR + os.sep \
      + get_starter_file_name() + '" >> "' + SEATTLE_FILES_DIR + os.sep \
      + service_vessel + '/cronlog.txt" 2>&1; else ' \
      + 'modifiedCrontab=`mktemp -t tempcrontab.XXXXX` && crontab -l | ' \
      + 'sed \'/start_seattle.sh/d\' > ${modifiedCrontab} && ' \
      + 'crontab ${modifiedCrontab} && rm -rf ${modifiedCrontab}; fi' \
      + os.linesep

  # Generate a temp file with the user's crontab plus our task.
  temp_crontab_file = tempfile.NamedTemporaryFile()
  temp_crontab_file.write(crontab_contents_stdout)
  temp_crontab_file.write(cron_line_entry)
  temp_crontab_file.flush()

  # Now, replace the crontab with that temp file and remove(close) the
  # tempfile.
  replace_crontab = subprocess.Popen(["crontab",temp_crontab_file.name],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
  replace_crontab.wait()                                    
  temp_crontab_file.close()




  # Finally, confirm that seattle was successfully added to the crontab.
  crontab_contents_stdout,crontab_contents_stderr = \
      subprocess.Popen(["crontab", "-l"], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE).communicate()
  if get_starter_file_name() in crontab_contents_stdout:
    return True
  else:
    return False




# Derek Cheng: added function for setting up the startup of Seattle on the 
# Nokia tablet. This is to be called from setup_linux_or_mac() since the Nokia
# runs on a Linux-based OS.
def setup_nokia_startup():
  """
  <Purpose>
    Sets up seattle to run at startup on a Nokia tablet. It requires the user
    to be currently on root access (checked in main()). It creates a short
    shell script in /etc/init.d that will in turn run start_seattle.sh, and a
    symlink in /etc/rc2.d that will link to the short script in /etc/init.d.
    These two files will cause Seattle to run on startup.

  <Arguments>
    None.
    
  <Exceptions>
    AlreadyInstalledError if seattle has already been installed on the system.

  <Side Effects>
    None.

  <Returns>
    True if the files are created successfully,
    False otherwise.
  """
  

  # Note to developers: If you need to change the path of the startup script or
  # the path of the symlink, make sure you keep it consistent with those in
  # test_seattle_is_installed() and seattleuninstaller.py.

  # The name of the startup script.
  startup_script_name = "nokia_seattle_startup.sh"
  # The directory where the startup script will reside.
  startup_script_dir = "/etc/init.d/"
  # The full path to the startup script.
  startup_script_path = startup_script_dir + startup_script_name

  # The name of the symlink that links to the startup script.
  symlink_name = "S99startseattle"
  # The directory where the symlink to the startup script will reside.
  symlink_dir = "/etc/rc2.d/"
  # The full path to the symlink.
  symlink_path = symlink_dir + symlink_name

  # The username of the user. This is assumed to be 'user'.
  # However, if you do change your user name on the Nokia,
  # you will need to modify the following line to match your user name.
  username = "user"
  
  # If the startup script or the symlink already exists prior to this 
  # installation, an AlreadyInstalledError is raised.
  if os.path.exists(startup_script_path) or \
        os.path.lexists(symlink_dir + symlink_name):
    _output("The files that are required for running Seattle on startup " \
              + "already exists. If you would like a clean installation, " \
              + "please run the uninstaller first to remove those files.")
    servicelogger.log("The startup files were not added to the /etc/ " \
                        + "directories because they already existed prior to " \
                        + "the installation.")
    raise AlreadyInstalledError()  
  
  # The contents of the startup script in its entirety.
  # This line indicates that it is a shell script.
  startup_script_content = "#! /bin/sh" + "\n"
  # This line runs start_seattle.sh as "user".
  startup_script_content += "su - " + username + " -c " \
      + os.path.realpath(get_starter_file_name()) + "\n" 
  
  # Creates the startup script file.
  try:
    startup_script_handle = file(startup_script_path, 'w')
  except:
    _output("Cannot create startup script file. Make sure you have the " \
              + "permission to do so.")
    servicelogger.log("Seattle was not configured to run on startup because " \
                        + startup_script_path + " cannot be created.")
    return False

  # Writes the startup script content to the startup script file.
  try:
    startup_script_handle.write(startup_script_content)
  except:
    _output("Cannot write to the startup script file. Make sure you have the " \
              + "permission to do so.")
    servicelogger.log("Seattle was not configured to run on startup because " \
                        + startup_script_path + " cannot be written to.")
    return False
  finally:
    startup_script_handle.close()

  # Derek Cheng: This is for changing the permission bits on the startup scripts
  # on the Nokia tablet. (i.e., stat.S_IXUSR gives owner permission to execute)
  # JAC: this is only needed on the Nokia, so is imported here since stat isn't
  # portable
  import stat
  # Changes the permission bits of the startup script to executable by owner.
  try:
    os.chmod(startup_script_path, stat.S_IXUSR)
  except:
    _output("Cannot change the startup script permission to executable. Make " \
              + "sure you have the permission to do so.")
    servicelogger.log("Seattle was not configured to run on startup because " \
                        + "permissions of " +  startup_script_path + \
                        " cannot be changed.")
    # This is an attempt to clean up by removing the script file if chmod fails.
    try:
      os.remove(startup_script_path)
    except:
      pass
    return False

  # Creates the symlink to the startup script at symlink_dir.
  try:
    os.symlink(startup_script_path, symlink_path)
  except:
    _output("Cannot create symlink to the startup script. Make sure you have " \
              + "the permission to do so.")
    servicelogger.log("Seattle was not configured to run on startup because " \
                        + " the symlink " + symlink_path + " cannot be " \
                        + "created.")
    # Attempt to clean up by removing the startup script.
    try:
      os.remove(startup_script_path)
    except:
      pass
    return False

  servicelogger.log("Seattle has been configured to run on startup. Two " \
                      + "files were created: " + startup_script_path + " and " \
                      + symlink_path +".")
  return True


# Added function for setting up the startup of Seattle on the OpenWrt firmware.
# This is to be called from setup_linux_or_mac() since the OpenWrt runs on a
# Linux-based OS.
def setup_openwrt_startup():
  """
  <Purpose>
    Sets up seattle to run at startup on a OpenWrt firmware. It creates a 
    init.d script, e.g./etc/init.d/seattle that will in turn run start_seattle.sh, 
    then enable the init script. This init script will cause Seattle to run on 
    startup.

  <Arguments>
    None.
    
  <Exceptions>
    AlreadyInstalledError if seattle has already been installed on the system.

  <Side Effects>
    None.

  <Returns>
    True if the files are created successfully,
    False otherwise.
  """
  

  # Note to developers: If you need to change the path of the startup script, 
  # make sure you keep it consistent with those in test_seattle_is_installed()
  # and seattleuninstaller.py.

  startup_script_name = "seattle"
  # The directory where the startup script will reside
  startup_script_dir = "/etc/init.d/"
  # The full path to the startup script.
  startup_script_path = startup_script_dir + startup_script_name

  # The name of the symlink that links to the startup script.
  symlink_name = "S99seattle"
  # The directory where the symlink to the startup script will reside.
  symlink_dir = "/etc/rc.d/"
  # The full path to the symlink.
  symlink_path = symlink_dir + symlink_name
  
  # If the startup script already exists prior to this 
  # installation, an AlreadyInstalledError is raised.
  if os.path.exists(startup_script_path) or os.path.exists(symlink_path):
    _output("The files that are required for running Seattle on startup " \
              + "already exists. If you would like a clean installation, " \
              + "please run the uninstaller first to remove those files.")
    servicelogger.log("The startup files were not added to the /etc/ " \
                        + "directories because they already existed prior to " \
                        + "the installation.")
    raise AlreadyInstalledError()

  # The contents of the startup script in its entirety.
  # This line indicates that it is a shell script.
  startup_script_content = "#! /bin/sh /etc/rc.common" + "\n"
  startup_script_content += "START=99 \n"
  startup_script_content += "start() { \n"
  startup_script_content += "         export PATH=$PATH:/opt/usr/bin:/opt/usr/sbin \n" 
  startup_script_content += "         export LD_LIBRARY_PATH=/opt/lib:/opt/usr/lib \n" 
  startup_script_content += "         sh " + os.path.realpath(get_starter_file_name()) + "\n"
  startup_script_content += "} \n"

  # Creates the startup script file.
  try:
    startup_script_handle = file(startup_script_path, 'w')
  except:
    _output("Cannot create startup script file. Make sure you have the " \
              + "enough space to do so.")
    servicelogger.log("Seattle was not configured to run on startup because " \
                        + startup_script_path + " cannot be created.")
    return False

  # Writes the startup script content to the startup script file.
  try:
    startup_script_handle.write(startup_script_content)
  except:
    _output("Cannot write to the startup script file. Make sure you have the " \
              + "permission to do so.")
    servicelogger.log("Seattle was not configured to run on startup because " \
                        + startup_script_path + " cannot be written to.")
    return False
  finally:
    startup_script_handle.close()

  # Enable the init script.
  try:
    os.system("chmod +x " + startup_script_path)
    os.system(startup_script_path + " enable")
  except:
    _output("Cannot enable the init script ")
    servicelogger.log("Seattle was not configured to run on startup because " \
                        + " the init script " + startup_script_path + " cannot be " \
                        + "enabled.")


  servicelogger.log("Seattle has been configured to run on startup. Two " \
                      + "files were created: " + startup_script_path + ".")
  return True




def setup_linux_or_mac_startup():
  """
  <Purpose>
    Sets up seattle to run at startup on this Linux or Macintosh machine. This
    means adding an entry to crontab after running tests to make sure that cron
    is running and that the user has the ability to modify the crontab.  If any
    of these tests show problems, the appropriate output is given to the user.
    Otherwise, if seattle is successfully configured to run automatically at
    machine boot, then no output is given to the user.
    For Nokia N800/900 Tablets, crontab will not be used. Instead, two files 
    are created in the special directories (/etc/init.d and /etc/rc2.d by
    default) that will cause Seattle to run on startup.
    For OpenWrt firmware, crontab will not be used. Instead, two files 
    are created in the special directories (/etc/init.d and /etc/rc.d by
    default) that will cause Seattle to run on startup.
  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the os is not supported.
    AlreadyInstalledError if seattle has already been installed on the system.
    cron nor crond are found on this system.

  <Side Effects>
    None.

  <Returns>
    True if the crontab was able to be modified,
    False otherwise.
  """

  if OS != "Linux" and OS != "Darwin":
    raise UnsupportedOSError

  # Derek Cheng: check to see if Seattle is being installed on a Nokia tablet.
  #if platform.machine().startswith('armv'):
  #  return setup_nokia_startup()
  # Check to see if Seattle is being installed on a OpenWrt firmware. 
  if platform.machine().startswith('mips'):
    return True

  _output("Attempting to add an entry to the crontab...")

  # The error_output will only be displayed to the user if the ultimate attempt
  # to add an entry to the crontab fails.
  error_output = ""

  # First, check to see that cron is running.
  # This variable is declared here because it is referenced later outside the
  # try:block statement. In the unlikely event that an unpredicted exception is
  # raised while checking if cron is running, it will be determined later by 
  # noting that the value of this variable is None rather than a boolean value.
  cron_is_running = None
  # If the following check raises a general exception, fall through to continue 
  # attempting to set up the crontab since we want the crontab to be set up
  # properly in case this user is able to use cron in the future.
  try:
    cron_is_running,executable_cron_file = test_cron_is_running()

  except CannotDetermineCronStatusError:
    # This exception means cron is installed, though whether or not it is
    # running cannot be determined.
    error_output = error_output + "It cannot be determined whether or not " \
        + "cron is installed and running. Please confirm with the root user " \
        + "that cron is installed and indeed running. If you believe cron is " \
        + "running on your system and seattle does not get configured to run " \
        + "automatically at startup, please read the following instructions " \
        + "or contact the seattle development team if no further " \
        + "instructions are given.\n"

  except Exception,e:
    # If there is an unexpected exception raised when accessing cron, fall
    # through the try: block to continue trying to set up the crontab.
    pass
  else:
    if not cron_is_running:
      _output("cron is not currently running on your system. Only the root " \
                + "user may start cron by running the following command:")
      _output(str(executable_cron_file) + " start")
      _output("An attempt to setup crontab to run seattle at startup will " \
                + "still be made, although seattle will not automatically " \
                + "run at startup until cron is started as described above.")
      servicelogger.log("cron is not running on this system at install time.")




  # Second, check that the user has permission to use cron. If this check raises
  # a general exception, fall through to continue attempting to set up the
  # crontab since we want the crontab to be set up properly in case this user
  # is able to use cron in the future.
  try:
    crontab_accessible,cron_deny_permission_filepath = test_cron_accessibility()

  except CronAccessibilityFilesPermissionDeniedError,c:
    error_output = error_output + "One or both of the files listing users " \
        + "who have access and who do not have access to use cron have been " \
        + "found, but this user does not have permission to read them. If " \
        + "seattle does not get configured to run automatically at machine " \
        + "boot, it is possible that it is because this user name must be " \
        + "listed in the cron 'allow' file which can be found in the man " \
        + "document for crontab (found by running the command 'man crontab' " \
        + "from the terminal).\n"

  except CronAccessibilityFilesNotFoundError,n:
    error_output = error_output + "The cron allow and deny files, which " \
        + "specify which users have permission to use the cron service, " \
        + "cannot be found.  If seattle is not able to be configured to " \
        + "run automatically at startup, it may be that your user name " \
        + "needs to be added to the cron allow file. The location of this " \
        + "cron allow file can be found in the man document for crontab " \
        + "(found by running the command 'man crontab' from the terminal).\n"

  except DetectUserError,d:
    error_output = error_output + "The cron accessibility files were found, " \
        + "but the current user name could not be determined; therefore, the " \
        + "ability for this user to use the cron service could not be " \
        + "determined. If seattle fails to be configured to run " \
        + "automatically at startup, it is probable that the user name needs " \
        + "be added to the cron allow file. The location of the cron allow " \
        + "file can be found in the man document for crontab (found by " \
        + "running the command 'man crontab' from the terminal).\n"

  except Exception,e:
    # If there is an unexpected exception raised when accessing the
    # allow/deny files, fall through the try: block to continue trying to set up
    # the crontab.
    pass
  else:
    if not crontab_accessible:
      _output("You do not have permission to use cron which makes seattle " \
                + "run automatically at startup. To get permission to use " \
                + "the cron service, the root user must remove your user " \
                + "name from the " + str(cron_deny_permission_filepath) \
                + " file.")
      servicelogger.log("seattle was not added to the crontab because the " \
                          + "user does not have permission to use cron.")
      return False




  # Lastly, add seattle to the crontab.
  try:
    successfully_added_to_crontab = add_seattle_to_crontab()

  except AlreadyInstalledError,a:
    raise AlreadyInstalledError()

  except Exception:
    if not error_output:
      _output("seattle could not be configured to run automatically at " \
                + "startup on your machine for an unknown reason. It is " \
                + "that you do not have permission to access crontab. Please " \
                + "contact the seattle development team for more assistance.")
      servicelogger.log("seattle could not be successfully added to the " \
                          + "crontab for an unknown reason, although it is " \
                          + "likely due to the user not having permission to " \
                          + "use crontab since an exception was most likely " \
                          + "raised when the 'crontab -l' command was run.")
    else:
      _output("seattle could not be configured to run automatically at " \
                + "machine boot. Following are more details:")
      _output(error_output)
      servicelogger.log("seattle could not be successfully added to the " \
                          + "crontab. Following was the error output:")
      servicelogger.log(error_output)

    return False

  else:
    # Zack Boka: modify nodeman.cfg if the crontab was successfully installed so
    #            nmmain.py knows that the correct seattle crontab entry is
    #            installed.
    if successfully_added_to_crontab:
      configuration = persist.restore_object("nodeman.cfg")
      configuration['crontab_updated_for_2009_installer'] = True
      persist.commit_object(configuration,"nodeman.cfg")

      if cron_is_running == None:
        _output("seattle was configured to start automatically at machine " \
                  + "startup; however, an error occured when trying to " \
                  + "detect if cron, the program that starts seattle at " \
                  + "machine startup, is actually running.  If cron is not " \
                  + "running, then seattle will NOT automatically start up " \
                  + "at machine boot.  Please check with the root user to " \
                  + "confirm that cron is installed and indeed running. Also " \
                  + "confirm that you have access to use cron.")
        return None
      else:
        return cron_is_running


    else:
      if cron_is_running and not error_output:
        # Since cron is running, that could not have been the problem, so output
        # to the user that it is unknown what seattle could not be configured to
        # start at boot.
        _output("seattle could not be configured to run automatically at " \
                  + "startup on your machine for an unknown reason. Please " \
                  + "contact the seattle development team for assistance.")
        servicelogger.log("seattle could not be successfully added to the " \
                            + "crontab for an unknown reason.")
      elif not cron_is_running and not error_output:
        # Despite cron not running, crontab could also not be modified for an
        # unknown reason.  We must output a message separate from above to not
        # confuse the user since we already reported that cron is not running.
        _output("seattle could not be configured to run automatically at " \
                  + "startup on your machine for an unknown reason, despite " \
                  + "cron not running. Please contact the seattle " \
                  + "development team for assistance.")
        servicelogger.log("seattle could not be successfully added to the " \
                            + "crontab for an unknown reason, other than the " \
                            + "face that cron is not running.")
        return False
      else:
        _output("seattle could not be configured to run automatically at " \
                  + "machine boot.  Following are more details:")
        _output(error_output)
        servicelogger.log("seattle could not be successfully added to the " \
                            + "crontab. Following was the error output:")
        servicelogger.log(error_output)


      # Although the default setting for
      # config['crontab_updated_for_2009_installer'] = False, it should still be
      # set in the event that there was a previous installer which set this
      # value to True, but now for whatever reason, installation in the crontab
      # failed.
      configuration = persist.restore_object("nodeman.cfg")
      config['crontab_updated_for_2009_installer'] = False
      persist.commit_object(config,'nodeman.cfg')
        
      return False




def customize_win_batch_files():
  """
  <Purpose>
    Preprocesses the Windows batch files to replace all instances of %PROG_PATH%
    and %STARTER_FILE% with their appropriate specified values.
    
    %PROG_PATH% is used in the scripts to specify the absolute filepath to
    the location to that batch file, primarily so the user does not have to be
    in the seattle directory to use the scripts.

    %STARTER_FILE% is used in the scripts to specify the absolute filepath to
    the location of the starter script in the startup folder (regardless of
    whether or not the file actually exists in the startup folder). This is so
    the starter batch file and uninstall batch file can appropriately remove
    this file in the event that the starter file may still appear in the 
    startup folder even if install succeeds in installing seattle in the Windows
    registry. (It will be rare that uninstall.bat will need this, but
    start_seattle.bat may need this file path in case it must remove itself from
    the startup folder in the even that the user deletes the seattle directory
    without uninstalling.)

    Currently, only start_seattle_shortcut.bat and uninstall.bat are
    preprocessed with this function.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if OS is not Windows\WindowsCE.
    IOError may be called by child-function on being passed a bad file name.

  <Side Effects>
    Changes all instances of %PROG_PATH% and %STARTER_FILE% in the below-
    specified files to the appropriate absolute filepath.

  <Returns>
    None.
  """
  if OS != "Windows" and OS != "WindowsCE":
    raise UnsupportedOSError("This must be a Windows system in order to " \
                               + "modify Windows batch files.")

  _output("Customizing seattle batch files...")
    
  # Customize the start_seattle_shortcut.bat and uninstall.bat files.
  full_startup_file_path,file_path_exists = \
      get_filepath_of_win_startup_folder_with_link_to_seattle()
  for batchfile in [get_starter_shortcut_file_name(),
                    get_uninstaller_file_name()]:
    preprocess_file(SEATTLE_FILES_DIR + os.sep + batchfile,
                    {"%PROG_PATH%": SEATTLE_FILES_DIR,
                     "%STARTER_FILE%": full_startup_file_path})




def setup_sitecustomize():
  """
  <Purpose>
    On Windows CE, edits the sitecustomize.py file to reference the right
    program path, then copies it to the python directory.

  <Arguments>
    None.

  <Exceptions>
    Raises UnsupportedOSError if the version is not Windows CE.
    Raises IOError if the original sitecustomize.py file doesn't exist or 
    if the python path specified in repy_constants doesn't exist.

  <Side Effects>
    None.
    
  <Returns>
    None.
  """
  original_fname = SEATTLE_FILES_DIR + os.sep + "sitecustomize.py"
  if not OS == "WindowsCE":
    raise UnsupportedOSError
  elif not os.path.exists(original_fname):
    raise IOError("Could not find sitecustomize.py under " + SEATTLE_FILES_DIR)
  else: 
    python_dir = os.path.dirname(repy_constants.PATH_PYTHON_INSTALL)
    if not os.path.isdir(python_dir):
      raise IOError("Could not find repy_constants.PATH_PYTHON_INSTALL")
    elif os.path.exists(python_dir + os.sep + "sitecustomize.py"):
      raise IOError("sitecustomize.py already existed in python directory")
    else:
      preprocess_file(original_fname,{"%PROG_PATH%": SEATTLE_FILES_DIR})
      shutil.copy(original_fname, python_dir + os.sep + "sitecustomize.py")




def start_seattle():
  """
  <Purpose>
    Starts seattle by running the starter file on any system.

  <Arguments>
    None.

  <Exceptions>
    IOError if the starter file can not be found under SEATTLE_FILES_DIR.

  <Side Effects>
    None.

  <Returns>
    None.
  """
  starter_file_path = [SEATTLE_FILES_DIR + os.sep + get_starter_file_name()]
  if OS == "WindowsCE":
    windows_api.launch_python_script(starter_file_path)
  else:
    if SILENT_MODE:
      p = subprocess.Popen(starter_file_path,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    else:
      p = subprocess.Popen(starter_file_path)

    p.wait()




# Anthony Honstain's benchmarking function.
def perform_system_benchmarking():
  """
  <Purpose>
    To call benchmark_resources.main (which performs the system 
    benchmarking (to find the resources available to the user installing), 
    calculate the amount that is to be donated, and then generate the 
    vessel resource files, vessel directories, and the vesseldict.) and
    handle any exceptions that may be raised, logging information and
    output useful information to the user installing seattle. 

  <Arguments>
    None

  <Exceptions>
    IOError if unable to create a log file.

  <Side Effects>
    May initialize the service logger 'installInfo'.
    
    Will create or append a temporary log file 'installer_benchmark.log'
    that will be used during the benchmark process, if the benchmarking is 
    successful it will be removed.
    
    Creates the vessel resource files, vessel directories, and the
    vesseldict.
    
    The benchmarking will look to several OS specific sources for 
    information, and perform benchmarking that includes retrieving
    random numbers and creating a file to measure read/write rate.
    WARNING: These benchmarks may take a noticeable amount of time 
    or consume more resources than normal.
    
  <Returns>
    Returns True if the benchmarking and creation of vessel structure
    is complete, if those failed then False is returned.

  """
  # Run the benchmarks to benchmark system resources and generate
  # resource files and the vesseldict.
  _output("System benchmark starting...")
  # Anthony - this file will be logged to until the v2 directory has
  # been created, this will not happen until after the benchmarks
  # have run and the majority of the installer state has been created.
  benchmark_logfileobj = file("installer_benchmark.log", 'a+')
    
  try:
    benchmark_resources.main(SEATTLE_FILES_DIR, RESOURCE_PERCENTAGE,
                             benchmark_logfileobj)
  except benchmark_resources.BenchmarkingFailureError:
    _output("Installation terminated.")
    _output("Please email the Seattle project for additional support, and " \
              + "attach the installer_benchmark.log and vesselinfo files, " \
              + "found in the seattle_repy directory, in order to help us " \
              + "diagnose the issue.")
    benchmark_logfileobj.close()
    return False
  except benchmark_resources.InsufficientResourceError:
    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
    traceback.print_exception(exceptionType, exceptionValue, \
                              exceptionTraceback, file=benchmark_logfileobj)
    _output("Failed.")
    _output("This install cannot succeed because resources are insufficient. " \
              + "This could be because the percentage of donated resources " \
              + "is too small or because a custom install had too many " \
              + "vessels.")
    _output("Please email the Seattle project for additional support, and " \
              + "attach the installer_benchmark.log and vesselinfo files, " \
              + "found in the seattle_repy directory, in order to help us " \
              + "diagnose the issue.")
    benchmark_logfileobj.close()
    return False
  except Exception:
    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
    traceback.print_exception(exceptionType, exceptionValue, \
                              exceptionTraceback, file=benchmark_logfileobj)
    _output("Failed.")
    _output("This install cannot succeed either because required " \
              + "installation info is corrupted or resources are insufficient.")
    _output("Please email the Seattle project for additional support, and " \
              + "attach the installer_benchmark.log and vesselinfo files, " \
              + "found in the seattle_repy directory, in order to help us " \
              + "diagnose the issue.")
    benchmark_logfileobj.close()
    return False
  
  else:
    # Transfer the contents of the file used to log the benchmark and creation
    # of vessel states. The service logger cannot be used sooner because
    # the seattle vessel directory has not yet been created.
    benchmark_logfileobj.seek(0)
    servicelogger.log(benchmark_logfileobj.read())
    benchmark_logfileobj.close()
    os.remove(benchmark_logfileobj.name)
    
    _output("Benchmark complete and vessels created!")
    return True




# Anthony Honstain's test urandom function.
def test_urandom_implemented():
  """
  <Purpose>
    This will test if os.urandom is implemented on the OS
    If we did not check here and os.urandom raised a NotImplementedError
    then the install would surely fail when it attempted to generate
    a RSA key (the key generation requires that os.urandom work).
    
    It should be noted that even if installation no longer required
    key generation, currently all random numbers for vessels
    come from this source, so when ever os.urandom is called it
    would result in an internal error.

  <Arguments>
    None

  <Exceptions>
    None

  <Side Effects>
    Make a call to a Operating System specific source of 
    cryptographically secure pseudo random numbers.
    
    Outputs instructions to the user installing seattle if their
    system fails.
    
  <Returns>
    True if the test succeeded, 
    False otherwise.
  """
  # Anthony - This will test if os.urandom is implemented on the OS
  # If we did not check here and os.urandom raised a NotImplementedError
  # the next step (setup_start) would surely fail when it tried
  # to generate a key pair.
  try:
    os.urandom(1)
  except NotImplementedError:
    _output("Failed.")
    _output("No source of OS-specific randomness")
    _output("On a UNIX-like system this would be /dev/urandom, and on " \
              + "Windows it is CryptGenRandom.")
    _output("Please email the Seattle project for additional support.")
    return False
  else:
    # Test succeeded!
    return True




def prepare_installation(options,arguments):
  """
  <Purpose>
    Prepare all necessary global variables and files for the actual installation
    process.  This includes combing through the arguments passed to the installer
    to set the appropriate variables and setting the Node Manager configuration
    information (in nodeman.cfg file).

  <Arguments>
    options:
      A list of tuples (flag,value) where flag is the argument name passed to
      the installer (e.g., --nm-key-bitsize) and value is the value for that
      particular flag (e.g., 1024).  Example element that could appear in the
      list described by options: ("--nm-key-bitsize","1024")

    arguments:
      A list of arguments that did not have an argument name associated with it
      (e.g., Specifying the install directory. See [install_dir] in usage())

  <Exceptions>
    IOError if the specified install directory does not exist.

  <Side Effects>
    Changes default local and global variables, and injects relevant information
    into the Node Manager configuration file (nodeman.cfg).

  <Return>
    True if this entire prepare_installation() process finished,
    False otherwise (meaning an argument was passed that calls for install to be
    halted [e.g., --usage] or a value for one of the named arguments is
    unreasonable [e.g., setting the resource percentage to be %0].).
  """
  global SILENT_MODE
  global RESOURCE_PERCENTAGE
  global KEYBITSIZE
  global DISABLE_STARTUP_SCRIPT
  global DISABLE_INSTALL

  # Armon: Specify the variables that will be used to generate the Restrictions
  # Information for the NM and Repy.
  repy_restricted = False
  repy_nootherips = False
  repy_user_preference = []
  nm_restricted = False
  nm_user_preference = []
  repy_prepend = []
  repy_prepend_dir = None

  # Iterate through and process the arguments, checking for IP/Iface
  # restrictions.
  for (flag, value) in options:
    if flag == "-s":
      SILENT_MODE = True
    elif flag == "--onlynetwork":
      disable_install = True
    elif flag == "--percent":
      # Check to see that the desired percentage of system resources is valid
      # I do not see a reason someone couldn't donate 20.5 percent so it
      # will be allowed for now.
      try:
        RESOURCE_PERCENTAGE = float(value)
      except ValueError:
        usage()
        return False
      if RESOURCE_PERCENTAGE <= 0.0 or RESOURCE_PERCENTAGE > 100.0:
        usage()
        return False
    elif flag == "--nm-ip":
      nm_restricted = True
      nm_user_preference.append((True, value))
    elif flag == "--nm-iface":
      nm_restricted = True
      nm_user_preference.append((False, value))
    elif flag == "--repy-ip":
      repy_restricted = True
      repy_user_preference.append((True, value))
    elif flag == "--repy-iface":
      repy_restricted = True
      repy_user_preference.append((False,value))
    elif flag == "--repy-nootherips":
      repy_restricted = True
      repy_nootherips = True
    elif flag == "--nm-key-bitsize":
      KEYBITSIZE = int(value)
    elif flag == "--disable-startup-script":
      DISABLE_STARTUP_SCRIPT = True
    elif flag == "--usage":
      usage()
      return False
    elif flag == "--repy-prepend":
      repy_prepend.extend(value.split())
    elif flag == "--repy-prepend-dir":
      repy_prepend_dir = value

  # Print this notification after having processed all the arguments in case one
  # of the arguments specifies silent mode.
  if DISABLE_STARTUP_SCRIPT:
    _output("Seattle will not be configured to run automatically at boot.")
    

  # Build the configuration dictionary.
  config = {}
  config['nm_restricted'] = nm_restricted
  config['nm_user_preference'] = nm_user_preference
  config['repy_restricted'] = repy_restricted
  config['repy_user_preference'] = repy_user_preference
  config['repy_nootherips'] = repy_nootherips 

  # Armon: Inject the configuration information.
  configuration = persist.restore_object("nodeman.cfg")
  configuration['networkrestrictions'] = config
  configuration['repy_prepend'] = repy_prepend
  configuration['repy_prepend_dir'] = repy_prepend_dir
  persist.commit_object(configuration,"nodeman.cfg")

  # Tell the parent function that the passed-in arguments allow it to continue
  # with the installation.
  return True




def test_seattle_is_installed():
  """
  <Purpose>
    Tests to see if Seattle is already installed on this computer.

  <Arguments>
    None.

  <Exceptions>
    UnsupportedOSError if the os is not supported.

  <Side Effects>
    None.

  <Returns>
    True if Seattle is installed, False otherwise.
  """
  
  if OS == "Windows" or OS == "WindowsCE":

    # Tests if Seattle is set to run at user login.
    # See comments in add_to_win_registry_Current_User_key() for details.
    try:
      Current_User_key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                          "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                          0, _winreg.KEY_ALL_ACCESS)
    except WindowsError:
      pass
    else:
      Current_User_key_exists = search_value_in_win_registry_key(
                                              Current_User_key, "seattle")
      _winreg.CloseKey(Current_User_key)
      if Current_User_key_exists:
        return True

    # Tests if Seattle is set to run at machine startup.
    # See comments in add_to_win_registry_Local_Machine_key() for details.
    try:
      Local_Machine_key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                          "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                          0, _winreg.KEY_ALL_ACCESS)
    except WindowsError:
      pass
    else:
      Local_Machine_key_exists = search_value_in_win_registry_key(
                                              Local_Machine_key, "seattle")
      _winreg.CloseKey(Local_Machine_key)
      if Local_Machine_key_exists:
        return True

    # If neither registry key is present, then test if there is a shortcut
    # to Seattle in the startup folder to determine if Seattle is installed.
    full_startup_file_path,file_path_exists = \
              get_filepath_of_win_startup_folder_with_link_to_seattle()
    return file_path_exists

  elif OS == "Linux" or OS == "Darwin":

    # Check to see if Seattle is being installed on a Nokia tablet.
    #if platform.machine().startswith('armv'):
    #  # The full path to the startup script.
    #  startup_script_path = "/etc/init.d/nokia_seattle_startup.sh"
    #  # The full path to the symlink.
    #  symlink_path = "/etc/rc2.d/S99startseattle"
    #  
    #  # If the startup script or the symlink exist, then Seattle was installed.
    #  return os.path.exists(startup_script_path) or \
    #            os.path.lexists(symlink_path)

    # Check to see if Seattle is being installed on a OpenWrt.
    #if platform.machine().startswith('mips'):
    #  # The full path to the startup script.
    #  startup_script_path = "/etc/init.d/seattle"
    #  # The full path to the symlink.
    #  symlink_path = "/etc/rc.d/S99seattle"
    #  
    #  # If the startup script or the symlink exist, then Seattle was installed.
    #  return os.path.exists(startup_script_path) or \
    #            os.path.lexists(symlink_path)

    #else:
      # Check to see if the crontab has been modified to run seattle.
      crontab_contents_stdout,crontab_contents_stderr = \
          subprocess.Popen(["crontab", "-l"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE).communicate()
      return get_starter_file_name() in crontab_contents_stdout

  else:
    raise UnsupportedOSError()




def usage():
  """
  Prints command line usage of script.
  """

  if OS == "Windows" or OS == "WindowsCE":
    print "install.bat",
  elif OS == "Linux" or OS == "Darwin":
    print "install.sh",
  else:
    print "python seattleinstaller.py",

  print "[-s] [--usage] " \
      + "[--disable-startup-script] [--percent float] " \
      + "[--nm-key-bitsize bitsize] [--nm-ip ip] [--nm-iface iface] " \
      + "[--repy-ip ip] [--repy-iface iface] [--repy-nootherips] " \
      + "[--onlynetwork] [--repy-prepend args] [--repy-prepend-dir dir]"
  print "Info:"
  print "-s\t\t\t\tSilent mode: does not print output."
  print "--disable-startup-script\tDoes not install the Seattle startup " \
      + "script, meaning that Seattle will not automatically start running " \
      + "at machine start up. It is recommended that this option only be " \
      + "used in exceptional circumstances."
  print "--percent percent\t\tSpecifies the desired percentage of available " \
      + "system resources to donate. Default percentage: " \
      + str(RESOURCE_PERCENTAGE)
  print "--nm-key-bitsize bitsize\tSpecifies the desired bitsize of the Node " \
      + "Manager keys. Default bitsize: " + str(KEYBITSIZE)
  print "--nm-ip IP\t\t\tSpecifies a preferred IP for the NM. Multiple may " \
      + "be specified, they will be used in the specified order."
  print "--nm-iface iface\t\tSpecifies a preferred interface for the NM. " \
      + "Multiple may be specified, they will be used in the specified order."
  print "--repy-ip, --repy-iface. See --nm-ip and --nm-iface. These flags " \
      + "only affect repy and are separate from the Node Manager."
  print "--repy-nootherips\t\tSpecifies that repy is only allowed to use " \
      + "explicit IP's and interfaces."
  print "--onlynetwork\t\t\tDoes not install Seattle, but updates the " \
      + "network restrictions information."
  print "--repy-prepend args\t\tSpecifies a list of arguments to be " \
      + "prepended to any repy program run by the user. If multiple argument " \
      + "lists are specified, they will be concatenated."
  print "--repy-prepend-dir dir\t\tSpecifies a directory containing files to " \
      + "be copied to newly created vessels."
  print "See https://seattle.cs.washington.edu/wiki/SecurityLayers for " \
      + "details on using --repy-prepend and --repy-prepend-dir to " \
      + "construct custom security layers."




def main():
  if OS not in SUPPORTED_OSES:
    raise UnsupportedOSError("This operating system is not supported.")


  # Begin pre-installation process.

  # Pre-install: parse the passed-in arguments.
  try:
    # Armon: Changed getopt to accept parameters for Repy and NM IP/Iface
    # restrictions, also a special disable flag
    opts, args = getopt.getopt(sys.argv[1:], "s",
                               ["percent=", "nm-key-bitsize=","nm-ip=",
                                "nm-iface=","repy-ip=","repy-iface=",
                                "repy-nootherips","onlynetwork",
                                "disable-startup-script","usage",
                                "repy-prepend=", "repy-prepend-dir="])
  except getopt.GetoptError, err:
    print str(err)
    usage()
    return


  # Check if Seattle is already installed. This needs to be done seperately
  # from setting Seattle to run at startup because installation might fail
  # during the pre-installation process.
  if test_seattle_is_installed():
    _output("Seattle was already installed. You must run the uninstall " \
              + "script before reinstalling Seattle.")
    return


  # Initialize the service logger.
  servicelogger.init('installInfo')
  
  if platform.machine().startswith('mips'):
     _output('Seattle is being installed on a OpenWrt firmware.')

  # This catches Nokias/Androids/iPhones/iPads
  if platform.machine().startswith('armv'):
    # AR: The Android installer is a GUI, stdout/stderr are redirected to files.
    try:
      import android
      global IS_ANDROID
      IS_ANDROID = True
      sys.stdout = open('installerstdout.log', 'w')
      sys.stderr = open('installerstderr.log', 'w')
      _output('Seattle is being installed on an Android compatible handset.')

    except ImportError:
      IS_ANDROID = False

    # Derek Cheng: if the user is running a Nokia N800 tablet, we require them
    # to be on root first in order to have files created in the /etc/init.d and
    # /etc/rc2.d directories. 
    #if IS_ANDROID == False:
    #  _output('Seattle is being installed on a Nokia N800/900 Internet Tablet.')
    #  # JAC: I can't import this on Windows, so will do it here...
    #  import pwd
    #  # if the current user name is not 'root'
    #  if pwd.getpwuid(os.getuid())[0] != 'root':
    #    _output('Please run the installer as root. This can be done by ' \
    #              + 'installing/using the rootsh or openssh package.')
    #    return

  # Pre-install: process the passed-in arguments, and set up the configuration
  #   dictionary.
  continue_install = prepare_installation(opts,args)
  if not continue_install:
    return

  # Pre-install: run all tests and benchmarking.
  #   test_urandom_implemented() MUST be performed before
  #   perform_system_benchmarking() to get relevant results from the
  #   benchmarking.
  urandom_test_succeeded = test_urandom_implemented()
  if not urandom_test_succeeded:
    return
  benchmarking_succeeded = perform_system_benchmarking()
  if not benchmarking_succeeded:
    return



  # Begin installation.
  if DISABLE_INSTALL:
    return
  
  # First, customize any scripts since they may be copied to new locations when
  # configuring seattle to run automatically at boot.


  # If running on a Windows system, customize the batch files.
  if OS == "Windows" or OS == "WindowsCE":
    customize_win_batch_files()
    _output("Done!")

  # If running on WindowsCE, setup the sitecustomize.py file.
  if OS == "WindowsCE":
    _output("Configuring python for WindowsCE...")
    setup_sitecustomize()
    _output("Done!")

    
   
  # Configure seattle to run at startup.
  if not DISABLE_STARTUP_SCRIPT:
    _output("Preparing Seattle to run automatically at startup...")
    # This try: block attempts to install seattle to run at startup. If it
    # fails, continue on with the rest of the install process since the seattle
    # starter script may still be run even if seattle is not configured to run
    # at boot.
    try:
      # Any errors generated while configuring seattle to run at startup will be
      # printed in the child functions, unless an unexpected error is raised,
      # which will be caught in the general except Exception: block below.
      if OS == "Windows" or OS == "WindowsCE":
        setup_win_startup()
        _output("Seattle is setup to run at startup!")
      elif OS == "Linux" or OS == "Darwin":
        setup_success = setup_linux_or_mac_startup()
        if setup_success == None:
          # Do not print a final message to the user about setting up seattle to
          # run automatically at startup.
          pass
        elif setup_success:
          _output("Seattle is setup to run at startup!")
        else:
          # The reasons for which seattle was unable to be configured at startup
          # will have been logged by the service logger in the
          # setup_linux_or_mac_startup() function, and output for the possible
          # reasons why configuration to run at startup failed will have already
          # be given to the user from the setup_linux_or_mac_startup() function.
          _output("Seattle failed to be configured to run automatically at " \
                    + "startup.")
      else:
        raise UnsupportedOSError("This operating system is not supported.")

    except UnsupportedOSError,u:
      raise UnsupportedOSError(u)

    # If an unpredicted error is raised while setting up seattle to run at
    # startup, it is caught here.
    except Exception,e:
      _output("seattle could not be installed to run automatically at " \
                + "startup for the following reason: " + str(e))
      _output("Continuing with the installation process now.  To manually " \
                + "run seattle at any time, just run " \
                + get_starter_file_name() + " from within the seattle " \
                + "directory.")
      _output("Please contact the seattle project for further assistance.")
      servicelogger.log(time.strftime(" seattle was NOT installed on this " \
                                        + "system for the following reason: " \
                                        + str(e) + ". %m-%d-%Y  %H:%M:%S"))



  # Generate the Node Manager keys even if configuring seattle to run
  # automatically at boot fails because Node Manager keys are needed for the
  # seattle_starter script which can be run at any time.
  _output("Generating the Node Manager RSA keys.  This may take a few " \
            + "minutes...")
  createnodekeys.initialize_keys(KEYBITSIZE,
                                 nodemanager_directory=SEATTLE_FILES_DIR)
  _output("Keys generated!")



  # Modify nodeman.cfg so the start_seattle script knows that seattle has been
  # installed.  This is a new feature that will require seattle to have been
  # installed before it can be started.
  configuration = persist.restore_object("nodeman.cfg")
  configuration['seattle_installed'] = True
  persist.commit_object(configuration,"nodeman.cfg")

  


  # Everything has been installed, so start seattle and print concluding output
  # messages.
  # AR: On Android, the native installer/app takes care of starting Seattle 
  # after this script ends. (It collects our logs as well).
  try:
    if not IS_ANDROID:
      _output("Starting seattle...")
      start_seattle()
  except Exception,e:
    _output("seattle could not be started for the following reason: " + str(e))
    _output("Please contact the seattle project immediately for assistance.")
    servicelogger.log(time.strftime(" seattle installation failed. seattle " \
                                      + "could not be started for the " \
                                      + "following reason: " + str(e) + " " \
                                      + "%m-%d-%Y %H:%M:%S"))
  else:
    _output("seattle has been installed!")
    _output("To learn more about useful, optional scripts related to running " \
              + "seattle, see the README file.")
    servicelogger.log(time.strftime(" seattle completed installation on: " \
                                      + "%m-%d-%Y %H:%M:%S"))




if __name__ == "__main__":
  main()
	
