""" 
Author: Justin Cappos

Start Date: August 4, 2008

Description:
A software updater for the node manager.   The focus is to make it secure, 
robust, and simple (in that order).

Usage:  ./softwareupdater.py


Updated 1/23/2009 use servicelogger to log errors - Xuanhua (Sean)s Ren


"""



import sys
import os

# AR: Determine whether we're running on Android
try:
  import android
  is_android = True
except ImportError:
  is_android = False


import daemon


# this is being done so that the resources accounting doesn't interfere with logging
from repyportability import *
_context = locals()
add_dy_support(_context)


import urllib      # to retrieve updates
import random
import shutil
import socket   # we'll make it so we don't hang...
import tempfile
import traceback    # For exception logging if the servicelogger fails.
import runonce
import harshexit  # Used for portablekill
import portable_popen


# Import servicelogger to do logging
import servicelogger


dy_import_module_symbols("signeddata.r2py")
dy_import_module_symbols("sha.r2py")

# Armon: The port that should be used to update our time using NTP
TIME_PORT = 51234
TIME_PORT_2 = 42345

softwareurl = "https://sensibilityclearinghouse.poly.edu/updatesite/"

# embedded this because it seems easier to update it along with this file
# Every computer running Seattle will have this same public key, and will trust
# files signed by this key.
softwareupdatepublickey = {'e':65537, 'n':850516311642908482075083191348360387788364366799865048165653401413249310858891652778772628815207808251776747085276341828007395755004744862685275832699716193877185985845139924088950344910367926939086585488639871160501030381824876795914411861802834503882617615732372327216385730700757649884274237532480710766788420883367076491644116387715930228867869197753934626155942769710340946293971983731935056316203862498978255936300362082627141441239361298385196792744073417875496301192251108162638750973511151099921343881717412164647655716010281556079394828316272626282241170389625834661013565423391219193548572355380281861811310798788133784900628157886102648201396233100580919467946526716082763019846560347634503360123102398491291243626726305321753289626205428018191818444564116266314060820282951606136809393944344134085320327321300064536364213055275257555441723777848226989404513153269233614155740953709248750799343145751368474669957954611097392619327893924045209576661769697442686153480435288277261720273783119378132464998333015399786355939942363481927252328859597969126306593061133859023408591861890477952132444372120874209307300703290211155231175258952281371577131024185739471753755862104657229007037534941714802773782853027750088878974922148307520695544801759788244807335574835757209226296910817145048535978784912277570847790383361073463866758465153406800337003556201039984041453316543112168850031406167015459147820620644105492577143427475682067396876243783754131784008925804727340135477544647613339515054569914706941340987770596579855088119605726131832562729418447465709150769856101623825653873407861402935822317789327133192298984385235761377331687378140591915542890648480707975734743547412185981065892270740063989437010133279659339776823897488436094411085025580341765351947097477427030433681910486229552294021612146903265829340681527016608153318161051919817208671110550775843083798583019920094167775193438631222696823554974303304761424327400125990386942127174315120339441053293442375669782018411979113578221449720564118453435985529579771273214506366471962763057122578533746144646098465214751254653212141162751636309312427646316027156394755091933495769789664668097985032916742664889739805643601962189602086379642453167876604562051179656215966895861649771609173996556721573125173682257964152511159375724029538081755208952144666108431461002938004739376306589505648820441505999756486062208452948546832496935198602485411673335690189087806435873599657255347728477193314319391}

# Whether the nodemanager should be told not to daemonize when it is restarted.
# This is only to assist our automated tests.
run_nodemanager_in_foreground = False

# Whether the softwareupdater should run in the foreground or not. Default
# to yes.
run_softwareupdater_in_foreground = True

# If this is True, the software updater needs to restart itself. Once True, it
# will never be False again. This is global rather than in main() because the
# way that main() is currently written, an exception may escape from main and
# a loop in the global scope will catch it and call main() again.
restartme = False



