#!/bin/sh

cd "`echo $0 | sed 's/uninstall.sh//'`"

python seattleuninstaller.py $*
