"""
<Program Name>
  seattleuninstaller.py
<Started>
  November 8, 2009
<Author>
  Zachary Boka, with some code inspired by Carter Butaud
<Purpose>
  Kills any seattle processes that are running, and removes seattle from any
  startup scripts, locations, keys, or programs.
  Linux/Mac/FreeBSD: remove seattle entry from the crontab.
  Windows: remove seattle from the registry (and the Startup folder if installed
           there).
  NOTE: Unlike seattleinstaller.py, this uninstaller was not created to
        potentially handle WindowsCE.  This uninstaller has no functionality for
        WindowsCE!
"""


import subprocess
import os
import tempfile
import sys
import getopt
import time
# Derek Cheng: This is for detecting Nokia N800/900 tablets.
import platform
# Derek Cheng: This is for detecting error codes when removing the script or
# the link is unsuccessful.
import errno

# Import seattle modules
import persist
import nonportable
import stop_all_seattle_processes
import servicelogger
# import the installer to easily use some of it's functionality (e.g., get the
#   name of the starter scripts, the file path to the windows startup folder,
#   etc.)
import seattleinstaller


SILENT_MODE = False
OS = nonportable.ostype
SUPPORTED_OSES = ["Windows", "WindowsCE", "Linux", "Darwin"]


# OS SPECIFIC
WIN_STARTUP_SCRIPT_PATH = None
WIN_STARTUP_SCRIPT_EXISTS = None
_winreg = None
if OS == "Windows":
  import _winreg
  WIN_STARTUP_SCRIPT_PATH,WIN_STARTUP_SCRIPT_EXISTS = \
      seattleinstaller.get_filepath_of_win_startup_folder_with_link_to_seattle()





class SeattleNotInstalledError(Exception):
  pass

class UnsupportedOSError(Exception):
  pass





def _output(text):
    # For internal use, in case we want to silence the program
    # at some point
    if not SILENT_MODE:
        print text




def remove_value_from_registry_helper(opened_key,remove_value_name):
  """
  <Purpose>
    Removes remove_value_name from opened_key in the Windows Registry.
  <Arguments>
    opened_key:
      A key opened using _winreg.OpenKey(...) or _winreg.CreateKey(...).
    remove_value_name:
      A string of the value name to be removed from opened_key.
  
  <Exceptions>
    WindowsError if the uninstaller is unable to access and manipulate the
    Windows registry, or if opened_key was not previously opened.
  <Side Effects>
    seattle is removed from the Windows registry key opened_key.
  <Returns>
    True if seattle was removed from the registry, False otherwise (indicating
    that seattle could not be found in the registry).
  """
  # The following try: block iterates through all the values contained in the
  # opened key.
  try:
    # The variable "index" will index into the list of values for the opened
    # key.
    index = 0
    # The list that will contain all the names of the values contained in the
    # key.
    value_name_list = []
    # Standard python procedure for _winreg: Continue indexing into the list of
    # values until a WindowsError is raised which indicates that there are no
    # more values to enumerate over.
    while True:
      value_name, value_data, value_type = _winreg.EnumValue(opened_key,index)
      value_name_list.append(value_name)
      index += 1
  except WindowsError:
    # Reaching this point means there are no more values left to enumerate over.
    # If the registry were corrupted, it is probable that a WindowsError will be
    # raised, in which case this function should simply return False.
    pass


  # The following test to see if the value seattle appears in the registry key
  # was not done in real-time in the above while-loop because it is potentially
  # possible that the _winreg.DeleteValue(...) command below could raise a
  # WindowsError.  In that case, it would not be possible for the parent
  # function to know whether the WindowsError was raised because the uninstaller
  # does not have access to the registry or because the value seattle does not
  # exist in the registry key since a WindowsError is raised to exit the while
  # loop when there are no more values to enumerate over.
  if remove_value_name in value_name_list:
    # ARGUMENTS:
    # startkey: the key that contains the value that will be deleted.
    # "seattle": the name of the value that will be deleted form this key.
    _winreg.DeleteValue(opened_key,remove_value_name)
    return True
  else:
    return False




