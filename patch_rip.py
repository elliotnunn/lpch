#!/usr/bin/env python3

import argparse
import math
import struct
import re
from collections import defaultdict


COND_NAMES = ['Plus', 'SE', 'II', 'Portable', 'IIci', 'SuperMario',
    'noPatchProtector', 'notVM', 'notAUX', 'hasHMMU', 'hasPMMU',
    'hasMemoryDispatch', 'has800KDriver', 'hasFDHDDriver', 'hasIWM',
    'hasEricksonOverpatchMistake', 'hasEricksonSoundMgr', 'notEricksonSoundMgr',
    'using24BitHeaps', 'using32BitHeaps', 'notTERROR', 'hasTERROR', 'hasC96',
    'hasPwrMgr']


global_sym_names = {}
def name(jt_offset):
    retval = 'R%03X' % jt_offset
    betterval = global_sym_names.get(jt_offset, None)
    if betterval:
        return retval + '/' + betterval
    else:
        return retval

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
        self.offset = -1
        self.stop = -1
        self.jt_entry = -1
        self.rsrc_id = 0

    def __str__(self):
        return 'PROC ' + name(self.jt_entry)


class Ent:
    def __init__(self):
        self.offset = -1
        self.jt_entry = -1

    def __str__(self):
        return 'ENTRY ' + name(self.jt_entry)


class Ref:
    def __init__(self):
        self.offset = -1
        self.opcode = -1
        self.jt_entry = -1
        self.force_resident = False

    @property
    def assembly(self):
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
            'unknown11Y x',
            'unknown12Y x',
            'unknown13Y x',
            'unknown14Y x',
            'dcImportY x',
        )[self.opcode]

        x = x.replace('x', name(self.jt_entry))
        x = x.replace('Y', 'Resident' if self.force_resident else '')

        return x    

    def __str__(self):
        return self.assembly

global_romref_names = {}
class RomRef:
    def __init__(self):
        self.offset = -1
        self.romofs_pairs = []

    def __str__(self):
        retval = ','.join('(%s,$%x)' % (k, v) for k, v in self.romofs_pairs)
        betterval = global_romref_names.get(retval, None)
        if betterval:
            return 'ROM ' + betterval
        else:
            return retval


parser = argparse.ArgumentParser(description='''
    Very hacky. 
''')

parser.add_argument('src', nargs='+', action='store', help='Source file (.rdump) or files (numbered)')
parser.add_argument('-roms', nargs='+', default=['Plus', 'SE', 'II', 'Portable', 'IIci', 'SuperMario'])
parser.add_argument('-pt', action='store_true', help='Print raw module tokens')
parser.add_argument('-pm', action='store_true', help='Print information about modules and code references')
parser.add_argument('-pr', action='store_true', help='Print information about ROM references')
parser.add_argument('-pj', action='store_true', help='Print jump table')
parser.add_argument('-pp', action='store_true', help='Print patch names')
parser.add_argument('-rh', action='store', help='LinkedPatches.lib, so we know how to name ROM references')
parser.add_argument('-sh', action='store', help='output of LinkedPatch -l, so we know how to name symbols')
parser.add_argument('-oo', action='store', help='Base destination path to dump resources as raw files')
parser.add_argument('-oc', action='store', help='Base destination path to dump code files')
parser.add_argument('-oe', action='store', help='Base destination path to dump code files with refs changed to NOPs')
parser.add_argument('-w', action='store', dest='width', type=int, default=128, help='Width in chars')

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

# LinkedPatches.lib, so we know how to name ROM references
# mutates global_romref_names, which the RomRef class can read
if args.rh:
    library = open(args.rh, 'rb').read()
    name_map = defaultdict(list)
    for m in re.finditer(rb'BIND\$([A-Za-z0-9@%]+)\$(\d+)\$(\d+)\$', library):
        name_map[m.group(1).decode('ascii')].append((int(m.group(2)), int(m.group(3))))
    for rname, rlist in name_map.items():
        rlist.sort()
        keystring = ','.join('(%s,$%x)' % (COND_NAMES[k], v) for k, v in rlist)
        global_romref_names[keystring] = rname

# output of LinkedPatch -l, so we know how to name symbols
if args.sh:
    for l in open(args.sh):
        l = l.split()
        if len(l) == 2:
            sym_number = int(l[0], 16)
            sym_name = l[1]
            global_sym_names[sym_number] = sym_name

########################################################################

large_rom_table = []
large_jump_table = []

all_modules = []

