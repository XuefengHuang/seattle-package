"""
<Program Name>
  Linux_resources.py

<Started>
  January 18, 2009

<Author>
  Anthony Honstain
  Modified by Steven Portzer

<Purpose>
  Measure system resources on a Linux system, makes
  extensive use of /proc files and df command for
  disk info.

<Return value notes>
  The dictionary returned by measure_resources() is used by
  benchmark_resources.py and contains a value for every system resource.
  If the system resource is successfully measured, then the measured value
  of that resource is returned as an integer. If a test fails, then a
  string describing the failure is returned for that resource. If the
  resource is not currently being measured, then None is returned.

  Formerly, None was returned for both failed and unimplemented tests, but
  this made it impossible to determine whether a benchmark had actually
  failed or if it was simply not being measured.
  
<Resource events>
  WARNING the 'events' resource is hardcoded to a value of 500
  
  The 'events' resource has proven very difficult to measure across the
  different operating systems, and on some it is infeasible to measure.
  The decision has been made to take 500 events for the node
  
  see benchmark_resources for more information.  
  
<Notes about cpu measurement>
  Two different ways to measure the number of processors is offered.
  
  get_cpu() will return the number of physical processors/cores that
  are on the machine. There is no strait forward way to directly measure
  this as a computer could have multiple processors with multiple cores
  and possibly be hyperthreaded as well.
  
  get_cpu_virtual() will return the total number processors (both virtual
  and physical) as would be the case on a processors with hyperthreading.
  
  Test cases and reasoning behind get_cpu()

  EXAMPLE 1) Core2Duo dual core no HT
    $ grep 'processors' /proc/cpuinfo
    processor    : 0
    processor    : 1
    $ grep 'cores' /proc/cpuinfo
    cpu cores    : 2
    cpu cores    : 2
    $ grep 'physical' /proc/cpuinfo
    physical id    : 0
    physical id    : 0
    
    Result: Multiple cores on a single chip will have the same physical
    id and each processors will list its number of cores.

  EXAMPLE 2) ATTU's dual core xenon with HT
    attu3 ~]$  grep 'processor' /proc/cpuinfo
    processor    : 0
    processor    : 1
    processor    : 2
    processor    : 3
    attu3 ~]$ grep 'cores' /proc/cpuinfo
    cpu cores    : 1
    cpu cores    : 1
    cpu cores    : 1
    cpu cores    : 1
    attu3 ~]$ grep 'physical' /proc/cpuinfo
    physical id    : 0
    physical id    : 3
    physical id    : 0
    physical id    : 3
    
    Results: Two physical processors with one core each, but have 
    hyperthreading enabled. 

  EXAMPLE 3) Pentium 3 with HT
    grep 'processor' /proc/cpuinfo
    processor    :0
    processor    :1
    grep 'cores' /proc/cpuinfo
    cpu cores     :1
    cpu cores     :1
    grep 'physical' /proc/cpuinfo
    physical id    :0
    physical id    :0
    
  OVERALL RESULTS: Judging from examples 1-3, if the number of physical id's
  is multiplied by the number of cores we arrive at the correct number
  of processors on the computer.     
"""

import commands
import measure_random
import measuredisk

def count_processor(procfiledata):
  """
  <Purpose>
    count_processor will return the number of physical and virtual 
    processors that are recorded in the /proc/cpuinfo file.
    
    Each processor (both physical and virtual) will have its statistics
    recorded in the /proc/cpuinfo file.
    Example
 
    processor  : 0
    vendor_id  : GenuineIntel
    ...

    processor  : 1
    ...
    The count of processors is done by counting the number of lines
    that contain the word processor.

  <Arguments>
    procfiledata:
           A list with each line from the /proc/cpuinfo as an element.
           
  <Exceptions>
    Exception raised if no lines in /proc/cpuinfo contain the
    string processor.
    
  <Returns>
    The total number of virtual and physical processors.
  """
  count = 0
  # Read each line of the file and look for lines containing "processor"
  for line in procfiledata:
    if (line.find("processor") != -1):
      count += 1
  if(count > 0):
    return count
  else:
    raise Exception("processor data not found")


