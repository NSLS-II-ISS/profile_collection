print(__file__)

import glob
import logging
import os
import sys
import time
from pathlib import Path
from timeit import default_timer as timer
import appdirs
import bluesky
import nslsii
from bluesky.simulators import summarize_plan
# Check version of bluesky and act accordingly
from distutils.version import LooseVersion
from datetime import datetime
# from xview.spectra_db.db_io import get_spectrum_catalog
from tiled.client import from_profile
import json
import time as ttime
import numpy as np
import pandas as pd
import xraydb
from bluesky.utils import PersistentDict

# the file paths for acquitision and analysis

ROOT_PATH_SHARED = '/nsls2/data/iss/legacy/xf08id'
ROOT_PATH = '/nsls2/data/iss/legacy'
RAW_PATH = 'raw'
USER_PATH = 'processed'


# ROOT_PATH_SHARED = '/nsls2/xf08id'
# ROOT_PATH = '/nsls2/xf08id'
# RAW_PATH = 'data'
# USER_PATH = 'users'


def time_now_str():
    return datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S.%f')

# def print_to_gui(msg, tag='', add_timestamp=False, ntabs=0, stdout=sys.stdout):
def print_to_gui(msg, tag='', add_timestamp=False, ntabs=0, stdout_alt=sys.stdout):
    # print('THIS IS STDOUT', stdout, stdout is xlive_gui.emitstream_out)
    try:
        stdout = xlive_gui.emitstream_out
    except NameError:
        stdout = stdout_alt

    msg = '\t'*ntabs + msg
    if add_timestamp:
        msg = f'({time_now_str()}) {msg}'
    if tag:
        msg = f'[{tag}] {msg}'

    print(msg, file=stdout, flush=True)

def print_debug(msg):
    print_to_gui(msg, tag='>> DEBUG <<', add_timestamp=True, ntabs=1)


# Qt config for 4K displays.
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'



###############################################################################
# TODO: remove this block once https://github.com/bluesky/ophyd/pull/959 is
# merged/released.
from ophyd.signal import EpicsSignalBase, EpicsSignal, DEFAULT_CONNECTION_TIMEOUT

def wait_for_connection_base(self, timeout=DEFAULT_CONNECTION_TIMEOUT):
    '''Wait for the underlying signals to initialize or connect'''
    if timeout is DEFAULT_CONNECTION_TIMEOUT:
        timeout = self.connection_timeout
    # print(f'{print_now()}: waiting for {self.name} to connect within {timeout:.4f} s...')
    start = time.time()
    try:
        self._ensure_connected(self._read_pv, timeout=timeout)
        # print(f'{print_now()}: waited for {self.name} to connect for {time.time() - start:.4f} s.')
    except TimeoutError:
        if self._destroyed:
            raise DestroyedError('Signal has been destroyed')
        raise

def wait_for_connection(self, timeout=DEFAULT_CONNECTION_TIMEOUT):
    '''Wait for the underlying signals to initialize or connect'''
    if timeout is DEFAULT_CONNECTION_TIMEOUT:
        timeout = self.connection_timeout
    # print(f'{print_now()}: waiting for {self.name} to connect within {timeout:.4f} s...')
    start = time.time()
    self._ensure_connected(self._read_pv, self._write_pv, timeout=timeout)
    # print(f'{print_now()}: waited for {self.name} to connect for {time.time() - start:.4f} s.')

EpicsSignalBase.wait_for_connection = wait_for_connection_base
EpicsSignal.wait_for_connection = wait_for_connection
###############################################################################

from ophyd.signal import EpicsSignalBase
# if not OLD_BLUESKY:
EpicsSignalBase.set_defaults(timeout=10, connection_timeout=10)

from databroker import Broker

db_archive = Broker.named('iss')
db = Broker.named('iss-local')

# db_proc = get_spectrum_catalog()

db_proc = from_profile('iss-dev-analyzed')

nslsii.configure_base(get_ipython().user_ns, db, pbar=False)
nslsii.configure_kafka_publisher(RE, "iss")

logger_db = logging.getLogger('databroker')
logger_db.setLevel('WARNING')

bec.disable_plots()
bec.disable_table()
RE.subscribe(bec)
peaks = bec.peaks  # just as alias for less typing

runengine_metadata_dir = Path(f'{ROOT_PATH_SHARED}/metadata/') / Path("runengine-metadata")
RE.md = PersistentDict(runengine_metadata_dir) # PersistentDict will create the directory if it does not exist


# Patch to fix Tom's terrible deeds
# import matplotlib.backends.backend_qt
from matplotlib.backends.backend_qt import _create_qApp

_create_qApp()
# qApp = matplotlib.backends.backend_qt.qApp

# /nsls2/data/iss/shared/config/bluesky/profile_collection/startup/00-startup.py:130:
# MatplotlibDeprecationWarning: The qApp attribute was deprecated in Matplotlib 3.6 and will be removed two minor
# releases later. Use QtWidgets.QApplication.instance() instead.
#   qApp = matplotlib.backends.backend_qt.qApp

RE.is_aborted = False

def ensure_proposal_id(md):
    if 'proposal_id' not in md:
        raise ValueError("You forgot the proposal_id.")

# Set up default metadata.
RE.md['group'] = 'iss'
RE.md['Facility'] = 'NSLS-II'
RE.md['beamline_id'] = 'ISS (8-ID)'
RE.md['proposal_id'] = None
RE.md_validator = ensure_proposal_id

def get_hook():
    from bluesky.utils import ts_msg_hook
    RE.msg_hook = ts_msg_hook

# get_hook()

import faulthandler
faulthandler.enable()
