#!/usr/bin/env python
# Generate build.ninja for the SeaBIOS QEMU target (clang + lld + llvm tools).
#
# This mirrors the upstream Makefile pipeline command-for-command.  It exists
# because mingw32-make (a native Windows process) mangles backslashes in
# recipe strings on the way to the shell, which corrupts
# -fmacro-prefix-map=.\src=./src and lets Windows-style __FILE__ spellings
# (".\src\kbd.c") leak into UNIQSEC section names.  Ninja reads its commands
# from build.ninja as plain file content, so the flag survives verbatim.
#
# The objdump dumps that layoutrom.py/checkrom.py consume are produced by
# scripts/llvmdump.py (llvm-readobj + llvm-objdump), so no GNU binutils
# binary is needed anywhere in the pipeline.
#
# The per-mode source lists below are pinned from the SeaBIOS 1.17.0
# Makefile in their exact original order (include order in the whole-program
# tmp.c files feeds section order into layoutrom.py, so the order is
# load-bearing).  A pristine copy of that Makefile lives under compare/ for
# reference.  The kconfig pass that produced .config/out/autoconf.h is not
# rebuilt here.
# Usage:  python scripts/gen-ninja.py   (writes ./build.ninja)
import os

SRCDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRCBOTH = (
    'misc.c stacks.c output.c string.c block.c cdrom.c disk.c '
    'mouse.c kbd.c system.c serial.c sercon.c clock.c resume.c '
    'pnpbios.c vgahooks.c pcibios.c apm.c cp437.c '
    'hw/pci.c hw/timer.c hw/rtc.c hw/dma.c hw/pic.c hw/ps2port.c '
    'hw/serialio.c hw/usb.c hw/usb-uhci.c hw/usb-ohci.c hw/usb-ehci.c '
    'hw/usb-hid.c hw/usb-msc.c hw/usb-uas.c hw/blockcmd.c '
    'hw/floppy.c hw/ata.c hw/ramdisk.c hw/lsi-scsi.c hw/esp-scsi.c '
    'hw/megasas.c hw/mpt-scsi.c'
).split()

SRC32FLAT = SRCBOTH + (
    'post.c e820map.c malloc.c romfile.c x86.c '
    'optionroms.c pmm.c font.c boot.c bootsplash.c jpeg.c bmp.c '
    'tcgbios.c sha1.c '
    'hw/pcidevice.c hw/ahci.c hw/pvscsi.c '
    'hw/usb-xhci.c hw/usb-hub.c hw/sdcard.c '
    'fw/coreboot.c fw/lzmadecode.c fw/multiboot.c fw/csm.c '
    'fw/biostables.c '
    'fw/paravirt.c fw/shadow.c fw/pciinit.c fw/smm.c fw/smp.c '
    'fw/mtrr.c fw/xen.c fw/acpi.c fw/mptable.c fw/pirtable.c '
    'fw/smbios.c fw/romfile_loader.c fw/dsdt_parser.c hw/virtio-ring.c '
    'hw/virtio-pci.c hw/virtio-mmio.c hw/virtio-blk.c hw/virtio-scsi.c '
    'hw/tpm_drivers.c hw/nvme.c sha256.c sha512.c'
).split()

SRC32SEG = (
    'string.c output.c pcibios.c apm.c stacks.c '
    'hw/pci.c hw/serialio.c'
).split()

# VGA BIOS sources (upstream Makefile SRCVGA, same order).  This is the
# option ROM a display card carries, not part of the core BIOS; it is built as
# its own 16bit whole-program image when CONFIG_BUILD_VGABIOS is set.  The list
# mixes src/ and vgasrc/ paths, so it carries its own prefixes.
SRCVGA = (
    'src/output.c src/string.c src/hw/pci.c src/hw/serialio.c '
    'vgasrc/vgainit.c vgasrc/vgabios.c vgasrc/vgafb.c vgasrc/swcursor.c '
    'vgasrc/vgafonts.c vgasrc/vbe.c '
    'vgasrc/stdvga.c vgasrc/stdvgamodes.c vgasrc/stdvgaio.c '
    'vgasrc/clext.c vgasrc/svgamodes.c vgasrc/atiext.c vgasrc/bochsvga.c vgasrc/geodevga.c '
    'src/fw/coreboot.c vgasrc/cbvga.c vgasrc/bochsdisplay.c vgasrc/ramfb.c'
).split()

