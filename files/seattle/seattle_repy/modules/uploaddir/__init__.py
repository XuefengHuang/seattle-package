import seash_exceptions
import command_callbacks
import os

module_help = """
UploadDir Module

Using this module, you can upload the contents of a directory 
(i.e. the code and data files it contains) to all of the VMs in 
your current seash target (e.g., browsegood).

A typical use case would be to create a directory on your local 
machine, then copy into it all the code (including libraries) and 
data your program needs to function, and lastly do

user@target !> uploaddir /path/to/directory

to have seash upload each file to every VM in 'target'.

(Note however that this module does not allow you to create 
directories on VMs. This is not supported in Repy!)
"""



def upload_directory_contents(input_dict, environment_dict):
  """This function serves to upload every file in a user-supplied 
  source directory to all of the vessels in the current target group.
  It essentially calls seash's `upload` function repeatedly, each 
  time with a file name taken from the source directory.

  A note on the input_dict argument:
  `input_dict` contains our own `command_dict` (see below), with 
  the `"[ARGUMENT]"` sub-key of `children` renamed to what 
  argument the user provided. In our case, this will be the source 
  dir to read from. (If not, this is an error!)
  """
  # Check user input and seash state:
  # 1, Make sure there is an active user key.
  if environment_dict["currentkeyname"] is None:
    raise seash_exceptions.UserError("""Error: Please set an identity before using 'uploaddir'!
Example:

 !> loadkeys your_user_name
 !> as your_user_name
your_user_name@ !>
""")

  # 2, Make sure there is a target to work on.
  if environment_dict["currenttarget"] is None:
    raise seash_exceptions.UserError("""Error: Please set a target to work on before using 'uploaddir'!
Example
your_user_name@ !> on browsegood
your_user_name@browsegood !> 
""")

  # 3, Complain if we don't have a source dir argument
  try:
    source_directory = input_dict["uploaddir"]["children"].keys()[0]
  except IndexError:
    raise seash_exceptions.UserError("""Error: Missing operand to 'uploaddir'

Please specify which source directory's contents you want uploaded, e.g.
your_user_name@browsegood !> uploaddir a_local_directory

""")


  # Sanity check: Does the source dir exist?
  if not os.path.exists(source_directory):
    raise seash_exceptions.UserError("Error: Source directory '" + source_directory + "' does not exist.")

  # Sanity check: Is the source dir a directory?
  if not os.path.isdir(source_directory):
    raise seash_exceptions.UserError("Error: Source directory '" + source_directory + "' is not a directory.\nDid you mean to use the 'upload' command instead?")

  # Alright --- user input and seash state seem sane, let's do the work!
  # These are the files we will need to upload:
  file_list = os.listdir(source_directory)

  for filename in file_list:
    # We construct the filename-to-be uploaded from the source dir, 
    # the OS-specific path separator, and the actual file name. 
    # This is enough for `upload_target` to find the file.
    path_and_filename = source_directory + os.sep + filename
    print "Uploading '" + path_and_filename + "'..."

    # Construct an input_dict containing command args for seash's 
    # `upload FILENAME` function.
    # XXX There might be a cleaner way to do this.
    faked_input_dict = {"upload": {"name": "upload", 
        "children": {path_and_filename: {"name": "filename"}}}}
    command_callbacks.upload_filename(faked_input_dict, environment_dict)




command_dict = {
  "uploaddir": {
    "name": "uploaddir",
    "callback": upload_directory_contents,
    "summary": "Upload every file in the specified directory",
    "help_text": module_help,
    "children": {
      "[ARGUMENT]": {
        "name": "source_directory",
        "callback": None,
        "children": {},
      }
    }
  }
}


moduledata = {
  'command_dict': command_dict,
  'help_text': module_help,
  'url': None,
}



