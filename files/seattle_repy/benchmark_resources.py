"""
<Program Name>
  benchmark_resources.py

<Started>
  2009-08-1

<Author>
  Anthony Honstain
  Modified by Steven Portzer
  
<Purpose>
  Will use the file 'vesselinfo' which should already be in the directory
  (which is constructed by the website) and runs a OS specific benchmark
  to construct the vessels defined in vesselinfo with the correct resource
  files so that seattle only the donated resources.
  
  A wiki page concerning this module can be found at:
  https://seattle.poly.edu/wiki/BenchmarkCustomInstallerInfo
  Which contains a more high level overview of the operation.
  
  This should be run internally by seattleinstaller.py

<Resource events>
  WARNING the 'events' resource is hardcoded to a value of 500
  
  The 'events' resource has proven very difficult to measure across the
  different operating systems, and on some it is infeasible to measure.
  The decision has been made to take 500 events for the node, regardless
  of the percentage the user will donate. The value of 500 is inserted
  in the benchmark_resources.get_donated_from_maxresources. 
  
  Warning: there is still a default value in the DEFAULT_MAX_RESOURCE_DICT
  and run_benchmark will return a dict with the default or what ever the
  OS specific script returned (they should be set to return None for events).
  This is confusing, but I chosen to do this for the sake of future
  modifications, if we found a way to measure the number of events or the
  meaning of how we use them changed completely, it would be easy to
  transition back to getting a benchmark for the resource.

"""


import nonportable
import create_installer_state
import nmresourcemath
import sys
import traceback
import platform # for detecting Nokia tablets


# These are the default maximum values that we assume a computer to have
# These values will be used in the event the OS specific script is unable
# to determine a maximum for the value.
# These were the lower numbers returned from developer testing.
DEFAULT_MAX_RESOURCE_DICT = {"cpu":1,
                             "memory":510000000, # allmost 512MB
                             "diskused":3700000000, # 3.44589 GB
                             "events":500, # see module's doc string.
                             "filesopened":250,
                             "insockets":250,
                             "outsockets":250,
                             "random":200000,
                             "filewrite":1200000,
                             "fileread":1200000,
                             "netrecv":500000,
                             "netsend":500000,
                             "lograte":1500000,
                             "loopsend":50000000,
                             "looprecv":50000000}

# Default resources that define the cost of splitting a vessel
DEFAULT_OFFCUT_DICT =  {'cpu':.002,
                        'memory': 1000000,   # 1 MiB
                        'diskused': 100000, # .1 MiB
                        'events':2,
                        'filewrite':1000,
                        'fileread':1000,
                        'filesopened':1, 
                        'insockets':0,
                        'outsockets':0,
                        'netsend':0,
                        'netrecv':0,
                        'loopsend':0,  # would change with prompt functionality (?)
                        'looprecv':0,
                        'lograte':100, # the monitor might log something
                        'random':0 }


# Reduce the default max resources for ARM devices such as Android 
# phones/tablets, RaspberryPis, OpenWrt routers, iPhones and iPads, and 
# Nokia N800/900.

if platform.machine().startswith('armv'):
  DEFAULT_MAX_RESOURCE_DICT.update({
    "random": DEFAULT_MAX_RESOURCE_DICT["random"] / 4,
    "filewrite": DEFAULT_MAX_RESOURCE_DICT["filewrite"] / 20,
    "fileread": DEFAULT_MAX_RESOURCE_DICT["filewrite"] / 20,
    })


# Current this is only raised when nmresourcemath raises a ResourceParseError.
# I suppose we could let the nmresourcemath exception propagate instead
# of catching it and raising out own, but I was hoping this would provide 
# more useful information and possibly be more useful if at some point
# this module takes over some of the functionality of nmresourcemath, or
# performs more checking on initial resources.
class InsufficientResourceError(Exception):
  """Error to indicate that vessels cannot be created with given resources."""
  pass

class BenchmarkingFailureError(Exception):
  """
  Error to indicate that benchmarking failures occurred and installation should
  not continue.
  """
  pass



