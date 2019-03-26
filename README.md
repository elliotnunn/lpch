Everything I know about the obscure "linked patch" system
programming/binary interface in System 7.1-??

The idea was to provide a macro-based interface that a 68k assembly
programmer could use to create RAM-based "patches" for a newly booted
MacOS system. Similar patches were needed even in the original Macintosh
System Software to fix bugs in the shipping ROM. Runtime patching also
came to be used to add new software features to old Mac models. But
writing a patch in pure 68k assembly, especially a "come-from" patch,
was very tedious and usually required self-modifying code.

The linked patches incrementally improved that situation. Here is a
summary of the design decisions made:

- A library of 68k macros provided a nearly-declarative way to describe
  to installation process for a given patch.
- The runtime RAM usage was minimised by separating installation from
  runtime code, and by segmenting each code module at build time
  according to its target ROM releases.
- Advantage was taken of the huge commonality carefully between
  Macintosh ROM releases, which was painstakingly maintained by binary
  patching and "overpatching".
- Object files containing patches woulod be linked into resources by a
  full linker, making dead code elimination available and allowing the
  direct inclusion of code originally meant for a ROM build.
- Runtime self-modification of code was done almost entirely by a
  generic runtime loader, instead of allowing each patch writer to come
  up with a unique and uniquely buggy solution.
- Special assembly facilities were made available to ease the writing of
  come-from patches (patches that wrested control from a buggy segment
  of ROM by hijacking a possibly unrelated trap in the vicinity).
  Specifically, it was easy to describe the address of the target trap
  and to produce code that would test that the trap was indeed being
  called from that address.
