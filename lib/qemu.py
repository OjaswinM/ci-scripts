import argparse
import uuid
import tarfile
import atexit
import os
import sys
import subprocess
import logging
import tempfile
from utils import *
from pexpect_utils import PexpectHelper, standard_boot, ping_test, wget_test
import qemu_callbacks
from application_tests.factory import *


class QemuConfig:
    def __init__(self, machine):
        self.uuid = uuid.uuid4().hex[:8]
        self.machine = machine
        self.machine_caps = []
        self.cpu = None
        self.mem = None
        self.accel = 'tcg'
        self.use_vof = False
        self.smp = None
        self.cloud_image = None
        self.host_mounts = []
        self.cmdline = ['noreboot']
        self.pexpect_timeout = 60
        self.logpath = f'/tmp/console-{self.uuid}.log'
        self.quiet = False
        self.net = None
        self.net_tests = False
        self.host_command = 'run'
        self.gdb = None
        self.interactive = False
        self.drives = []
        self.next_drive = 0
        self.initrd = None
        self.compat_rootfs = False
        self.boot_func = None
        self.shutdown = None
        self.callbacks = []
        self.extra_args = []
        self.qemu_path = None
        self.qemu_cmd = None
        self.login = False
        self.prompt = None
        self.user = 'root'
        self.password = None
        self.expected_release = None
        self.vmlinux = None
        self.cpuinfo = None
        self.bios = None
        self.test_base_dir = None
        self.test_name = None
        self.test_tarball = None

        # Detect root disks if we're called from scripts/boot/qemu-xxx
        base = os.path.dirname(sys.argv[0])
        path = f'{base}/../../root-disks'
        if os.path.isdir(path):
            self.root_disk_path = path
        else:
            self.root_disk_path = None

    def machine_is(self, needle):
        return self.machine.startswith(needle)

    def configure_from_env(self):
        self.expected_release = get_expected_release()
        self.vmlinux = get_vmlinux()
        self.modules_tarball = get_modules_tarball()
        self.selftests_tarball = get_selftests_tarball()

    def valid_test_name(self, name):
        """Check if the provided path is a valid test folder."""
        base = os.path.dirname(sys.argv[0])
        test_dir = f'{base}/../../tests'

        if not os.path.isdir(test_dir):
            print(f'Test dir not found at: {test_dir}')
            sys.exit(1)
        else:
            self.test_base_dir = test_dir

        valid_tests = {test for test in os.listdir(test_dir) if os.path.isdir(os.path.join(test_dir, test))}

        if name not in valid_tests:
            raise argparse.ArgumentTypeError(f"Invalid test name. Must be one of: {', '.join(valid_tests)}")

        return name

    def valid_test_args(self, args):
        # TODO: Source these file systems from avodaco misc tests repository instead of hardcoding
        supported_fs = ['ext2', 'ext4', 'xfs', 'btrfs']

        # Check if there are at least two arguments: first is the fs type, second is the config file
        if len(args.split(":")) < 2:
            raise ValueError("At least two arguments are required: filesystem type and config file")

        avocado_fs_type = args.split(":")[0]
        if avocado_fs_type not in supported_fs:
            raise ValueError(f"Invalid filesystem type '{avocado_fs_type}'. Must be one of: {', '.join(supported_fs)}")

        # TODO: make sure the second arg is always the config file
        avocado_yaml_config = args.split(":")[1]

        print(f"Running avocado test with filesystem type '{avocado_fs_type}' and config file '{avocado_yaml_config}'")
        return f"{avocado_fs_type} {avocado_yaml_config}"

    def valid_test_op_mnt(self, path):
        if os.path.isdir(path):
            return path
        else:
            raise argparse.ArgumentTypeError(f"Invalid mount point: '{path}' is not a directory.")


    def configure_from_args(self, orig_args):
        parser = argparse.ArgumentParser()
        parser.add_argument('-v', dest='verbose', action='store_true', help='Verbose logging')
        parser.add_argument('--gdb', action='store_true', help='Wait for gdb connection')
        parser.add_argument('--interactive', action='store_true', help='Run interactively')
        parser.add_argument('--accel', type=str, help="Accelerator to use, 'tcg' (default) or 'kvm'")
        parser.add_argument('--cpu', type=str, help="CPU to use")
        parser.add_argument('--smp', type=str, help="SMP config")
        parser.add_argument('--mem-size', type=str, help="Memory config")
        parser.add_argument('--cloud-image', type=str, help="Cloud image to use")
        parser.add_argument('--initrd', type=str, help="Name of initrd to use")
        parser.add_argument('--compat-rootfs', action='store_true', help="Use compat rootfs (if available)")
        parser.add_argument('--use-vof', action='store_true', help="Use pseries vof")
        parser.add_argument('--quiet', action='store_true', help="Reduce output")
        parser.add_argument('--net-tests', action='store_true', help="Run network tests")
        parser.add_argument('--logpath', type=str, help="Alternate log path")
        parser.add_argument('--pexpect-timeout', type=str, help="pexepect timeout in seconds (default 60)")
        parser.add_argument('--mount', dest='mounts',  type=str, default=[], action='append', help='Host mount points')
        parser.add_argument('--mount-cmd', dest='mount_command',  type=str, help="Command to run in mount point (default 'run')")
        parser.add_argument('--cmdline', type=str, help='Kernel command line arguments')
        parser.add_argument('--release-path', type=str, help='Path to kernel.release')
        parser.add_argument('--kernel-path', type=str, help='Path to kernel (vmlinux)')
        parser.add_argument('--modules-path', type=str, help='Path to modules tarball')
        parser.add_argument('--selftests-path', type=str, help='Path to selftests tarball')
        parser.add_argument('--test-name', type=self.valid_test_name, help='Path to the test directory in ci-scripts/tests')
        parser.add_argument('--test-output-dir', type=self.valid_test_op_mnt, help='Path to a folder where test will store the logs')
        parser.add_argument('--test-args', type=self.valid_test_args, help='Test type and configuration for the test provided in --test-name')
        parser.add_argument('--bios', type=str, help='BIOS option for qemu')
        parser.add_argument('--cap', dest='machine_caps',  type=str, default=[], action='append', help='Machine caps')
        parser.add_argument('--qemu-path', dest='qemu_path', type=str, help='Path to qemu bin directory')
        parser.add_argument('--root-disk-path', dest='root_disk_path', type=str, help='Path to root disk directory')
        parser.add_argument('--callback', metavar='callback', dest='callbacks', type=str, default=[], action='append', help='Callback to run')
        parser.add_argument('-x', metavar='shell command', dest='shell_commands', type=str, default=[], action='append', help='Shell command to run')
        args = parser.parse_args(orig_args)

        if args.gdb:
            self.extra_args += ['-S', '-s']
            self.pexpect_timeout = 0

        if args.pexpect_timeout:
            self.pexpect_timeout = int(args.pexpect_timeout,10)

        if args.interactive:
            self.interactive = True

        if args.accel:
            self.accel = args.accel

        if args.cpu:
            self.cpu = args.cpu

        if args.smp:
            self.smp= args.smp

        if args.mem_size:
            self.mem= args.mem_size

        if args.cloud_image:
            self.cloud_image = args.cloud_image

        if args.initrd:
            self.initrd = args.initrd

        if args.logpath:
            self.logpath = args.logpath

        if args.mount_command:
            self.host_command = args.mount_command

        if args.cmdline:
            self.cmdline.append(args.cmdline)

        if args.release_path:
            self.expected_release = read_expected_release(args.release_path)

        if args.kernel_path:
            self.vmlinux = args.kernel_path

        if args.modules_path:
            self.modules_tarball = args.modules_path

        if args.qemu_path:
            self.qemu_path = args.qemu_path

        if args.root_disk_path:
            self.root_disk_path = args.root_disk_path

        if args.selftests_path:
            self.selftests_tarball = args.selftests_path

        if args.test_name:
            self.test_name = args.test_name

            if args.test_output_dir:
                self.test_output_dir = args.test_output_dir
            else:
                self.test_output_dir = tempfile.mkdtemp(prefix="test-output-", dir="/tmp")

            if args.test_args:
                self.test_args = args.test_args

        self.compat_rootfs = args.compat_rootfs
        self.use_vof = args.use_vof
        self.quiet = args.quiet
        self.net_tests = args.net_tests
        self.host_mounts.extend(args.mounts)
        self.machine_caps.extend(args.machine_caps)
        self.bios = args.bios

        def make_callback(func, arg_str):
            if arg_str:
                return lambda qconf, p: func(qconf, p, arg_str)
            else:
                return func

        for cb in args.callbacks:
            # Callbacks can take args, like callback(foo bar)
            # But the callback just gets a string "foo bar"
            if '(' in cb:
                name, arg_str = cb.split('(', 1)
                arg_str = arg_str[:-1] # Crop trailing )
            else:
                name = cb
                arg_str = None

            func = getattr(qemu_callbacks, name)
            self.callbacks.append(make_callback(func, arg_str))

        func = getattr(qemu_callbacks, 'sh')
        for cmd in args.shell_commands:
            self.callbacks.append(make_callback(func, cmd))


    def apply_defaults(self):
        if not self.expected_release:
            logging.error("Couldn't find kernel.release")
            return
            
        if not self.vmlinux:
            logging.error("Can't find kernel vmlinux")
            return

        if not self.root_disk_path:
            logging.error("Couldn't locate root disks")
            return
 
        if self.machine_is('pseries'):
            if self.accel == 'tcg':
                self.machine_caps += ['cap-htm=off']
            else:
                self.__set_spectre_v2_caps()

            if self.cpu and self.accel == 'kvm':
                if self.cpu != 'host':
                    self.machine_caps += ['max-cpu-compat=%s' % self.cpu.lower()]
                self.cpu = None

            if self.use_vof:
                self.machine_caps += ['x-vof=on']

        if self.cpuinfo is None:
            if self.machine_is('pseries'):
                self.cpuinfo = [r'IBM pSeries \(emulated by qemu\)']
            elif self.machine_is('powernv'):
                self.cpuinfo = [r'IBM PowerNV \(emulated by qemu\)']
            elif self.machine == 'mac99':
                self.cpuinfo = [r'PowerMac3,1 MacRISC MacRISC2 Power Macintosh']
            elif self.machine == 'g3beige':
                self.cpuinfo = [r'AAPL,PowerMac G3 MacRISC']
            elif self.machine == 'bamboo':
                self.cpuinfo = [r'PowerPC 44x Platform']
            elif self.machine == 'ppce500':
                self.cpuinfo = [r'QEMU ppce500']
                if self.cpu:
                    self.cpuinfo.insert(0, f'cpu\\s+: {self.cpu}')

        if self.qemu_cmd is None:
            if self.machine_is('pseries') or self.machine_is('powernv'):
                self.qemu_cmd = 'qemu-system-ppc64'
            else:
                self.qemu_cmd = 'qemu-system-ppc'

        if self.qemu_path:
            self.qemu_cmd = f'{self.qemu_path}/{self.qemu_cmd}'

        if self.smp is None:
            if self.machine_is('mac99'): # Doesn't support SMP
                self.smp = 1
            elif self.accel == 'tcg':
                self.smp = 2
            else:
                self.smp = 8

        if self.mem is None:
            if self.machine_is('pseries'):
                self.mem = '4G'
                if type(self.smp) is int and self.smp % 4 == 0:
                    cpus = int(self.smp / 4)
                else:
                    cpus = None
                    s = ''
                for i in range(0, 4):
                    self.extra_args.append(f'-object memory-backend-ram,size=1G,id=m{i}')
                    if cpus:
                        first = i * cpus
                        last  = first + cpus - 1
                        s = f',cpus={first}-{last}'
                    self.extra_args.append(f'-numa node,nodeid={i},memdev=m{i}{s}')
            elif self.machine_is('powernv'):
                self.mem = '4G'
            else:
                self.mem = '1G'

        if self.net is None:
            if self.machine_is('pseries'):
                self.net = '-nic user,model=virtio-net-pci'
            elif self.machine_is('powernv'):
                self.net = '-netdev user,id=net0 -device e1000e,netdev=net0'
            else:
                self.net = '-nic user'

        if self.machine == 'powernv':
            if self.cpu and self.cpu.upper() == 'POWER8':
                self.machine = 'powernv8'
            elif self.cpu and self.cpu.upper() == 'POWER10':
                self.machine = 'powernv10'
            else:
                self.machine = 'powernv9'

        if self.cloud_image:
            self.login = True
            self.password = 'linuxppc'
            self.user = 'root'

            if 'ubuntu' in self.cloud_image:
                self.prompt = 'root@ubuntu:'
            elif 'fedora' in self.cloud_image:
                self.prompt = r'\[root@fedora ~\]#'
            elif 'debian' in self.cloud_image:
                self.prompt = 'root@debian:~#'

        if self.prompt is None:
            # Default prompt for our root disks
            self.prompt = "~ #"

        if self.initrd is None and len(self.drives) == 0 and self.cloud_image is None:
            if self.compat_rootfs or self.qemu_cmd.endswith('qemu-system-ppc'):
                subarch = 'ppc'
            elif get_endian(self.vmlinux) == 'little':
                subarch = 'ppc64le'
            elif self.machine_is('powernv') or self.machine_is('pseries'):
                subarch = 'ppc64'
            else:
                subarch = 'ppc64-novsx'

            self.initrd = f'{subarch}-rootfs.cpio.gz'

        if self.host_mounts or self.test_output_dir:
            i = 0
            if self.machine_is('powernv'):
                bus = f',bus=pcie.{i+2}'
            else:
                bus = ''

            for path in self.host_mounts:

                self.extra_args.append(f'-fsdev local,id=fsdev{i},path={path},security_model=none')
                self.extra_args.append(f'-device virtio-9p-pci,fsdev=fsdev{i},mount_tag=host{i}{bus}')
                i += 1

            if self.test_output_dir:
                self.extra_args.append(f'-fsdev local,id=fsdev{i},path={self.test_output_dir},security_model=none')
                self.extra_args.append(f'-device virtio-9p-pci,fsdev=fsdev{i},mount_tag=testdir{bus}')
                i += 1

        if self.machine_is('pseries'):
            rng = '-object rng-random,filename=/dev/urandom,id=rng0 -device spapr-rng,rng=rng0'
            if self.accel == 'kvm':
                rng += ',use-kvm=true'

            self.extra_args += [rng]

        if self.boot_func is None:
            def boot(p, timeout, qconf):
                standard_boot(p, qconf.login, qconf.user, qconf.password, timeout)

            self.boot_func = boot

        if self.modules_tarball:
            self.modules_drive = self.add_drive(f'file={self.modules_tarball},format=raw,readonly=on')

        if self.selftests_tarball:
            self.selftests_drive = self.add_drive(f'file={self.selftests_tarball},format=raw,readonly=on')

        if self.test_name:
            if not os.path.exists(self.test_base_dir):
                logging.error(f"Test directory '{self.test_base_dir}' does not exist.")
                raise FileNotFoundError(f"Base directory '{self.test_base_dir}' does not exist.")

            test_dir = os.path.join(self.test_base_dir, self.test_name)
            if not os.path.isdir(test_dir):
                logging.error(f"'{test_dir}' is not a directory.")
                raise NotADirectoryError(f"'{test_dir}' is not a directory.")

            tar_filename = f"{self.test_name}_{self.uuid}.tar"
            tar_path = os.path.join("/tmp", tar_filename)

            try:
                with tarfile.open(tar_path, "w") as tar:
                    tar.add(test_dir, arcname=self.test_name)
                self.test_tarball = tar_path
                logging.info(f"Test directory '{test_dir}' archived to '{self.test_tarball}'")
            except Exception as e:
                logging.error(f"Failed to create tarball: {e}")
                raise

            self.test_drive = self.add_drive(f"file={self.test_tarball},format=raw,readonly=on")
            

    def add_drive(self, args):
        drive_id = self.next_drive
        self.next_drive += 1

        if self.machine_is('powernv'):
            interface = 'none'
            self.drives.append(f'-device virtio-blk-pci,drive=drive{drive_id},id=blk{drive_id},bus=pcie.{drive_id}')
        else:
            interface = 'virtio'

        self.drives.append(f'-drive {args},if={interface},id=drive{drive_id}')

        # Convert to drive letter
        return chr(ord('a') + drive_id)
        
    def prepare_cloud_image(self):
        if self.cloud_image is None:
            return

        rdpath = self.root_disk_path
        img_path = f'{rdpath}/{self.cloud_image}'

        # qemu-img gives random issues when we are not in
        # the dir where the output image will be
        cwd = os.getcwd()
        os.chdir(rdpath)

        if self.cloud_image.endswith('.qcow2'):
            # Create snapshot image
            pid = os.getpid()
            dst = f'qemu-temp-{pid}.img'

            if self.test_name:
                # some tests need VMs with more disk space like avocado.
                # hence create the image accordingly
                cmd1 = f'qemu-img create -f qcow2 -F qcow2 -b {self.cloud_image} {dst} 50G'.split()
                cmd2 = f'qemu-img resize {dst} 50G'.split()
                logging.info(cmd1)
                logging.info(cmd2)
                subprocess.run(cmd1, check=True)
                subprocess.run(cmd2, check=True)
            else:
                cmd = f'qemu-img create -f qcow2 -F qcow2 -b {self.cloud_image} {dst}'.split()
                logging.info(cmd)
                subprocess.run(cmd, check=True)
            img_path = f"{rdpath}/{dst}"
            atexit.register(lambda: os.unlink(img_path))
            format = 'qcow2'
        else:
            format = 'raw'

        os.chdir(cwd)

        cloud_drive = self.add_drive(f'file={img_path},format={format}')
        self.add_drive(f'file={rdpath}/cloud-init-user-data.img,format=raw,readonly=on')

        if 'ubuntu' in self.cloud_image:
            self.cmdline.insert(0, f'root=/dev/vd{cloud_drive}1')
        elif 'fedora34' in self.cloud_image or 'debian' in self.cloud_image:
            self.cmdline.insert(0, f'root=/dev/vd{cloud_drive}2')
        elif 'fedora' in self.cloud_image:
            if 'fedora39' in self.cloud_image:
                partition = 5
            else:
                partition = 3
            self.cmdline.insert(0, 'systemd.mask=hcn-init.service systemd.hostname=fedora')
            self.cmdline.insert(0, f'root=/dev/vd{cloud_drive}{partition} rootfstype=btrfs rootflags=subvol=root')

    def __set_spectre_v2_caps(self):
        try:
            body = open('/sys/devices/system/cpu/vulnerabilities/spectre_v2', 'r').read()
        except (FileNotFoundError, PermissionError):
            # Should be readable, but continue anyway and cross fingers
            return

        for s in ['Indirect branch cache disabled', 'Software count cache flush']:
            if s in body:
                return

        self.machine_caps += ['cap-ccf-assist=off']

    def cmd(self):
        logging.info('Using qemu version %s.%s "%s"' % get_qemu_version(self.qemu_cmd))

        machine = self.machine
        if len(self.machine_caps):
            machine = ','.join([machine] + self.machine_caps)

        l = [
            self.qemu_cmd,
            '-nographic',
            '-vga', 'none',
            '-M', machine,
            '-smp', str(self.smp),
            '-m', self.mem,
            '-accel', self.accel,
            '-kernel', self.vmlinux,
        ]

        if self.net:
            l.append(self.net)

        if self.initrd:
            l.append('-initrd')
            l.append(os.path.join(self.root_disk_path, self.initrd))

        if len(self.drives):
            l.extend(self.drives)

        if self.cpu is not None:
            l.append('-cpu')
            l.append(self.cpu)

        if self.bios is not None:
            l.append('-bios')
            l.append(self.bios)

        if len(self.cmdline):
            l.append('-append')
            cmdline = ' '.join(self.cmdline)
            l.append(f'"{cmdline}"')

        l.extend(self.extra_args)

        logging.debug(l)

        return ' '.join(l)


