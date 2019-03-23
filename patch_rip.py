#!/usr/bin/env python3

import argparse
import math
import struct


def parse_res_file(f):
    import macresources

    res = macresources.parse_rez_code(open(f, 'rb').read())
    res = (r for r in res if r.type == b'lpch')
    return sorted((r.id,r.data) for r in res)

def parse_raw_files(ff):
    biglist = []
    for f in ff:
        num = ''
        for char in reversed(f):
            if char not in '0123456789': break
            num = char + num
        num = int(num)

        dat = open(f, 'rb').read()

        biglist.append((num, dat))

    return sorted(biglist)

def exact_log(n):
    if not n: return None
    sh = 0
    while n & 1 == 0:
        sh += 2
        n >>= 1
    if n != 1: return None
    return sh


class Mod:
    def __init__(self):
        self.entry_points = []
        self.references = []
        self.start = -1
        self.stop = -1
        self.jt_entry = -1

    def __str__(self):
        return '%x:%x/jt%d entries=(%s) refs=(%s)' % (self.start, self.stop, self.jt_entry, ', '.join(str(x) for x in self.entry_points), ', '.join('%x'%x for x in self.references))


class Ent:
    def __init__(self):
        self.offset = -1
        self.jt_entry = -1

    def __str__(self):
        return '%x/jt%d' % (self.offset, self.jt_entry)


parser = argparse.ArgumentParser(description='''
    Very hacky. 
''')

parser.add_argument('src', nargs='+', action='store', help='Source file (.rdump) or files (numbered)')
parser.add_argument('-roms', nargs='+', default=['Plus', 'SE', 'II', 'Portable', 'IIci', 'SuperMario'])
parser.add_argument('-pm', action='store_true', help='Print information about modules and code references')
parser.add_argument('-pr', action='store_true', help='Print information about ROM references')
parser.add_argument('-oo', action='store', help='Base destination path to dump resources as raw files')
parser.add_argument('-oc', action='store', help='Base destination path to dump code files')
parser.add_argument('-oe', action='store', help='Base destination path to dump code files with refs changed to NOPs')

args = parser.parse_args()

if len(args.src) == 1:
    lpch_list = parse_res_file(args.src[0])
else:
    lpch_list = parse_raw_files(args.src)

# Add an "annotations" field...
lpch_list = [(a,b,[]) for (a,b) in lpch_list]


# Check that we have the right number of declared ROMs...
roms_now = len(args.roms)
roms_at_build = int(math.log(lpch_list[-1][0] + 1, 2.0))

if roms_now != roms_at_build:
    print('Warning: %d ROMs specified but there were %d at build time' % (roms_now, roms_at_build))


########################################################################

large_rom_table = []
large_jump_table = []

