#!/bin/bash

cd "$(dirname $BASH_SOURCE)"

VANILLA=~/Documents/mac/primary/Sys710x.rdump
SUPERMARIO=~/Documents/mac/supermario/worktree/cube-e
BUILT=$SUPERMARIO/BuildResults/System/System.rdump

RH="-rh $SUPERMARIO/BuildResults/System/Lib/LinkedPatches.lib"
SH="-sh $SUPERMARIO/BuildResults/System/Text/LinkPatchJumpTbl"
COMMON="-w 16 $RH $SH"

for MODE in pt pm pr pj pjh pp; do
	(
		./patch_rip.py -$MODE $COMMON $BUILT   >/tmp/elliot-$MODE-lpch
		./patch_rip.py -$MODE $COMMON $VANILLA >/tmp/apple-$MODE-lpch; echo >>/tmp/apple-$MODE-lpch

		git diff --no-index -U999999999 /tmp/elliot-$MODE-lpch /tmp/apple-$MODE-lpch >lpch-$MODE.patch
		true
	) &
done

for job in `jobs -p`; do
	wait $job
done
