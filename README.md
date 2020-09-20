The "Linked Patches" are an unusual 68k code format in the System
resource fork of Mac OS 7-9. They contain initialization code to run at
boot and runtime code for installation in RAM-based vector tables.

The first Linked Patches shipped in the interdependent 'lpch' resources
of System 7.0.

From System 7.5, 'gpch' resources contained groups of functionally
related 'lpch' resources. A group could be loaded or not according to
the host machine. This was controlled by one 'gusd' and multiple 'gtbl'
resource.

`patch_rip.py` is a Python 3 script to dump a group of 'lpch' resources
(or a single 'gpch' resource) to text.


## Usage

First, `pip3 install macresources` to get the `rfx` command-line tool,
which exposes the resources inside a resource fork like regular files.

Then point `patch_rip.py` at the System file of interest:

    rfx ./patch_rip.py System/..namedfork/rsrc//lpch/   # macOS 10's kernel resource fork support
    rfx ./patch_rip.py System.hqx//lpch/                # BinHex file
    rfx ./patch_rip.py System//lpch/                    # Rez file named "System.rdump"

To dump a numbered 'gpch' file instead, replace `//lpch/`, which expands
to a path for each lpch resource, with `//gpch/NNN`, which expands to a
single path.

The output is not disassembled, but it is annotated with the known
locations of specialised "jsr" instructions, etc.
