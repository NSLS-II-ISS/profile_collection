
def extrapolate_linearly(x_in, x, y):
    if type(x_in) != np.ndarray:
        x_in = np.array(x_in)
    if len(x) == 0:
        return np.zeros(x_in.shape)
    elif len(x) == 1:
        return y * np.ones(x_in.shape)
    else:
        f = interpolate.interp1d(x, y, kind='linear', fill_value='extrapolate')
        return f(x_in)

# bla = []
# DELTA = []
# extrapolate_linearly([3, 4], bla, DELTA)


from xas.xray import bragg2e, e2bragg, crystal_reflectivity
from xas.spectrometer import compute_rowland_circle_geometry, _compute_rotated_rowland_circle_geometry

_BIG_DETECTOR_ARM_LENGTH = 550 # length of the big arm
_SMALL_DETECTOR_ARM_LENGTH = 91 # distance between the second gon and the sensitive surface of the detector

_johann_det_arm_motor_keys = ['motor_det_x', 'motor_det_th1', 'motor_det_th2']
_johann_cr_assy_motor_keys = ['motor_cr_assy_x', 'motor_cr_assy_y']
_johann_cr_main_motor_keys = ['motor_cr_main_roll', 'motor_cr_main_yaw']
_johann_cr_aux2_motor_keys = ['motor_cr_aux2_x', 'motor_cr_aux2_y', 'motor_cr_aux2_roll', 'motor_cr_aux2_yaw']
_johann_cr_aux3_motor_keys = ['motor_cr_aux3_x', 'motor_cr_aux3_y', 'motor_cr_aux3_roll', 'motor_cr_aux3_yaw']


_johann_cr_all_motor_keys = (_johann_cr_assy_motor_keys +
                             _johann_cr_main_motor_keys +
                             _johann_cr_aux2_motor_keys +
                             _johann_cr_aux3_motor_keys)
_johann_spectrometer_motor_keys = (_johann_det_arm_motor_keys +
                                   _johann_cr_all_motor_keys)

_allowed_roll_offsets = [2.5, 11.5, 20.5]