for num, data, annotations in lpch_list:
    if args.oo: open(args.oo + str(num), 'wb').write(data)

    if exact_log(num) is not None:
        is_single = True
    else:
        is_single = False

    if num == lpch_list[-1][0]:
        is_all = True
    else:
        is_all = False

    matches_roms = []
    for i, r in enumerate(args.roms):
        if (num >> i) & 1: matches_roms.append(r)


    idx = 0

    if is_single:
        num_lpch_for_this_rom, = struct.unpack_from('>H', data, offset=idx); idx += 2
        counted = len([xnum for (xnum,xdata,*_) in lpch_list if xnum & num])
        assert num_lpch_for_this_rom == counted

    if is_all:
        bound_rom_addr_table_cnt, jump_table_cnt = struct.unpack_from('>HH', data, offset=idx); idx += 4

    code_size, = struct.unpack_from('>I', data, offset=idx); idx += 4
    code = data[idx:idx+code_size]; idx += code_size
    annotations[:] = [None] * code_size


    print('lpch %d\t\t%db(%db)\t\t%s' % (num, len(data), code_size, ','.join(matches_roms)))


    if args.oc:
        open(args.oc + str(num), 'wb').write(code)


    # do the rom table

    rom_table_start, = struct.unpack_from('>H', data, offset=idx); idx += 2
    if rom_table_start == 0xFFFF: rom_table_start = None
    rom_table = []
    if rom_table_start is not None:
        while 1:
            this_dict = {}
            for r in matches_roms:
                the_int = int.from_bytes(data[idx:idx+3], byteorder='big'); idx += 3
                this_dict[r] = the_int & 0x7FFFFF

            rom_table.append(this_dict)

            if the_int & 0x800000:
                break

        while len(large_rom_table) < rom_table_start + len(rom_table):
            large_rom_table.append(None)

        large_rom_table[rom_table_start:rom_table_start+len(rom_table)] = rom_table

        if args.pr: print('ROM table entries are %d:%d' % (rom_table_start, rom_table_start+len(rom_table)))


    # Figure out where all the ROM references are

    rom_exception_table = []
    for i in range(10):
        the_int = int.from_bytes(data[idx:idx+3], byteorder='big'); idx += 3
        if the_int == 0:
            break
        else:
            rom_exception_table.append(the_int)

    for code_offset in rom_exception_table:
        while 1:
            link, which_rom_part = struct.unpack_from('>HH', code, offset=code_offset)
            annotations[code_offset] = (4, 'rom_reference', which_rom_part) # offset within large_rom_table
            if link == 0: break
            code_offset += 4 + 2 * link


    tokens = []
    # do the exception table
    while 1:
        opcode = data[idx]; idx += 1
        this_is_an_entry = False

        if opcode <= 251:
            tok = ('distance', opcode * 2)

        elif opcode == 252: # skip entries in the jump table
            opcode2 = data[idx]; idx += 1

            if opcode2 == 0: # end of packed jump table
                tok = ('end', None)
            elif 1 <= opcode2 <= 254: # number of jump table entries to skip
                tok = ('skipjt', opcode2)
            elif opcode2 == 255: # word follows with number of jump table entries to skip
                opcode3, = struct.unpack_from('>H', data, offset=idx); idx += 2
                tok = ('skipjt', opcode3)

        elif opcode == 253: # previous was reference list head for this module
            tok = ('prev=ref_list_head', None)

        elif opcode == 254: # previous was an entry, not a new module
            tok = ('prev=entry_not_module', None)

        elif opcode == 255: # word distance from current position in the code to next
                            # entry or module specified in the packed jump table follows
            opcode2, = struct.unpack_from('>H', data, offset=idx); idx += 2
            tok = ('distance', opcode2)

        tokens.append(tok)
        if tok[0] == 'end': break

    # daccum = 0
    # for i, (a, b) in enumerate(tokens):
    #     if a == 'distance':
    #         daccum += b
    #         print('%02d'%i, a, hex(b), '='+hex(daccum))
    #     elif b is None:
    #         print('%02d'%i, a)
    #     else:
    #         print('%02d'%i, a, hex(b))


    jt_offset = 0
    cur_offset = 0

    modules = []

    modules.append(Mod())
    modules[-1].start = 0

    i = 0
    while tokens[i][0] != 'end':
        a, b = tokens[i]; i += 1

        if a == 'distance':
            cur_offset += b
            if tokens[i][0] == 'prev=entry_not_module':
                i += 1
                modules[-1].entry_points.append(Ent())
                modules[-1].entry_points[-1].offset = cur_offset
            elif tokens[i][0] == 'prev=ref_list_head':
                i += 1
                modules[-1].references.append(cur_offset)
            else:
                modules[-1].stop = cur_offset
                modules.append(Mod())
                modules[-1].start = cur_offset

    modules.pop()

    if modules: assert modules[-1].stop == code_size


    for m in modules:
        if m.references:
            ofs, = m.references
            while 1:
                dist_to_next, = struct.unpack_from('>H', code, offset=ofs)
                dist_to_next &= 0x7FFF
                dist_to_next *= 2
                if dist_to_next == 0: break
                ofs += dist_to_next
                m.references.append(ofs)


    if args.pm:
        for m in modules:
            print(m)


    edited_code = bytearray(code)
    # Now edit the code to look more sexier...
    for m in modules:
        for r in m.references:
            edited_code[r:r+4] = b'NqNq'
    if args.oe:
        open(args.oe + str(num), 'wb').write(edited_code)


for el in large_rom_table:
    assert el is not None

# print(large_jump_table)
# print(large_rom_table)