def count_cores(procfiledata):
  """
  <Purpose>
    count_cores will return the number of cpu cores that are 
    recorded by the processor in the /proc/cpuinfo file.
    HELPER FUNCTION FOR get_cpu()
    
  <Arguments>
    procfiledata:
           A list with each line from the /proc/cpuinfo as an element.
           
  <Exceptions>
    Exception raised if no lines in /proc/cpuinfo contain the
    string 'cpu cores' or number of cores is invalid.
    
  <Returns>
    The total number of cores for a single physical processor, 
    or 1 if no core data is found.
  """
  # Search each line for the desired string
  for line in procfiledata:
    if (line.find("cpu cores") != -1):
      splitline = line.split()
      # example value for desired line from /proc/cpuinfo
      # ['cpu', 'cores',':', '2'] 
      cpucores = splitline[-1]      
      try:
        return int(cpucores)
      except ValueError:
        raise Exception("bad value for number of cpu cores: " + str(cpucores))
  else:
    # No CPU cores data found, use a default of 1.
    # This is required for nonstandard /proc/cpuinfo layouts as 
    # found on RaspberryPis (#1308) and OpenWrt routers.
    return 1

def count_processor_physical_id(procfiledata):
  """
  <Purpose>
    count_processor_physical_id will search each line of a the
    /proc/cpuinfo file and record each unique physical id and
    return the total number of unique id's.
    HELPER FUNCTION FOR get_cpu()
    
  <Arguments>
    procfiledata:
           A list with each line from the /proc/cpuinfo as an element.
           
  <Exceptions>
    Exception raised if no lines in /proc/cpuinfo contain the
    contained information on the 'physical id' or the physical
    id is not an integer.
    
  <Returns>
    The total number of unique identifiers, or 1 if none were found.
  """
  id_list = []
  for line in procfiledata:
    if (line.find("physical id") != -1):
      splitline = line.split()
      # example value for desired line from /proc/cpuinfo
      # ['physical', 'id',':', '3'] 
      phys_id = splitline[-1]      
      try:
        phys_id = int(phys_id)
      except ValueError:
        raise Exception("bad value for physical id: " + str(phys_id))
      if(phys_id not in id_list):
        id_list.append(phys_id)

  # Return the number of physical IDs found, or 1 if none were found. 
  # The latter is required for nonstandard /proc/cpuinfo layouts as 
  # found on RaspberryPis (#1308) and OpenWrt routers.
  return len(id_list) or 1

 
def get_cpu():
  """
  <Purpose>
    Measure the number of PHYSICAL cores and processors.

  <Exceptions>
    Exception is raised if /proc/cpuinfo cannot be opened or it's
    contents are are insufficient for determining the the number
    of physical processors/cores.
  
  <Returns>
    The number of physical processors/cores.
  """
  cpu_cores = 0 # Stores integer value for number of cores
  cpu_physicalid = 0 # Stores the unique id's for the processors
  
  cpuinfo_copy = []
 
  try:
    openfile = open("/proc/cpuinfo", 'r') 
  except IOError:     
    raise Exception("unable to read cpu data from /proc/cpuinfo")

  # Read each line of the file and store it in a list, this is done 
  # because the contents of /proc/cpuinfo will be traversed up to 
  # two seperate times.
  for line in openfile:
    cpuinfo_copy.append(line)
  openfile.close()
      
  # get the number of cpu cores
  cpu_cores = count_cores(cpuinfo_copy)
  
  # get the number of physical id's 
  cpu_physicalid = count_processor_physical_id(cpuinfo_copy)
  
  # Refer to detailed explanation from program's opening comment.  
  return cpu_cores * cpu_physicalid
  
  
def get_cpu_virtual():
  """
  <Purpose>
    Measure the number of processors, this count includes both
    physical and virtual processors.

  <Exceptions>
    Exception is raised if /proc/cpuinfo cannot be opened or it's
    contents are are insufficient for determining the the number
    of processors.
  
  <Returns>
    The number of processors.
  """
  cpu_processors = None # Stores the number of processors
 
  try:
    openfile = open("/proc/cpuinfo", 'r') 
  except IOError:
    raise Exception("unable to read cpu data from /proc/cpuinfo")

  # get the number of processors
  cpu_processors = count_processor(openfile)
  
  openfile.close()
  return cpu_processors