def remove_seattle_from_win_startup_registry():
  """
  <Purpose>
    Removes seattle from the Windows startup registry key.
  <Arguments>
    None.
  
  <Exceptions>
    WindowsError if the uninstaller is unable to access and manipulate the
    Windows registry.
  <Side Effects>
    seattle is removed from the following Windows registry keys which runs
    programs at machine startup and user login:
    HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Run
    HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
  <Returns>
    True if seattle was removed from the registry, False otherwise (indicating
    that seattle could not be found in the registry).
  """

  # The following try: block attempts to remove seattle from the
  # HKEY_LOCAL_MACHINE startup key.  This must be in a try: block in case the
  # user does not have permission to access this key (in which case seattle will
  # not have been installed there anyway).  The uninstall will need to continue
  # without interruption if this is the case.
  removed_from_LM = False
  try:
    # The startup key must first be opened before any operations, including
    # search, may be performed on it.
    # ARGUMENTS:
    # _winreg.HKEY_LOCAL_MACHINE: specifies the key containing the subkey used
    #                             to run programs at machine startup
    #                             (independent of user login).
    # "Software\\Microsoft\\Windows\\CurrentVersion\\Run": specifies the subkey
    #                                                      that runs programs on
    #                                                      machine startup.
    # 0: A reserved integer that must be zero.
    # _winreg.KEY_ALL_ACCESS: an integer that allows the key to be opened with
    #                         all access (e.g., read access, write access,
    #                         manipulaiton, etc.)
    startkey_Local_Machine = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                            "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                             0,_winreg.KEY_ALL_ACCESS)
    removed_from_LM = remove_value_from_registry_helper(startkey_Local_Machine,
                                                 "seattle")
  except Exception, e:
    # Reaching this point means the user must not have access to
    # HKEY_LOCAL_MACHINE.  The user should only be notified about this if the
    # HKEY_CURRENT_USER key fails to be accessed.  The user will be notified in
    # the parent function if this is the case because the below attempt to
    # access HKEY_CURRENT_USER will throw a WindowsError exception.
    pass


  removed_from_CU = False
  # The startup key must first be opened before any operations, including
  # search, may be performed on it.
  # ARGUMENTS:
  # _winreg.HKEY_CURRENT_USER: specifies the key containing the subkey used
  #                             to run programs at user login.
  # "Software\\Microsoft\\Windows\\CurrentVersion\\Run": specifies the subkey
  #                                                      that runs programs on
  #                                                      user login.
  # 0: A reserved integer that must be zero.
  # _winreg.KEY_ALL_ACCESS: an integer that allows the key to be opened with all
  #                         access (e.g., read access, write access,
  #                         manipulaiton, etc.)
  startkey_Current_User = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                            "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                             0,_winreg.KEY_ALL_ACCESS)
  removed_from_CU = remove_value_from_registry_helper(startkey_Current_User,
                                                      "seattle")


  if removed_from_LM or removed_from_CU:
    return True
  else:
    return False

  


def remove_seattle_from_win_startup_folder():
  """
  <Purpose>
    Remove a link to the seattle starter script from the Windows startup folder.
    PRECONDITION: The global variable WIN_STARTUP_SCRIPT_PATH must not = None.
  <Arguments>
    None.
  <Exceptions>
    Possible IOError raised during filepath manipulation.
    An error will be raised if the global variable WIN_STARTUP_SCRIPT_PATH = None
  <Side Effects>
    Removes the link to the seattle starter script from the Windows startup
    folder should it exist there.
  <Returns>
    True if the function removed the link to the seattle starter script in the
    startup folder, False otherwise (indicating that the link did not exist).
  """

  if WIN_STARTUP_SCRIPT_EXISTS:
    os.remove(WIN_STARTUP_SCRIPT_PATH)
    return True
  else:
    return False





def uninstall_Windows():
  """
  <Purpose>
    Removes seattle from the Winodws registry startup key and/or the
    startup folder should either exist, then stops all seattle processes using
    stop_all_seattle_process.py
  <Arguments>
    None.
  <Exceptions>
    Possible IOError could be caused by filepath manipulation from a
      sub-function.
    SeattleNotInstalledError if seattle was not installed prior to uninstall.
  <Side Effects>
    Removes seattle from the Windows registry key and/or the Windows startup
    folder if it exists in either place.
    Stops seattle from running.
  <Returns>
    True if the uninstall succeeded.  Currently, if uninstall fails, it must be
    because seattle was not installed prior to uninstall.  We must return a
    boolean value for the parent function.
  """
  # First see if seattle appears as a value in the Windows startup registry key,
  # and remove it if it exists.
  # removed_from_registry is used later and thus must have a value in case the
  # try: block below raises an exception.
  removed_from_registry = False
  try:
    removed_from_registry = remove_seattle_from_win_startup_registry()
  except WindowsError:
    print "The uninstaller does not have access to the Windows registry " \
        + "startup keys. This means that seattle is likely not installed in " \
        + "your Windows registry startup key, though you may want to " \
        + "manually check the following registry keys and remove seattle " \
        + "from those keys should it exist there: "
    print "HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Run"
    print "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"
    # Distinguish the above-printed text from what will be printed later by
    # by printing a blank line.
    print
    servicelogger.log(" uninstaller could not access the Windows registry " \
                        + "during this attempted uninstall.")



  # Next, see if there is a link to the seattle starter script in the startup
  # folder and remove it if it is there.
  if not WIN_STARTUP_SCRIPT_PATH == None:
    removed_from_startup_folder = \
        remove_seattle_from_win_startup_folder()



  # Check to see if uninstall actually removed seattle from the computer.
  if not removed_from_registry and not removed_from_startup_folder:
    raise SeattleNotInstalledError("Seattle could not be detected as " \
                                     + "having been installed prior to " \
                                     + "uninstall.")
  elif removed_from_registry or removed_from_startup_folder:
    # Stop all instances of seattle from running before returning.
    stop_all_seattle_processes.main()
    return True




