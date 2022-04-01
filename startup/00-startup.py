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
from xview.spectra_db.db_io import get_spectrum_catalog

import time as ttime
import numpy as np
import pandas as pd
import xraydb



def print_now():
    return datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S.%f')

def print_message_now(message):
    print(f"({datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S.%f')}) {message}")

# Qt config for 4K displays.
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'

if bluesky.__version__ < LooseVersion('1.6'):
    OLD_BLUESKY = True
else:
    OLD_BLUESKY = False


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
if not OLD_BLUESKY:
    EpicsSignalBase.set_defaults(timeout=10, connection_timeout=10)


from databroker.v0 import Broker

class Broker_local(Broker):

    def insert(self, name, doc):
        """
        Insert a new document.
        Parameters
        ----------
        name : {'start', 'descriptor', 'event', 'stop'}
            Document type
        doc : dict
            Document
        """
        print_message_now(name)
        # super().insert(name, doc)
        if name in {'event', 'bulk_events', 'descriptor'}:
            return self.event_source_for_insert.insert(name, doc)
        # We are transitioning from ophyd objects inserting directly into a
        # Registry to ophyd objects passing documents to the RunEngine which in
        # turn inserts them into a Registry. During the transition period, we
        # allow an ophyd object to attempt BOTH so that configuration files are
        # compatible with both the new model and the old model. Thus, we
        # need to ignore the second attempt to insert.
        elif name == 'datum':
            return self.reg.insert_datum(ignore_duplicate_error=True, **doc)
        elif name == 'bulk_datum':
            return self.reg.bulk_insert_datum(**doc)
        elif name == 'resource':
            return self.reg.insert_resource(ignore_duplicate_error=True, **doc)
        elif name in {'start', 'stop'}:
            return self.hs.insert(name, doc)
        else:
            raise ValueError


if OLD_BLUESKY:
    nslsii.configure_base(get_ipython().user_ns, 'iss-local') #, pbar=False)
    # nslsii.configure_base(get_ipython().user_ns, 'iss')  # , pbar=False)
else:
    # We need to use v0 to have a pandas.Dataframe type returned via hdr.data() using the APBBinFileHandler handler.
    from databroker.v0 import Broker
    # db = Broker.named('iss-local')
    db = Broker_local.named('iss-local')
    # db = Broker_local.named('iss')
    db_proc = get_spectrum_catalog()
    nslsii.configure_base(get_ipython().user_ns, db, pbar=False)

# nslsii.configure_base(get_ipython().user_ns, 'iss',  publish_documents_to_kafka=True)

# # Temporary fix before it's fixed in ophyd
# logger = logging.getLogger('ophyd')
# logger.setLevel('WARNING')
logger_db = logging.getLogger('databroker')
logger_db.setLevel('WARNING')

bec.disable_plots()
bec.disable_table()
#
# from bluesky.run_engine import RunEngine
#
# RE = RunEngine({})
RE.subscribe(bec)
peaks = bec.peaks  # just as alias for less typing

try:
    from bluesky.utils import PersistentDict
except ImportError:
    import msgpack
    import msgpack_numpy
    import zict

    class PersistentDict(zict.Func):
        """
        A MutableMapping which syncs it contents to disk.
        The contents are stored as msgpack-serialized files, with one file per item
        in the mapping.
        Note that when an item is *mutated* it is not immediately synced:
        # >>> d['sample'] = {"color": "red"}  # immediately synced
        # >>> d['sample']['shape'] = 'bar'  # not immediately synced
        but that the full contents are synced to disk when the PersistentDict
        instance is garbage collected.
        """
        def __init__(self, directory):
            self._directory = directory
            self._file = zict.File(directory)
            self._cache = {}
            super().__init__(self._dump, self._load, self._file)
            self.reload()

            # Similar to flush() or _do_update(), but without reference to self
            # to avoid circular reference preventing collection.
            # NOTE: This still doesn't guarantee call on delete or gc.collect()!
            #       Explicitly call flush() if immediate write to disk required.
            def finalize(zfile, cache, dump):
                zfile.update((k, dump(v)) for k, v in cache.items())

            import weakref
            self._finalizer = weakref.finalize(
                self, finalize, self._file, self._cache, PersistentDict._dump)

        @property
        def directory(self):
            return self._directory

        def __setitem__(self, key, value):
            self._cache[key] = value
            super().__setitem__(key, value)

        def __getitem__(self, key):
            return self._cache[key]

        def __delitem__(self, key):
            del self._cache[key]
            super().__delitem__(key)

        def __repr__(self):
            return f"<{self.__class__.__name__} {dict(self)!r}>"

        @staticmethod
        def _dump(obj):
            "Encode as msgpack using numpy-aware encoder."
            # See https://github.com/msgpack/msgpack-python#string-and-binary-type
            # for more on use_bin_type.
            return msgpack.packb(
                obj,
                default=msgpack_numpy.encode,
                use_bin_type=True)

        @staticmethod
        def _load(file):
            return msgpack.unpackb(
                file,
                object_hook=msgpack_numpy.decode,
                raw=False)

        def flush(self):
            """Force a write of the current state to disk"""
            for k, v in self.items():
                super().__setitem__(k, v)

        def reload(self):
            """Force a reload from disk, overwriting current cache"""
            self._cache = dict(super().items())

runengine_metadata_dir = Path('/nsls2/xf08id/metadata/') / Path("runengine-metadata")

# PersistentDict will create the directory if it does not exist
RE.md = PersistentDict(runengine_metadata_dir)


if OLD_BLUESKY:
    # Make plots update live while scans run.
    from bluesky.utils import install_qt_kicker
    install_qt_kicker()
else:
    # Patch to fix Tom's terrible deeds
    import matplotlib.backends.backend_qt5
    from matplotlib._pylab_helpers import Gcf
    from matplotlib.backends.backend_qt5 import _create_qApp

    _create_qApp()
    qApp = matplotlib.backends.backend_qt5.qApp


RE.is_aborted = False

start = timer()

def ensure_proposal_id(md):
    if 'proposal_id' not in md:
        raise ValueError("You forgot the proposal_id.")

# Set up default metadata.
RE.md['group'] = 'iss'
RE.md['Facility'] = 'NSLS-II'
RE.md['beamline_id'] = 'ISS (8-ID)'
RE.md['proposal_id'] = None
stop2 = timer()
RE.md_validator = ensure_proposal_id
stop = timer()

print("MD handling complete in {} sec".format(stop - start))

# from bluesky.utils import ts_msg_hook
# RE.msg_hook = ts_msg_hook


# the file paths for acquitision and analysis
ROOT_PATH = '/nsls2/xf08id'
RAW_FILEPATH = 'data'
USER_FILEPATH = 'users'


def print_to_gui(string, stdout=sys.stdout):
    print(string, file=stdout, flush=True)

import faulthandler
faulthandler.enable()