# This code is in its own function called later rather than directly in the
# global scope right here because otherwise we need to ensure that the
# safe_log* methods are defined above this code or else they would cause a
# NameError because they aren't defined yet.
def safe_servicelogger_init():
  """
  This initializes the servicelogger in a way that will not throw an exception
  even if servicelogger.init() does.
  """
  # initialize the servicelogger to log on the softwareupdater file
  try:
    servicelogger.init("softwareupdater")
  except:
    # We assume that if servicelogger.init() fails, then safe_log will
    # fall back on using 'print' because servicelogger.log() calls
    # will throw a ValueError.
    safe_log("Servicelogger.init() failed. Will try to use stdout. The exception from servicelogger.init() was:")
    safe_log_last_exception()



def safe_log(message):
  """
  Log a message in a way that cannot throw an exception. First try to log using
  the servicelogger, then just try to print the message.
  """
  try:
    servicelogger.log(message)
  except:
    try:
      print message
    except:
      # As the standard output streams aren't closed, it would seem that this
      # should never happen. If it does, though, what can we do to log the
      # message, other than directly write to a file?
      pass



def safe_log_last_exception():
  """
  Log the last exception in a way that cannot throw an exception. First try to
  log using the servicelogger, then just try to print the message.
  """
  try:
    # Get the last exception in case the servicelogger fails.
    exceptionstr = traceback.format_exc()
  except:
    pass
  
  try:
    servicelogger.log_last_exception()
  except:
    try:
      print exceptionstr
    except:
      # As the standard output streams aren't closed, it would seem that this
      # should never happen. If it does, though, what can we do to log the
      # message, other than directly write to a file?
      pass




def get_file_hash(filename):
  fileobj = file(filename, 'rb')
  filedata = fileobj.read()
  fileobj.close()

  return sha_hexhash(filedata)



# We'll use this to get a file.   If it doesn't download in a reasonable time, 
# we'll fail. (BUG: doesn't do this yet.   I use timeouts, but they don't
# always work)
def safe_download(serverpath, filename, destdir, filesize):
  # TODO: filesize isn't being used.
  # TODO: raise an RsyncError from here if the download fails instead of
  #       returning True/False.
  try:
    # Create the destination directory just in case
    fullpath = os.path.join(destdir, filename)
    destination_directory = os.path.dirname(fullpath)
    os.makedirs(destination_directory)
  except OSError:
    pass

  try:
    # Fix for #1361.   serverpath may not end in '/'
    urllib.urlretrieve(serverpath+'/'+filename,destdir+filename)
    return True

  except Exception,e:
    # Steven: these errors are common enough that they don't merit tracebacks
    if 'timed out' in str(e):
      safe_log('Retrieve timed out')
    elif 'Name or service not known' in str(e):
      safe_log('[Error] Name or service not known')
    elif 'Temporary failure in name resolution' in str(e):
      safe_log('[Error] Temporary failure in name resolution')
    else:
      safe_log_last_exception()

    safe_log('[safe_download] Failed to download ' + serverpath + filename)
    return False
 
#  # how much we have left to download
#  remainingsize = filesize
#
#  # get a file-like object for the URL...
#  safefo = urllib.urlopen(filename)
#
#  # always close after this...
#  try:
#    # download up to "filesize" worth of data...   
#    # BUG: We also should check to see if this is too slow...
#    mydata
#  
#  
#  finally:
#    try:
#      safefo.close()
#    except:
#      pass



def _copy(orig_filename, copy_filename):
  # AR: Wrap Android-specific shutil.copy() quirks. They seem to have a problem 
  # setting the file access mode bits there, and shutil.copyfile() suffices 
  # for the task at hand.

  try:
    # Create the destination directory just in case
    destination_directory = os.path.dirname(copy_filename)
    os.makedirs(destination_directory)
  except OSError:
    pass

  if not is_android:
    shutil.copy(orig_filename, copy_filename)
  else:
    shutil.copyfile(orig_filename, copy_filename)




################### Begin Rsync ################### 
# I'd love to be able to put this in a separate module or repyify it, but 
# I'd need urllib...

class RsyncError(Exception):
  pass