class RowlandCircle:

    def __init__(self):

        self.json_path = f'{ROOT_PATH_SHARED}/settings/json/johann_config_upd.json'
        self.energy_converter = None

        self.x_src = 0
        self.y_src = 0
        self.bragg_min = 59
        self.bragg_max = 95

        self.allowed_roll_offsets = _allowed_roll_offsets

        self.det_L1 = _BIG_DETECTOR_ARM_LENGTH
        self.det_L2 = _SMALL_DETECTOR_ARM_LENGTH
        self.cr_aux2_z = 139.5 # z-distance between the main and the auxiliary crystal (stack #2)

        self.init_from_settings()
        self.compute_trajectories()

    def load_config(self, file):
        with open(file, 'r') as f:
            config = json.loads(f.read())
        return config

    def save_current_spectrometer_config(self, file):
        with open(file, 'w') as f:
            json.dump(self.config, f)

    def save_current_spectrometer_config_to_settings(self):
        self.save_current_spectrometer_config(self.json_path)

    def init_from_settings(self):
        try:
            config = self.load_config(self.json_path)
        except Exception as e:
            print(f'Spectrometer config could not be loaded from settings. Loading the default configuration.\n\n{e}')
            config = { 'initialized': True,
                       'R' : 1000,
                       'crystal' : 'Si',
                       'hkl' : [6, 2, 0],
                       'enabled_crystals': {'main': True, 'aux2': True, 'aux3': True},
                       'parking': { 'motor_det_x': -10.0,  # high limit of this motor should be at 529 mm
                                    'motor_det_th1': 0.0,
                                    'motor_det_th2': 0.0,
                                    'motor_cr_assy_x': 0.000,
                                    'motor_cr_assy_y': 5.682,
                                    'motor_cr_main_roll': -100.0,
                                    'motor_cr_main_yaw': 560.0,
                                    'motor_cr_aux2_x': 0,
                                    'motor_cr_aux2_y': -9420.0,
                                    'motor_cr_aux2_roll': -330,
                                    'motor_cr_aux2_yaw': -790.0,
                                    'motor_cr_aux3_x': 0,
                                    'motor_cr_aux3_y': -3100.0,
                                    'motor_cr_aux3_roll': -350,
                                    'motor_cr_aux3_yaw': 1320,
                                    },
                       'roll_offset' : 3.00,
                       'det_offsets': { 'motor_det_th1': 69.0,
                                        'motor_det_th2': -69.0},
                       'det_focus' : 10.0,
                       'bragg_registration' : {'pos_nom' : {k : [] for k in _johann_spectrometer_motor_keys},
                                               'pos_act' : {k : [] for k in _johann_spectrometer_motor_keys}},
                       'energy_calibration' : {'x_nom': [],
                                               'x_act': [],
                                               'n_poly': 2},
                       }
        self.set_spectrometer_config(config)

    def set_spectrometer_config(self, config):
        # config needs a validation may be
        self.config = config
        self.config['bragg_registration']['bragg'] = {k : [] for k in _johann_spectrometer_motor_keys}
            #
            #
            #
            #
            # self.converter_nom2act = {}
            # for motor_key in _johann_spectrometer_motor_keys:
            #     # _c_nom2act = Nominal2ActualConverterWithLinearInterpolation()
            #     pos_nom = config['bragg_registration']['pos_nom'][motor_key]
            #     pos_act = config['bragg_registration']['pos_act'][motor_key]
            #     for _pos_nom, _pos_act in zip(pos_nom, pos_act):
            #         _c_nom2act.append_point(_pos_nom, _pos_act)
            #     self.converter_nom2act[motor_key] = _c_nom2act

        if 'energy_calibration' in config.keys():
            config_ec = config['energy_calibration']
            if (len(config_ec['x_nom']) > 0) and (len(config_ec['x_act']) > 0) and (config_ec['n_poly'] > 0):
                self.energy_converter = Nominal2ActualConverter(config_ec['x_nom'], config_ec['x_act'], config_ec['n_poly'])

    def set_spectrometer_calibration(self, x_nom, x_act, n_poly=2):
        self.config['energy_calibration'] = {'x_nom' : x_nom.tolist(), 'x_act' : x_act.tolist(), 'n_poly' : n_poly}
        self.energy_converter = Nominal2ActualConverter(x_nom, x_act, n_poly=n_poly)

    def reset_spectrometer_calibration(self):
        self.config['energy_calibration'] = {'x_nom': [], 'x_act': [], 'n_poly': 2}
        self.energy_converter = None

    def set_det_arm_parking(self, pos_dict):
        self.config['parking']['motor_det_x'] = pos_dict['motor_det_x']
        self.config['det_offsets']['motor_det_th1'] = pos_dict['motor_det_th1']
        self.config['det_offsets']['motor_det_th2'] = pos_dict['motor_det_th2']
        self.save_current_spectrometer_config_to_settings()

    def det_arm_parking(self):
        return (self.config['parking']['motor_det_x'],
                self.config['det_offsets']['motor_det_th1'],
                self.config['det_offsets']['motor_det_th2'])

    def set_main_crystal_parking(self, pos_dict):
        self.config['parking']['motor_cr_assy_x'] = pos_dict['motor_cr_assy_x'] - self.R
        self.config['parking']['motor_cr_assy_y'] = pos_dict['motor_cr_assy_y']
        self.config['parking']['motor_cr_main_roll'] = pos_dict['motor_cr_main_roll'] - 2500
        self.config['parking']['motor_cr_main_yaw'] = pos_dict['motor_cr_main_yaw']
        self.save_current_spectrometer_config_to_settings()

    def main_crystal_parking(self, human_readable=True):
        x, y, roll, yaw = (self.config['parking']['motor_cr_assy_x'],
                           self.config['parking']['motor_cr_assy_y'],
                           self.config['parking']['motor_cr_main_roll'],
                           self.config['parking']['motor_cr_main_yaw'])
        if human_readable:
            x = x + self.R
            roll = (roll + 2500) / 1000
            yaw = yaw / 1000
        return x, y, roll, yaw

    def set_aux2_crystal_parking(self, pos_dict):
        self.config['parking']['motor_cr_aux2_x'] = pos_dict['motor_cr_aux2_x']
        self.config['parking']['motor_cr_aux2_y'] = pos_dict['motor_cr_aux2_y']
        self.config['parking']['motor_cr_aux2_roll'] = pos_dict['motor_cr_aux2_roll'] - 2500
        self.config['parking']['motor_cr_aux2_yaw'] = pos_dict['motor_cr_aux2_yaw']
        self.save_current_spectrometer_config_to_settings()

    def aux2_crystal_parking(self, human_readable=True):
        x, y, roll, yaw = (self.config['parking']['motor_cr_aux2_x'],
                           self.config['parking']['motor_cr_aux2_y'],
                           self.config['parking']['motor_cr_aux2_roll'],
                           self.config['parking']['motor_cr_aux2_yaw'])
        if human_readable:
            x /= 1000
            y /= 1000
            roll = (roll + 2500) / 1000
            yaw /= 1000
        return x, y, roll, yaw

    def set_aux3_crystal_parking(self, pos_dict):
        self.config['parking']['motor_cr_aux3_x'] = pos_dict['motor_cr_aux3_x']
        self.config['parking']['motor_cr_aux3_y'] = pos_dict['motor_cr_aux3_y']
        self.config['parking']['motor_cr_aux3_roll'] = pos_dict['motor_cr_aux3_roll'] - 2500
        self.config['parking']['motor_cr_aux3_yaw'] = pos_dict['motor_cr_aux3_yaw']
        self.save_current_spectrometer_config_to_settings()

    def aux3_crystal_parking(self, human_readable=True):
        x, y, roll, yaw = (self.config['parking']['motor_cr_aux3_x'],
                           self.config['parking']['motor_cr_aux3_y'],
                           self.config['parking']['motor_cr_aux3_roll'],
                           self.config['parking']['motor_cr_aux3_yaw'])
        if human_readable:
            x /= 1000
            y /= 1000
            roll = (roll + 2500) / 1000
            yaw /= 1000
        return x, y, roll, yaw

    @property
    def det_dx(self):
        return self.det_L1 * np.cos(np.deg2rad(self.config['det_offsets']['motor_det_th1'])) - self.det_L2

    @property
    def det_h(self):
        return self.det_L1 * np.sin(np.deg2rad(self.config['det_offsets']['motor_det_th1']))

    @property
    def det_focus(self):
        return self.config['det_focus']

    @det_focus.setter
    def det_focus(self, value):
        self.config['det_focus'] = value

    @property
    def R(self):
        return self.config['R']

    @R.setter
    def R(self, value):
        self.config['parking']['motor_cr_assy_x'] += (self.config['R'] - value)
        self.config['R'] = value

    @property
    def crystal(self):
        return self.config['crystal']

    @crystal.setter
    def crystal(self, value):
        self.config['crystal'] = value

    @property
    def hkl(self):
        return self.config['hkl']

    @hkl.setter
    def hkl(self, value):
        self.config['hkl'] = value

    @property
    def roll_offset(self):
        return self.config['roll_offset']

    @roll_offset.setter
    def roll_offset(self, value):
        assert value in self.allowed_roll_offsets, f'roll_offset value must be equal to one of {self.allowed_roll_offsets}'
        self.config['roll_offset'] = value
        self.compute_trajectories()

    @property
    def enabled_crystals(self):
        return self.config['enabled_crystals']

    def enable_crystal(self, crystal_key, enable):
        self.enabled_crystals[crystal_key] = enable
        self.save_current_spectrometer_config_to_settings()

    @property
    def initialized(self):
        return self.config['initialized']

    @initialized.setter
    def initialized(self, value):
        self.config['initialized'] = value
        self.save_current_spectrometer_config_to_settings()

    def _compute_nominal_trajectory(self, npt=1000):
        braggs = np.linspace(self.bragg_min, self.bragg_max, npt-1)
        braggs = np.sort(np.hstack((braggs, 90)))

        # pseudos
        det_x = np.zeros(npt)
        det_y = np.zeros(npt)

        cr_main_x = np.zeros(npt)
        cr_main_y = np.zeros(npt)
        cr_main_roll = braggs.copy()
        cr_main_yaw = np.zeros(npt)

        cr_aux2_x = np.zeros(npt)
        cr_aux2_y = np.zeros(npt)
        cr_aux2_roll = np.zeros(npt)
        cr_aux2_yaw = np.zeros(npt)

        for i, bragg in enumerate(braggs):
            cr_main_x[i], cr_main_y[i], det_x[i], det_y[i] = \
                compute_rowland_circle_geometry(self.x_src, self.y_src, self.R, bragg, 0)
            cr_aux2_x[i], cr_aux2_y[i], cr_aux2_roll[i], cr_aux2_yaw[i] = \
                _compute_rotated_rowland_circle_geometry(cr_main_x[i], cr_main_y[i], det_x[i], det_y[i], bragg, self.cr_aux2_z)

        # reals
        # detector
        motor_det_x, motor_det_th1, motor_det_th2 = self._compute_trajectory_for_detector(braggs, det_x, det_y)

        # main crystal
        motor_cr_assy_x = -cr_main_x
        motor_cr_assy_y = cr_main_y
        motor_cr_main_roll = (cr_main_roll - 90 + self.config['roll_offset']) * 1000
        motor_cr_main_yaw = cr_main_yaw * 1000

        # aux crystal2
        _cr_aux2_yaw_0 = np.arcsin(self.cr_aux2_z / self.R)
        _cr_aux2_dx_0 = (-self.R * np.cos(_cr_aux2_yaw_0)) + self.R
        _cr_aux2_dx = cr_aux2_x - cr_main_x
        motor_cr_aux2_x = -(_cr_aux2_dx - _cr_aux2_dx_0) * 1000
        motor_cr_aux2_y = cr_aux2_y * 1000
        motor_cr_aux2_roll = (cr_aux2_roll - 90 + self.config['roll_offset']) * 1000
        motor_cr_aux2_yaw = (cr_aux2_yaw - np.rad2deg(_cr_aux2_yaw_0)) * 1000

        # aux crystal3
        motor_cr_aux3_x = motor_cr_aux2_x.copy()
        motor_cr_aux3_y = motor_cr_aux2_y.copy()
        motor_cr_aux3_roll = motor_cr_aux2_roll.copy()
        motor_cr_aux3_yaw = -motor_cr_aux2_yaw.copy()

        return pd.DataFrame(
               {'bragg' :               braggs,
                'det_x' :               det_x,
                'det_y' :               det_y,
                'cr_main_x' :           cr_main_x,
                'cr_main_y' :           cr_main_y,
                'cr_main_roll' :        cr_main_roll,
                'cr_main_yaw' :         cr_main_yaw,
                'cr_aux2_x':            cr_aux2_x,
                'cr_aux2_y':            cr_aux2_y,
                'cr_aux2_roll':         cr_aux2_roll,
                'cr_aux2_yaw':          cr_aux2_yaw,
                'motor_det_x':          motor_det_x,
                'motor_det_th1':        motor_det_th1,
                'motor_det_th2':        motor_det_th2,
                'motor_cr_assy_x' :     motor_cr_assy_x,
                'motor_cr_assy_y':      motor_cr_assy_y,
                'motor_cr_main_roll':   motor_cr_main_roll,
                'motor_cr_main_yaw':    motor_cr_main_yaw,
                'motor_cr_aux2_x' :     motor_cr_aux2_x,
                'motor_cr_aux2_y':      motor_cr_aux2_y,
                'motor_cr_aux2_roll':   motor_cr_aux2_roll,
                'motor_cr_aux2_yaw':    motor_cr_aux2_yaw,
                'motor_cr_aux3_x':      motor_cr_aux3_x,
                'motor_cr_aux3_y':      motor_cr_aux3_y,
                'motor_cr_aux3_roll':   motor_cr_aux3_roll,
                'motor_cr_aux3_yaw':    motor_cr_aux3_yaw})

    def _compute_trajectory_for_detector(self, braggs, det_x, det_y, det_focus=0):

        _det_bragg_rad = np.deg2rad(braggs)
        det_x = det_x.copy() - det_focus * np.cos(np.pi - 2 * _det_bragg_rad)
        det_y = det_y.copy() - det_focus * np.sin(np.pi - 2 * _det_bragg_rad)

        _phi = np.pi - 2 * _det_bragg_rad
        _sin_th1 = (self.det_h - self.det_L2 * np.sin(_phi) - det_y) / self.det_L1
        motor_det_th1 = np.arcsin(_sin_th1)
        motor_det_th2 = _phi + motor_det_th1
        motor_det_x = -self.det_dx + self.det_L1 * np.cos(motor_det_th1) - self.det_L2 * np.cos(_phi) - det_x
        motor_det_th1 = np.rad2deg(motor_det_th1)
        motor_det_th2 = -np.rad2deg(motor_det_th2)
        return motor_det_x, motor_det_th1, motor_det_th2

    def update_nominal_trajectory_for_detector(self, det_focus, force_update=False):
        if force_update or (not np.isclose(det_focus, self.det_focus, atol=1e-4)):
            self.det_focus = det_focus
            motor_det_x, motor_det_th1, motor_det_th2 = self._compute_trajectory_for_detector(self.traj_nom['bragg'],
                                                                                              self.traj_nom['det_x'],
                                                                                              self.traj_nom['det_y'],
                                                                                              det_focus=det_focus)
            self.traj_nom['motor_det_x'] = motor_det_x
            self.traj_nom['motor_det_th1'] = motor_det_th1
            self.traj_nom['motor_det_th2'] = motor_det_th2


    def compute_nominal_trajectory(self, npt=250):
        self.traj_nom = self._compute_nominal_trajectory(npt=npt)

    def compute_trajectory_correction(self):
        self.traj_delta = {}
        for motor_key in _johann_spectrometer_motor_keys:
            pos_act = np.array(self.config['bragg_registration']['pos_act'][motor_key])
            pos_nom = np.array(self.config['bragg_registration']['pos_nom'][motor_key])
            delta =  pos_act - pos_nom
            bragg = np.array(self.config['bragg_registration']['bragg'][motor_key])
            bragg_in = self.traj_nom['bragg']
            self.traj_delta[motor_key] = extrapolate_linearly(bragg_in, bragg, delta)
            # self.traj[motor_key] = self.traj[motor_key] + self.traj_delta[motor_key]
        self.traj_delta = pd.DataFrame(self.traj_delta)
        self.traj = self.traj_nom.copy()
        self.traj[self.traj_delta.columns] = self.traj[self.traj_delta.columns] + self.traj_delta

    def compute_trajectories(self):
        self.compute_nominal_trajectory()
        self.update_nominal_trajectory_for_detector(self.det_focus, force_update=True)
        self.compute_trajectory_correction()

    # def _convert_motor_pos_nom2act(self, motor_key, pos):
    #     if motor_key in self.converter_nom2act.keys():
    #         pos = self.converter_nom2act[motor_key].nom2act(pos)
    #     return pos
    #
    # def _convert_motor_pos_act2nom(self, motor_key, pos):
    #     if motor_key in self.converter_nom2act.keys():
    #         pos = self.converter_nom2act[motor_key].act2nom(pos)
    #     return pos

    def register_bragg(self, bragg_act, motor_pos_dict):
        pos_nom = {}
        for motor_key in motor_pos_dict.keys():
            print(motor_key)
            pos_nom[motor_key] = self.compute_motor_position(motor_key, bragg_act, nom2act=False)
        pos_act = {**motor_pos_dict}
        for motor_key in pos_act.keys():
            # self.converter_nom2act[motor_key].append_point(pos_nom[motor_key], pos_act[motor_key])
            self.config['bragg_registration']['bragg'][motor_key].append(bragg_act)
            self.config['bragg_registration']['pos_nom'][motor_key].append(pos_nom[motor_key])
            self.config['bragg_registration']['pos_act'][motor_key].append(pos_act[motor_key])

        self.compute_trajectory_correction()
        self.save_current_spectrometer_config_to_settings()

    # @property
    # def traj(self):
    #
    #     return self.traj_nom + self.traj_delta

    def register_energy(self, energy_act, motor_pos_dict):
        bragg_act = self.e2bragg(energy_act)
        self.register_bragg(bragg_act, motor_pos_dict)

    def reset_bragg_registration(self):
        self.config['bragg_registration'] = {'bragg' :  {k: [] for k in _johann_spectrometer_motor_keys},
                                             'pos_nom': {k: [] for k in _johann_spectrometer_motor_keys},
                                             'pos_act': {k: [] for k in _johann_spectrometer_motor_keys}}
        self.compute_trajectory_correction()
        # for motor_key in _johann_spectrometer_motor_keys:
        #     self.converter_nom2act[motor_key] = Nominal2ActualConverterWithLinearInterpolation()

    def plot_motor_pos_vs_bragg(self, motor_key, fignum=1):
        bragg = self.traj['bragg']
        pos = self.compute_motor_position(motor_key, bragg)
        plt.figure(fignum, clear=True)
        plt.plot(bragg, pos)

    def _compute_motor_position(self, motor_key, bragg, nom2act=True):
        if nom2act:
            pos = np.interp(bragg, self.traj['bragg'], self.traj[motor_key])
        else:
            pos = np.interp(bragg, self.traj_nom['bragg'], self.traj_nom[motor_key])

        if motor_key in self.config['parking'].keys():
            pos0 = self.config['parking'][motor_key]
        else:
            pos0 = 0
        pos += pos0
        return pos

    def compute_motor_position(self, motor_keys, bragg, nom2act=True):
        if type(motor_keys) == str:
            return self._compute_motor_position(motor_keys, bragg, nom2act=nom2act)
        else:
            output = {}
            for motor_key in motor_keys:
                output[motor_key] = self._compute_motor_position(motor_key, bragg, nom2act=nom2act)
            return output

    def compute_motor_position_from_energy(self, motor_keys, energy, nom2act=True, use_energy_calibration=True):
        if use_energy_calibration and (self.energy_converter is not None):
            energy = self.energy_converter.act2nom(energy)
        bragg = e2bragg(energy, self.crystal, self.hkl)
        return self.compute_motor_position(motor_keys, bragg, nom2act=nom2act)

    def compute_bragg_from_motor(self, motor_key, pos, nom2act=True):
        if motor_key in self.config['parking'].keys():
            pos0 = self.config['parking'][motor_key]
        else:
            pos0 = 0

        if nom2act:
            bragg = np.interp(pos - pos0, self.traj[motor_key], self.traj['bragg'])
        else:
            bragg = np.interp(pos - pos0, self.traj_nom[motor_key], self.traj_nom['bragg'])

        # if nom2act:
        #     pos = self.converter_nom2act[motor_key].act2nom(pos)
            # pos = self._convert_motor_pos_act2nom(motor_key, pos)

        # vs = self.traj[motor_key]
        # bs = self.traj['bragg']
        # bragg = np.interp(pos - pos0, vs[bs <= 90],  bs[bs <= 90])

        if bragg > 90:
            bragg = 180 - bragg
        return bragg

    def compute_energy_from_motor(self, motor_key, pos, nom2act=True, use_energy_calibration=True):
        bragg = self.compute_bragg_from_motor(motor_key, pos, nom2act=nom2act)
        energy = bragg2e(bragg, self.crystal, self.hkl)
        if use_energy_calibration and (self.energy_converter is not None):
            energy = self.energy_converter.nom2act(energy)
        return energy

    def compute_bragg_from_motor_dict(self, motor_pos_dict, nom2act=True):
        output = {}
        for motor_key, motor_pos in motor_pos_dict.items():
            output[motor_key] = self._compute_motor_position(motor_key, motor_pos, nom2act=nom2act)

    def e2bragg(self, energy):
        return e2bragg(energy, self.crystal, self.hkl)

    def bragg2e(self, bragg):
        return bragg2e(bragg, self.crystal, self.hkl)

    def e2reflectivity(self, energy):
        bragg = self.e2bragg(energy)
        return crystal_reflectivity(self.crystal, self.hkl, bragg, energy)

    def suggest_roll_offset(self, bragg_target, roll_range=5):
        offsets = np.array(self.allowed_roll_offsets)
        offset_braggs = 90 - offsets
        options = np.isclose(bragg_target, offset_braggs, atol=roll_range)
        return offsets[options][0]

    # def append_energy_converter(self, ec):
    #     self.energy_converter = ec