def log_failure(errorstring, logfileobj):
  """
  <Purpose>
    To log benchmarking failures to the log file and print it so the user can
    tell what errors occurred.

    This function exists to keep run_benchmark a bit cleaner.
       
  <Arguments>
    errorstring: The string describing the benchmarking failure being logged.

    logfileobj: The open file object that will be used for logging
        the benchmarking failure.
    
  <Exceptions>
    None
    
  <Side Effects>
    Will log failure to logfileob and print it to system output.
  
  <Return>
    None
     
  """

  logfileobj.write(errorstring + "\n")
  print errorstring


def prompt_user(promptstring):
  """
  <Purpose>
    To receive yes or no input from the user. Capitalization is ignored and
    y or n will also be accepted.
       
  <Arguments>
    promptstring: The string to display when prompting the user for a yes or no
      input.
    
  <Exceptions>
    None
    
  <Side Effects>
    Prints promptstring and waits for a yes or no input from the user.
  
  <Return>
    True if the user responds with yes and false if no.
     
  """

  userinput = raw_input(promptstring)

  while True:
    userinput = userinput.lower()

    if userinput == "yes" or userinput == "y":
      return True
    if userinput == "no" or userinput == "n":
      return False

    userinput = raw_input("Please enter either yes or no: ")


def run_benchmark(logfileobj):
  """
  <Purpose>
    To run the individual OS specific scripts and supplement their results
    (if they do not returned a benchmark for every resource) with default
    values if needed.
    
    This method has some cut and paste, but it seemed to be the simplest
    way to handle the OS specific imports and logging.
    
    WARNING the dictionary returned still treats cpu as an integer representing
    the number of processors (not a float like it will be later in the process).
       
  <Arguments>
    logfileobj: The open file object that will be used for logging
        the benchmark process and the creation of the installer state.
    
  <Exceptions>
    BenchmarkingFailureError: Indicates that one or more benchmark failed and
      the user opted to terminate installation.
    
  <Side Effects>
    May use the drive to measure read/write, network resources to measure
    bandwidth, and request OS sources of crypto-graphically strong 
    pseudo-random numbers.
    Will use servicelogger to log benchmark failures to 'installInfo'.
  
  <Return>
    A dictionary with measurement value for all the resources in the dict.
     
  """
  OS = nonportable.ostype
  
  max_resource_dict = None
  benchmarking_failed = False

  # The imports are all done based on OS because the scripts cannot be
  # imported into a different OS. I can not import the Windows script on
  # Linux because I lack required libraries etc..
  # If any of them crash we want to log it and continue with default values.
  if OS == "Windows":
    try:
      import Win_WinCE_resources
      max_resource_dict = Win_WinCE_resources.measure_resources() 
    except Exception:
      log_failure("Failed to benchmark Windows OS.", logfileobj)
      exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
      traceback.print_exception(exceptionType, exceptionValue, \
                                exceptionTraceback, file=logfileobj)
      max_resource_dict = DEFAULT_MAX_RESOURCE_DICT.copy()
      benchmarking_failed = True

  elif OS == "Linux":
    try:
      import Linux_resources
      max_resource_dict = Linux_resources.measure_resources()
      try:
        import android
        is_android = True
        import os
        # Use environmental variables to pass data from Java->Python on Android
        cores = long(os.environ.get('SEATTLE_AVAILABLE_CORES', 0))
        if cores > 0:
          max_resource_dict["cpu"] = cores
        diskused = long(os.environ.get('SEATTLE_AVAILABLE_SPACE', 0))
        if diskused > 0:
          max_resource_dict["diskused"] = diskused
      except ImportError:
        is_android = False
    except Exception:
      log_failure("Failed to benchmark Linux OS.", logfileobj)
      exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
      traceback.print_exception(exceptionType, exceptionValue, \
                                exceptionTraceback, file=logfileobj)
      max_resource_dict = DEFAULT_MAX_RESOURCE_DICT.copy()
      benchmarking_failed = True
      
  elif OS == "Darwin":
    try:
      import Mac_BSD_resources
      max_resource_dict = Mac_BSD_resources.measure_resources()
    except Exception:
      log_failure("Failed to benchmark Darwin OS.", logfileobj)
      exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
      traceback.print_exception(exceptionType, exceptionValue, \
                                exceptionTraceback, file=logfileobj)
      max_resource_dict = DEFAULT_MAX_RESOURCE_DICT.copy()
      benchmarking_failed = True
  else:
    raise nonportable.UnsupportedSystemException("The operating system '" \
              + OS + "' is not supported.")
    
  # We are going to log the benchmarked system resources, this will be
  # very useful in the event a user chooses to share the data with us.
  if not benchmarking_failed:
    logfileobj.write("Total resources measured by the script for " + OS + \
                   " OS: " + str(max_resource_dict) + "\n")    
    
  # The dictionary returned by the scripts will contain null values for
  # resources that they were not benchmarked. If a benchmark failed, the
  # dictionary will contain a string describing the failure that occurred.
  for resource in DEFAULT_MAX_RESOURCE_DICT:
    
    # Make sure the benchmarking script actually returned something for the
    # given resource. This should be the case, but if the scripts are
    # changed at some point, then the problem will be caught here.
    if resource not in max_resource_dict:
      log_failure("Benchmark script did not return value for " + resource, \
                         logfileobj)
      max_resource_dict[resource] = DEFAULT_MAX_RESOURCE_DICT[resource]
      benchmarking_failed = True

    # For all the null values, we want to set a default.
    elif max_resource_dict[resource] is None:
      max_resource_dict[resource] = DEFAULT_MAX_RESOURCE_DICT[resource]

    # If the value is a string, then the benchmark failed, so we want to
    # log the failure and use the default value.
    elif isinstance(max_resource_dict[resource], basestring):
      log_failure("Benchmark failed for " + resource + " resource: " +
                    max_resource_dict[resource], logfileobj)
      max_resource_dict[resource] = DEFAULT_MAX_RESOURCE_DICT[resource]
      benchmarking_failed = True

    else:  
      # This is done for added security in case scripts gets changed or
      # modified in the future, it will get caught here if the scripts
      # are not catching bad values (since they all reach out to other 
      # OS specific files and programs).
      try:
        max_resource_dict[resource] = int(max_resource_dict[resource])
      except ValueError, e:
        log_failure("Benchmark script had bad value for " + resource \
                           + ": " + str(max_resource_dict[resource]), logfileobj)
        max_resource_dict[resource] = DEFAULT_MAX_RESOURCE_DICT[resource]
        benchmarking_failed = True
      
      if max_resource_dict[resource] <= 0:
        log_failure("Benchmark script had non-positive value for " + resource \
                           + ": " + str(max_resource_dict[resource]), logfileobj)
        max_resource_dict[resource] = DEFAULT_MAX_RESOURCE_DICT[resource]
        benchmarking_failed = True
       
  # If one or more benchmark failed, then we want to give the user the option
  # of aborting the installation
  if benchmarking_failed:
    print "The above benchmarking error(s) occurred."
    print "If you choose to continue anyways then default values will be " + \
                    "used for failed benchmarks."

    if not is_android:
      continue_install = prompt_user("Continue with installation? (yes/no) ")

    # AR: This pops up the actual dialog on the screen on Android 
    else:
      droid = android.Android()
      droid.dialogCreateAlert("Benchmarking error(s) occurred",
        "If you choose to continue, then default values will be used for failed benchmarks.")
      droid.dialogSetPositiveButtonText("Continue")
      droid.dialogSetNegativeButtonText("Cancel")
      droid.dialogShow()
      response = droid.dialogGetResponse().result
      droid.dialogDismiss()
      if response.has_key("which"):
        result = response["which"]
        if result == "positive":
          continue_install = True
        else:
          continue_install = False

    if not continue_install:
      logfileobj.write("Installation terminated by user after one or " + \
                      "more failed benchmarks.\n")
      raise BenchmarkingFailureError()

    logfileobj.write("Installation continued by user. Default values are " + \
                    "being used for failed benchmarks.\n")

  # These are the resources the script will use to calculate the donated
  # resources, I am going to log this just to be safe.     
  logfileobj.write("Final checked resources that we will use: " + \
                   str(max_resource_dict) + "\n")
  
  # There should be no missing keys.
  # An example of what could now be contained in max_resource_dict
  # {'diskused': 63202701312L, 'fileread': 35140832, 'filewrite': 35140832, 
  #  'loopsend': 1000000, 'lograte': 30000, 'netrecv': 100000, 
  #  'random': 27776, 'insockets': 1024, 'filesopened': 1024, 
  #  'looprecv': 1000000, 'cpu': 2, 'memory': 2047868000L, 
  #  'netsend': 100000, 'outsockets': 1024, 'events': 32620}
  return max_resource_dict



