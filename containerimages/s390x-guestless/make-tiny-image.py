#!/usr/bin/env python3
#
# Copyright (C) 2020 Red Hat, Inc.
#
# SPDX-License-Identifier: GPL-2.0-or-later

import re
import sys
import glob
import argparse
import os
import os.path
import stat
import subprocess
from tempfile import TemporaryDirectory
from shutil import copy

def which(exe):
    path = os.environ['PATH']

    if exe[0] == '.':
        exe = os.path.abspath(exe)
    if exe[0] == '/':
        return exe

    for p in path.split(os.pathsep):
        f = os.path.join(p, exe)
        if os.path.isfile(f):
            return f
    else:
        raise Exception("Cannot find '%s' in '%s'" % (exe, path))

def make_busybox(tmpdir, runcmd, loadmods, blockdevs, verbose):
    bin = os.path.join(tmpdir, "bin")
    os.makedirs(bin, exist_ok=True)

    busyboxbin = which("busybox")
    if verbose:
        print("%s --install -s %s" % (busyboxbin, bin))
    subprocess.check_call([busyboxbin, "--install", "-s", bin])
    shlink = os.path.join(tmpdir, "bin", "sh")
    if verbose:
        subprocess.check_call(["ls", "-l", shlink])
    busyboxin = os.readlink(shlink)
    busyboxout = os.path.join(tmpdir, busyboxin[1:])

    install_deps(tmpdir, [busyboxbin], verbose)

    bbbin = os.path.dirname(busyboxout)
    if verbose:
        print("mkdir %s" % bbbin)
    os.makedirs(bbbin, exist_ok=True)
    if os.path.exists(busyboxout):
        os.unlink(busyboxout)
    if verbose:
        print("copy %s -> %s" % (busyboxbin, busyboxout))
    copy(busyboxbin, busyboxout)

    init = os.path.join(tmpdir, "init")
    with open(init, "w") as fh:
        print("""#!/bin/sh

mkdir /proc /sys
mount -t proc none /proc
mount -t sysfs none /sys

mount -n -t tmpfs none /dev
mknod -m 622 /dev/console c 5 1
mknod -m 666 /dev/null c 1 3
mknod -m 666 /dev/zero c 1 5
mknod -m 666 /dev/ptmx c 5 2
mknod -m 666 /dev/tty c 5 0
mknod -m 666 /dev/ttyS0 c 4 64
mknod -m 444 /dev/random c 1 8
mknod -m 444 /dev/urandom c 1 9

""", file=fh)

        for mod in loadmods:
            print("insmod %s" % mod, file=fh)

        if blockdevs:
            # XXX sensibly wait for block dev partition probing
            print("""
for bdev in /sys/block/*
do
    dev=`basename $bdev`
    maj=`awk -F : '{print $1}' $bdev/dev`
    min=`awk -F : '{print $2}' $bdev/dev`
    mknod -m 666 /dev/$dev b $maj $min

    for part in $bdev/$dev*
    do
        dev=`basename $part`
        maj=`awk -F : '{print $1}' $part/dev`
        min=`awk -F : '{print $2}' $part/dev`
        mknod -m 666 /dev/$dev b $maj $min
    done
done
""", file=fh)

        print("""%s
poweroff -f
""" % runcmd, file=fh)
    os.chmod(init, stat.S_IRWXU)

def get_deps(binary, verbose):
    try:
        os.environ["LC_ALL"] = "C"
        out = subprocess.check_output(["ldd", binary], stderr=subprocess.STDOUT).decode("utf8")
        deps = []
        for line in out.split("\n"):
            m = re.search(r"\s*([^ ]+) => (/[^ ]+)", line)
            if m is not None:
                deps.append(m.group(2))
                if m.group(1).startswith('/'):
                    deps.append(m.group(1))
            else:
                m = re.match(r"\s*(/[^ ]+)\s+\(.*\)\s*$", line)
                if m is not None:
                    deps.append(m.group(1))
                elif "not found" in line:
                    raise Exception(line)
        return deps
    except subprocess.CalledProcessError as ex:
        out = ex.output.decode("utf8")
        if "not a dynamic executable" in out:
            if verbose:
                print("Not a dynamic executable")
            return []
        raise



def install_deps(tmpdir, binaries, verbose):
    seen = {}
    libs = []

    for binary in binaries:
        src = which(binary)
        libs.extend(get_deps(src, verbose))

    while len(libs):
        todo = libs
        libs = []
        for lib in todo:
            if lib in seen:
                continue

            dir = os.path.dirname(lib)
            libdir = os.path.join(tmpdir, dir[1:])
            os.makedirs(libdir, exist_ok=True)
            dst = os.path.join(tmpdir, lib[1:])
            copy(lib, dst)
            if verbose:
                print("Copy lib %s -> %s"% (lib, dst))
            seen[lib] = True
            libs.extend(get_deps(lib, verbose))

def make_binaries(tmpdir, binaries, verbose):
    bindir = os.path.join(tmpdir, "bin")

    for binary in binaries:
        src = which(binary)
        dst = os.path.join(tmpdir, "bin", os.path.basename(src))
        if os.path.exists(dst):
            os.unlink(dst)
        dstdir = os.path.dirname(dst)
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)

        if verbose:
            print("Copy bin %s -> %s" % (src, dst))
        copy(src, dst)

    install_deps(tmpdir, binaries, verbose)