rowland_circle = RowlandCircle()

# def suggest_roll_offsets(bragg_target, roll_range=5):

# bragg_target = 85
# allowed_roll_offsets = [2.5, 11.5, 20.5]
# offsets = np.array(allowed_roll_offsets)
# offset_braggs = 90 - offsets
#
# print(offsets[options][0])

# rowland_circle.det_focus =
# rowland_circle.update_nominal_trajectory_for_detector(-8)
# johann_det_arm.position_dict
# johann_main_crystal.position_dict

# rowland_circle.plot_motor_pos_vs_bragg('motor_det_th1')
# ___nom = rc.compute_motor_position('motor_cr_assy_x', 85.0, nom2act=False)
# rc.register_bragg(85.1, {'motor_cr_assy_x' : ___nom})
#
# _bragg = np.linspace(65, 90, 101)
# _x_nom = rc.compute_motor_position('motor_cr_assy_x', _bragg, nom2act=False)
# _x_act = rc.compute_motor_position('motor_cr_assy_x', _bragg, nom2act=True)
#
# plt.figure(1, clear=True)
# plt.subplot(211)
# plt.plot(_bragg, _x_nom)
# plt.plot(_bragg, _x_act)
#
# plt.hlines(___nom, 65, 90, colors='k')
# plt.vlines(85.0, _x_nom.min(), _x_nom.max(), colors='k')
# plt.vlines(85.1, _x_nom.min(), _x_nom.max(), colors='k')
#
# plt.subplot(212)
# plt.plot(_bragg, _x_act - _x_nom)
#
#
# rc.compute_motor_position('motor_cr_assy_x', 85.0, nom2act=False) - rc.compute_motor_position('motor_cr_assy_x', 85.1, nom2act=False)
# rc.compute_motor_position('motor_cr_assy_x', 85.2, nom2act=False) - rc.compute_motor_position('motor_cr_assy_x', 85.1, nom2act=False)
#
# rc.compute_motor_position('motor_cr_assy_x', 85.0, nom2act=True) - rc.compute_motor_position('motor_cr_assy_x', 85.1, nom2act=True)
# rc.compute_motor_position('motor_cr_assy_x', 85.1, nom2act=True) - rc.compute_motor_position('motor_cr_assy_x', 85.2, nom2act=True)

