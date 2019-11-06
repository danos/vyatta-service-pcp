#!/usr/bin/python3
# Copyright (c) 2019 AT&T Intellectual Property.
# All Rights Reserved.
#
# SPDX-License-Identifier: GPL-2.0-only

import logging
import vci
from vyatta.pcp.service import PCPService

try:
    import vrfmanager
    vrf_manager = vrfmanager.VrfManager()
except ImportError:
    pass

class PCPConfig(vci.Config):
    def __init__(self, prog):
        super().__init__()
        self.prog = prog
        self.service = {}
        self.log = logging.getLogger()

    def set(self, cfg):
        self.log.debug('set: {}'.format(cfg))
        self.cfg = cfg

        # Global config
        try:
            pcfg = cfg['vyatta-services-v1:service']['vyatta-service-pcp-v1:pcp']
        except KeyError:
            pcfg = {}
        self._apply('default', pcfg)

        # Per routing-instance config
        vrflist = []
        try:
            rtlist = cfg['vyatta-routing-v1:routing']['routing-instance']
        except KeyError:
            rtlist = {}
        for rt in rtlist:
            rtname = rt['instance-name']
            vrflist.append(rtname)
            try:
                rtcfg = rt['service']['vyatta-service-pcp-routing-instance-v1:pcp']
            except KeyError:
                rtcfg = {}

            # Make sure vrf exists - it might not yet
            try:
                vrf_id = vrf_manager.get_vrf_id(rtname)
                if vrf_id == vrfmanager.vrfid_invalid:
                    raise Exception()
            except:
                self.log.info('defer config for vrf {}'.format(rtname));
                continue

            self._apply(rtname, rtcfg)

        # routing-instance whose config has gone
        # Since dictionary may change, iterate through a list of keys
        for vrf in list(self.service.keys()):
            if vrf == 'default':
                continue
            if vrf not in vrflist:
                self._apply(vrf, {})

    def get(self):
        # Return the configuration
        return self.cfg

    def check(self, cfg):
        # Do additional configuration checks
        return

    def _apply(self, vrf, cfg):
        # Apply per-vrf configuration
        self.log.debug('apply {}: {}'.format(vrf, cfg))

        # Check if config has changed to avoid unnecessary daemon restart
        try:
            service = self.service[vrf]
            old = service.get_cfg()
        except KeyError:
            service = None
            old = {}

        if cfg == old:
            # no change in config
            self.log.debug('{} config unchanged'.format(vrf))
            return

        if cfg == {}:
            # config has gone
            self.log.debug('{} de-configured'.format(vrf))
            if service != None:
                service.shutdown()
                del self.service[vrf]
        else:
            if service == None:
                # create new service
                self.log.debug('{} newly configured'.format(vrf))
                service = PCPService(self.prog, vrf)
                self.service[vrf] = service
            else:
                # config change for existing service
                self.log.debug('{} config changed'.format(vrf))
            service.configure(cfg)

    def new_vrf(self, data):
        # Apply configuration for a newly discovered vrf
        self.log.info('new vrf: {}'.format(data))
        try:
            newvrf = data['vyatta-routing-v1:name']
        except KeyError:
            return

        try:
            rtlist = self.cfg['vyatta-routing-v1:routing']['routing-instance']
        except KeyError:
            return

        for rt in rtlist:
            try:
                rtname = rt['instance-name']
            except KeyError:
                continue

            try:
                rtcfg = rt['service']['vyatta-service-pcp-routing-instance-v1:pcp']
            except KeyError:
                continue

            if newvrf == rtname:
                self._apply(rtname, rtcfg)
                return
