
import sys

sys.path.insert(0, '/home/xf08id/Repos/bloptools')

import bloptools
from bloptools import bo
from bloptools.experiments.nsls2 import iss


sas_dofs = np.array([six_axes_stage.x, six_axes_stage.y, six_axes_stage.pitch, six_axes_stage.yaw])

sas_fiducial = {
 'six_axes_stage_x': 2.34275,
 'six_axes_stage_y': -2.1400625,
 'six_axes_stage_yaw': 0.0241424,
 'six_axes_stage_pitch': 3.2050,
}


sas_rel_bounds = {
 'six_axes_stage_x': np.array([-1.0, +1.0]),
 'six_axes_stage_y': np.array([-1.0, +1.0]),
 'six_axes_stage_yaw': np.array([-0.05, +0.05]),
 'six_axes_stage_pitch': np.array([-0.3, +0.3]),
}

sas_bounds = np.array([sas_fiducial[dof.name] + sas_rel_bounds[dof.name] for dof in sas_dofs])