# Derek Cheng: Added a separate uninstaller for Nokia N800/900 Tablets. This 
# function is to be called from uninstall_Linux_and_Mac().
def uninstall_nokia():
  """
    <Purpose>
    Remove the startup script and symlink to it in the /etc/init.d and 
    /etc/rc2.d directories, and kill all seattle processes by using 
    stop_all_seattle_processes. This requires the user to be currently on root
    access. 
  <Arguments>
    None.
  <Exceptions>
    None.
  <Side Effects>
    Removes the startup script and the symlink to it, and stops seattle from 
    running.
  <Returns>
    True if succeeded in uninstalling,
    False otherwise.
  """
  

  # Note to developers: If you need to change the path of the startup script or
  # the path of the symlink, make sure you keep it consistent with those in
  # seattleinstaller.py.

  startup_script_name = "nokia_seattle_startup.sh"
  # The directory where the startup script resides.
  startup_script_dir = "/etc/init.d/"
  # The full path to the startup script.
  startup_script_path = startup_script_dir + startup_script_name

  # The name of the symlink that links to the startup script.
  symlink_name = "S99startseattle"
  # The directory where the symlink to the startup script resides.
  symlink_dir = "/etc/rc2.d/"
  # The full path to the symlink.
  symlink_path = symlink_dir + symlink_name

  # Check if the startup script and the symlink exists.
  if not os.path.exists(startup_script_path) and \
        not os.path.lexists(symlink_path):
    _output("Neither the startup script nor the symlink exists.")
    return True

  # Remove the startup script.
  try:
    os.remove(startup_script_path)
  # Cannot remove the startup script due to some reason.
  except OSError, e:
    # The startup script does not exist - that is fine, we will continue 
    # and try to remove the symlink.
    if e.errno == errno.ENOENT:
      pass
    else:
      # The startup script cannot be removed.
      _output("The startup script cannot be removed. Make sure you have the " \
                + "permission to do so.")
      servicelogger.log("Seattle cannot be uninstalled because " \
                          + startup_script_path + " cannot be removed.")
      return False

  # Remove the symlink.
  try:
    os.remove(symlink_path)
  # Cannot remove the symlink due to some reason.
  except OSError, e:
    # The symlink does not exist - that is fine.
    if e.errno == errno.ENOENT:
      pass
    else:
      # The symlink cannot be removed.
      _output("The symlink cannot be removed. Make sure you have the " \
                + "permission to do so.")
      servicelogger.log("Seattle cannot be uninstalled because " \
                          + symlink_path + " cannot be removed.")
      return False

  # Stop all instances of seattle from running.
  stop_all_seattle_processes.main()

  return True