def qemu_monitor_shutdown(p):
    p.send('\x01c') # invoke qemu monitor
    p.expect(r'\(qemu\)')
    p.send('quit')


def get_qemu_version(emulator):
    p = PexpectHelper()
    p.spawn('%s --version' % emulator, quiet=True)
    p.expect(r'QEMU emulator version (([0-9]+)\.([0-9]+)[^\n]*)')
    full, major, minor = p.matches()
    return (int(major), int(minor), full.strip())


def qemu_supports_p10(path):
    major, _, _ = get_qemu_version(path)
    return major >= 7


def get_host_cpu():
    f = open('/proc/cpuinfo')
    while True:
        # Not pretty but works
        l = f.readline()
        words = l.split()
        if words[0] == 'cpu':
            return words[2]

def kvm_present():
    return os.path.exists('/sys/module/kvm_hv')


def kvm_possible(machine, cpu):
    if kvm_present() and machine == 'pseries':
        host_cpu = get_host_cpu()
        if host_cpu == 'POWER8':
            supported = ['POWER8']
        elif host_cpu == 'POWER9':
            supported = ['POWER8', 'POWER9']
        elif host_cpu == 'POWER10':
            supported = ['POWER8', 'POWER9', 'POWER10']
        else:
            supported = []

        return cpu in supported

    return False


