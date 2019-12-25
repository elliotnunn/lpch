#!/bin/bash

cd "$(dirname $BASH_SOURCE)"

VANILLA=~/Documents/mac/primary/Sys710x.rdump
SUPERMARIO=~/Documents/mac/supermario/worktree/cube-e
BUILT=$SUPERMARIO/BuildResults/System/System.rdump

WIDTHS="16 32 64"

MODE=-pj
RH="-rh $SUPERMARIO/BuildResults/System/Lib/LinkedPatches.lib"
SH="-sh $SUPERMARIO/BuildResults/System/Text/LinkPatchJumpTbl"

for WIDTH in $WIDTHS; do
	DEST=lpchdmp$WIDTH.txt
	COLUMN=$((10 + $WIDTH*5/4 + 4))
	(
		paste \
			<(./patch_rip.py $VANILLA $MODE -w $WIDTH $RH $SH | cut -c -$(($COLUMN-1)) ) \
			<(./patch_rip.py $BUILT   $MODE -w $WIDTH $RH $SH ) \
		| expand -t $COLUMN
	)>/tmp/$DEST &
done

for job in `jobs -p`; do
    wait $job
done

for WIDTH in $WIDTHS; do
	DEST=lpchdmp$WIDTH.txt
	mv /tmp/$DEST $DEST
done