def get_memory():
  """
  <Purpose>
    get_memory will search the /proc/meminfo file on a linux
    system to find the size of RAM. Does not measure swap size
    because that has a seperate field in meminfo. 

  <Exceptions>
    Exception is raised if unable to open the file, or if no valid data
    was retrieved.

  <Returns>  
    The size of RAM in bytes (converted from kB as it is stored in
    the meminfo file.
  """
  memory = ''
  
  try:
    openfile = open("/proc/meminfo", 'r') 
  except IOError:     
    raise Exception("unable to read memory data from /proc/meminfo")

  # Search each line in the file for the line containing the
  # memory total.
  for line in openfile:
    if(line.find("MemTotal:") != -1):
      splitline = line.split()
      #example value for desired splitline
      #['MemTotal:', '2066344', 'kB']
      memory = splitline[1]
      openfile.close()  
     
      try:
        memory = long(memory)
      except ValueError:
        raise Exception("bad value for total memory: " + str(memory))
      
      #Assuming memory will be stored in kB
      #memory is converted to bytes using 1kByte = 1000 Bytes
      memory = memory * (1000) 
      return memory  
  
  openfile.close()
  raise Exception("memory data not found")


def get_diskused():
  """
  <Purpose>
    Returns the total size in Bytes that are available on the 
    partition that the working directory is on.

  <Exceptions>
    Exception is raised if unable to retrieve partition data.

  <Returns>
    The total number of Bytes available to the user on the current
    partition.
  """
 
  #blocks are typically 1024bytes
  blocksize = 1024
  freeblocks = 0

  #Unix command df
  #-P, --portability     use the POSIX output format
  #Possible result from "df -P ."
  # Filesystem  1024-blocks  Used  Available Capacity Mounted on
  # /dev/sda1   15007228   5645076  8757148      40%    /
  statresult = commands.getstatusoutput('df -P .')
   
  # Test because if first element of tuple is other than 0
  # then the exit status of the linux command is an error.
  if (statresult[0] != 0):
    raise Exception("unable to read disk partition size")
  
  # Second element of tuple returned by commands.getstatusoutput
  # is the stdout from the command.  
  statresult = (statresult[1]).split()

  try:
    freeblocks = long(statresult[10])
  except ValueError:
    raise Exception("bad value for disk partition size: " + str(statresult[10]))

  disksize = blocksize * freeblocks 
  return disksize 


def get_events():
  """
  <Purpose>
    Measure the maximum number threads the operating system will allow.
    This uses the ulimit command with option -a. While it would be ideal
    to use the -u option, on ubuntu the -u option raised the
    error 'ulimit: 1: Illegal option -u' when it was executed by
    commands.getstatusoutput (it did not have this error when 
    run normally from the shell). I was unable to discover
    why this error occurred or why it was specific to only option -u.

    The original method that found the maximum allowed by the kernel
    has been left it the comment, but not provided as a fallback because
    I think it is likely to be far to high, and it would be better
    that a predefined default is used, then potentially get more events
    than a user could really have. 

  <Original Method>
    This will find the maximum number of threads that the kernel will
    allow, however the number available to a giver user will be less.
    The ulimit command has been observed to produce a number much closer
    to the actual number of threads available.
    
      maxevents = 0
      defaultevents = None
    
      try:
        openfile = open('/proc/sys/kernel/threads-max', 'r') 
      except IOError:     
        return defaultevents
      
      try:
        maxevents = int(openfile.read())
      except ValueError:
        openfile.close()
        return defaultevents 
       
      openfile.close()
      return maxevents
  """
  max_processes = 0

  # Sample result of successful getstatusoutput is 
  # (0, '16310')
  status_result = commands.getstatusoutput('ulimit -u')
   
  # Test because if first element of tuple is other than 0
  # then the exit status of the linux command is an error.
  if (status_result[0] != 0):
    raise Exception("unable to read maximum number of threads")
  
  # Second element of tuple returned by commands.getstatusoutput
  # is the stdout from the command, should be just a single integer.  
  status_result = status_result[1]

  try:
    max_processes = int(status_result)
  except ValueError:
    raise Exception("bad value for maximum number of threads: " + \
                        str(status_result))

  return max_processes


  
