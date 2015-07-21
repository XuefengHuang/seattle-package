""" 
<Program Name>
  create_installer_state.py
  
<Started>
  October 20th, 2008

<Author>
  Author: Justin Cappos - file was formerly named writecustominstallerinfo.mix
  Modified by Anthony Honstain
    
<Purpose>
  Module: Writes the state for the custom installer...

  This initializes the custom installer for Seattle. It sets up the starting 
  resource files, creates the necessary dictionaries, creates a vesseldict, etc.


"""

# need to load public keys
from repyportability import *
add_dy_support(locals())

dy_import_module_symbols("rsa.r2py")

import sys

import os

import persist

import nmresourcemath

import shutil

class InvalidVesselInfoError(Exception):
  """Error to indicate vesselinfo was invalid. """
  pass


def read_vesselinfo_from_file(filename):
  """
  <Purpose>
    Take a file containing the vessel information and construct a list.
    
  <Arguements>
    filename:
             name of file containing vessel information in the correct format.
             All the percentages should be a multiple of ten, and the sum of all
             the percentages should be 100%. A percentage here indicates the 
             percent of the resources being donated. A vessel MUST have a
             valid Percent and a owner, it does not need a user.
              
             "Percent  10 
              Owner   owners_publickey_filename
              User    users_publickey_filename
              User    users_publickey_filename
              ...
              User    users_publickey_filename
              Percent 20
              Owner   owners_publickey_filename
              User    users_publickey_filename
              Percent 10
              Owner   owners_publickey_filename
              User    users_publickey_filename
              ...
             "
              
  <Exceptions>
    InvalidVesselInfoError: Exception to indicate an improper vesselinfo
      file, it means a vessel did not have an owner or the file was corrupted
      or improperly formated.
    
    TypeError: In the event that there are empty lines in vesselinfo or
      that the format is incorrect.
      
    ValueError: Raised by rsa_string_to_publickey if the publickey string
      is improperly formated (IE not like "123 1234567").
      
  <Side Effects>
    None
  
  <Return>
    A list containing the vessel information in the format expected
    by create_installer_state. 
    [(vessel percent, ownerpubkeyfilename, list of user pubkeyfilenames),
      (vessel percent, ownerpubkeyfilename, list of user pubkeyfilenames),...]

  <WalkThrough>
    retvesselinfo = [] is the list that will contain the final result.
    
    Format for lastvesseldata
      lastvesseldata = [ percent , owner, list of users ]
           
    Start with the file 
      "Percent 100
       Owner bob
       User bob1
       User bob2"
       
      Line 1) "Percent 100" is read then lastvesseldata is initialized to
        be lastvesseldata = [ 100 , None, [] ]
      Line 2) "Owner bob" is read then lastvesseldata is set to
        lastvesseldata = [ 100 , 'bob', [] ]
      Line 3) "User bob1" is read then lastvesseldata is set to
        lastvesseldata = [ 100 , 'bob', ['bob1'] ]
      Line 4) "User bob2" is read then lastvesseldata is set to
        lastvesseldata = [ 100, 'bob', ['bob1','bob2']]
      
    lastvesseldata is appended to retvesselinfo and the process is repeated
    for another vessel if needed.
    
    This has created a list that will construct a node with 100% of its
    resources owned by bob.
  
  """
  
  retvesselinfo = []
  lastvesseldata = None
  for line in open(filename):

    vesselline = line.split() # This should be a list [vessel key word, value]
    if vesselline[0] == 'Percent': # indicates a new vessel should be started.
      # Check to ensure that the vessel has an owner.
      if lastvesseldata:
        if lastvesseldata[1] == None:
          raise InvalidVesselInfoError("Error, must have Owner for each vessel")
        retvesselinfo.append(lastvesseldata)
      # start a new vessel  
      lastvesseldata = [int(vesselline[1]), None, []]
    
    elif vesselline[0] == 'Owner':
      ownerkey = rsa_string_to_publickey(vesselline[1] + " " + vesselline[2])
      lastvesseldata[1] = ownerkey
    
    elif vesselline[0] == 'User':
      userkey = rsa_string_to_publickey(vesselline[1] + " " + vesselline[2])
      lastvesseldata[2].append(userkey)

  # Check to ensure that the vessel has an owner.  
  if lastvesseldata:
    if lastvesseldata[1] == None:
      raise InvalidVesselInfoError("Error, must have Owner for each vessel")
      
  retvesselinfo.append(lastvesseldata)
  
  # Check to ensure that at least one vessel was created.
  if len(retvesselinfo) == 1 and retvesselinfo[0] == None:
    raise InvalidVesselInfoError("Error, invalid 'vesselinfo' file.")
  
  return retvesselinfo