def get_donated_from_maxresources(max_resources_dict, resource_percent):
  """
  <Purpose>
    To get the portion of system resources requested by the user, this
    will be the user determined percentage of each resource in 
    max_resources_dict.
    
  <Arguments>
    max_resource_dict: dictionary containing the total amount of each
      resource that is available on the machine.  
  
    resource_percent: The number representing the percent of system resources
        that will be donated to seattle (Normally 10 is requested).
        
  <Exceptions>
    None
    
  <Side Effects>
    None
  
  <Return>
    Dictionary with the same keys as the DEFAULT_MAX_RESOURCE_DICT that
    contains the donated system resources.
  
  """    
  
  donatedresources = {}  
  resource_percent /= 100.0
  
  # So far only cpu and events are handled specially. Computed result should
  # be an integer
  for resource in max_resources_dict:
    if resource == 'cpu':
      # Result should be a float in [0,1] (while most other
      # values in the resource file are integers). 
      tmp_resource = (max_resources_dict['cpu'] * resource_percent)
      donatedresources[resource] = tmp_resource
    elif resource == 'events':
      # Given the difficulty of accurately measuring this on
      # most systems, 500 was chosen as a reasonable value, if
      # for some reason a system has less, the node will deal
      # with that later.
      donatedresources[resource] = 500      
    else:
      tmp_resource = int(max_resources_dict[resource] * resource_percent)
      donatedresources[resource] = tmp_resource      
      
  return donatedresources


    