from collections import namedtuple
class ISSPseudoPositioner(PseudoPositioner):

    def __init__(self, *args, **kwargs):
        self.pseudo_keys = [k for k, _ in self._get_pseudo_positioners()]
        self.real_keys = [k for k, _ in self._get_real_positioners()]
        self.motor_keys = self.pseudo_keys + self.real_keys
        super().__init__(*args, **kwargs)

    def pseudo_pos2dict(self, pseudo_pos):
        ret = {k: getattr(pseudo_pos, k) for k in self.pseudo_keys}
        for k in ret.keys():
            if ret[k] is None:
                try:
                    ret[k] = getattr(self, k).position
                except:
                    ttime.sleep(1)
                    ret[k] = getattr(self, k).position
        return ret

    def real_pos2dict(self, real_pos):
        ret = {k: getattr(real_pos, k) for k in self.real_keys}
        for k in ret.keys():
            if ret[k] is None:
                try:
                    ret[k] = getattr(self, k).position
                except:
                    ttime.sleep(1)
                    ret[k] = getattr(self, k).position
        return ret

    @pseudo_position_argument
    def forward(self, pseudo_pos):
        pseudo_dict = self.pseudo_pos2dict(pseudo_pos)
        real_dict = self._forward(pseudo_dict)
        return self.RealPosition(**real_dict)

    @real_position_argument
    def inverse(self, real_pos):
        real_dict = self.real_pos2dict(real_pos)
        pseudo_dict = self._inverse(real_dict)
        return self.PseudoPosition(**pseudo_dict)

    @property
    def position_dict(self):
        return self.pseudo_pos2dict(self.position)

    @property
    def real_position_dict(self):
        return self.real_pos2dict(self.real_position)


class JohannPseudoPositioner(ISSPseudoPositioner):
    rowland_circle = rowland_circle

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)


class JohannDetectorArm(JohannPseudoPositioner):
    motor_det_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:Y}Mtr')
    motor_det_th1 = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Det:Gon:Theta1}Mtr')  # give better names
    motor_det_th2 = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Det:Gon:Theta2}Mtr')

    bragg = Cpt(PseudoSingle, name='bragg')
    det_focus = Cpt(PseudoSingle, name='det_focus')

    _real = ['motor_det_x', 'motor_det_th1', 'motor_det_th2']
    _pseudo = ['bragg', 'det_focus']

    def _forward(self, pseudo_dict):
        bragg, det_focus = pseudo_dict['bragg'], pseudo_dict['det_focus']
        self.rowland_circle.update_nominal_trajectory_for_detector(det_focus)
        return self.rowland_circle.compute_motor_position(self.real_keys, bragg)

    def _inverse(self, real_dict):
        motor_det_th1 = real_dict['motor_det_th1']
        bragg = self.rowland_circle.compute_bragg_from_motor('motor_det_th1', motor_det_th1)
        det_focus = self.rowland_circle.det_focus
        return {'bragg': bragg, 'det_focus' : det_focus}


johann_det_arm = JohannDetectorArm(name='johann_detector_arm')



class JohannMainCrystal(JohannPseudoPositioner):

    motor_cr_assy_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:X}Mtr')
    motor_cr_assy_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Ana:Assy:Y}Mtr')
    motor_cr_main_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:1:Roll}Mtr')
    motor_cr_main_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:1:Yaw}Mtr')

    bragg = Cpt(PseudoSingle, name='bragg')

    _real = ['motor_cr_assy_x', 'motor_cr_assy_y', 'motor_cr_main_roll', 'motor_cr_main_yaw']
    _pseudo = ['bragg']

    def _forward(self, pseudo_dict):
        bragg = pseudo_dict['bragg']
        return self.rowland_circle.compute_motor_position(self.real_keys, bragg)

    def _inverse(self, real_dict):
        motor_cr_main_roll = real_dict['motor_cr_main_roll']
        bragg = self.rowland_circle.compute_bragg_from_motor('motor_cr_main_roll', motor_cr_main_roll)
        return {'bragg': bragg}

johann_main_crystal = JohannMainCrystal(name='johann_main_crystal')


class JohannAux2Crystal(JohannPseudoPositioner):
    motor_cr_assy_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:X}Mtr')
    motor_cr_assy_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Ana:Assy:Y}Mtr')
    motor_cr_aux2_x = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:X}Mtr')
    motor_cr_aux2_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Y}Mtr')
    motor_cr_aux2_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Roll}Mtr')
    motor_cr_aux2_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Yaw}Mtr')

    bragg = Cpt(PseudoSingle, name='bragg')
    _real = ['motor_cr_assy_x', 'motor_cr_assy_y',
             'motor_cr_aux2_x', 'motor_cr_aux2_y', 'motor_cr_aux2_roll', 'motor_cr_aux2_yaw']
    _pseudo = ['bragg']

    def _forward(self, pseudo_dict):
        bragg = pseudo_dict['bragg']
        return self.rowland_circle.compute_motor_position(self.real_keys, bragg)

    def _inverse(self, real_dict):
        motor_cr_aux2_roll = real_dict['motor_cr_aux2_roll']
        bragg = self.rowland_circle.compute_bragg_from_motor('motor_cr_aux2_roll', motor_cr_aux2_roll)
        return {'bragg': bragg}

johann_aux2_crystal = JohannAux2Crystal(name='johann_aux2_crystal')

