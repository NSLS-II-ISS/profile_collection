import pandas as pd
from xas.spectrometer import Crystal, analyze_many_elastic_scans
import copy



from ophyd import (PseudoPositioner, PseudoSingle)
from ophyd.pseudopos import (pseudo_position_argument,
                             real_position_argument)


def move_crystal_plan(x, y):
    yield from bps.mv(auxxy.x, x)
    yield from bps.mv(auxxy.y, y)



class EmissionEnergyMotor(PseudoPositioner):
    energy = Cpt(PseudoSingle, name='emission_energy')
    motor_crystal_x = auxxy.x
    motor_crystal_y = auxxy.y
    motor_detector_y = huber_stage.z
    _real = ['motor_crystal_x',
             'motor_crystal_y',
             'motor_detector_y']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.energy0 = None
        self.cr_x0 = None
        self.cr_x0=None
        self.cr_y0=None
        self.det_y0=None
        self.spectrometer_root_path = f"{ROOT_PATH}/{USER_PATH}"

        # ROOT_PATH = '/nsls2/data/iss/legacy'
        #
        # RAW_PATH = 'raw'
        # USER_PATH = 'processed'

        self._initialized = False


    def define_motor_coordinates(self, energy0, R, kind, hkl,
                                  cr_x0=None, cr_y0=None, det_y0=None,
                 energy_limits=None):

        self.energy0 = energy0
        if cr_x0 is None:
            self.cr_x0 = self.motor_crystal_x.user_readback.get()
        else:
            self.cr_x0 = cr_x0
        if cr_y0 is None:
            self.cr_y0 = self.motor_crystal_y.user_readback.get()
        else:
            self.cr_y0 = cr_y0
        if det_y0 is None:
            self.det_y0 = self.motor_detector_y.user_readback.get()
        else:
            self.det_y0 = det_y0
        self.crystal = Crystal(R, 50, hkl, kind)
        self.crystal.place_E(energy0)
        self.cr_x0_nom = copy.copy(self.crystal.x)
        self.cry_0_nom = copy.copy(self.crystal.y)
        self.det_y0_nom = copy.copy(self.crystal.d_y)

        if energy_limits is not None:
            condition = ((type(energy_limits) == tuple) and (len(energy_limits)==2))
            assert condition, 'Invalid limits for emission energy motor'
            self.energy._limits = energy_limits
        self.energy_converter = None
        self._initialized = True

    def append_energy_converter(self, ec):
        self.energy_converter = ec

    @pseudo_position_argument
    def forward(self, energy_input_object):
        energy = energy_input_object.energy
        if self.energy_converter is not None:
            energy = self.energy_converter.act2nom(energy)
        self.crystal.place_E(energy)
        dcr_x = self.crystal.x - self.cr_x0_nom
        dcr_y = self.crystal.y - self.cry_0_nom
        ddet_y = self.crystal.d_y - self.det_y0_nom

        position_detector_y = self.det_y0 - ddet_y
        position_crystal_y = self.cr_y0 + dcr_y
        position_crystal_x = self.cr_x0 - dcr_x

        return self.RealPosition(motor_detector_y = position_detector_y,
                                 motor_crystal_y = position_crystal_y,
                                 motor_crystal_x = position_crystal_x)

    @real_position_argument
    def inverse(self, real_pos):
        x = self.cr_x0 + self.cr_x0_nom  - real_pos.motor_crystal_x
        y = self.cry_0_nom - self.cr_y0 + real_pos.motor_crystal_y
        d_y = self.det_y0 + self.det_y0_nom - real_pos.motor_detector_y
        energy = self.crystal.compute_energy_from_positions(x, y, d_y)
        if self.energy_converter is not None:
            energy = self.energy_converter.nom2act(energy)
        return [energy]


motor_emission = EmissionEnergyMotor(name='motor_emission')

motor_emission_key = 'motor_emission'
motor_emission_dict = {'name': motor_emission.name, 'description' : 'Emission energy', 'object': motor_emission, 'group': 'spectrometer'}
motor_dictionary['motor_emission'] = motor_emission_dict



