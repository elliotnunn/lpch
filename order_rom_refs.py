#!/usr/bin/env python3

import argparse
import re
from os import path


parser = argparse.ArgumentParser(description='''
    Determine the order in which various object files make jmpROM, jsrROM etc calls.
    This is relevant to matching up the link order with the linkedpatch ROM bind order
''')

parser.add_argument('src', action='store', nargs='+', help='Object files')
parser.add_argument('-1', action='store_true', dest='onlyonce', help='Mention each rom reference only once')
parser.add_argument('-f', '--filter', action='store', dest='filter', help='List of truly included ROM reference names (one per line)')
parser.add_argument('-n', '--number', action='store', dest='number', type=int, help='lpch resource number (helps sub-filter -f)')
args = parser.parse_args()

every = None
right_number = True
if args.number: right_number = False
if args.filter:
    every = set()
    for l in open(args.filter):
        if args.number:
            if 'lpch %d' % args.number in l:
                right_number = True
            elif 'lpch ' in l:
                right_number = False
        l = l.partition(';')[0].split()
        if len(l) == 1:
            if right_number:
                name = l[0]
                every.add(name)

already = set()
for src_path in args.src:
    if not args.onlyonce: already = set()

    obj_file = open(src_path, 'rb').read()
    if obj_file.startswith(b'\x01'):
        didprint = False
        for m in re.finditer(rb'ROM\$([_A-Za-z][_A-Za-z0-9@%]*)\$', obj_file):
            rom_name = m.group(1).decode('mac_roman')
            if (every is None or rom_name in every) and rom_name not in already:
                if not didprint:
                    print(path.basename(src_path))
                    didprint = True
                already.add(rom_name)
                print('  ' + rom_name)