class JohannAux3Crystal(JohannPseudoPositioner):
    motor_cr_assy_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:X}Mtr')
    motor_cr_assy_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Ana:Assy:Y}Mtr')
    motor_cr_aux3_x = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:X}Mtr')
    motor_cr_aux3_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Y}Mtr')
    motor_cr_aux3_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Roll}Mtr')
    motor_cr_aux3_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Yaw}Mtr')

    bragg = Cpt(PseudoSingle, name='bragg')
    _real = ['motor_cr_assy_x', 'motor_cr_assy_y',
             'motor_cr_aux3_x', 'motor_cr_aux3_y', 'motor_cr_aux3_roll', 'motor_cr_aux3_yaw']
    _pseudo = ['bragg']

    def _forward(self, pseudo_dict):
        bragg = pseudo_dict['bragg']
        return self.rowland_circle.compute_motor_position(self.real_keys, bragg)

    def _inverse(self, real_dict):
        motor_cr_aux3_roll = real_dict['motor_cr_aux3_roll']
        bragg = self.rowland_circle.compute_bragg_from_motor('motor_cr_aux3_roll', motor_cr_aux3_roll)
        return {'bragg': bragg}

johann_aux3_crystal = JohannAux3Crystal(name='johann_aux3_crystal')


class JohannSpectrometerX(JohannPseudoPositioner):
    motor_det_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:Y}Mtr')
    motor_cr_assy_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:X}Mtr')

    x = Cpt(PseudoSingle, name='x')

    _real = ['motor_det_x', 'motor_cr_assy_x']
    _pseudo = ['x']

    aligned = True

    def _compute_pos_nom(self):
        # instead of real keys we use hard-coded keys for the motors !
        bragg_det_arm = johann_det_arm.bragg.position
        pos_nom_det_arm = self.rowland_circle.compute_motor_position(['motor_det_x'], bragg_det_arm, nom2act=True)

        bragg_cr_main = johann_main_crystal.bragg.position
        pos_nom_cr_main = self.rowland_circle.compute_motor_position(['motor_cr_assy_x'], bragg_cr_main, nom2act=True)

        return {**pos_nom_det_arm, **pos_nom_cr_main}


    def _forward(self, pseudo_dict):
        x = pseudo_dict['x']
        # bragg = johann_spectrometer.bragg.position
        # pos_nom = self.rowland_circle.compute_motor_position(self.real_keys, bragg, nom2act=False)
        pos_nom = self._compute_pos_nom()
        pos_act = {}
        for key in pos_nom.keys():
            pos_act[key] = pos_nom[key] + x
        return pos_act

    def _inverse(self, pos_act):
        # bragg = johann_spectrometer.bragg.position
        # pos_nom = self.rowland_circle.compute_motor_position(self.real_keys, bragg, nom2act=False)
        pos_nom = self._compute_pos_nom()
        x = [(pos_act[k] - pos_nom[k]) for k in self.real_keys]
        self.aligned = np.all(np.isclose(x, x[0], atol=5e-3))
        return {'x' : np.mean(x)}

johann_spectrometer_x = JohannSpectrometerX(name='johann_spectrometer_x')


class JohannCrystalHoming(Device):
    cr_main_roll_home = Cpt(EpicsSignal, '1:Roll}Mtr.HOMF')
    cr_main_yaw_home = Cpt(EpicsSignal, '1:Yaw}Mtr.HOMF')

    cr_aux2_roll_home = Cpt(EpicsSignal, '2:Roll}Mtr.HOMF')
    cr_aux2_yaw_home = Cpt(EpicsSignal, '2:Yaw}Mtr.HOMF')
    cr_aux2_x_home = Cpt(EpicsSignal, '2:X}Mtr.HOMF')
    cr_aux2_y_home = Cpt(EpicsSignal, '2:Y}Mtr.HOMF')

    cr_aux3_roll_home = Cpt(EpicsSignal, '3:Roll}Mtr.HOMF')
    cr_aux3_yaw_home = Cpt(EpicsSignal, '3:Yaw}Mtr.HOMF')
    cr_aux3_x_home = Cpt(EpicsSignal, '3:X}Mtr.HOMF')
    cr_aux3_y_home = Cpt(EpicsSignal, '3:Y}Mtr.HOMF')

    def home_all_axes(self):
        for component in self.component_names:
            cpt = getattr(self, component)
            cpt.put(1)


class JohannMultiCrystalPseudoPositioner(JohannPseudoPositioner):
    _real = _johann_spectrometer_motor_keys
        # ['motor_det_x', 'motor_det_th1', 'motor_det_th2',
        #      'motor_cr_assy_x', 'motor_cr_assy_y', 'motor_cr_main_roll', 'motor_cr_main_yaw',  # ]
        #      'motor_cr_aux2_x', 'motor_cr_aux2_y', 'motor_cr_aux2_roll', 'motor_cr_aux2_yaw',
        #      'motor_cr_aux3_x', 'motor_cr_aux3_y', 'motor_cr_aux3_roll', 'motor_cr_aux3_yaw']

    aligned = True
    piezo_homing = Cpt(JohannCrystalHoming, 'XF:08IDB-OP{HRS:1-Stk:')

    @property
    def initialized(self):
        return self.rowland_circle.initialized

    @initialized.setter
    def initialized(self, value):
        self.rowland_circle.initialized = value

    def __init__(self, *args, **kwargs):
        self.enabled_crystals = self.rowland_circle.enabled_crystals
        super().__init__(*args, **kwargs)

    def enable_crystal(self, crystal_key, enable):
        self.rowland_circle.enable_crystal(crystal_key, enable)

    @property
    def motor_to_bragg_keys(self):
        keys = ['motor_det_th1']
        if self.enabled_crystals['main']: keys.append('motor_cr_main_roll')
        if self.enabled_crystals['aux2']: keys.append('motor_cr_aux2_roll')
        if self.enabled_crystals['aux3']: keys.append('motor_cr_aux3_roll')
        return keys

    def _compute_new_real_positions_for_enabled_crystals(self, bragg):
        new_real_position = self.rowland_circle.compute_motor_position(self.real_keys, bragg)
        for crystal_key, enabled in self.enabled_crystals.items():
            if not enabled: # then find keys that must be static during the motion of enabled crystals
                if crystal_key == 'main':
                    _motor_keys = _johann_cr_main_motor_keys
                elif crystal_key == 'aux2':
                    _motor_keys = _johann_cr_aux2_motor_keys
                elif crystal_key == 'aux3':
                    _motor_keys = _johann_cr_aux3_motor_keys
                else:
                    raise ValueError('this crystal key is not implemented yet')
                for k in _motor_keys:
                    new_real_position[k] = getattr(self, k).position
        return new_real_position

    def _compute_braggs_from_motors(self, real_dict):
        braggs = []
        for key in self.motor_to_bragg_keys:
            pos = real_dict[key]
            bragg = self.rowland_circle.compute_bragg_from_motor(key, pos)
            braggs.append(bragg)

        self.aligned = np.all(np.isclose(braggs, braggs[0], atol=1e-3))
        return braggs

    def home_crystal_piezos(self):
        self.piezo_homing.home_all_axes()


class JohannAllCrystals(JohannMultiCrystalPseudoPositioner):
    _real = _johann_cr_all_motor_keys
    motor_cr_assy_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:X}Mtr')
    motor_cr_assy_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Ana:Assy:Y}Mtr')
    motor_cr_main_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:1:Roll}Mtr')
    motor_cr_main_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:1:Yaw}Mtr')

    motor_cr_aux2_x = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:X}Mtr')
    motor_cr_aux2_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Y}Mtr')
    motor_cr_aux2_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Roll}Mtr')
    motor_cr_aux2_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Yaw}Mtr')

    motor_cr_aux3_x = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:X}Mtr')
    motor_cr_aux3_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Y}Mtr')
    motor_cr_aux3_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Roll}Mtr')
    motor_cr_aux3_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Yaw}Mtr')

    bragg = Cpt(PseudoSingle, name='bragg')

    _pseudo = ['bragg']

    @property
    def motor_to_bragg_keys(self):
        keys = []
        if self.enabled_crystals['main']: keys.append('motor_cr_main_roll')
        if self.enabled_crystals['aux2']: keys.append('motor_cr_aux2_roll')
        if self.enabled_crystals['aux3']: keys.append('motor_cr_aux3_roll')
        return keys

    def _forward(self, pseudo_dict):
        bragg = pseudo_dict['bragg']
        new_real_positions = self._compute_new_real_positions_for_enabled_crystals(bragg)
        return new_real_positions

    def _inverse(self, real_dict):
        braggs = self._compute_braggs_from_motors(real_dict)
        return {'bragg': np.mean(braggs)}