class SamplePointRegistry:
    position_list = pd.DataFrame(columns=['x', 'y', 'z', 'exposed', 'uid'])
    sample_x = giantxy.x
    sample_y = giantxy.y
    sample_z = usermotor2.pos
    current_index = None
    xyz1 = None
    xyz2 = None
    root_path = f"{ROOT_PATH}/{USER_PATH}"
    _dumpfile = None
    npoints = None

    def __init__(self):
        pass

    def initialize(self, x1, y1, z1, x2, y2, z2, step=0.2):
        self.reset()
        self.xyz1 = [x1, y1, z1]
        self.xyz2 = [x2, y2, z2]

        f = np.cos(np.deg2rad(45))
        _xs = np.arange(x1, x2 + step/f, step / f * np.sign(x2 - x1))
        _ys = np.arange(y1, y2 + step, step * np.sign(y2 - y1))
        npt = _xs.size
        _zs = np.linspace(z1, z2, npt)
        # self.position_list = []
        for _x, _z in zip(_xs, _zs):
            for _y in _ys:
                point = {'x' : _x, 'y' : _y, 'z' : _z, 'exposed' : False, 'uid' : ''}
                self.position_list = self.position_list.append(point, ignore_index=True)
        self.current_index = 0
        self.npoints = len(self.position_list.index)

    def reset(self):
        self.position_list = pd.DataFrame(columns=['x', 'y', 'z', 'exposed', 'uid'])
        self.current_index = None
        self.xyz1 = None
        self.xyz2 = None

    def _get_point(self, index):
        return self.position_list.iloc[index]

    def _move_to_point_plan(self, point):
        print(f'moving stage to x={point["x"]}, y={point["y"]}, z={point["z"]}')
        yield from bps.mv(self.sample_x, point['x'],
                          self.sample_y, point['y'],
                          self.sample_z, point['z'],
                          )

    def goto_start_plan(self):
        self.current_index = 0
        point = self._get_point(0)
        yield from self._move_to_point_plan(point)

    def goto_end_plan(self):
        self.current_index = self.npoints - 1
        point = self.position_list.iloc[self.current_index]
        yield from self._move_to_point_plan(point)

    def goto_next_point_plan(self):
        self.current_index += 1
        point = self._get_point(self.current_index)
        yield from self._move_to_point_plan(point)

    def goto_index_plan(self, idx):
        self.current_index = idx
        point = self._get_point(idx)
        yield from self._move_to_point_plan(point)

    def find_first_unexposed_point(self):
        idx = self.position_list['exposed'].ne(False).idxmin()
        p = self.position_list.iloc[idx]
        return idx, p
        # for i, p in enumerate(self.position_list):
        #     if not p['exposed']:
        #         return i, p
        # return None

    def set_current_point_exposed(self):
        if self.current_index is not None:
            self.position_list.at[self.current_index, 'exposed'] = True
            if self._dumpfile is not None:
                self.dump_data()


    def record_uid_for_current_point(self, uid):
        self.position_list.at[self.current_index, 'uid'] = uid

    def get_list_of_uid_positions(self):
        # herfd_index_list = []
        # for idx, point in enumerate(self.position_list):
        #     if 'uid' in point.keys():
        #         herfd_index_list.append(idx)
        return self.position_list['uid'].loc[lambda x: x != ''].values

    def get_current_point(self):
        point = self._get_point(self, self.current_index)
        return point['x'], point['y'], point['z']

    def goto_unexposed_point_plan(self):
        i, point = self.find_first_unexposed_point()
        self.current_index = i
        yield from self._move_to_point_plan(point)

    def save(self, filename):
        # with open(filename, 'w') as f:
        #     f.write(json.dumps(self.position_list))
        print(f'sample registry - saving data - {ttime.ctime()}')
        self.position_list.to_json(filename)

    def load(self, filename):
        # with open(filename, 'r') as f:
        #     self.position_list = json.loads(f.read())
        self.position_list = pd.read_json(filename)
        self.npoints = len(self.position_list.index)


    def set_dump_file(self, filename):
        self._dumpfile = filename

    def dump_data(self):
        self.save(self._dumpfile)

    def get_nom_and_act_positions(self):
        x_act = self.sample_x.user_readback.get()
        y_act = self.sample_y.user_readback.get()
        z_act = self.sample_z.user_readback.get()

        point = self.position_list[self.current_index]
        return point['x'], point['y'], point['z'], x_act, y_act, z_act


