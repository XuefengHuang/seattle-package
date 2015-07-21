#!/bin/sh
which_out=`which python`
if [ "$which_out" = "" ]; then
    echo seattle requires that python be installed on your computer.
    echo Please install python and try again.
else
    cd "`echo $0 | sed 's/install.sh//'`"
    python seattleinstaller.py $*
fi
exit