def get_filesopened():
  """
  <Purpose>
    Reads the result of ulimit -n to get the number
    of files that a individual user has access to.

  <Original Method>
    Reads the value stored in /proc/sys/fs/file-max
    May not represent the number of file descriptors
    that a user/process is able to obtain.
  
      maxfile = 0
    
      try:
        openfile = open('/proc/sys/fs/file-max', 'r') 
      except IOError:     
        return None
      
      try:
        maxfile = int(openfile.read())
      except ValueError:
        openfile.close()
        return None
    
      openfile.close()
      return maxfile
  """
  maxfile = 0

  # Sample result of successful getstatusoutput is (0, '1024')
  status_result = commands.getstatusoutput('ulimit -n')
   
  # Test because if first element of tuple is other than 0
  # then the exit status of the linux command is an error.
  if (status_result[0] != 0):
    raise Exception("unable to read maximum number of open files")
  
  # Second element of tuple returned by commands.getstatusoutput
  # is the stdout from the command.  
  status_result = status_result[1]

  try:
    maxfile = int(status_result)
  except ValueError:
    raise Exception("bad value for maximum number of open files: " + \
                        str(status_result))

  return maxfile



def measure_resources():

  resource_dict = {}

  # SP: If any test fails then a string describing the failure should be
  # returned, so catch the exception and return it as a string.
  # None is reserved for tests that aren't implemented so that failed tests and
  # unimplemented tests can be differentiated.

  try:
    resource_dict["cpu"] = get_cpu()
  except Exception, e:
    resource_dict["cpu"] = str(e)
  
  try:
    resource_dict["memory"] = get_memory()
  except Exception, e:
    resource_dict["memory"] = str(e)

  try:
    resource_dict["diskused"] = get_diskused()
  except Exception, e:
    resource_dict["diskused"] = str(e)
  
  # For the time being we will be using the default number
  # of events.
  #resource_dict["events"] = get_events()
  resource_dict["events"] = None
  
  # filesopened, insockets, and outsockets are restricted by linux and all 
  # come from the same total, I do a quick check to avoid an exception being 
  # raised, it unlikely that the test would fail, but after seeing the 
  # strange behavior of ulimit for events it seems best error on the side 
  # of safety.
  try:
    maxfiles = get_filesopened() / 3
  except Exception, e:
    maxfiles = str(e)

  resource_dict["filesopened"] = maxfiles
  resource_dict["insockets"] = maxfiles
  resource_dict["outsockets"] = maxfiles

  # SP: this test should work on all systems now, but catch the exception just
  # in case.
  try:
    random_max = measure_random.measure_random()
  except measure_random.InvalidTimeMeasurementError, e:
    random_max = str(e)
      
  resource_dict["random"] = random_max

  # Measure the disk read write rate
  try:
    filewrite, fileread = measuredisk.main()
  except Exception, e:
    filewrite, fileread = str(e), str(e)

  resource_dict["filewrite"] = filewrite
  resource_dict["fileread"] = fileread
  
  # These resources are not measure in this script so a None
  # value is used to indicate it was not measured. 
  resource_dict["netrecv"] = None
  resource_dict["netsend"] = None
  resource_dict["lograte"] = None
  resource_dict["loopsend"] = None
  resource_dict["looprecv"] = None

  return resource_dict

if __name__ == "__main__":

  dict = measure_resources()

  print "resource cpu ", dict['cpu']
  print "resource memory ", dict['memory'], '\t', dict['memory'] / 1073741824.0, "GB"
  print "resource diskused ", dict['diskused'], '\t', dict['diskused'] / 1073741824.0, "GB"
  print "resource events ", dict['events']
  print "resource filesopened ", dict['filesopened']
  print "resource insockets ", dict['insockets']
  print "resource outsockets ", dict['outsockets']
  print "resource random ", dict['random'], '\t', dict['random'] / 11048576.0, "MB"
  print "resource filewrite ", dict['filewrite'], '\t', dict['filewrite'] / 1048576.0, "MB"
  print "resource fileread ", dict['fileread'], '\t', dict['fileread'] / 1048576.0, "MB"
  print "resource netrecv ", dict["netrecv"]
  print "resource netsend ", dict["netsend"]
  print "resource lograte ", dict["lograte"]
  print "resource loopsend ", dict["loopsend"]
  print "resource looprevc ", dict["looprecv"]