sample_registry = SamplePointRegistry()


import h5py
class RIXSLogger:
    scanned_emission_energies = np.array([])
    normalized_points = np.array([])
    herfd_list = []

    def __init__(self, filepath, resume_flag=False):
        self.filepath = filepath
        if resume_flag:
            self._find_scanned_emission_energies()
        else:
            try:
                f = h5py.File(self.filepath, 'w-')
                f.close()
            except OSError:
                raise OSError('rixs log file with this name already exists')



    def _find_scanned_emission_energies(self):
        f = h5py.File(self.filepath, 'r')
        self.herfd_list = list(f.keys())
        for uid in self.herfd_list:
            ee = f[f'{uid}/emission_energy'][()]
            # self.scanned_emission_energies.append(ee)
            self.scanned_emission_energies = np.append(self.scanned_emission_energies, ee)
            # print(ee)
            if 'uid_norm' in f[f'{uid}'].keys():
                # self.normalized_points.append(True)
                self.normalized_points = np.append(self.normalized_points, True)
            else:
                self.normalized_points = np.append(self.normalized_points, False)
        f.close()
        self.scanned_emission_energies = np.array(self.scanned_emission_energies)
        self.normalized_points = np.array(self.normalized_points)

    def energy_was_measured(self, emission_energy, threshold=1e-3):
        if len(self.scanned_emission_energies) == 0:
            return False
        d = np.min(np.abs(self.scanned_emission_energies - emission_energy))
        return d < threshold

    def point_was_normalized(self, herfd_uid_to_check):
        for i, herfd_uid in enumerate(self.herfd_list):
            if herfd_uid_to_check == herfd_uid:
                return self.normalized_points[i]
        return

    def set_point_as_normalized(self, herfd_uid_to_check):
        for i, herfd_uid in enumerate(self.herfd_list):
            if herfd_uid_to_check == herfd_uid:
                self.normalized_points[i] = True

    def write_uid_herfd(self, uid_herfd, emission_energy):
        f = h5py.File(self.filepath, 'r+')
        f.create_group(uid_herfd)
        f[uid_herfd]['emission_energy'] = emission_energy
        f.close()
        self.herfd_list.append(uid_herfd)
        self.scanned_emission_energies = np.array(self.scanned_emission_energies.tolist() + [emission_energy])
        self.normalized_points = np.array(self.normalized_points.tolist() + [False])

    def write_herfd_pos(self, uid_herfd, x_nom, y_nom, z_nom, x_act, y_act, z_act):
        f = h5py.File(self.filepath, 'r+')
        f[uid_herfd]['x_nom'] = x_nom
        f[uid_herfd]['y_nom'] = y_nom
        f[uid_herfd]['z_nom'] = z_nom
        f[uid_herfd]['x_act'] = x_act
        f[uid_herfd]['y_act'] = y_act
        f[uid_herfd]['z_act'] = z_act
        f.close()

    def write_uid_norm(self, uid_herfd, uid_norm, energy_in_norm, energy_out_norm,
                       x_norm_nom, y_norm_nom, z_norm_nom,
                       x_norm_act, y_norm_act, z_norm_act):
        f = h5py.File(self.filepath, 'r+')
        f[uid_herfd]['uid_norm'] = uid_norm
        f[uid_herfd]['x_norm_nom'] = x_norm_nom
        f[uid_herfd]['y_norm_nom'] = y_norm_nom
        f[uid_herfd]['z_norm_nom'] = z_norm_nom
        f[uid_herfd]['x_norm_act'] = x_norm_act
        f[uid_herfd]['y_norm_act'] = y_norm_act
        f[uid_herfd]['z_norm_act'] = z_norm_act
        f[uid_herfd]['energy_in_norm'] = energy_in_norm
        f[uid_herfd]['energy_out_norm'] = energy_out_norm
        f.close()
        self.set_point_as_normalized(uid_herfd)






