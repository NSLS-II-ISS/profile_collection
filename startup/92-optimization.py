
import sys

sys.path.insert(0, '/home/xf08id/Repos/bloptools')

import bloptools
from bloptools import bo
from bloptools.experiments.nsls2 import iss

def johann_acquire(dofs, inputs):

    uids = []

    for _input in inputs:

        yield from bps.mv(*[_ for items in zip(dofs, np.atleast_1d(inputs).T) for _ in items])
        uid = yield from main_roll_optimization_plan()

        uids.append(uid)

    return uids

def johann_digest(db, uid, **kwargs): # this accepts (db, uid). returns a dictionary of products
    fwhm = estimate_peak_fwhm_from_roll_scan(db, uid, **kwargs)
    return {'johann_fwhm': fwhm}


sas_dofs = np.array([six_axes_stage.x, six_axes_stage.y, six_axes_stage.pitch, six_axes_stage.yaw])

sas_fiducial = {
 'six_axes_stage_x': 2.5571,
 'six_axes_stage_y': -2.0413,
 'six_axes_stage_yaw': 0.0561,
 'six_axes_stage_pitch': 2.7154,
}


sas_rel_bounds = {
 'six_axes_stage_x': np.array([-1.0, +1.0]),
 'six_axes_stage_y': np.array([-1.0, +1.0]),
 'six_axes_stage_yaw': np.array([-0.05, +0.05]),
 'six_axes_stage_pitch': np.array([-0.3, +0.3]),
}

sas_bounds = np.array([sas_fiducial[dof.name] + 1e-2 * sas_rel_bounds[dof.name] for dof in sas_dofs])



# OrderedDict([('six_axes_stage_x',
#               {'value': 2.5570625000000007, 'timestamp': 1683824477.635277}),
#              ('six_axes_stage_x_user_setpoint',
#               {'value': 2.5570845085664944, 'timestamp': 1683824477.635277}),
#              ('six_axes_stage_y',
#               {'value': -2.0413125, 'timestamp': 1683824504.972467}),
#              ('six_axes_stage_y_user_setpoint',
#               {'value': -2.0412992618090025, 'timestamp': 1683824504.972467}),
#              ('six_axes_stage_z',
#               {'value': -5.4991625, 'timestamp': 631152000.0}),
#              ('six_axes_stage_z_user_setpoint',
#               {'value': -5.4991625, 'timestamp': 631152000.0}),
#              ('six_axes_stage_pitch',
#               {'value': 2.7154249999999998, 'timestamp': 1683824532.318062}),
#              ('six_axes_stage_pitch_user_setpoint',
#               {'value': 2.7153352262064008, 'timestamp': 1683824532.318062}),
#              ('six_axes_stage_yaw',
#               {'value': 0.05613249999999992, 'timestamp': 1683824558.382899}),
#              ('six_axes_stage_yaw_user_setpoint',
#               {'value': 0.0561266494762479, 'timestamp': 1683824558.382899}),
#              ('six_axes_stage_roll',
#               {'value': 0.01998875, 'timestamp': 1683572502.209611}),
#              ('six_axes_stage_roll_user_setpoint',
#               {'value': 0.019991250000000016,
#                'timestamp': 1683572502.209611})])


johann_dofs = np.array([johann_spectrometer_x.x])

johann_fiducial = {'johann_spectrometer_x_x': 0}
johann_rel_bounds = {'johann_spectrometer_x_x': np.array([-2, 2])}

johann_bounds = np.array([johann_fiducial[dof.name] + johann_rel_bounds[dof.name] for dof in johann_dofs])

