

import sys
import numpy as np

sys.path.insert(0, '/home/xf08id/Repos/bloptools')

import bloptools
from bloptools.bayesian import Agent

def johann_acquire(dofs, inputs, dets=[]):

    uids = []
    for _input in inputs:

        yield from bps.mv(*[_ for items in zip(dofs, np.atleast_1d(_input)) for _ in items])
        uid = yield from main_roll_optimization_plan()
        uids.append(uid)

    return uids

def johann_digest(db, uids, **kwargs): # this accepts (db, uid). returns a dictionary of products

    products = pd.DataFrame()

    for uid in uids:



        fwhm = estimate_peak_fwhm_from_roll_scan(db, uid, **kwargs)

    return {'johann_fwhm': fwhm}

#
# sas_dofs = np.array([six_axes_stage.x, six_axes_stage.y, six_axes_stage.pitch, six_axes_stage.yaw])
#
# sas_fiducial = {
#  'six_axes_stage_x': 2.5571,
#  'six_axes_stage_y': -2.0413,
#  'six_axes_stage_yaw': 0.0561,
#  'six_axes_stage_pitch': 2.7154,
# }
#
#
# sas_rel_bounds = {
#  'six_axes_stage_x': np.array([-1.0, +1.0]),
#  'six_axes_stage_y': np.array([-1.0, +1.0]),
#  'six_axes_stage_yaw': np.array([-0.05, +0.05]),
#  'six_axes_stage_pitch': np.array([-0.3, +0.3]),
# }
#
# sas_bounds = np.array([sas_fiducial[dof.name] + 1e-2 * sas_rel_bounds[dof.name] for dof in sas_dofs])

dofs = [
    {"device": six_axes_stage.x,      "limits": 2.7633 + 0.1 * np.array([-1.0, +1.0]), "kind": "active"},
    {"device": six_axes_stage.y,      "limits": -1.36875 + 0.1 * np.array([-1.0, +1.0]), "kind": "active"},
    #{"device": six_axes_stage.pitch,  "limits": 3.7344 + 0.1 * np.array([-0.05, +0.05]), "kind": "active"},
    #{"device": six_axes_stage.yaw,    "limits": 0.11059249999999987 + 0.1 * np.array([-0.3, +0.3]), "kind": "active"},
]

dofs = [
    {"device": johann_emission.motor_cr_main_roll, "limits": 990. + 0.1 * np.array([-100.0, +100.0]), "kind": "active"},
    {"device": johann_emission.motor_cr_assy_x, "limits": 983. + np.array([-30.0, +20.0]), "kind": "active", "latent_group": "x"},
    {"device": johann_emission.motor_cr_aux2_roll, "limits": 473. + 0.1 * np.array([-200.0, +200.0]), "kind": "active"},
    {"device": johann_emission.motor_cr_aux2_yaw, "limits": -627. + 0.1 * np.array([-300.0, +300.0]), "kind": "active"},
    {"device": johann_emission.motor_cr_aux2_x, "limits": -1875. + 0.25 * np.array([-13000.0, +13000.0]), "kind": "active", "latent_group": "x"},
    {"device": johann_emission.motor_cr_aux3_roll, "limits": 1262. + 0.1 * np.array([-200.0, +200.0]), "kind": "active"},
    {"device": johann_emission.motor_cr_aux3_yaw, "limits": -56. + 0.1 * np.array([-300.0, +300.0]), "kind": "active"},
    {"device": johann_emission.motor_cr_aux3_x, "limits": -1775. + 0.25 * np.array([-13000.0, +13000.0]), "kind": "active", "latent_group": "x"},
    # {"device": johann_emission.motor_cr_aux2_y, "limits": 990. + np.array([-100.0, +100.0]), "kind": "active"},
]

tasks = [
    {"key": "pil100k_stats1_total", "kind": "maximize"},
]

dets = [
    pil100k,
]

agent = Agent(dofs=dofs,
              tasks=tasks,
              #acquisition_plan=johann_acquire,
              #digestion_function=johann_digest,
              dets=dets,
              db=db,
              allow_acquisition_errors=False)


for i in range(256):

    RE(agent.initialize("qr", n_init=256))
    RE(agent.learn("ei", n_iter=32, n_per_iter=1, train=True))
    agent.save_data(f"/nsls2/data/iss/legacy/Sandbox/BLOP_Tom/three_crystals_{int(ttime.time())}.h5")