def function_for_measuing_samples():
    sample_1_x, sample_1_y, sample_1_z = -25.586,  1.613, -20.301
    sample_2_x, sample_2_y, sample_2_z = -25.741,-15.287, -20.401
    sample_3_x, sample_3_y, sample_3_z = -25.146, -29.887, -21.301
    RE(move_sample(sample_1_x, sample_1_y, sample_1_z))
    xlive_gui.widget_run.parameter_values[0].setText(f'FeTiO3 HERFD')
    xlive_gui.widget_run.run_scan()
    for i in range(3):
        RE(move_sample(sample_2_x, sample_2_y, sample_2_z))
        xlive_gui.widget_run.parameter_values[0].setText(f'LiTi2O3 HERFD')
        xlive_gui.widget_run.run_scan()

        RE(move_sample(sample_3_x, sample_3_y, sample_3_z))
        xlive_gui.widget_run.parameter_values[0].setText(f'CaTiO3 HERFD')
        xlive_gui.widget_run.run_scan()



def rixs_scan_plan(energies_in, energies_out):
    for energy_in in energies_in:
        yield from bps.mv(hhm.energy, energy_in)
        yield from emission_scan_plan(energies_out)


###########
def rixs_scan_RE(energies_out):
    for energy_out in energies_out:

        widget_run.run_scan()




###########


def move_sample(x, y, z):
    yield from bps.mv(giantxy.x, x)
    yield from bps.mv(giantxy.y, y)
    yield from bps.mv(usermotor2.pos, z)

# def move_sample_back(dx, dy, dz):
#     sdsdfsd
#     yield from bps.mv(giantxy.x, -dx)
#     yield from bps.mv(giantxy.y, -dy)
#     yield from bps.mvr(usermotor2.pos, -dz)


def get_snake_trajectory(x, y, step=0.2):
    x0 = giantxy.x.user_readback.get()
    y0 = giantxy.y.user_readback.get()
    z0 = usermotor2.pos.user_readback.get()

    _dxs = np.arange(0, x+step, step) / np.cos(np.deg2rad(30))
    _dys = np.arange(0, y+step, step)
    _dzs = -_dxs/np.cos(np.deg2rad(30))
    position_list = []
    for dx, dz in zip(_dxs, _dzs):
        for dy in _dys:
            position_list.append([x0 + dx, y0+dy, z0+dz])
    return position_list


#positions = get_snake_trajectory(3, 3, 0.2)
# widget_run = xlive_gui.widget_run

def rixs_scan_from_mara_at_each_new_point(energies_out, positions, energies_kbeta):
    filename = f'/nsls2/xf08id/users/2021/1/308190/rixs_Co3MnO4_uids_{new_uid()[:6]}.txt'
    print(f'Uids will be stored under  {filename}')
    for energy_out, position in zip(energies_out, positions):
        print(f'Emission energy {energy_out}' )
        print('Starting Move Energy...')
        RE(move_emission_energy_plan(energy_out))
        print('Move Energy Complete')
        print('Starting Move Sample...')
        RE(move_sample(*position))
        print('Move Sample Complete')
        print('Starting HERFD Scan...')
        widget_run.run_scan()
        print('HERFD Scan complete...')
        uid_herfd = db[-1].start['uid']


        while np.abs(hhm.energy.user_readback.get() - 8000) > 1:
            try:
                print('attempting to move energy to 8000')
                RE(bps.mv(hhm.energy, 8000, timeout=30))
            except:
                print('the motion timed out. Stopping the motor.')
                hhm.energy.stop()

        print('Starting Emission Scan...')
        uid_xes = RE(emission_scan_plan(energies_kbeta))
        print('Emission Scan complete...')
        with open(filename, "a") as text_file:
            text_file.write(ttime.ctime() + ' ' + uid_herfd + ' ' + uid_xes[0] + '\n')

#rixs_scan_from_mara_at_each_new_point(energies_emission,
#                                      positions[:energies_emission.size],
#                                      energies_kbeta)

# start_position_idx = 21
# for i in range(4):
#    idx1 = i*energies_emission.size + start_position_idx
#    idx2 = (i+1) * energies_emission.size + start_position_idx
#    print(idx1, idx2)
#    rixs_scan_from_mara_at_each_new_point(energies_emission, positions_co3mno4[idx1:idx2], energies_kbeta)
#    print(f'last position used was {idx2}')