def do_rsync(serverpath, destdir, tempdir):
  """
  <Purpose>
    This method is the one that attempts to download the metainfo file from
    the given serverpath, then uses that to attempt to do an update.  This
    method makes sure that the downloaded metainfo file is valid and signed
    correctly before changing any files.  Once the metainfo file is determined
    to be valid, it will then compare file hashes between the ones in the new
    metainfo file and the hashes of the files currently on disk.  If there is
    a difference, the new file is downloaded and added to the updated list.  
    Once all the new files have been downloaded, if they all did so 
    successfully they are then copied over the old ones, replacing them and
    completing the update of the files.  Then a list of the files updated is
    returned.

  <Arguments>
    serverpath - The url for the update site that we will try to contact.  
                 This should be the url of the directory that contains all of
                 the files that are being pushed as an update.
    destdir - This is the directory where the new files will end up if 
              everything goes well.
    tempdir - This is the directory where the new files will be initially
              downloaded to before their hashes are checked.  This is not
              cleaned up after finishing.

  <Exceptions>
    Will throw various socket errors if there is trouble getting a file from
    the webserver.
    Will throw an RsyncError if the downloaded metainfo is malformed, or if
    the hash of a downloaded file does not match the one listed in the 
    metainfo file.

  <Side Effects>
    Files will be downloaded to tempdir, and they might be copied over to
    destdir if everything is successful.

  <Returns>
    A list of files that have been updated.  The list is empty if nothing is
    to be updated.
  """

  # get the metainfo (like a directory listing)
  metainfo_downloaded = safe_download(serverpath, "metainfo", tempdir, 1024*32)

  # if downloading the new metainfo failed, then we can't really do anything
  if not metainfo_downloaded:
    safe_log("[do_rsync] Failed to download metainfo. Not updating.")
    return []

  # read the file data into a string
  newmetafileobject = file(tempdir+"metainfo")
  newmetafiledata = newmetafileobject.read()
  newmetafileobject.close()

  # Incorrectly signed, we don't update...
  if not signeddata_issignedcorrectly(newmetafiledata, softwareupdatepublickey):
    safe_log("[do_rsync] New metainfo not signed correctly. Not updating.")
    return []

  try:
    # read in the old file
    oldmetafileobject = file(destdir+"metainfo")
    oldmetafiledata = oldmetafileobject.read()
    oldmetafileobject.close()
  except Exception:
    # The old file has problems.   We'll use the new one since it's signed
    pass

  else:
    try:
      # Armon: Update our time via NTP, before we check the meta info
      time_updatetime(TIME_PORT)
    except Exception:
      try:
        time_updatetime(TIME_PORT_2)
      except Exception:
        # Steven: Sometimes we can't successfully update our time, so this is
        # better than generating a traceback.
        safe_log("[do_rsync] Unable to update ntp time. Not updating.")
        return []
    
    # they're both good.   Let's compare them...
    shoulduse, reasons = signeddata_shouldtrust(oldmetafiledata,newmetafiledata,softwareupdatepublickey)

    if shoulduse == True:
      # great!   All is well...
      pass
    elif shoulduse == None:
      # hmm, a warning...   
      if len(reasons) == 1 and reasons[0] == 'Cannot check expiration':
        # we should probably allow this.  The node may be offline
        # JCS: if it's offline, how is it downloading the metainfo or even
        # getting past the time_updatetime() calls above?
        safe_log("[do_rsync] Warning: " + str(reasons))
      elif 'Timestamps match' in reasons:
        # Already seen this one...
        safe_log("[do_rsync] The metainfo indicates no update is needed: " + str(reasons))
        return []

    elif shoulduse == False:
      if 'Public keys do not match' in reasons:
        # If the only complaint is that the oldmetafiledata and newmetafiledata
        # are signed by different keys, this is actually OK at this point.  We
        # know that the newmetafiledata was correctly signed with the key held
        # within this softwareupdater, so this should actually only happen when
        # the oldmetafiledata has an out of date signature.  However, we do 
        # still need to make sure there weren't any other fatal errors that 
        # we should distrust. - Brent
        reasons.remove('Public keys do not match')
        for comment in reasons:
          if comment in signeddata_fatal_comments:
            # If there is a different fatal comment still there, still log it
            # and don't perform the update.
            safe_log("[do_rsync] Serious problem with signed metainfo: " + str(reasons))
            return []
            
          if comment in signeddata_warning_comments:
            # If there is a different warning comment still there, log the
            # warning.  We will take care of specific behavior shortly.
            safe_log("[do_rsync] " + str(comment))
            
        if 'Timestamps match' in reasons:
          # Act as we do above when timestamps match
          # Already seen this one...
          safe_log("[do_rsync] The metainfo indicates no update is needed: " + str(reasons))
          return []
      else:
        # Let's assume this is a bad thing and exit
        safe_log("[do_rsync] Something is wrong with the metainfo: " + str(reasons))
        return []

  # now it's time to update
  updatedfiles = [ "metainfo" ]

  for line in file(tempdir+"metainfo"):

    # skip comments
    if line[0] == '#':
      continue
 
    # skip signature parts
    if line[0] == '!':
      continue
 
    # skip blank lines
    if line.strip() == '':
      continue

    linelist = line.split()
    if len(linelist)!= 3:
      raise RsyncError, "Malformed metainfo line: '"+line+"'"

    filename, filehash, filesize = linelist
    
    shoulddownloadfile = False
    
    # if the file is missing or the hash is different, we want to download...
    if not os.path.exists(destdir+filename):
      shoulddownloadfile = True
      safe_log("[do_rsync] Downloading file " + filename + " because it doesn't already exist at " + destdir+filename)
    elif get_file_hash(destdir+filename) != filehash:
      shoulddownloadfile = True
      safe_log("[do_rsync] Downloading file " + filename + " because the hash changed.")
      
    if shoulddownloadfile:
      # get the file
      safe_download(serverpath, filename, tempdir, filesize)

      # The hash doesn't match what we expected it to be according to the signed metainfo.
      if get_file_hash(tempdir+filename) != filehash:
        safe_log("[do_rsync] Hash mismatch on file '"+filename+"':" + filehash +
            " vs " + get_file_hash(tempdir+filename))
        raise RsyncError, "Hash of file '"+filename+"' does not match information in metainfo file"

      # put this file in the list of files we need to update
      updatedfiles.append(filename)      


  # copy the files to the local dir...
  safe_log("[do_rsync] Updating files: " + str(updatedfiles))
  for filename in updatedfiles:
    _copy(tempdir+filename, destdir+filename)
    
  # done!   We updated the files
  return updatedfiles
  