def get_tenpercent_of_donated(donatedresources):
  """
  <Purpose>
    To get ten percent of the resources that have been donated (offcut
    resources for the multiple vessels has already been removed).
    
  <Arguments>
    max_resource_dict: dictionary containing the total amount of each
      donated resource on the machine.  
        
  <Exceptions>
    None
    
  <Side Effects>
    None
  
  <Return>
    Dictionary with the same keys as the DEFAULT_MAX_RESOURCE_DICT that
    contains ten percent of the donated system resources.
  
  """    
  
  tenpercent = {}  
  
  # So far only cpu is handled specially, if others needed special
  # consideration it could be added here. Computed result should
  # be an integer
  for resource in donatedresources:
    if resource == 'cpu':
      # Result should be a float in [0,1] (while most other
      # values in the resource file are integers). 
      tenpercent[resource] = donatedresources['cpu'] * .1   
    else:
      tenpercent[resource] = int(donatedresources[resource] * .1)    
      
  return tenpercent



def main(prog_path, resource_percent, logfileobj):
  """
  <Purpose>
    To run the benchmarks and use the writecustominstaller to create
    the state for the vessels (resource files and directories).
    
  <Arguments>
    prog_path:
      Path to the directory in which seattle is being installed.
    
    resource_percent: The number representing the percent of system resources
        that will be donated to seattle (Normally 10 is requested).
        
    logfileobj: The open file object that will be used for logging
        the benchmark process and the creation of the installer state.
    
  <Exceptions>
    InsufficientResourceError: Exception to indicate that there was
      and insufficient amount of resources. This could be because
      the benchmarks were very low or because there are to many
      vessels for a specific resource quantity.
  
    We let the exceptions raised by create_installer_state propogate up
    since they indicate this installation will completely fail and must
    be terminated.
    
    The following are exceptions that are raised by create_installer_state:
      
      InvalidVesselInfoError: Exception to indicate an improper vesselinfo
        file, it means a vessel did not have an owner or the file was corrupted
        or improperly formated.
      
      ValueError: if the vessel percent (from element 0 of a tuple in the 
        vesselcreationlist list) is not 10,20,30, ... , 80, 90, 100
        A ValueError will also be raised if the total percent (of all
        the vessel percents in the vesselcreationlist list) does not add
        up to the integer 100
  
      IOError: if vessel.restrictions is not found, this must be included
        ahead of time in the target directory.
    
      OSError, WindowsError: if os.mkdir is unable to create the vessel
        directories.

    Installation will also fail if run_benchmark raises the following exception:

      BenchmarkingFailureError: Indicates that one or more benchmark failed and
        the user opted to terminate installation.
  
  
  <Side Effects>
    Will log to the logfileob that was passed as an argument if there is 
    a failure. 
    Writes out resource.v1, resource.v2, ... vessel resources files and 
    creates directories v1,v2,...
    
  <Return>
    None
  
  """

  logfileobj.write("New installation, beginning benchmark.\n")
    
  # Read the vesselinfo file, this may be corrupted or if it is put together
  # wrong by the server we let the exception propagate in order to stop the 
  # install because it would result in a bad node.  
  try:
    vesselcreationlist = create_installer_state.read_vesselinfo_from_file("vesselinfo")
  except Exception:
    vesselinfodata = open("vesselinfo",'r')
    logfileobj.write(vesselinfodata.read() + "\n")
    vesselinfodata.close()
    raise
  
  max_resources_dict = run_benchmark(logfileobj)  
  
  # I am logging the percentage that should donated to make it easier
  # to track down the cause of exceptions related to resource splitting.
  logfileobj.write("User intended to donate :" + str(resource_percent) + \
                   " percent.\n")
  
  # Take the max resources and get the donated resources.
  donatedresources = get_donated_from_maxresources(max_resources_dict, 
                                                   resource_percent)
  logfileobj.write("Donated resources:" + str(donatedresources) + "\n")
  
  
  # Find the number of vessels and that the initial node should contain
  # and deduct the appropriate offcut resources to account for all the vessels.
  vesselcount = 0
  for item in vesselcreationlist:
    vesselcount += 1
  
  for i in range(vesselcount):
    donatedresources = nmresourcemath.subtract(donatedresources, 
                                               DEFAULT_OFFCUT_DICT)
  
  # ensure there aren't negative resources, we will log this and raise
  # an exception for seattleinstaller to catch.
  try:
    nmresourcemath.check_for_negative_resources(donatedresources)
  except nmresourcemath.ResourceParseError, e:
    logfileobj.write("donatedresources that contain a negative resource" +  \
                      str(donatedresources) + "\n")
    logfileobj.write("Insufficient resources for desired number of " + \
                      "vessels :" + str(e) + "\nThis means that after " + \
                      "accounting for the resources.offcut (the cost of " + \
                      "splitting a vessel) there were negative " + \
                      "resources.\n")
    
    
    raise InsufficientResourceError("Cost of splitting vessels resulted in " + \
                                   "negative resource values.")
    
  # ten percent is selected to make the job of create_installer_state as
  # simple as possible, it requires vessels be alloted from the donated 
  # resources in increments of 10 percent. If we allowed vessels to be
  # alloted portions like 22% of the donated resources we would need to
  # split the donated resources down farther and the likely hood of vessels
  # getting little or none of a resource increases. It could be possible
  # to improve this in the future but for now this seems safest, especially
  # since some of the benchmark scripts pick very safe/low values.
  tenpercentdict = get_tenpercent_of_donated(donatedresources)
  # Going to go ahead and log it just to be safe.
  logfileobj.write("Useful amount of the donatedresources (offcut costs " + \
                    "removed already): " + str(tenpercentdict) + "\n")
  
  # Create the installer installer initial vessel state, this will create
  # the vesseldict, vessel directories, and vessel resource files. 
  # Note: possible exceptions for this module are: ValueError, IOError, 
  # OSError, WindowsError. But they will be allowed to propagate up.
  create_installer_state.main(vesselcreationlist, tenpercentdict, prog_path)