code_list = [] # this is getting hackier and hackier

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
    code_list.append(code)


    if args.pt or args.pm or args.pr:
        if not is_all: print()
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
            human_readable_idx = idx
            for r in reversed(matches_roms): # data packed from newest to oldest rom
                the_int = int.from_bytes(data[idx:idx+3], byteorder='big'); idx += 3
                romofs_pairs.append((r, the_int & 0x7FFFFF))
            romofs_pairs.reverse()

            rom_table.append(romofs_pairs)

            if args.pr:
                print(','.join('(%s,$%x)' % (k, v) for k, v in romofs_pairs))

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


    if is_all:
        patches = defaultdict(list) # mapping from jt number to (trap, cond_names)
        curjt = 0
        end_of_table = False
        while not end_of_table:
            conds = int.from_bytes(data[idx:idx+3], byteorder='big'); idx += 3
            #print('conds', hex(conds))
            cond_names = []
            for i, n in enumerate(COND_NAMES):
                if conds & (1 << i): cond_names.append(n)
            cond_names = ','.join(cond_names)

            while 1:
                delta = data[idx]; idx += 1
                #print('  delta', hex(delta))
                if delta == 254:
                    break # get new condition set
                elif delta == 255:
                    delta, = struct.unpack_from('>H', data, idx); idx += 2
                    #print('  delta2', hex(delta))
                    if delta == 0:
                        end_of_table = True; break
                curjt += delta

                trap, = struct.unpack_from('>H', data, idx); idx += 2
                #print('  trap', hex(trap))
                patches[curjt].append((trap, cond_names))


    jt_offset = 0
    cur_offset = 0

    modules = []

    modules.append(Mod())
    modules[-1].offset = 0
    modules[-1].__hack_refhead = -1
    modules[-1].rsrc_id = num

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
            modules[-1].offset = cur_offset
            modules[-1].__hack_refhead = -1
            modules[-1].rsrc_id = num

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
        m.rom_references = [r for r in rom_references if m.offset <= r.offset < m.stop]


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
                nu = struct.pack('>HH', opcode, r.jt_entry)
            except IndexError:
                nu = b'NqNq'
            edited_code[r.offset:r.offset+4] = nu
    if args.oe:
        open(args.oe + str(num), 'wb').write(edited_code)

    all_modules.extend(modules)


for el in large_rom_table:
    assert el is not None


if args.pp:
    for jt, v in patches.items():
        for trap, cond_names in v:
            print(f'    MakePatch {name(jt)}, _{trap:04X}, ({cond_names})')


if args.pj:
    nums = [num for num, data in lpch_list]

    def render_line(ofs, line):
        return '%05x: %s' % (ofs, line)

    def render_code(start, stop):
        ofs = start

        while ofs < stop:
            ofs2 = ofs + args.width; ofs2 -= ofs2 % args.width; ofs2 = min(ofs2, stop)
            line = code[ofs:ofs2]
            if not line:
                print('expected', stop, 'got', len(code))
                raise ValueError()
            line = bytes(x if (32 < x and x != 127 and x != 0xF0 and x < 127) else 46 for x in line).decode('mac_roman')
            line = ' ' * (ofs % args.width) + line

            yield render_line(ofs, line)

            ofs = ofs2

    def render_offset(ofs, line):
        return '%05x: %s%s' % (ofs, ' ' * (ofs % args.width), line)

    def render_sep(ofs):
        return '%05x: %s' % (ofs, '=' * args.width)

    last_rsrc = -1
    rsrc_print_progress = [0] * len(nums)

    all_modules.sort(key=lambda mod: mod.jt_entry)
    for mod in all_modules:
        rsrc_idx = nums.index(mod.rsrc_id)

        everything = sorted([mod] + mod.entry_points + mod.references + mod.rom_references, key=lambda x: x.offset)
        code = code_list[rsrc_idx]
        last_printed = 0

        leftside = str(mod.rsrc_id).zfill(2) + ':'
        def myprint(*args, **kwargs):
            if args: args = (leftside + str(args[0]), *args[1:])
            return print(*args, **kwargs)

        def print_up_to(ofs):
            for jank in render_code(rsrc_print_progress[rsrc_idx], ofs):
                myprint(jank)
            rsrc_print_progress[rsrc_idx] = ofs

        if last_rsrc != mod.rsrc_id:
            myprint(render_sep(mod.offset))
            matches_roms = []
            for i, r in enumerate(args.roms):
                if (mod.rsrc_id >> i) & 1: matches_roms.append(r)
            myprint(render_line(mod.offset, ','.join(matches_roms)))
            # print()
            last_rsrc = mod.rsrc_id

        for mod_ent in everything + [None]:
            print_up_to(mod_ent.offset if mod_ent else mod.stop)

            if mod_ent:
                myprint(render_offset(mod_ent.offset, '(' + str(mod_ent) + ')'))

                try:
                    for trap, cond_names in patches[mod_ent.jt_entry]:
                        myprint(render_offset(mod_ent.offset, f'${trap:X},({cond_names})'))
                except AttributeError:
                    pass

                if not (isinstance(mod_ent, Mod) or isinstance(mod_ent, Ent)):
                    rsrc_print_progress[rsrc_idx] += 4 # close enough

# print(large_jump_table)
# print(large_rom_table)