################### End Rsync ################### 





# MUTEX  (how I prevent multiple copies)
# a new copy writes an "OK" file. if it's written the previous can exit.   
# a previous copy writes a "stop" file. if it's written the new copy must exit
# each new program has its own stop and OK files (listed by mutex number)
# 
# first program (fresh_software_updater)
#              get softwareupdater.new mutex
#              clean all mutex files
#              once in main, take softwareupdater.old, release softwareupdater.new
#              exit if we ever lose softwareupdater.old
#
# old program (restart_software_updater)
#              find an unused mutex 
#              starts new with arg that is the mutex
#              wait for some time
#              if "OK" file exists, release softwareupdater.old, remove it and exit
#              else write "stop" file
#              continue normal operation
#
# new program: (software_updater_start)
#              take softwareupdater.new mutex
#              initializes
#              if "stop" file exists, then exit
#              write "OK" file
#              while "OK" file exists
#                 if "stop" file exists, then exit
#              take softwareupdater.old, release softwareupdater.new
#              start normal operation
#


def init():
  """
  <Purpose>
    This method is here to do a runthrough of trying to update.  The idea is
    that if there is going to be a fatal error, we want to die immediately
    rather than later.  This way, when a node is updating to a flawed version,
    the old one won't die until we know the new one is working.  Also goes
    through the magic explained in the comment block above.

  <Arguments>
    None

  <Exceptions>
    See fresh_software_updater and software_updater_start.

  <Side Effects>
    If we can't get the lock, we will exit.
    We will hold the softwareupdater.new lock while trying to start, but if
    all goes well, we will release that lock and aquire the 
    softwareupdater.old lock.

  <Returns>
    None
  """
  # Note: be careful about making this init() method take too long. If it takes
  # longer to complete than the amount of time that restart_software_updater()
  # waits, then the new software updater will never be left running. Keep in
  # mind very slow systems and adjust the wait time in restart_software_updater()
  # if needed.
  
  gotlock = runonce.getprocesslock("softwareupdater.new")
  if gotlock == True:
    # I got the lock.   All is well...
    pass
  else:
    # didn't get the lock, and we like to be real quiet, so lets 
    # exit quietly
    sys.exit(55)

  # Close stdin because we don't read from stdin at all. We leave stdout and stderr
  # open because we haven't done anything to make sure that output to those (such as
  # uncaught python exceptions) go somewhere else useful.
  sys.stdin.close()

  # don't hang if the socket is slow (in some ways, this doesn't always work)
  # BUG: http://mail.python.org/pipermail/python-list/2008-January/471845.html
  socket.setdefaulttimeout(10)

  # time to handle startup (with respect to other copies of the updater
  if len(sys.argv) == 1:
    # I was called with no arguments, must be a fresh start...
    fresh_software_updater()
  else:
    # the first argument is our mutex number...
    software_updater_start(sys.argv[1])