def main():
    both, flat, seg = SRCBOTH, SRC32FLAT, SRC32SEG
    BS = chr(92)
    # direct (no-shell) rules need Windows paths; bash -c rules need MSYS paths
    CC = 'D:/LLVM/bin/clang --target=i386-unknown-elf'
    LD = 'D:/LLVM/bin/ld.lld -melf_i386'
    OBJCOPY = 'D:/LLVM/bin/llvm-objcopy'
    STRIP = 'D:/LLVM/bin/llvm-strip'
    PYTHON = 'D:/Python/Python312/python.exe'
    SH_CC = '/d/LLVM/bin/clang --target=i386-unknown-elf'
    SH_LD = '/d/LLVM/bin/ld.lld -melf_i386'
    SH_OBJCOPY = '/d/LLVM/bin/llvm-objcopy'
    SH_STRIP = '/d/LLVM/bin/llvm-strip'
    SH_PYTHON = '/d/Python/Python312/python.exe'
    SH_LLVMDUMP = SH_PYTHON + ' ./scripts/llvmdump.py'
    MSYS_BASH = 'C:/Program Files/Git/usr/bin/bash.exe'

    COMMON = ('-Iout/ -Isrc -Os -MD -Wall -Wno-strict-aliasing '
              '-Wold-style-definition -Wtype-limits -m32 -march=i386 -mregparm=3 '
              '-mstack-alignment=2 -minline-all-stringops -fomit-frame-pointer '
              '-freg-struct-return -ffreestanding -fno-delete-null-pointer-checks '
              '-ffunction-sections -fdata-sections -fno-common -fno-merge-constants '
              '-fno-pie -fno-stack-protector -Wno-address-of-packed-member '
              '-Wno-array-bounds -fcf-protection=none '
              '-Wno-ignored-optimization-argument')
    MACROMAP = ' -fmacro-prefix-map=.' + BS + 'src=./src -fmacro-prefix-map=.' + BS + 'vgasrc=./vgasrc'
    F16 = COMMON + ' -DMODESEGMENT=1 -fno-defer-pop -fno-jump-tables -DMODE16=1 -m16 -fno-inline'
    F32FLAT = COMMON + ' -DMODE16=0 -DMODESEGMENT=0'
    F32SEG = COMMON + ' -DMODESEGMENT=1 -fno-defer-pop -fno-jump-tables -DMODE16=0'

    # The VGA BIOS target follows the configuration (upstream Makefile
    # target-$(CONFIG_BUILD_VGABIOS)).  .config and out/autoconf.h are
    # configuration inputs for this chain, so the answer is read off the header.
    autoconf = open(os.path.join(SRCDIR, 'out', 'autoconf.h')).read()
    vgabios_enabled = '\n#define CONFIG_BUILD_VGABIOS 1' in autoconf

    def includes(files, prefix=''):
        return '\n'.join('#include "%s%s"' % (prefix, f) for f in files)

    # The tmp.c files must contain quoted #include lines.  Write them with a
    # python helper rule (avoids printf quoting issues entirely).
    gen_inc_16 = includes(both, 'src/')
    gen_inc_32flat = includes(flat, 'src/')
    gen_inc_32seg = includes(seg, 'src/')

    n = []
    w = n.append
    w('# Generated by scripts/gen-ninja.py -- do not edit.')
    w('ninja_required_version = 1.10')
    w('')
    w('bs_src_flag = -fmacro-prefix-map=.' + BS + 'src=./src -fmacro-prefix-map=.' + BS + 'vgasrc=./vgasrc')
    w('')
    # write tmp.c via a rule that cats a heredoc-ish python one-liner? No:
    # simplest robust approach: generator pre-writes the three .tmp.c files'
    # CONTENT as response include files next to build.ninja, and a copy rule.
    inc16_file = 'out/.includes16.txt'
    inc32flat_file = 'out/.includes32flat.txt'
    inc32seg_file = 'out/.includes32seg.txt'
    outdir = os.path.join(SRCDIR, 'out')
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(SRCDIR, inc16_file), 'w', newline='\n').write(gen_inc_16 + '\n')
    open(os.path.join(SRCDIR, inc32flat_file), 'w', newline='\n').write(gen_inc_32flat + '\n')
    open(os.path.join(SRCDIR, inc32seg_file), 'w', newline='\n').write(gen_inc_32seg + '\n')
    if vgabios_enabled:
        open(os.path.join(SRCDIR, 'out/.includesvga.txt'), 'w', newline='\n').write(
            includes(SRCVGA) + '\n')
        os.makedirs(os.path.join(outdir, 'vgasrc'), exist_ok=True)

    w('rule mktmp')
    w('  command = cp $in $out')
    w('  description = GEN $out')
    w('')
    w('rule cc16')
    w('  command = %s -I. $flags $bs_src_flag -MF $out.d -c $out.tmp.c -o $out' % CC)
    w('  description = CC16 $out')
    w('  deps = gcc')
    w('  depfile = $out.d')
    w('')
    w('rule cc32flat')
    w('  command = %s -I. $flags $bs_src_flag -MF $out.d -c $out.tmp.c -o $out' % CC)
    w('  description = CC32FLAT $out')
    w('  deps = gcc')
    w('  depfile = $out.d')
    w('')
    w('rule cc32seg')
    w('  command = %s -I. $flags $bs_src_flag -MF $out.d -c $out.tmp.c -o $out' % CC)
    w('  description = CC32SEG $out')
    w('  deps = gcc')
    w('  depfile = $out.d')
    w('')
    w('rule as')
    w('  command = %s $flags -MF $out.d -c -D__ASSEMBLY__ $in -o $out' % CC)
    w('  description = AS $out')
    w('  deps = gcc')
    w('  depfile = $out.d')
    w('')
    w('rule asmoffsets')
    w('  command = %s -c "mkdir -p out/src && %s $flags -S -c src/asm-offsets.c -o out/src/asm-offsets.s && ./scripts/gen-offsets.sh out/src/asm-offsets.s out/asm-offsets.h"' % (MSYS_BASH, SH_CC))
    w('  description = ASMOFFSETS $out')
    w('')
    ldscripts_inner = ' && '.join([
        '%s ./scripts/buildversion.py -e "" -t "/d/LLVM/bin/clang;/d/LLVM/bin/clang;/d/LLVM/bin/ld.lld;/d/LLVM/bin/llvm-objcopy;D:/LLVM/bin/llvm-readobj;/d/LLVM/bin/llvm-strip" out/autoversion.h' % SH_PYTHON,
        '%s $flags -c src/version.c -o out/version.o' % SH_CC,
        '%s -r out/ccode32flat.o out/version.o -o out/code32flat.o' % SH_LD,
        '%s -r out/ccode16.o out/romlayout.o -o out/code16.o' % SH_LD,
        '%s out/code32flat.o D:/LLVM/bin > out/code32flat.o.objdump' % SH_LLVMDUMP,
        '%s out/code32seg.o D:/LLVM/bin > out/code32seg.o.objdump' % SH_LLVMDUMP,
        '%s out/code16.o D:/LLVM/bin > out/code16.o.objdump' % SH_LLVMDUMP,
        '%s ./scripts/layoutrom.py out/code16.o.objdump out/code32seg.o.objdump out/code32flat.o.objdump out/autoconf.h out/romlayout16.lds out/romlayout32seg.lds out/romlayout32flat.lds' % SH_PYTHON,
    ])
    ldscripts_cmd = '"C:/Program Files/Git/usr/bin/bash.exe" -c "%s"' % ldscripts_inner.replace('"', chr(39))
    w('rule ldscripts')
    w('  command = %s' % ldscripts_cmd)
    w('  description = LAYOUT $out')
    w('')
    w('rule ldrom16')
    w('  command = %s --no-check-sections -s -T out/romlayout16.lds $in -o $out' % LD)
    w('  description = LD $out')
    w('')
    w('rule ldrom32seg')
    w('  command = %s --no-check-sections -s -T out/romlayout32seg.lds $in -o $out' % LD)
    w('  description = LD $out')
    w('')
    w('rule noexec')
    w('  command = "C:/Program Files/Git/usr/bin/bash.exe" -c "%s --strip-unneeded $stem -o $stem.strip.o && %s ./scripts/ldnoexec.py $stem.strip.o $out"' % (SH_STRIP, SH_PYTHON))
    w('  description = NOEXEC $out')
    w('')
    w('rule ldrom')
    w('  command = %s -N -T out/romlayout32flat.lds out/rom16.noexec.o out/rom32seg.noexec.o out/code32flat.o -o $out' % LD)
    w('  description = LD $out')
    w('')
    w('rule rawbin')
    w('  command = "C:/Program Files/Git/usr/bin/bash.exe" -c "%s $in D:/LLVM/bin > $in.objdump && %s -O binary $in out/bios.bin.raw"' % (SH_LLVMDUMP, SH_OBJCOPY))
    w('  description = RAW $out')
    w('')
    w('rule checkrom')
    w('  command = %s ./scripts/checkrom.py out/rom.o.objdump 0 out/bios.bin.raw $out' % PYTHON)
    w('  description = CHECKROM $out')
    w('')
    w('rule cp')
    w('  command = cp $in $out')
    w('  description = CP $out')
    w('')
    if vgabios_enabled:
        # VGA BIOS rules (upstream Makefile "VGA build rules"): preprocess the
        # layout script, whole-compile the 16bit VGA sources, link with the
        # option-ROM layout, then hand the raw image to buildrom.py, which fills
        # in the 55aa header's size/checksum fields.
        w('rule cpplds')
        w('  command = "%s" -c "%s -E -P -D__ASSEMBLY__ -Iout -Isrc $in -o $out"' %
          (MSYS_BASH, SH_CC))
        w('  description = CPP $out')
        w('')
        w('rule ccvga1')
        w('  command = %s -I. $flags $bs_src_flag -MF $out.d -c $in -o $out' % CC)
        w('  description = CCVGA $out')
        w('  deps = gcc')
        w('  depfile = $out.d')
        w('')
        w('rule vgaversion')
        w('  command = "%s" -c "%s ./scripts/buildversion.py -e %s -t %s out/autovgaversion.h"'
          % (MSYS_BASH, SH_PYTHON, "''", "'clang;clang;ld.lld;llvm-objcopy;llvm-readobj;llvm-strip'"))
        w('  description = VGAVERSION $out')
        w('')
        w('rule ldvga')
        w('  command = %s --gc-sections -T out/vgasrc/vgalayout.lds $in -o $out' % LD)
        w('  description = LDVGA $out')
        w('')
        w('rule rawvga')
        w('  command = "%s" -c "%s -O binary $in out/vgabios.bin.raw"' % (MSYS_BASH, SH_OBJCOPY))
        w('  description = RAWVGA $out')
        w('')
        w('rule buildrom')
        w('  command = %s ./scripts/buildrom.py $in $out' % PYTHON)
        w('  description = BUILDROM $out')
        w('')
    # ---- edges ----
    w('# tmp.c inputs')
    w('build out/ccode16.o.tmp.c: mktmp %s' % inc16_file)
    w('build out/ccode32flat.o.tmp.c: mktmp %s' % inc32flat_file)
    w('build out/code32seg.o.tmp.c: mktmp %s' % inc32seg_file)
    w('')
    w('# whole-program compiles (fresh, correct section names)')
    w('build out/ccode16.o: cc16 out/ccode16.o.tmp.c | out/autoconf.h')
    w('  flags = %s' % F16)
    w('build out/ccode32flat.o: cc32flat out/ccode32flat.o.tmp.c | out/autoconf.h')
    w('  flags = %s' % F32FLAT)
    w('build out/code32seg.o: cc32seg out/code32seg.o.tmp.c | out/autoconf.h')
    w('  flags = %s' % F32SEG)
    w('')
    w('# 16-bit assembly entry code')
    w('build out/romlayout.o: as src/romlayout.S | out/autoconf.h out/asm-offsets.h')
    w('  flags = %s' % F16)
    w('')
    w('# assembler offsets (pure LLVM: clang -S + gen-offsets.sh sed)')
    w('build out/asm-offsets.h: asmoffsets src/asm-offsets.c | out/autoconf.h')
    w('  flags = %s' % F16)
    w('')
    w('# layout + partial links (single rule keeps the -j dependency chain honest)')
    w('build out/romlayout16.lds: ldscripts out/ccode32flat.o out/code32seg.o out/ccode16.o out/romlayout.o src/version.c | scripts/layoutrom.py scripts/buildversion.py scripts/llvmdump.py')
    w('  flags = %s' % F32FLAT)
    w('build out/romlayout32seg.lds out/romlayout32flat.lds out/code32flat.o out/code16.o: phony out/romlayout16.lds')
    w('')
    w('build out/rom16.o: ldrom16 out/code16.o | out/romlayout16.lds')
    w('build out/rom32seg.o: ldrom32seg out/code32seg.o | out/romlayout32seg.lds')
    w('')
    w('build out/rom16.noexec.o: noexec out/rom16.o')
    w('  stem = out/rom16.o')
    w('build out/rom32seg.noexec.o: noexec out/rom32seg.o')
    w('  stem = out/rom32seg.o')
    w('')
    w('build out/rom.o: ldrom out/rom16.noexec.o out/rom32seg.noexec.o out/code32flat.o | out/romlayout32flat.lds')
    w('')
    w('build out/bios.bin.raw: rawbin out/rom.o | scripts/llvmdump.py')
    w('build out/bios.bin.prep: checkrom out/bios.bin.raw | scripts/checkrom.py')
    w('build out/bios.bin: cp out/bios.bin.prep')
    w('')
    if vgabios_enabled:
        w('# VGA BIOS image: the option ROM a display card carries, not part of')
        w('# bios.bin (upstream Makefile "VGA build rules", CONFIG_BUILD_VGABIOS).')
        w('build out/vgaccode16.o.tmp.c: mktmp out/.includesvga.txt')
        w('build out/vgaccode16.o: cc16 out/vgaccode16.o.tmp.c | out/autoconf.h')
        w('  flags = %s' % F16)
        w('build out/vgaentry.o: as vgasrc/vgaentry.S | out/autoconf.h out/asm-offsets.h')
        w('  flags = %s' % F16)
        w('build out/vgasrc/vgalayout.lds: cpplds vgasrc/vgalayout.lds.S')
        w('build out/autovgaversion.h: vgaversion scripts/buildversion.py')
        w('build out/vgaversion.o: ccvga1 vgasrc/vgaversion.c | out/autovgaversion.h')
        w('  flags = %s' % F16)
        w('build out/vgarom.o: ldvga out/vgaccode16.o out/vgaentry.o out/vgaversion.o | out/vgasrc/vgalayout.lds')
        w('build out/vgabios.bin.raw: rawvga out/vgarom.o')
        w('build out/vgabios.bin: buildrom out/vgabios.bin.raw | scripts/buildrom.py')
        w('')
        w('default out/bios.bin out/vgabios.bin')
    else:
        w('default out/bios.bin')
    w('')

    open(os.path.join(SRCDIR, 'build.ninja'), 'w', newline='\n').write('\n'.join(n))
    print('build.ninja written: %d rules' % 8)

if __name__ == '__main__':
    main()
