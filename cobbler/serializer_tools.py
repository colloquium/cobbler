# Abstracts out the config file format/access and holds
# reasonable default settings.
#
# Michael DeHaan <mdehaan@redhat.com>

import api
import util
from msg import *
import distros
import profiles
import systems

import weakref
import syck # pysyck > 0.61, so it has dump() 
import os
import traceback

global_settings_file = "/etc/cobbler.conf"
global_state_file = "/var/lib/cobbler/cobbler.conf"


class BootConfig:

    __instance

    def __new__(typ, *args, **kwargs):
        if __instance is None:
           __instance = object.__new__(type,*args,**kwargs)
        return __instance

    def __init__(self):
        """
        Constructor.  This class maintains both the logical
        configuration for Cobbler and the file representation thereof.
        Creating the config object only loads the default values,
        users of this class need to call deserialize() to load config
        file values.  See cobbler.py for how the CLI does it.
        """
        self.settings_file    = global_settings_file
        self.state_file       = global_state_file
        self.set_defaults()
        self.clear()

    def files_exist(self):
        """
        Returns whether the config files exist.
        """
        return os.path.exists(self.settings_file) and os.path.exists(self.state_file)

    def clear(self):
        """
        Establish an empty list of profiles distros, and systems.
        """
        profiles.clear()
        distros.clear()
        systems.clear()

    def set_defaults(self):
        """
        Set some reasonable defaults in case no values are available
        """
        self.server         = "localhost"
        self.tftpboot       = "/tftpboot"
        self.dhcpd_conf     = "/etc/dhcpd.conf"
        self.tftpd_conf     = "/etc/xinetd.d/tftp"
        self.pxelinux       = "/usr/lib/syslinux/pxelinux.0"
        self.tftpd_bin      = "/usr/sbin/in.tftpd"
        self.dhcpd_bin      = "/usr/sbin/dhcpd"
        self.httpd_bin      = "/usr/sbin/httpd"
        self.kernel_options = "append devfs=nomount ramdisk_size=16438 lang= vga=788 ksdevice=eth0" #initrd and ks added programmatically

    def get_profiles(self):
        """
        Access the current profiles list
        """
        return self.profiles

    def get_distros(self):
        """
        Access the current distros list
        """
        return self.distros

    def get_systems(self):
        """
        Access the current systems list
        """
        return self.systems

    def config_to_hash(self):
        """
        Save all global config options in hash form (for serialization)
        """
        data = {}
        data["server"]         = self.server
        data['tftpboot']       = self.tftpboot
        data['dhcpd_conf']     = self.dhcpd_conf
        data['tftpd_conf']     = self.tftpd_conf
        data['pxelinux']       = self.pxelinux
        data['tftpd_bin']      = self.tftpd_bin
        data['dhcpd_bin']      = self.dhcpd_bin
        data['httpd_bin']      = self.httpd_bin
        data['kernel_options'] = self.kernel_options
        return data

    def config_from_hash(self,hash):
        """
        Load all global config options from hash form (for deserialization)
        """
        try:
            self.server          = hash['server']
            self.tftpboot        = hash['tftpboot']
            self.dhcpd_conf      = hash['dhcpd_conf']
            self.tftpd_conf      = hash['tftpd_conf']
            self.pxelinux        = hash['pxelinux']
            self.tftpd_bin       = hash['tftpd_bin']
            self.dhcpd_bin       = hash['dhcpd_bin']
            self.httpd_bin       = hash['httpd_bin']
            self.kernel_options  = hash['kernel_options']
        except:
            print "WARNING: config file error: %s" % (self.settings_file)
            self.set_defaults()

    def to_hash(self,is_etc):
        """
        Convert all items cobbler knows about to a nested hash.
        There are seperate hashes for the /etc and /var portions.
        """
        world = {}
        if is_etc:
            world['config']      = self.config_to_hash()
        else:
            world['distros']     = self.get_distros().to_datastruct()
            world['profiles']    = self.get_profiles().to_datastruct()
            world['systems']     = self.get_systems().to_datastruct()
        return world


    def from_hash(self,hash,is_etc):
        """
        Convert a hash representation of a cobbler to 'reality'
        There are seperate hashes for the /etc and /var portions.
        """
        if is_etc:
            self.config_from_hash(hash['config'])
        else:
            distros.from_datastruct(hash['distros'])
            profiles.from_datastruct(hash['profiles'])
            systems.from_datastruct(hash['systems'])

    # ------------------------------------------------------
    # we don't care about file formats until below this line

    def serialize(self):
        """
        Save everything to the config file.
        This goes through an intermediate data format so we
        could use YAML later if we wanted.
        """

        settings = None
        state = None

        # ------
        # dump internal state (distros, profiles, systems...) into /var/lib/...
        # /etc is not serialized, it's packaged.

        if not os.path.isdir(os.path.dirname(self.state_file)):
            dirname = os.path.dirname(self.state_file)
            if dirname != "":
                os.makedirs(os.path.dirname(self.state_file))
        try:
            state = open(self.state_file,"w+")
        except:
            runtime.set_error(m("cant_create: %s" % self.state_file))
            return False
        data = self.to_hash(False)
        state.write(syck.dump(data))

        # all good
        return True

    def deserialize(self):
        """
        Load everything from the config file.
        This goes through an intermediate data structure format so we
        could use YAML later if we wanted.
        """

        # -----
        # load global config (pathing, urls, etc)...
        try:
            settings = syck.load(open(self.settings_file,"r").read())
            if settings is not None:
                self.from_hash(settings,True)
            else:
                self.last_error = m("parse_error")
                raise Exception("parse_error")
        except:
            runtime.set_error("parse_error")
            raise Exception("parse_error")

        # -----
        # load internal state(distros, systems, profiles...)
        try:
            state = syck.load(open(self.state_file,"r").read())
            if state is not None:
                self.from_hash(state,False)
            else:
                self.last_error = m("parse_error2")
                raise Exception("parse_error2")
        except:
            runtime.set_error("parse_error2")
            raise Exception("parse_error2")

        # all good
        return True