def software_updater_start(mutexname):
  """
  <Purpose>
    When restarting the software updater, this method is called in the new 
    one.  It will write an OK file to let the original know it has started,
    then will wait for the original to acknowledge by either removing the OK
    file, meaning we should carry on, or by writing a stop file, meaning we
    should exit.  Carrying on means getting the softwareupdater.old lock, and
    releasing the softwareupdater.new lock, then returning.
  
  <Arguments>
    mutexname - The new software updater was started with a given mutex name,
                which is used to uniquely identify the stop and OK files as
                coming from this softwareupdater.  This way the old one can
                know that the softwareupdater it started is the one that is
                continueing on.

  <Exceptions>
    Possible Exception creating the OK file.

  <Side Effects>
    Acquires the softwareupdater.old lock and releases the softwareupdater.new
    lock.

  <Return>
    None
  """

  safe_log("[software_updater_start] This is a new software updater process started by an existing one.")

  # if "stop" file exists, then exit
  if os.path.exists("softwareupdater.stop."+mutexname):
    safe_log("[software_updater_start] There's a stop file. Exiting.")
    sys.exit(2)

  # write "OK" file
  file("softwareupdater.OK."+mutexname,"w").close()
  
  # while "OK" file exists
  while os.path.exists("softwareupdater.OK."+mutexname):
    safe_log("[software_updater_start] Waiting for the file softwareupdater.OK."+mutexname+" to be removed.")
    sleep(1.0)
    # if "stop" file exists, then exit
    if os.path.exists("softwareupdater.stop."+mutexname):
      sys.exit(3)

  # Get the process lock for the main part of the program.
  gotlock = runonce.getprocesslock("softwareupdater.old")
  # Release the lock on the initialization part of the program
  runonce.releaseprocesslock('softwareupdater.new')
  if gotlock == True:
    # I got the lock.   All is well...
    pass
  else:
    if gotlock:
      safe_log("[software_updater_start] Another software updater old process (pid: "+str(gotlock)+") is running")
      sys.exit(55)
    else:
      safe_log("[software_updater_start] Another software updater old process is running")
      sys.exit(55)
 
  safe_log("[software_updater_start] This software updater process is now taking over.")
 
  # start normal operation
  return


# this is called by either the installer or the program that handles starting
# up on boot
def fresh_software_updater():
  """
  <Purpose>
    This function is ment to be called when starting a softwareupdater when no
    other is currently running.  It will clear away any outdated OK or stop
    files, then release the softwareupdater.new lock and acquire the
    softwareupdater.old lock.

  <Arguments>
    None
 
  <Exceptions>
    Possible exception if there is a problem removing the OK/stop files.    

  <Side Effects>
    The softwareupdater.new lock is released.
    The softwareupdater.old lock is acquired.
    All old OK and stop files are removed.

  <Returns>
    None
  """
  # clean all mutex files
  for filename in os.listdir('.'):
    # Remove any outdated stop or OK files...
    if filename.startswith('softwareupdater.OK.') or filename.startswith('softwareupdater.stop.'):
      os.remove(filename)

  # Get the process lock for the main part of the program.
  gotlock = runonce.getprocesslock("softwareupdater.old")
  # Release the lock on the initialization part of the program
  runonce.releaseprocesslock('softwareupdater.new')
  if gotlock == True:
    # I got the lock.   All is well...
    pass
  else:
    if gotlock:
      safe_log("[fresh_software_updater] Another software updater old process (pid: "+str(gotlock)+") is running")
      sys.exit(55)
    else:
      safe_log("[fresh_software_updater] Another software updater old process is running")
      sys.exit(55)
  # Should be ready to go...

  safe_log("[fresh_software_updater] Fresh software updater started.")


