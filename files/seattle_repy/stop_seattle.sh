#!/bin/sh

cd "`echo $0 | sed 's/stop_seattle.sh//'`"

python stop_all_seattle_processes.py


# Check to confirm that nmmain.py and softwareupdater.py have been killed and
#   echo the status to the user.
# Some systems respond differently to some options passed to 'ps', so we use
#   'ps axww' to create a universal command that will tell us if nmmain.py
#   is currently running.
#
#   'ps axww':
#     'ax': shows all processes
#     'ww': makes sure that the output is not limited by column length.
#     

NMMAIN=`ps axww 2>/dev/null | grep nmmain.py | grep -i python | grep -v grep`
SOFTWAREUPDATER=`ps axww 2>/dev/null | grep softwareupdater.py | \
    grep -i python | grep -v grep`
    

if ! echo "$NMMAIN" | grep nmmain.py > /dev/null
then
    if ! echo "$SOFTWAREUPDATER" | grep softwareupdater.py > /dev/null
    then
	echo "seattle has been stopped: $(date)"
    fi
else
    echo "seattle could not be stopped for an unknown reason."
    echo "If you continue to see this error, please contact the seattle" \
	"development team."
fi