johann_all_crystals = JohannAllCrystals(name='johann_all_crystals')

class JohannSpectrometer(JohannMultiCrystalPseudoPositioner):
    motor_det_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:Y}Mtr')
    motor_det_th1 = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Det:Gon:Theta1}Mtr')  # give better names
    motor_det_th2 = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Det:Gon:Theta2}Mtr')

    motor_cr_assy_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:X}Mtr')
    motor_cr_assy_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Ana:Assy:Y}Mtr')
    motor_cr_main_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:1:Roll}Mtr')
    motor_cr_main_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:1:Yaw}Mtr')

    motor_cr_aux2_x = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:X}Mtr')
    motor_cr_aux2_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Y}Mtr')
    motor_cr_aux2_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Roll}Mtr')
    motor_cr_aux2_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Yaw}Mtr')

    motor_cr_aux3_x = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:X}Mtr')
    motor_cr_aux3_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Y}Mtr')
    motor_cr_aux3_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Roll}Mtr')
    motor_cr_aux3_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Yaw}Mtr')

    bragg = Cpt(PseudoSingle, name='bragg')

    _pseudo = ['bragg']

    def _forward(self, pseudo_dict):
        bragg = pseudo_dict['bragg']
        new_real_positions = self._compute_new_real_positions_for_enabled_crystals(bragg)
        return new_real_positions

    def _inverse(self, real_dict):
        braggs = self._compute_braggs_from_motors(real_dict)
        return {'bragg': np.mean(braggs)}

johann_spectrometer = JohannSpectrometer(name='johann_spectrometer')

class JohannEmission(JohannMultiCrystalPseudoPositioner):
    motor_det_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:Y}Mtr')
    motor_det_th1 = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Det:Gon:Theta1}Mtr')  # give better names
    motor_det_th2 = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Det:Gon:Theta2}Mtr')

    motor_cr_assy_x = Cpt(EpicsMotor, 'XF:08IDB-OP{Stage:Aux1-Ax:X}Mtr')
    motor_cr_assy_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Ana:Assy:Y}Mtr')
    motor_cr_main_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:1:Roll}Mtr')
    motor_cr_main_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:1:Yaw}Mtr')

    motor_cr_aux2_x = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:X}Mtr')
    motor_cr_aux2_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Y}Mtr')
    motor_cr_aux2_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Roll}Mtr')
    motor_cr_aux2_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:2:Yaw}Mtr')

    motor_cr_aux3_x = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:X}Mtr')
    motor_cr_aux3_y = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Y}Mtr')
    motor_cr_aux3_roll = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Roll}Mtr')
    motor_cr_aux3_yaw = Cpt(EpicsMotor, 'XF:08IDB-OP{HRS:1-Stk:3:Yaw}Mtr')

    energy = Cpt(PseudoSingle, name='energy')
    _pseudo = ['energy']


    def _forward(self, pseudo_dict):
        energy = pseudo_dict['energy']
        bragg = self.rowland_circle.e2bragg(energy)
        new_real_positions = self._compute_new_real_positions_for_enabled_crystals(bragg)
        return new_real_positions

    def _inverse(self, real_dict):
        braggs = self._compute_braggs_from_motors(real_dict)
        bragg = np.mean(braggs)
        energy = self.rowland_circle.bragg2e(bragg)
        return {'energy': np.mean(energy)}

    # ops functions

    def move_crystals_to_90_deg(self):
        self.set_roll_offset(2.5)
        johann_main_crystal.move(bragg=90)
        johann_aux2_crystal.move(bragg=90)
        johann_aux3_crystal.move(bragg=90)

    def set_det_arm_parking(self):
        self.rowland_circle.set_det_arm_parking(self.real_position_dict)

    def read_det_arm_parking(self):
        return self.rowland_circle.det_arm_parking()

    def set_main_crystal_parking(self):
        self.rowland_circle.set_main_crystal_parking(self.real_position_dict)

    def read_main_crystal_parking(self):
        return self.rowland_circle.main_crystal_parking(human_readable=True)

    def set_aux2_crystal_parking(self):
        self.rowland_circle.set_aux2_crystal_parking(self.real_position_dict)

    def read_aux2_crystal_parking(self):
        return self.rowland_circle.aux2_crystal_parking(human_readable=True)

    def set_aux3_crystal_parking(self):
        self.rowland_circle.set_aux3_crystal_parking(self.real_position_dict)

    def read_aux3_crystal_parking(self):
        return self.rowland_circle.aux3_crystal_parking(human_readable=True)

    def register_energy(self, energy):
        self.rowland_circle.register_energy(energy, self.real_position_dict)

    def reset_config(self):
        self.rowland_circle.reset_bragg_registration()
        self.rowland_circle.reset_spectrometer_calibration()

    def put_detector_to_safe_position(self):
        self.motor_det_x.move(335)
        self.motor_det_th1.move(0)
        self.motor_det_th2.move(0)

    def set_spectrometer_calibration(self, x_nom, x_act, n_poly=2):
        self.rowland_circle.set_spectrometer_calibration(x_nom, x_act, n_poly=n_poly)

    def set_energy_limits(self, e_lo, e_hi):
        self.energy._limits = (e_lo, e_hi)

    def set_crystal(self, value):
        self.rowland_circle.crystal = value

    def set_hkl(self, value):
        self.rowland_circle.hkl = value

    def set_R(self, value):
        self.rowland_circle.R = value

    def set_roll_offset(self, value):
        self.rowland_circle.roll_offset = value

    @property
    def allowed_roll_offsets(self):
        return self.rowland_circle.allowed_roll_offsets

    def suggest_roll_offset(self, target_bragg):
        return self.rowland_circle.suggest_roll_offset(target_bragg)

    def bragg2e(self, bragg):
        return self.rowland_circle.bragg2e(bragg)

    def e2bragg(self, energy):
        return self.rowland_circle.e2bragg(energy)

    def e2reflectivity(self, energy):
        return self.rowland_circle.e2reflectivity(energy)

    # def move(self, position, step_size=0.5, **kwargs):
    #     old_position = self.energy.position
    #     n_steps = int(np.abs(position - old_position) / step_size + 1)
    #     _positions = np.linspace(old_position, position, n_steps)[1:]
    #     if _positions.size == 0:
    #         ret = NullStatus()
    #     else:
    #         for _pos in _positions:
    #             print_to_gui(f'Spectrometer moving to {_pos}')
    #             ret = super().move(_pos, **kwargs)
    #     return ret
    #
    # def set(self, *args, wait=True, **kwargs):
    #     return super().set(*args, wait=wait, **kwargs)

johann_emission = JohannEmission(name='johann_emission')


# johann_emission.energy._limits=(8004, 8068)


