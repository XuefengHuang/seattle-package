"""
<Program>
  measuredisk_linux.py

<Author>
  Brent Couvrette
  Modified by Anthony Honstain

<Started>
  January 17, 2008

<Purpose>
  This script will attempt to measure disk read and write rate.
  
  
"""

import os

# Used to determine the os type and for getruntime.
import nonportable

# Get the ctypes stuff so we can call libc.sync() instead of using subprocces.
# We want to do all the importing and such here so that it doesn't muck with
# the timing.  These things don't seem to be available on Windows, so we will
# only import them where we need them (Linux)
# Anthony - found this descriptions of libc.sync at
# http://www.delorie.com/djgpp/doc/libc/libc_798.html
# Intended to assist porting Unix programs. Under Unix, sync flushes all caches
# of previously written data. In this implementation, sync calls fsync on every 
# open file. See section fsync. It also calls _flush_disk_cache (see 
# section _flush_disk_cache) to try to force cached data to the disk.
if nonportable.osrealtype == 'Linux':
  import ctypes
  import ctypes.util
  libc = ctypes.CDLL(ctypes.util.find_library("c"))


def measure_write(write_file_obj, blocksize, totalbytes, use_sync=False):
  """
  <Purpose>
    Attempts to measure the disk write rate by writing totalbytes bytes to a
    temporary file (performing a flush each time blocksize many bytes have been
    written), timing how long it took, and dividing num_bytes by the time
    to get the write rate.

  <Arguments>
    write_file - The file to be written to.  This should be an already opened
                 file handle that was opened with write access.

    blocksize - The amount of data in bytes to write before a flush is performed.
    
    totalbytes - The total number of bytes that should be written for the test.

    use_sync - Set to True if sync should be used to make sure the data is
               actually written to disk.  Should not be set to True on
               Windows because sync does not exist there.  Defaults to False.

  <Side Effects>
    Creates a file of size totalbytes.

  <Exceptions>
    Exceptions could be thrown if there is a problem opening/writing the file.
    
    ZeroDivisionError if the drive is to fast for the accuracy of the clock (for
    a fast drive in combination with a time that provided poor granularity.

  <Return>
    A tuple (rate, fn) where rate is the measured write rate, and fn is the 
    name of the file created.  It is up to the caller to ensure that this 
    file is deleted.  We do not delete it here because it will likely be 
    useful in doing the read rate measurments.
  """
  
  start_time = nonportable.getruntime()
 
  for trial in range(0, totalbytes, blocksize):
    write_file_obj.write(' ' * blocksize)
    #write_file_obj.flush()
    #if use_sync:
    #  # Only use sync if it is requested. See comment at import for explanation.
    #  libc.sync()

  write_file_obj.flush()
  end_time = nonportable.getruntime()

  return (totalbytes)/(end_time - start_time)


def measure_read(read_file_obj, blocksize):
  """
  <Purpose>
    Attempts to measure the disk read rate by reading blocksize bytes from a
    temp file, timing how long it took, and dividing blocksize by the time
    to get the read rate.  Note that at this time, read rate is far too fast
    because it reads what was just written.  It should be ok to just take the
    value given by the write test and use it for both read and write rate.

  <Arguments>
    read_file_obj - The file object that is to be read from for the read test.
                    This file object is not closed by this function.
    blocksize - The number of bytes that should be read to determine the
                read rate.

  <Side Effects>
    None

  <Exceptions>
    Exceptions could be thrown if there is a problem opening/reading the file.

    ZeroDivisionError if the drive is to fast for the accuracy of the clock (for
    a fast drive in combination with a time that provided poor granularity.
    
  <Return>
    A tuple (rate, blocksize) where rate is the measured read rate, and 
    blocksize is the number of bytes actually read.  It will be no more than
    what was actually asked for, but it could be less if the given file was 
    too short.  The read rate will have been calculated using the returned
    blocksize.
  """

  # Time how long it takes to read in blocksize.
  start_time = nonportable.getruntime()
  junk_data = read_file_obj.read(blocksize)
  end_time = nonportable.getruntime()

  blocksize = len(junk_data)

  return (blocksize/(end_time - start_time), blocksize)


def main():
  """
  <Purpose>
    Attempts to measure the read write rate of the system's hard drive. The
    test will write 10240 bytes of data, 1 byte at a time to the drive and
    measure the time required. A single byte was chosen because it was the 
    slowest and most resource intensive, so we can provide the most 
    protection to the end user.
  
  <Arguements>
    None
  
  <Exceptions>
    IOError if the file cannot be opened.
    Exceptions could be thrown if there is a problem opening/reading the file.
  
    ZeroDivisionError if the drive is to fast for the accuracy of the clock (for
    a fast drive in combination with a time that provided poor granularity.
  
  <Side Effects>
    Creates a file of size totalbytes, may consume additional system resources
    for the flush operation.
    
  <Return>
    A tuple containing the write rate and the read rate for the hard drive
    (in bytes/sec) where this program is run from. 
  """
  # blocksize: the size in bytes of data to write or read at a time
  # (the amount of data to write before a flush/sync is called).
  # 1 byte was chosen because in testing it produced the slowest write
  # rate, so it seems the safest choice (to avoid a vessel performing
  # many 1 byte reads that would go unnoticed if we assumed all drives 
  # could write at 'ideal' speeds 30megabytes per second, and the users 
  # machine getting swamped).
  blocksize = 1
  
  # totalbytes: the total number of bytes that are to be written for the
  # test.
  # 10240 total bytes was chosen because on the test machine it appeared to
  # be the smallest total that provided consistent results.
  totalbytes = 10240
  
  # Create the filename based on the pid to make sure we don't accidentally
  # overwrite something.  I don't use mkstemp because I'm not sure those
  # files are necesarily written to disk.
  pid = os.getpid()
  write_file_obj = open('rate_measure.'+str(pid), 'w')
  try:    
    # On linux sync needs to be run, otherwise it returns values an order of
    # magnitude too large.
    if nonportable.osrealtype == 'Linux':
      # Anthony - I have not been able to measure the benefit of using
      # 'libc' on a linux system, until I am able explore the linux
      # specific advantage of performing this we will not use it.
      write_rate = measure_write(write_file_obj, blocksize, totalbytes, False)
    else:
      write_rate = measure_write(write_file_obj, blocksize, totalbytes)
      
    write_file_obj.close()
  
    #write_file_obj = open('rate_measure.'+str(pid), 'r')
    #read_rate, numbytesread = measure_read(write_file_obj, totalbytes)
    #write_file_obj.close()
  finally:
    os.remove(write_file_obj.name)

  # Currently the read rate measurement is ridiculusly high, likely because
  # we are reading something that we just wrote.  Because it would be 
  # non-trivial to get an accurate read rate, we feel it is safe enough to
  # assume that the read and write rates are the same, so we just print out
  # the write_rate here as well.
  return int(write_rate), int(write_rate)
  
if __name__ == '__main__':

  write_rate, read_rate = main(block, total)
  
  print 'resource filewrite ' + str(write_rate)
  # Currently the read rate measurement is ridiculusly high, likely because
  # we are reading something that we just wrote.  Because it would be 
  # non-trivial to get an accurate read rate, we feel it is safe enough to
  # assume that the read and write rates are the same, so we just print out
  # the write_rate here as well.
  print 'resource fileread ' + str(write_rate)
  
