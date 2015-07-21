"""
<Program Name>
  impose_seattlestopper_lock.py

<Started>
  December 25, 2009

<Author>
  Zachary Boka

<Purpose>
  Forces the seattle node manager and software updater to quit if they are
  running.
"""

import runonce
import harshexit


locklist = ["seattlenodemanager", "softwareupdater.old", "softwareupdater.new"]



def main():
  """
  <Purpose>
    Kills all the seattle programs that are running.

  <Arguments>
    None.
  
  <Exceptions>
    None.

  <Side Effects>
    Kills all the seattle programs that are running.

  <Returns>
    None.
  """
  for lockname in locklist:
    lockstate = runonce.getprocesslock(lockname)
    # If lockstate is a process pid, then we need to terminate it. Otherwise,
    # that lock is not being held by a program that needs to be terminated. 
    if not lockstate == True and not lockstate == False:
      # We got the pid, we can stop the process
      harshexit.portablekill(lockstate)

      # Now acquire the lock for ourselves, looping until we
      # actually get it.
      retrievedlock = runonce.getprocesslock(lockname)
      while retrievedlock != True:
        harshexit.portablekill(retrievedlock)
        retrievedlock = runonce.getprocesslock(lockname)




if __name__ == '__main__':
  main()
