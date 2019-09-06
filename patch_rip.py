#!/usr/bin/env python3

import argparse
import math
import struct


def name(jt_offset):
    return 'R%04X' % (jt_offset * 6)

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

def count_bits(n):
    cnt = 0
    while n:
        if n & 1: cnt += 1
        n >>= 1
    return cnt


class Mod:
    def __init__(self):
        self.entry_points = []
        self.references = []
        self.rom_references = []
        self.start = -1
        self.stop = -1
        self.jt_entry = -1

    def __str__(self):
        x = '%05x %s:' % (self.start, name(self.jt_entry))

        leave = sorted(self.entry_points + self.references + self.rom_references, key=lambda x: x.offset)

        x += ''.join('\n  ' + str(s) for s in leave)
        return x


class Ent:
    def __init__(self):
        self.offset = -1
        self.jt_entry = -1

    def __str__(self):
        return '%05x %s:' % (self.offset, name(self.jt_entry))


class Ref:
    def __init__(self):
        self.offset = -1
        self.opcode = -1
        self.jt_entry = -1
        self.force_resident = False

    @property
    def assembly(self):
        try:
            x = (
                'leaY x,A0',
                'leaY x,A1',
                'leaY x,A2',
                'leaY x,A3',
                'leaY x,A4',
                'leaY x,A5',
                'leaY x,A6',
                'leaY x,A7',
                'peaY x',
                'jsrY x',
                'jmpY x',
            )[self.opcode]
        except IndexError:
            x = 'unknownY x'

        x = x.replace('x', name(self.jt_entry))
        x = x.replace('Y', 'Resident' if self.force_resident else '')

        return x    

    def __str__(self):
        return '%05x %s' % (self.offset, self.assembly)


class RomRef:
    def __init__(self):
        self.offset = -1
        self.romofs_pairs = []

    def __str__(self):
        return '%05x %s' % (self.offset, ', '.join('(%s,$%x)' % (k, v) for k, v in self.romofs_pairs))


parser = argparse.ArgumentParser(description='''
    Very hacky. 
''')

parser.add_argument('src', nargs='+', action='store', help='Source file (.rdump) or files (numbered)')
parser.add_argument('-roms', nargs='+', default=['Plus', 'SE', 'II', 'Portable', 'IIci', 'SuperMario'])
parser.add_argument('-pt', action='store_true', help='Print raw module tokens')
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


# Check that we have the right number of declared ROMs...
roms_now = len(args.roms)
roms_at_build = int(math.log(lpch_list[-1][0] + 1, 2.0))

if roms_now != roms_at_build:
    print('Warning: %d ROMs specified but there were %d at build time' % (roms_now, roms_at_build))


# Sort the ROMs so that the most inclusive ones come first
lpch_list.sort(key=lambda rsrc: (-count_bits(rsrc[0]), rsrc[0]))

########################################################################

large_rom_table = []
large_jump_table = []

for num, data in lpch_list:
    if args.oo: open(args.oo + str(num), 'wb').write(data)

    if exact_log(num) is not None:
        is_single = True
    else:
        is_single = False

    if num == lpch_list[0][0]:
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


    print('lpch %d\t\t%db(%db)\t\t%s' % (num, len(data), code_size, ','.join(matches_roms)))


    if args.oc:
        open(args.oc + str(num), 'wb').write(code)


    # do the rom table

    rom_table_start, = struct.unpack_from('>H', data, offset=idx); idx += 2
    if rom_table_start == 0xFFFF: rom_table_start = None
    rom_table = []
    if rom_table_start is not None:
        while 1:
            romofs_pairs = []
            for r in reversed(matches_roms): # data packed from newest to oldest rom
                the_int = int.from_bytes(data[idx:idx+3], byteorder='big'); idx += 3
                romofs_pairs.append((r, the_int & 0x7FFFFF))
            romofs_pairs.reverse()

            rom_table.append(romofs_pairs)

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

    rom_references = [] # this is what we can salvage from the foregoing overcooked code
    for code_offset in rom_exception_table:
        while 1:
            link, which_rom_part = struct.unpack_from('>HH', code, offset=code_offset)
            rom_references.append(RomRef())
            rom_references[-1].offset = code_offset
            rom_references[-1].romofs_pairs = large_rom_table[which_rom_part]
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

    # Mutate the tokens list to merge the 'prev=' tokens
    for i in reversed(range(len(tokens) - 1)):
        if tokens[i+1][0].startswith('prev='):
            assert tokens[i][0] == 'distance'
            tokens[i] = (tokens[i][0] + tokens[i+1][0][4:],) + tokens[i][1:]
            del tokens[i+1]

    # From here on, a 'distance' token can be treated as 'distance=module_end'

    if args.pt:
        daccum = 0
        for i, (a, b) in enumerate(tokens):
            if a.startswith('distance'):
                daccum += b
                print('%02d'%i, a, hex(b), '='+hex(daccum))
            elif b is None:
                print('%02d'%i, a)
            else:
                print('%02d'%i, a, hex(b))


    jt_offset = 0
    cur_offset = 0

    modules = []

    modules.append(Mod())
    modules[-1].start = 0
    modules[-1].__hack_refhead = -1

    for tok, arg in tokens:
        if tok == 'skipjt':
            jt_offset += arg

        if tok.startswith('distance'):
            if modules[-1].jt_entry == -1:
                modules[-1].jt_entry = jt_offset
                jt_offset += 1

            cur_offset += arg

        if tok == 'distance': # to end of module
            modules[-1].stop = cur_offset
            modules.append(Mod())
            modules[-1].start = cur_offset
            modules[-1].__hack_refhead = -1

        if tok == 'distance=entry_not_module':
            modules[-1].entry_points.append(Ent())
            modules[-1].entry_points[-1].offset = cur_offset
            modules[-1].entry_points[-1].jt_entry = jt_offset

            jt_offset += 1

        if tok == 'distance=ref_list_head':
            modules[-1].__hack_refhead = cur_offset

    modules.pop()

    if modules: assert modules[-1].stop == code_size


    for m in modules:
        m.rom_references = [r for r in rom_references if m.start <= r.offset < m.stop]


    for m in modules:
        if m.__hack_refhead == -1: continue

        while 1:
            word1, word2 = struct.unpack_from('>HH', code, offset=m.__hack_refhead)

            m.references.append(Ref())
            m.references[-1].offset = m.__hack_refhead
            m.references[-1].jt_entry = word2 & 0xFFF
            m.references[-1].opcode = word2 >> 12
            m.references[-1].force_resident = bool(word1 & 0x8000)

            dist_to_next = word1 & 0x7FFF
            dist_to_next *= 2
            if dist_to_next == 0: break
            m.__hack_refhead += dist_to_next


    if args.pm:
        for m in modules:
            print(m)


    edited_code = bytearray(code)
    # Now edit the code to look more sexier...
    for m in modules:
        for r in m.references:
            try:
                opcode = [0x206D,0x226D,0x246D,0x266D,0x286D,0x2A6D,0x2C6D,0x2E6D,0x2F2D,0x4EAD,0x4EED][r.opcode]
                nu = struct.pack('>HH', opcode, r.jt_entry * 6)
            except IndexError:
                nu = b'NqNq'
            edited_code[r.offset:r.offset+4] = nu
    if args.oe:
        open(args.oe + str(num), 'wb').write(edited_code)


for el in large_rom_table:
    assert el is not None

# print(large_jump_table)
# print(large_rom_table)