def uninstall_Linux_and_Mac():
  """
  <Purpose>
    Remove the seattle entry from the crontab, and kill all seattle processes
    by using stop_all_seattle_processes.py
  <Arguments>
    None.
  <Exceptions>
    SeattleNotInstalledError if seattle had not been initially installed when
      the uninstaller was run.
    UnsupportedOSError from a child function if the OS running this script is
      not supported.
  <Side Effects>
    Removes the seattle entry from the crontab and stops seattle from running.
  <Returns>
    True if succeeded in uninstalling,
    False otherwise.
  """


  # Derek Cheng: Find out if this is a Nokia N800/900 Tablet, and if so runs a 
  # separate uninstaller because there is no crontab on the tablets.
  if platform.machine().startswith('armv'):
    return uninstall_nokia()

  if platform.machine().startswith('mips'):
    return True


  # Find out if Seattle is installed (currently in the crontab), and remove if
  # so.
  crontab_contents_stdout = subprocess.Popen(["crontab","-l"],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE).stdout

  # Generate a temp file with the user's crontab minus our task.
  temp_crontab_file = tempfile.NamedTemporaryFile()

  seattle_crontab_entry_found = False
  for line in crontab_contents_stdout:
    if not seattleinstaller.get_starter_file_name() in line:
      temp_crontab_file.write(line)
    else:
      seattle_crontab_entry_found = True


  if not seattle_crontab_entry_found:
    temp_crontab_file.close()
    raise SeattleNotInstalledError("Seattle cannot be uninstalled because it " \
                                     + "is not currently installed.")



  # Replace the old crontab with the updated crontab contents.
  temp_crontab_file.flush()
  replace_crontab = subprocess.Popen(["crontab",temp_crontab_file.name],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
  replace_crontab.wait()
  temp_crontab_file.close()



  # Confirm that seattle was successfully removed from the crontab, and set
  # the 'crontab_updated_for_2009_installer' value in nodeman.cfg to False.
  modified_crontab_contents_stdout,modified_crontab_contents_stderr = \
      subprocess.Popen(["crontab","-l"],
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE).communicate()

  if seattleinstaller.get_starter_file_name() \
        in modified_crontab_contents_stdout:
    return False
  else:
    # Stop all instances of seattle from running before returning.
    stop_all_seattle_processes.main()

    configuration = persist.restore_object("nodeman.cfg")
    configuration['crontab_updated_for_2009_installer'] = False
    persist.commit_object(configuration,"nodeman.cfg")

    return True




def prepare_uninstall(options,arguments):
  """
  <Purpose>
    Prepare all necessary global variables for the actual uninstall process.
    This involves combing through the arguments passed to the installer
    to set the appropriate variables.
  <Arguments>
    options:
      A list of tuples (flag,value) where flag is the argument name passed to
      the uninstaller and value is the value for that particular flag.
    arguments:
      A list of arguments that did not have an argument name associated with it.
  <Exceptions>
    None.
  <Side Effects>
    Changes default local and global variables.
  <Return>
    True if this entire prepare_installation() process finished,
    False otherwise (meaning an argument was passed that calls for install to be
    halted [e.g., --usage].)
  """

  global SILENT_MODE
  global WIN_STARTUP_SCRIPT_PATH

  # Iterate through and process the arguments.
  for (flag,value) in options:
    if flag == "-s":
      SILENT_MODE = True
    elif flag == "--usage":
      usage()
      return False
    elif flag == "--win-startup-script-path":
      WIN_STARTUP_SCRIPT_PATH = value

  # Tell the parent function the passed-in arguments allow it to continue with
  # the uninstall.
  return True




def usage():
  """
  Prints command line usage of script.
  """

  if OS == "Windows":
    print "uninstall.bat",
  elif OS == "Linux" or OS == "Darwin":
    print "uninstall.sh",
  else:
    print "python seattleuninstaller.py",


  print "[-s] [--usage] [--win-startup-script-path path]"
  print "Info:"
  print "-s\t\t\tSilent mode: does not print output."
  print "--win-startup-path\tSpecifies the path to the Windows startup " \
      + "script in the Startup folder.  If seattle is installed there and " \
      + "this option is not specified, then seattle will not get uninstalled."




def main():

  # Derek Cheng: If the user is running the uninstaller on the Nokia N800, we 
  # require them to be on root to remove some files in /etc/init.d and 
  # /etc/rc2.d directories. This needs to preceed servicelogger.init, since
  # only root has permission to installInfo. 
  if platform.machine().startswith('armv'):
    # Derek Cheng: This is for detecting if the user is root.   This module 
    # isn't portable so I only can import it on Linux / Nokia devices
    import pwd
    # Check to see if the current user is root.
    if pwd.getpwuid(os.getuid())[0] != 'root':
      _output('Please run the uninstaller as root. This can be done by ' \
                + 'installing/using the rootsh or openssh package.')
      return

  # Begin pre-uninstall process.

  # Initialize the service logger.
  servicelogger.init('installInfo')

  # Pre-uninstall: parse the passed-in arguments.
  try:
    opts, args = getopt.getopt(sys.argv[1:], "s", ["win-startup-path=","usage"])
  except getopt.GetoptError, err:
    print str(err)
    usage()
    return

  # Pre-uninstall: process the passed-in arguments.
  continue_uninstall = prepare_uninstall(opts,args)
  if not continue_uninstall:
    return


  # Begin uninstall process.

  # Perform the uninstall.
  successful_uninstall = False
  try:
    if OS == 'Linux' or OS == 'Darwin':
      successful_uninstall = uninstall_Linux_and_Mac()
    else:
      successful_uninstall = uninstall_Windows()
  except SeattleNotInstalledError,s:
    _output("Seattle was not detected as having been installed.")
    return



  # Print final output, and do final logging.
  if successful_uninstall:
    # Modify nodeman.cfg to note that seattle is no longer installed.
    configuration = persist.restore_object("nodeman.cfg")
    configuration['seattle_installed'] = False
    persist.commit_object(configuration,"nodeman.cfg")

    _output("Seattle has been successfully uninstalled.  It is now safe to " \
              + "remove all Seattle files and directories from your system.")
    servicelogger.log(time.strftime(" seattle completed uninstall on: " \
                                      + "%m-%d-%Y %H:%M:%S"))
  else:
    _output("Seattle could not be uninstalled for unknown reasons. Please " \
              + "contact the Seattle development team for assistance.")




if __name__ == "__main__":
  main()