#positions_co3mno4[0] = [-26.502437515, -29.168950962, -23.0959375]
#positions_co3mno4 = get_snake_trajectory(3.5, 4, 0.15)




def herfd_scan_in_pieces_plan(energies_herfd, positions, pos_start_index, n=4, exp_time=0.5):
    idx_e = np.round(np.linspace(0, energies_herfd.size-1, n+1))
    for i in range(idx_e.size-1):
        idx1 = int( np.max([idx_e[i]-1, 0]) )
        idx2 = int( np.min([idx_e[i+1]+1, energies_herfd.size-1]) )
        print(f'the scan will be performed between {energies_herfd[idx1]} and {energies_herfd[idx2]}')
        energy_steps = energies_herfd[idx1:idx2]
        time_steps = np.ones(energy_steps.shape) * exp_time
        yield from move_sample(*positions[pos_start_index+i])
        partial_herfd_plan = step_scan_plan('Co3MnO4 long HERFD scan',
                                            '',
                                            energy_steps, time_steps, [pil100k, apb_ave], element='Co', e0=7709, edge='K')
        yield from shutter.open_plan()
        yield from partial_herfd_plan
        yield from shutter.close_plan()





# energies_herfd = db['5bcffa42-fa10-48cb-a8ea-f77172456976'].table()['hhm_energy'].values
# this_herfd_plan = herfd_scan_in_pieces_plan(energies_herfd, positions, 21, n=4, exp_time=1)
# RE(this_herfd_plan)



# energies_calibration = np.array([7625,7650,7675,7700,7725])
# uids = RE(calibration_scan_plan(energies_calibration))
#EC = analyze_many_elastic_scans(db, uids, energies_calibration, plotting=True)








# def test():
#     eem = define_spectrometer_motor('Ge', [4,4,4])
#     print(eem._get_postion_for_energy(7649))
#     print(eem._get_postion_for_energy(7639))
#     print(eem._get_postion_for_energy(7629))

#
# test()

######


# spectrometer_calibration_dict = {}

# Energy      CrX         CrY         DetY
# 7649.2     -129.570     16.285       331.731
# 7639.2     -132.144

def move_to_7649():
    yield from bps.mv(auxxy.x,-129.570 )
    yield from bps.mv(auxxy.y, 16.285)
    yield from bps.mv(huber_stage.z,331.731)
    yield from bps.mv(hhm.energy,7649.2)

#######
def define_energy_range():
    # for CoO
   # energies_kbeta = np.linspace(7625, 7665, 41)
   # energies_emission = np.arange(7641, 7659+0.25, 0.25)
    # for Co4O
    energies_kbeta = np.linspace(7649, 7650, 2)
    energies_emission = np.arange(7627, 7659+0.25, 0.25)
    return energies_kbeta, energies_emission



# energies_vtc_cubanes = np.hstack((np.arange(7670, 7684+2, 2),
#                                   np.arange(7685, 7712+0.5, 0.5),
#                                   np.arange(7714, 7725+2, 2)))[::-1]
def scan_vtc_plan(energies_vtc, positions, start_index):
    idx = start_index + 0

    while True:
        print(f'moving to sample index {idx} at {positions[idx]}')
        yield from move_sample(*positions[idx])
        yield from emission_scan_plan(energies_vtc)
        idx += 1





# energies_vtc_cubanes = np.arange(7670, 7725+0.25, 0.25)
# energies_vtc_cubanes = np.hstack((np.arange(7670, 7684+2, 2), np.arange(7685, 7712+0.5, 0.5), np.arange(7714, 7725+2, 2)))
# RE(move_to_7649())
# eem_calculator = define_spectrometer_motor('Ge', [4, 4, 4])
# energies_kbeta, energies_emission = define_energy_range()
# RE(move_sample(*[-24.7386537495, -15.568973257, -22.495625]))
# positions = get_snake_trajectory(2.5, 4.2, 0.15)
# widget_run = xlive_gui.widget_run
#energies_kbeta_fine = np.linspace(7625, 7665, 51)