def get_mutex():
  # do this until we find an unused file mutex.   we should find one 
  # immediately with overwhelming probability
  while True:
    randtoken = str(random.random())
    if not os.path.exists("softwareupdater.OK."+randtoken) and not os.path.exists("softwareupdater.stop."+randtoken):
      return randtoken
  

def restart_software_updater():
  """
  <Purpose>
    Attempts to start a new software updater, and will exit this one if the
    new one seems to start successfully.  If the new one does not start
    successfully, then we just return.

  <Arguments>
    None

  <Exceptions>
   Possible exception if there is problems writing the OK file.
 
  <Side Effects>
    If all goes well, a new softwareupdater will be started, and this one will
    exit.

  <Returns>
    In the successful case, it will not return.  If the new softwareupdater does
    not start correctly, we will return None.
  """

  safe_log("[restart_software_updater] Attempting to restart software updater.")

  # find an unused mutex 
  thismutex = get_mutex()

  # starts new with arg that is the mutex 
  junkupdaterobject = portable_popen.Popen([sys.executable,"softwareupdater.py",thismutex])

  # wait for some time (1 minute) for them to init and stop them if they don't
  for junkcount in range(30):
    sleep(2.0)

    # if "OK" file exists, release softwareupdater.old, remove OK file and exit
    if os.path.exists("softwareupdater.OK."+thismutex):
      runonce.releaseprocesslock('softwareupdater.old')
      os.remove("softwareupdater.OK."+thismutex)
      # I'm happy, it is taking over
      safe_log("[restart_software_updater] The new instance of the software updater is running. This one is exiting.")
      sys.exit(10)

  # else write "stop" file because it failed...
  file("softwareupdater.stop."+thismutex,"w").close()

  safe_log("[restart_software_updater] Failed to restart software updater. This instance will continue.")

  # I continue normal operation
  return



def restart_client(filenamelist):
  """
  <Purpose>
    Restarts the node manager.

  <Arguments>
    filenamelist - Currently not used, but is included for possible future use.

  <Exceptions>
    None

  <Side Effects>
    The current node manager is killed, and a new one is started.

  <Returns>
    None.
  """
  # kill nmmain if it is currently running
  retval = runonce.getprocesslock('seattlenodemanager')
  if retval == True:
    safe_log("[restart_client] Obtained the lock 'seattlenodemanager', it wasn't running.")
    # I got the lock, it wasn't running...
    # we want to start a new one, so lets release
    runonce.releaseprocesslock('seattlenodemanager')
  elif retval == False:
    # Someone has the lock, but I can't do anything...
    safe_log("[restart_client] The lock 'seattlenodemanager' is held by an unknown process. Will try to start it anyways.")
  else:
    safe_log("[restart_client] Stopping the nodemanager.")
    # I know the process ID!   Let's stop the process...
    harshexit.portablekill(retval)
  
  safe_log("[restart_client] Starting the nodemanager.")

  # run the node manager.   I rely on it to do the smart thing (handle multiple
  # instances, etc.)
  nm_restart_command_args_list = [sys.executable, "nmmain.py"]
  
  if run_nodemanager_in_foreground:
    nm_restart_command_args_list.append('--foreground')
  
  junkprocessobject = portable_popen.Popen(nm_restart_command_args_list)
  
  # I don't do anything with the processobject.  The process will run for some 
  # time, perhaps outliving me (if I'm updated first)


