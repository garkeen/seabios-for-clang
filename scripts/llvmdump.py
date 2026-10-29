#!/usr/bin/env python
# Emit a GNU-objdump(-thr)-shaped dump of an ELF object using LLVM tools only.
#
# scripts/layoutrom.py (reused by checkrom.py) parses GNU binutils objdump
# -thr: the section table must carry the "Idx Name Size VMA LMA File off Algn"
# columns with alignment spelled "2**n".  llvm-objdump cannot produce that
# table (it has no LMA/File off/Algn columns), but its symbol table and
# relocation blocks are column-identical to GNU objdump.  This adapter prints
# the GNU-shaped Sections: block from llvm-readobj --sections and streams
# llvm-objdump -thr with its own Sections: block dropped.
#
# Usage: python scripts/llvmdump.py <object> [<llvm-bin-dir>]
import os
import subprocess
import sys


def field(block, name):
    for line in block.splitlines():
        line = line.strip()
        if line.startswith(name + ':'):
            return line[len(name) + 1:].strip()
    return ''


def main():
    obj = sys.argv[1]
    llvmbin = sys.argv[2] if len(sys.argv) > 2 else 'D:/LLVM/bin'

    def run(tool, args):
        exe = os.path.join(llvmbin, tool + '.exe')
        r = subprocess.run([exe] + args, capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            raise SystemExit(r.returncode)
        return r.stdout

    dump = run('llvm-objdump', ['-thr', obj])
    secs = run('llvm-readobj', ['--sections', obj])

    out = sys.stdout
    out.write('%s:     file format elf32-i386\n\nSections:\n' % obj)
    out.write('Idx Name          Size      VMA          LMA'
              '          File off  Algn\n')
    idx = 0
    for block in secs.split('Section {')[1:]:
        name = field(block, 'Name').split(' ')[0]
        if not name or name.startswith('('):
            continue  # null section (empty name)
        # GNU objdump -h omits relocation and symbol/string metadata tables
        # (no CONTENTS/ALLOC flags); matching that keeps the parsed section
        # set identical.
        if field(block, 'Type').startswith(('SHT_REL', 'SHT_SYMTAB',
                                            'SHT_STRTAB')):
            continue
        size = int(field(block, 'Size'), 0)
        vma = int(field(block, 'Address'), 0)
        off = int(field(block, 'Offset'), 0)
        align = int(field(block, 'AddressAlignment'), 0)
        out.write('%3d %-16s %08x  %08x  %08x  %08x  2**%d\n'
                  % (idx, name, size, vma, vma, off,
                     max(0, align.bit_length() - 1)))
        idx += 1

    intable = False
    for line in dump.splitlines():
        if not intable:
            if line.strip() == 'Sections:':
                intable = True  # drop llvm-objdump's own section table
            else:
                out.write(line + '\n')
        elif line.strip() == 'SYMBOL TABLE:':
            intable = False
            out.write(line + '\n')


if __name__ == '__main__':
    main()