# _johann_motor_dictionary = {
# 'auxxy_x':                  {'name': auxxy.x.name,                                     'description': 'Johann Crystal Assy X',        'object': auxxy.x,                                  'keyword': 'Crystal Assy X',       'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 2.5},
# 'auxxy_y':                  {'name': auxxy.y.name,                                     'description': 'Johann Detector X',            'object': auxxy.y,                                  'keyword': 'Detector X',           'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 2.5},
# 'johann_cr_main_roll':      {'name': johann_main_crystal.motor_cr_main_roll.name,      'description': 'Johann Main Crystal Roll',     'object': johann_main_crystal.motor_cr_main_roll,   'keyword': 'Main Crystal Roll',    'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 100},
# 'johann_cr_main_yaw':       {'name': johann_main_crystal.motor_cr_main_yaw.name,       'description': 'Johann Main Crystal Yaw',      'object': johann_main_crystal.motor_cr_main_yaw,    'keyword': 'Main Crystal Yaw',     'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 50},
# 'johann_cr_aux2_roll':      {'name': johann_aux2_crystal.motor_cr_aux2_roll.name,      'description': 'Johann Aux2 Crystal Roll',     'object': johann_aux2_crystal.motor_cr_aux2_roll,   'keyword': 'Aux2 Crystal Roll',    'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 100},
# 'johann_cr_aux2_yaw':       {'name': johann_aux2_crystal.motor_cr_aux2_yaw.name,       'description': 'Johann Aux2 Crystal Yaw',      'object': johann_aux2_crystal.motor_cr_aux2_yaw,    'keyword': 'Aux2 Crystal Yaw',     'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 50},
# 'johann_cr_aux2_x':         {'name': johann_aux2_crystal.motor_cr_aux2_x.name,         'description': 'Johann Aux2 Crystal X',        'object': johann_aux2_crystal.motor_cr_aux2_x,      'keyword': 'Aux2 Crystal X',       'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 2500},
# 'johann_cr_aux2_y':         {'name': johann_aux2_crystal.motor_cr_aux2_y.name,         'description': 'Johann Aux2 Crystal Y',        'object': johann_aux2_crystal.motor_cr_aux2_y,      'keyword': 'Aux2 Crystal Y',       'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 1000},
# 'johann_cr_aux3_roll':      {'name': johann_aux3_crystal.motor_cr_aux3_roll.name,      'description': 'Johann Aux3 Crystal roll',     'object': johann_aux3_crystal.motor_cr_aux3_roll,   'keyword': 'Aux3 Crystal roll',    'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 100},
# 'johann_cr_aux3_yaw':       {'name': johann_aux3_crystal.motor_cr_aux3_yaw.name,       'description': 'Johann Aux3 Crystal Yaw',      'object': johann_aux3_crystal.motor_cr_aux3_yaw,    'keyword': 'Aux3 Crystal Yaw',     'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 50},
# 'johann_cr_aux3_x':         {'name': johann_aux3_crystal.motor_cr_aux3_x.name,         'description': 'Johann Aux3 Crystal X',        'object': johann_aux3_crystal.motor_cr_aux3_x,      'keyword': 'Aux3 Crystal X',       'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 2500},
# 'johann_cr_aux3_y':         {'name': johann_aux3_crystal.motor_cr_aux3_y.name,         'description': 'Johann Aux3 Crystal Y',        'object': johann_aux3_crystal.motor_cr_aux3_y,      'keyword': 'Aux3 Crystal Y',       'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 1000},
# 'johann_cr_main_bragg':     {'name': johann_main_crystal.bragg.name,                   'description': 'Johann Main Crystal Bragg',    'object': johann_main_crystal.bragg,                'keyword': 'Main Crystal Bragg',   'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 0.05},
# 'johann_cr_aux2_bragg':     {'name': johann_aux2_crystal.bragg.name,                   'description': 'Johann Aux2 Crystal Bragg',    'object': johann_aux2_crystal.bragg,                'keyword': 'Aux2 Crystal Bragg',   'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 0.05},
# 'johann_cr_aux3_bragg':     {'name': johann_aux3_crystal.bragg.name,                   'description': 'Johann Aux3 Crystal Bragg',    'object': johann_aux3_crystal.bragg,                'keyword': 'Aux3 Crystal Bragg',   'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 0.05},
# 'johann_det_focus':         {'name': johann_det_arm.det_focus.name,                    'description': 'Johann Detector Focus',        'object': johann_det_arm.det_focus,                 'keyword': 'Detector Focus',       'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 5},
# 'johann_x':                 {'name': johann_spectrometer_x.x.name,                     'description': 'Johann Spectrometer X',        'object': johann_spectrometer_x.x,                  'keyword': 'Spectrometer X',       'group': 'spectrometer',  'user': False, 'spectrometer_kind': 'johann', 'typical_step': 2.5},
# 'johann_bragg_angle':       {'name': johann_spectrometer.bragg.name,                   'description': 'Johann Global Bragg Angle',    'object': johann_spectrometer.bragg,                'keyword': 'Global Bragg Angle',   'group': 'spectrometer',  'user': True,  'spectrometer_kind': 'johann', 'typical_step': 0.05},
# 'johann_energy':            {'name': johann_emission.energy.name,                      'description': 'Johann Emission Energy',       'object': johann_emission.energy,                   'keyword': 'Emission Energy',      'group': 'spectrometer',  'user': True,  'spectrometer_kind': 'johann', 'typical_step': 1},
# }
#
# motor_dictionary = {**motor_dictionary, **_johann_motor_dictionary}


centroid_y = EpicsSignal('XF:08IDB-BI{BPM:SP-2}Stats1:CentroidY_RBV', name='centroid_y')
intensity = EpicsSignal('XF:08IDB-BI{BPM:SP-2}Stats1:Total_RBV', name='intensity')

centroid_y_data = {'value': [], 'timestamp': []}
intensity_data =  {'value': [], 'timestamp': []}

def cb_add_data(value, **kwargs):
    # print_to_gui(f"{value = }", add_timestamp=True)
    if len(centroid_y_data) >=10000:
        centroid_y_data['value'].pop(0)
        centroid_y_data['timestamp'].pop(0)
    centroid_y_data['value'].append(value)
    centroid_y_data['timestamp'].append(kwargs['timestamp'])

centroid_y.subscribe(cb_add_data)

def cb_add_data_int(value, **kwargs):
    # print_to_gui(f"{value = }", add_timestamp=True)
    if len(intensity_data) >=10000:
        intensity_data['value'].pop(0)
        intensity_data['timestamp'].pop(0)
    intensity_data['value'].append(value)
    intensity_data['timestamp'].append(kwargs['timestamp'])

intensity.subscribe(cb_add_data_int)


def get_fft(t, s):
    freq = np.fft.fftfreq(t.size, d=t[1] - t[0])
    s_fft = np.abs(np.fft.fft(s))[np.argsort(freq)]
    freq = freq[np.argsort(freq)]
    return freq[freq>0], s_fft[freq>0]

def plot_fft(t, s, *args, **kwargs):
    f, s_fft = get_fft(np.array(t), np.array(s))
    plt.plot(f, s_fft, *args, **kwargs)

def plot_trace_info(data_dict, fignum=1, clear=True):
    t = np.linspace(data_dict['timestamp'][0], data_dict['timestamp'][-1], len(data_dict['timestamp']))
    v = np.interp(t, data_dict['timestamp'], data_dict['value'])

    # t = np.linspace(intensity_data['timestamp'][0], intensity_data['timestamp'][-1], len(intensity_data['timestamp']))
    # v = np.interp(t, intensity_data['timestamp'], intensity_data['value'])

    freq, centroid_fft = get_fft(t, v)
    # freq = np.fft.fftfreq(v.size, d=t[1] - t[0])
    # centroid_fft = np.abs(np.fft.fft(v))[np.argsort(freq)]
    # freq = freq[np.argsort(freq)]

    plt.figure(fignum, clear=clear)
    plt.subplot(221)
    plt.plot(data_dict['timestamp'], data_dict['value'] - np.mean(data_dict['value']))

    plt.subplot(222)
    plt.hist(data_dict['value'] - np.mean(data_dict['value']), 100, density=True);

    plt.subplot(223)
    plt.semilogy(freq, centroid_fft)
    plt.xlim(0.1, 15)
    # plt.ylim(1e2, 1e6)
# plt.semilogy(centroid_fft)


plot_trace_info(centroid_y_data, )
plot_trace_info(intensity_data, fignum=2)

centroid_y_data_85_3 = copy.deepcopy(centroid_y_data)
intensity_data_85_3 = copy.deepcopy(intensity_data)

plot_trace_info(centroid_y_data_85, clear=True, fignum=1)
plot_trace_info(centroid_y_data_65, clear=False, fignum=1)

plot_trace_info(intensity_data_85, fignum=2)

plot_trace_info(centroid_y_data_85_2, clear=True, fignum=1)
plot_trace_info(centroid_y_data_85_3, clear=False, fignum=1)

plot_trace_info(intensity_data_85_2, clear=True, fignum=2)
plot_trace_info(intensity_data_85_3, clear=False, fignum=2)


apb_ave.set_exposure_time(10)
RE(bp.count([apb_ave]))

t = db[-1].table()

# gain was set to 5
t_all_connected_no_scope = db['af703640-8980-4dcd-9545-4c8f0fce4046'].table()
t_all_connected_no_scope_ir_it = db['4d156431-bb99-47e0-af71-c1f1b8b3c0ec'].table()