def main():
  """
  <Purpose>
    Has an infinite loop where we sleep for 5-55 minutes, then check for 
    updates.  If an update happens, we will restart ourselves and/or the
    node manager as necesary.
    
  <Arguments>
    None

  <Exceptions>
    Any non-RsyncError exceptions from do_rsync.

  <Side Effects>
    If there is an update on the update site we are checking, it will be 
    grabbed eventually.

  <Return>
    Will not return.  Either an exception will be thrown, we exit because we
    are restarting, or we loop infinitely.
  """

  global restartme

  # This is similar to init only:
  #   1) we loop / sleep
  #   2) we restart ourselves if we are updated
  #   3) we restart our client if they are updated

  while True:
    # sleep for 5-55 minutes 
    for junk in range(random.randint(10, 12)):
      # We need to wake up every 30 seconds otherwise we will take
      # the full 5-55 minutes before we die when someone tries to
      # kill us nicely.
      sleep(30)
      # Make sure we still have the process lock.
      # If not, we should exit
      if not runonce.stillhaveprocesslock('softwareupdater.old'):
        safe_log('[main] We no longer have the processlock\n')
        sys.exit(55)


    # Make sure that if we failed somehow to restart, we keep trying before
    # every time we try to update. - Brent
    if restartme:
      restart_software_updater()
      
    # where I'll put files...
    tempdir = tempfile.mkdtemp()+"/"


    # I'll clean this up in a minute
    try:
      updatedlist = do_rsync(softwareurl, "./",tempdir)
    except RsyncError:
      # oops, hopefully this will be fixed next time...
      continue

    finally:
      shutil.rmtree(tempdir)

    # no updates   :)   Let's wait again...
    if updatedlist == []:
      continue

    # if there were updates, the metainfo file should be one of them...
    assert('metainfo' in updatedlist)

    clientlist = updatedlist[:]

    if 'softwareupdater.py' in clientlist:
      restartme = True
      clientlist.remove('softwareupdater.py')

    # if the client software changed, let's update it!
    # AR: On Android, the native app takes care of starting/restarting 
    # the client and/or updater, depending on the exit code we return here.
    if clientlist != []:
      if not is_android:
        restart_client(clientlist)
      else:
        sys.exit(200) # Native app should restart both client and updater

    # oh! I've changed too.   I should restart...   search for MUTEX for info
    if restartme:
      if not is_android:
        restart_software_updater()
      else:
        sys.exit(201) # Native app should restart the updater





def read_environmental_options():
  """
  This doesn't read command line options. It reads environment variable
  options. The reason is because the software updater currently expects that
  any first command line arg is the name of a mutex used by an already running
  software updater. I don't see any good reason to risk changing more than is
  needed until more major changes are being made to the software updater.
  This also makes it so that we don't have to bother passing the option through
  to restarts of the softwareupdater.
  """
  try:
    global run_nodemanager_in_foreground
    global run_softwareupdater_in_foreground
    if 'SEATTLE_RUN_NODEMANAGER_IN_FOREGROUND' in os.environ:
      run_nodemanager_in_foreground = True
    if os.environ.get('SEATTLE_RUN_SOFTWAREUPDATER_IN_FOREGROUND', True) == "False":
      run_softwareupdater_in_foreground = False
  except:
    # The defaults here are safe, so if something went wrong in
    # the code above, however unlikely, let's ignore it.
    pass




if __name__ == '__main__':
  read_environmental_options()
  if not run_softwareupdater_in_foreground:
    daemon.daemonize()

  # Initialize the service logger.
  safe_servicelogger_init()
  
  # problems here are fatal.   If they occur, the old updater won't stop...
  try:
    init()
  except Exception, e:
    safe_log_last_exception()
    raise e

  # in case there is an unexpected exception, continue (we'll sleep first thing
  # in main)
  while True:
    try:
      main()
    except SystemExit:
      # If there is a SystemExit exception, we should probably actually exit...
      raise
    except Exception, e:
      # Log the exception and let main() run again.
      safe_log_last_exception()
      # Sleep a little to prevent a fast loop if the exception is happening
      # before any other calls to do_sleep().
      sleep(1.0)