def kvm_or_tcg(machine, cpu):
    if kvm_possible(machine, cpu):
        return 'kvm'
    return 'tcg'


def qemu_net_setup(p):
    p.cmd('ip addr show')
    p.cmd('ls -l /sys/class/net')
    p.cmd('iface=$(ls -1d /sys/class/net/e* | head -1 | cut -d/ -f 5)')
    p.cmd('ip addr add dev $iface 10.0.2.15/24')
    p.cmd('ip link set $iface up')
    p.cmd('ip addr show')
    p.cmd('ip route show')


def qemu_main(qconf):
    if qconf.expected_release is None or qconf.vmlinux is None:
        return False

    for path in qconf.host_mounts:
        if not os.path.isdir(path):
            logging.error(f"Mount points must point to directories. Not found: '{path}'")
            return False

    qconf.prepare_cloud_image()

    cmd = qconf.cmd()

    logging.info(f"Running '{cmd}'")

    if qconf.interactive:
        logging.info("Running interactively ...")
        if qconf.host_mounts:
            logging.info("To mount host mount points run:")
            logging.info(" mkdir -p /mnt; mount -t 9p -o version=9p2000.L,trans=virtio host0 /mnt")

        if qconf.test_output_dir:
            logging.info("To mount test otuput_path run")
            logging.info(" mkdir -p /mnt; mount -t 9p -o version=9p2000.L,trans=virtio testdir /mnt")

        rc = subprocess.run(cmd, shell=True).returncode
        return rc == 0

    setup_timeout(10 * qconf.pexpect_timeout)
    pexpect_timeout = qconf.pexpect_timeout
    if pexpect_timeout:
        boot_timeout = pexpect_timeout * 5
    else:
        boot_timeout = pexpect_timeout = None

    p = PexpectHelper()
    logfile = open(qconf.logpath, 'w', encoding='utf-8', errors='ignore')
    p.spawn(cmd, logfile=logfile, timeout=pexpect_timeout, quiet=qconf.quiet)

    p.push_prompt(qconf.prompt)
    qconf.boot_func(p, boot_timeout, qconf)

    logging.info(f'Looking for kernel version: {qconf.expected_release}')
    p.send('echo "booted-revision: `uname -r`"')
    p.expect(f'booted-revision: {qconf.expected_release}')
    p.expect_prompt()

    p.send('cat /proc/cpuinfo')
    if qconf.cpuinfo:
        for s in qconf.cpuinfo:
            p.expect(s)
    p.expect_prompt()

    if qconf.modules_tarball:
        p.cmd('mkdir -p /lib/modules')
        p.send(f'cd /lib/modules; cat /dev/vd{qconf.modules_drive} | zcat | tar --strip-components=2 -xf -; cd -')
        p.expect_prompt(timeout=boot_timeout)

    if qconf.selftests_tarball:
        p.cmd('mkdir -p /var/tmp/selftests')
        p.send(f'cd /var/tmp/selftests; cat /dev/vd{qconf.selftests_drive} | zcat | tar --strip-components=1 -xf -; cd -')
        p.expect_prompt(timeout=boot_timeout)

    if qconf.net_tests:
        qemu_net_setup(p)
        ping_test(p)

    if qconf.host_mounts:
        # Clear timeout, we don't know how long it will take
        setup_timeout(0)

        for i in range(0, len(qconf.host_mounts)):
            p.cmd(f'mkdir -p /mnt/host{i}')
            p.cmd(f'mount -t 9p -o version=9p2000.L,trans=virtio host{i} /mnt/host{i}')

        for i in range(0, len(qconf.host_mounts)):
            p.send(f'[ -x /mnt/host{i}/{qconf.host_command} ] && (cd /mnt/host{i} && ./{qconf.host_command})')
            p.expect_prompt(timeout=None) # no timeout

    guest_output_dir = ""

    if qconf.test_output_dir:
        guest_output_dir = "/mnt/testdir"
        p.cmd(f'mkdir -p {guest_output_dir}')
        p.cmd(f'mount -t 9p -o version=9p2000.L,trans=virtio testdir {guest_output_dir}')

    if qconf.test_tarball:
        # extract the test folder in qemu
        p.cmd('mkdir -p /var/tmp/test')
        p.cmd(f'cd /var/tmp/test; cat /dev/vd{qconf.test_drive} | tar  -xf -; cd {qconf.test_name}')
        p.cmd(f'cd /var/tmp/test/{qconf.test_name}')

        #remove the temp tarball once copied in VM
        atexit.register(lambda: os.unlink(qconf.test_tarball))

        # set up package manager and install make
        if 'ubuntu' in qconf.cloud_image or 'debian' in qconf.cloud_image:
            p.cmd(f'apt update -y')
            p.cmd(f'apt install -y make zip unzip')
        elif 'fedora' in qconf.cloud_image:
            p.cmd(f'dnf update -y; dnf install -y make zip unzip')

        logging.info(f"Starting {qconf.test_name} test preparation...")
        test_runner = create_test_instance(qconf.test_name, qconf.test_args, p)

        # p.cmd("mkdir -p ~/avocado/job-results/latest")
        # p.cmd("echo Hello world > ~/avocado/job-results/latest/log.txt")

        test_runner.setup()
        test_runner.test()

        # avocado will copy xfstest logs to qconf.test_output_dir. All we need
        # to do is copy avocado logs the dir so we can retrieve them later.
        test_runner.collect_logs(guest_output_dir)


    for callback in qconf.callbacks:
        logging.info("Running callback ...")
        if callback(qconf, p) is False:
            logging.error("Callback failed")
            return False

    if qconf.shutdown:
        qconf.shutdown(p)
    else:
        p.send('poweroff')

    p.wait_for_exit(timeout=boot_timeout)

    if filter_log_warnings(open(qconf.logpath), open('warnings.txt', 'w')):
        logging.error('Errors/warnings seen in console log')
        return False

    logging.info('Test completed OK')

    return True
