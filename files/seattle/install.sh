#!/bin/sh

cd "`echo $0 | sed 's/install.sh/seattle_repy/'`"

if grep "'seattle_installed': False" nodeman.cfg > /dev/null
then
    ./install.sh $*
else
    echo "Seattle was already installed. You must run the uninstall script before reinstalling Seattle"
fi