def kmod_deps(modfile):
    out = subprocess.check_output(["modinfo", modfile], stderr=subprocess.STDOUT).decode("utf8")
    for line in out.split("\n"):
        if line.startswith("depends: "):
            deps = line[8:].strip()
            if deps == "":
                return []
            return [a.replace("-", "_") for a in deps.split(",")]


def copy_kmod(tmpdir, kmoddir, allmods, mod, verbose):
    src = os.path.join(kmoddir, allmods[mod])
    dstdir = os.path.join(tmpdir, "lib", "modules")
    if not os.path.exists(dstdir):
        os.makedirs(dstdir)
    dst = os.path.join(dstdir, os.path.basename(allmods[mod]))
    if os.path.exists(dst):
        return
    if verbose:
        print("Copy kmod %s -> %s" % (src, dst))
    copy(src, dst)

    loadmods = []
    for depmod in kmod_deps(src):
        loadmods.extend(copy_kmod(tmpdir, kmoddir, allmods, depmod, verbose))

    loadmods.append(os.path.join("/lib", "modules",
                                 os.path.basename(allmods[mod])))
    return loadmods


def make_kmods(tmpdir, kmods, kver, verbose):
    print(kver)
    kmoddir = os.path.join("/lib", "modules", kver, "kernel")
    if not os.path.exists(kmoddir):
        raise Exception("kmod dir '%s' does not exist" % kmoddir)

    allmods = {}
    for path in glob.glob(kmoddir + "/**/*.ko*", recursive=True):
        mod = os.path.basename(path).split(".")[0]
        mod = mod.replace("-", "_")
        allmods[mod] = path

    loadmods = []
    for mod in kmods:
        if mod not in allmods:
            raise Exception("kmod '%s' does not exist" % mod)
        loadmods.extend(copy_kmod(tmpdir, kmoddir, allmods, mod, verbose))
    return loadmods

def copy_extra(tmpdir, copyfiles):
    for copyfileitem in copyfiles:
        src = copyfileitem
        dstname = None
        if "=" in copyfileitem:
            bits = copyfileitem.split("=")
            src = bits[0]
            dstname = bits[1]

        if os.path.exists(src):
            if dstname is None:
                dstname = src
            if os.path.isabs(dstname):
                dst = os.path.join(tmpdir, dstname[1:])
            else:
                dst = os.path.join(tmpdir, os.path.basename(dstname))

            dstdir = os.path.dirname(dst)
            os.makedirs(dstdir, exist_ok=True)
            print("Copy extra %s -> %s" % (src, dst))
            copy(src, dst)
        else:
            items = glob.glob(src, recursive=True)
            if len(items) == 0:
                raise Exception("Path %s does not match any files" % src)
            for src in items:
                if dstname is None:
                    tmpdstname = src
                else:
                    tmpdstname = os.path.join(dstname, src[1:])

                if os.path.isabs(tmpdstname):
                    dst = os.path.join(tmpdir, tmpdstname[1:])
                else:
                    dst = os.path.join(tmpdir, tmpdstname)

                dstdir = os.path.dirname(dst)
                os.makedirs(dstdir, exist_ok=True)
                print("Copy extra %s -> %s" % (src, dst))
                copy(src, dst)

def make_image(tmpdir, output, copyfiles, kmods, kver, binaries, runcmd, blockdevs, verbose):
    loadmods = make_kmods(tmpdir, kmods, kver, verbose)
    make_busybox(tmpdir, runcmd, loadmods, blockdevs, verbose)
    if len(loadmods) > 0 and "insmod" not in binaries:
        binaries.append("insmod")
    make_binaries(tmpdir, binaries, verbose)

    copy_extra(tmpdir, copyfiles)

    files = glob.iglob(tmpdir + "/**", recursive=True)
    prefix=len(tmpdir) + 1
    files = [f[prefix:] for f in files]
    files = files[1:]
    filelist = "\n".join(files).encode("utf8")

    with open(output, "w") as fh:
        subprocess.run(["cpio", "--quiet", "-o", "-H", "newc"],
                       cwd=tmpdir, input=filelist, stdout=fh)

parser = argparse.ArgumentParser(description='Build a tiny initrd image')
parser.add_argument('--output', default="tiny-initrd.img",
                    help='Filename of output file')
parser.add_argument('--run', default="setsid cttyhack /bin/sh",
                    help='Command to execute in guest (default: "setsid cttyhack /bin/sh")')
parser.add_argument('--copy', action="append", default=[],
                    help='Extra files to copy  /src=/dst')
parser.add_argument('--kmod', action="append", default=[],
                    help='Kernel modules to load')
parser.add__argument('--kver', default=os.uname().release,
                    help='Kernel version to add modules for')
parser.add_argument('--blockdevs', action='store_true',
                    help='Wait for block devices and create /dev nodes')
parser.add_argument('--verbose', action='store_true',
                    help='Display information about contents of initrd')
parser.add_argument('binary', nargs="*",
                    help='List of binaries to include')

args = parser.parse_args()

if args.verbose:
    print("Creating %s" % args.output)

with TemporaryDirectory(prefix="make-tiny-image") as tmpdir:
    make_image(tmpdir, args.output, args.copy,
               args.kmod, args.kver, args.binary, args.run,
               args.blockdevs, args.verbose)