def main(vesselcreationlist, tenpercentdict, targetdirectory):
  """
  <Purpose>
    To take the vesselcreationlist (list containing owner and user info)
    and generate the initial resource files and directories. 
    
    Working Definition: 
      percentage - in this method we are dealing with how to split up the 
      donated resources (this could 10% of the system's available resources, 
      or it could be a user defined percentage but regardless we only 
      consider the portion donated). So any time we refer to percentages 
      in this method we are talking about the percentage of the donated 
      resources. This applies to the tenpercentdict that is passed as an
      arguement (it is only ten percent of the donated resources).
    
    This method does not special case the seattle vessel, it only creates
    vessels based off what is in the vesselcreationlist list (the original
    writecustominstaller handled the seattle vessel seperately).
    
  <Arguements>
    vesselcreationlist: a list that has the following format:
    [(vessel percent, ownerpubkeyfilename, list of user pubkeyfilenames),
      (vessel percent, ownerpubkeyfilename, list of user pubkeyfilenames),...]
      It contains the information for the initial vessels of the node.
     
    targetdirectory: a string containing the directory where the 
      restrictions files and vesseldict will be placed.
     
  <Exceptions>
    ValueError: if the vessel percent (from element 0 of a tuple in the 
      vesselcreationlist list) is not 10,20,30, ... , 80, 90, 100
      A ValueError will also be raised if the total percent (of all
      the vessel percents in the vesselcreationlist list) does not add
      up to the integer 100

    IOError: if vessel.restrictions is not found, this must be included
      ahead of time in the target directory.
  
    OSError, WindowsError: if os.mkdir is unable to create the vessel
      directories.
      
  <Side Effects>
    Creates the vesseldict using persist.commit_object.
    Creates resource files for each vessel with names of the form
      resource.v1, resource.v2, ...
    Creates a directory for each vessel with a name of the form v1, v2, ...
      
  <Return>
    None
  
  <Notes>   
    The vesselcreationlist is a list that has the following format:
    [(vessel percent, ownerpubkeyfilename, list of user pubkeyfilenames),
     (vessel percent, ownerpubkeyfilename, list of user pubkeyfilenames), ...]
  
    So it might look like:
      [(10, 'joe.publickey', []),
       (50, 'jim.publickey', ['alice.publickey', 'bob.publickey']), 
       (40, 'alice.publickey', []) ]
  
    This would indicate v1 is owned by joe and gets 10 percent, v2 is owned
    by jim has users alice and bob and gets 50 percent, v3 is owned by
    alice and gets 40 percent.   I'll track the seattle information and
    will write it independently.
  
  <Notes>
    The structure of this method can be described in 3 distinct sections.
    1) The vesseldict is constructed from the information in vesselcreationlist,
       is contains the public keys and other vessel information.
    2) The resource files are written to files for all the vessels
    3) Directories are created for all the vessels.
  """

  # Check to ensure that the vessel information is in the correct format.
  # Each vessel percent must be an integer multiple of ten from (0,100]
  # and the total must be 100. This is checked here instead of when the
  # list is originally constructed from the vesselinfo file so that only
  # this method must be changed if the granularity of the possible vessel
  # percentages is changed.  
  total = 0
  
  for item in vesselcreationlist:
    if item[0] not in range(10, 101, 10):
      raise ValueError, "Invalid vessel percent '"+str(item[0])+"'"
    total = total + item[0]

  if total != 100:
    raise ValueError, "Total of vessel percentage is '"+str(total)+"', not 100."


 
  vesseldict = {}
  vesselnumber = 1
  # time to work on the vessel dictionary...
  for item in vesselcreationlist:

    vesselname = 'v'+str(vesselnumber)

    vesseldict['v'+str(vesselnumber)] = {'userkeys':item[2], 'ownerkey':item[1], 'oldmetadata':None, 'stopfilename':vesselname+'.stop', 'logfilename':vesselname+'.log', 'statusfilename':vesselname+'.status', 'resourcefilename':'resource.'+vesselname, 'advertise':True, 'ownerinformation':'', 'status':'Fresh'}
    vesselnumber = vesselnumber + 1
    
  persist.commit_object(vesseldict,targetdirectory+"/vesseldict")


  # I'm going to do the resources / restrictions now...
  onetenth = tenpercentdict.copy()
  
  # These are the restrictions that apply to all vessels, they are
  # not a resource we measure.
  restrictionsfo = file('vessel.restrictions')
  restrictionsstring = restrictionsfo.read()
  restrictionsfo.close()

  # I'll use this to figure out which ports to assign
  usedpercent = 0
  vesselnumber = 1

  for item in vesselcreationlist:
    
    # the percentcount variable is slightly confusing, up until we have talked
    # about vessels as haveing 10 or 20 or ... percent of the donated resources.
    # We restrict vessels to being a multiple of ten so that we do not have to
    # cut down the donated resources to far (this is an attempt to keep things
    # simple and avoid getting resources at zero).
    # percentcount should be an integer between 0 and 10
    percentcount = item[0] / 10
    # make a resource file of the right size...
    size = percentcount
    thisresourcedata = tenpercentdict.copy()
    while size > 1:
      thisresourcedata = nmresourcemath.add(thisresourcedata, onetenth)
      size = size - 1

    # I need the ports...
    startpercent = usedpercent
    endpercent = usedpercent + percentcount
    # a yucky way of getting the ports.   Should do 63100-63109 for the first,
    # 63110-63119 for the second, etc.
    thisresourcedata['messport'] = set(range(63100+10*startpercent, 63100+10*endpercent))
    thisresourcedata['connport'] = set(range(63100+10*startpercent, 63100+10*endpercent))
    
    
    nmresourcemath.write_resource_dict(thisresourcedata, targetdirectory+"/resource.v"+str(vesselnumber))
        
    # append the restrictions data.
    restrictionsfo = file(targetdirectory+'/resource.v'+str(vesselnumber),"a")
    restrictionsfo.write(restrictionsstring)
    restrictionsfo.close()

    # increment the vesselnumber and used percent
    vesselnumber = vesselnumber + 1
    usedpercent = usedpercent + percentcount


  # Get the directory, if any, that is used for security layers.
  configuration = persist.restore_object("nodeman.cfg")
  repy_prepend_dir = None
  if 'repy_prepend_dir' in configuration:
    repy_prepend_dir = configuration['repy_prepend_dir']

  # Get the list of files in the security layer directory
  repy_prepend_files = []
  if repy_prepend_dir is not None:
    repy_prepend_files = os.listdir(repy_prepend_dir)

  # make the directories...
  for num in range(len(vesselcreationlist)):
    vesselname = 'v'+str(num+1)
    try:
      WindowsError

    except NameError: # not on windows...
      # make the vessel dirs...
      try:
        os.mkdir(targetdirectory+"/"+vesselname)
      except OSError,e:
        if e[0] == 17:
          # directory exists
          pass
        else:
          raise

    else: # on Windows...

      # make the vessel dirs...
      try:
        os.mkdir(targetdirectory+"/"+vesselname)
      except (OSError,WindowsError),e:
        if e[0] == 17 or e[0] == 183:
          # directory exists
          pass
        else:
          raise

    # Copy all the security layer files to the new vessel.
    for filename in repy_prepend_files:
      shutil.copy(os.path.join(repy_prepend_dir,filename), targetdirectory+"/"+vesselname)


  # and we're done!