t_no_amplifier_no_scope = db['ced4d069-6d30-443f-913c-704afa08b5a2'].table()
t_all_conneced_no_scope_with_dominik = db['1c8eaaf9-8d6a-4b86-8255-8559be5d9591'].table()

t_all_connected_no_scope_manual_gain = db['abc456fc-2014-4fab-b55c-6420c7a11e79'].table()
t_all_connected_no_scope_manual_gain_10MHz = db['676abda3-cb15-4612-a6a7-3c88d3be874e'].table()
t_all_connected_no_scope_manual_gain_FB = db['d44ce8d5-0fb3-4af6-985e-346dc98c3d93'].table()
t_all_connected_no_scope_direct_cable = db['aa5c3275-e63f-453a-847d-3d54cce0b015'].table()
t_all_connected_no_scope_direct_cable_with_grounding = db['6869fdc4-1fc9-4057-88ed-53c636bfed4a'].table()

# t_all_connected_no_scope_direct_cable_keithley = db['e0e2ef0e-796a-49d3-aad4-f8929762fe12'].table()
t_all_connected_no_scope_direct_cable_keithley = db['0d265f78-2950-4035-a5b8-60a148af1f19'].table()

t_all_connected_no_scope_direct_cable_ir_held_in_air = db['51f7ed41-e51d-4a5c-a45f-6f1db556ddd1'].table()

t_hv_on = db['62165c00-4b05-4883-850c-fa1510fcad8d'].table()
t_i0_hv_off = db['ae9987b5-7abf-4802-bf72-9067047480ea'].table()
t_all_hv_off = db['964d21f1-0d25-4ffa-91f7-10bd2c5e29b8'].table()

t_apb_only = db['a363016d-8f62-475b-b95c-20ac01172f91'].table()

def _plot_traces(_time, _v, *args, **kwargs):
    plt.subplot(221)
    plt.plot(_time, _v - np.mean(_v), *args, **kwargs)

    plt.subplot(222)
    plt.hist(_v - np.mean(_v), 50, alpha=0.5);

    plt.subplot(223)
    plot_fft(_time, _v, *args, **kwargs)

def plot_traces(t, *args, ch=1, **kwargs):
    _time = np.array(t[f'apb_ave_time_wf'][1])
    _v = np.array(t[f'apb_ave_ch{ch}_wf'][1])
    _plot_traces(_time, _v, *args, **kwargs)


plt.figure()
# plot_traces(t_hv_on, label='HV ON')
# plot_traces(t_i0_hv_off, label='I0 HV OFF')
# plot_traces(t_all_hv_off, label='ALL HV OFF')
plot_traces(t_apb_only, ch=1, label='APB only I0')
plot_traces(t_apb_only, ch=2, label='APB only It')
# plot_traces(t_apb_only, ch=3, label='APB only Ir')
# plot_traces(t_apb_only, ch=4, label='APB only If')



plt.legend()
plt.yscale('log')


bla1 = np.array(t_hv_on['apb_ave_ch1_wf'][1])
bla2 = np.array(t_hv_on['apb_ave_ch2_wf'][1])
bla3 = np.array(t_hv_on['apb_ave_ch3_wf'][1])
bla4 = np.array(t_hv_on['apb_ave_ch4_wf'][1])

bla = np.vstack((bla1, bla2, bla3, bla4))

plt.figure()
plt.plot(bla2, bla3, 'k.')
plt.axis('square')

plt.figure()
plt.imshow(np.corrcoef(bla))
# plot_traces(t_all_connected_no_scope, label='no scope')
# plot_traces(t_all_connected_no_scope_direct_cable, label='FEMTO direct cable no scope')
# plot_traces(t_all_connected_no_scope_direct_cable_keithley, label='KEITHLEY direct cable no scope')

# plot_traces(t_all_connected_no_scope_direct_cable_with_grounding, label='direct cable and grounding no scope')

# plot_traces(t_all_conneced_no_scope_with_dominik, label='dominik no scope')
# plot_traces(t_all_connected_no_scope_manual_gain, label='1 MHzmanual gain no scope')
# plot_traces(t_all_connected_no_scope_manual_gain_10MHz, label='10 Mhz manual gain no scope')
# plot_traces(t_all_connected_no_scope_manual_gain_FB, label='FB manual gain no scope')
plot_traces(t_no_amplifier_no_scope, label='no amplifier no scope')

plt.legend()
plt.yscale('log')



plt.figure()
plot_traces(t_all_connected_no_scope_ir_it, label='no scope IR', ch=3)
plot_traces(t_all_connected_no_scope_direct_cable_ir_held_in_air, label='no scope IR in air', ch=3)

# plot_traces(t_all_connected_no_scope_ir_it, label='with scope Ir', ch=2)
# plot_traces(t_all_connected_no_scope_ir_it, label='with scope It', ch=3)
# plot_traces(t_all_connected_no_scope_ir_it, label='no scope Ir', ch=3)
# plot_traces(t_all_conneced_no_scope_with_dominik, label='dominik no scope')
# plot_traces(t_all_connected_no_scope_manual_gain, label='manual gain no scope')
# plot_traces(t_all_connected_no_scope_manual_gain_10MHz, label='10 Mhz no scope')
# plot_traces(t_all_connected_no_scope_manual_gain_FB, label='FB no scope')
# plot_traces(t_no_amplifier_no_scope, label='no amplifier no scope')

plt.figure()
_plot_traces(t_all_connected_no_scope[f'apb_ave_time_wf'][1],
             np.array(t_all_connected_no_scope['apb_ave_ch2_wf'][1]) / np.array(t_all_connected_no_scope['apb_ave_ch1_wf'][1]))



RE(bp.count([apb_ave]))


t_85 = db['668a4f77-567e-4516-ba8e-a861740298ae'].table()
t_65 = db['d69716cf-454b-4f9d-b567-d5f9ea18b6be'].table()

# no expansion tank
t_85_2 = db['d8828258-96d6-4b0e-96d1-da68c099afb7'].table()

# with expansion tank
t_85_3 = db['b33a284e-a12f-4762-a57d-9a280e874b0f'].table()

t_5000 = db['280aec42-a42c-44fd-9862-bbc3f7339d65'].table()

t_2021 = db_archive['65eb5b76-4598-43f0-bde0-233df7a3a5db'].table()

plt.figure()
# plt.plot(t_2021.apb_ave_time_wf[1], np.array(t_2021.apb_ave_ch1_wf[1])/ 1560 * 930)
# plt.plot(t_5000.apb_ave_time_wf[1], t_5000.apb_ave_ch1_wf[1])
# plt.plot(t_85.apb_ave_time_wf[1], t_85.apb_ave_ch1_wf[1])
# plt.plot(t_65.apb_ave_time_wf[1], t_65.apb_ave_ch1_wf[1])

# plot_traces(t_85, label='85 Hz')
plot_traces(t_85_2, label='85 Hz no expansion tank')
plot_traces(t_85_3, label='85 Hz with expansion tank')
# plot_traces(t_65, label='65 Hz')
plt.legend()
plt.yscale('log')

# plt.hist(t_2021.apb_ave_ch1_wf[1]/np.mean(t_2021.apb_ave_ch1_wf[1]), 100, density=True, alpha=0.5);
# plt.hist(t_85.apb_ave_ch1_wf[1]/np.mean(t_85.apb_ave_ch1_wf[1]), 100, density=True, alpha=0.5);
# plt.xlabel('intensity')
# plt.ylabel('')

hdr = db[-1]
_t = hdr.table(stream_name='apb_stream', fill=True)['apb_stream'][1]
t_apb = hdr.table(stream_name='apb_stream', fill=True)['apb_stream'][1]
# _t = hdr.table(stream_name='pb9_enc1', fill=True)['pb9_enc1'][1]
# t_enc = hdr.table(stream_name='pb9_enc1', fill=True)['pb9_enc1'][1]

# plt.figure(); plt.plot(t_enc[:, 0] + t_enc[:, 1]*1e-9, t_enc[:, 2])
plt.plot(t_apb[:, 0], t_apb[:, 1])



img = bpm_es.get_image_array_data_reshaped()





