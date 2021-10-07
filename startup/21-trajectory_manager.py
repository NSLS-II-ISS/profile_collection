import time as ttime
#import pexpect
from pexpect import pxssh
from ftplib import FTP
from subprocess import call

from xas import xray
import pandas as pd
# from xas.bin import xas_energy_grid

from PyQt5 import QtCore

class TrajectoryManager():
    def __init__(self, hhm, **kwargs):
        self.hhm = hhm
        self.traj_info = {}
        self.trajectory_path = f'{ROOT_PATH_SHARED}/trajectory/'

    # Function used to count the number of lines in a file
    def file_len(self, fname):
        with open(fname) as f:
            plusone = 0
            if f.readline()[0] != '#':
                plusone = 1
            for i, l in enumerate(f):
                pass
        return i + 1 + plusone

    def read_header(self, filename):
        test = ''
        line = '#'
        with open(filename) as myfile:
            while line[0] == '#':
                line = next(myfile)
                test += line
        return test[:-len(line) - 1]

    ########## load ##########
    # Transfer the trajectory file to the motor controller
    # arg1 = orig_file_name             -> Filename of the trajectory: E.g.: 'traj_Cu_fast.txt'
    # arg2 = new_file_path              -> LUT number where the new trajectory file will be stored
    # arg3 (optional) = new_file_name     -> New name that will be used as filename in the controller. Currently, it MUST be 'hhm.txt'
    # arg4 (optional) = orig_file_path     -> Path to look for the file that will be transfered. Default = '/GPFS/xf08id/trajectory/'
    # arg5 (optional) = ip                 -> IP of the controller that will receive the file. Default = '10.8.2.86'
    def load(self, orig_file_name, new_file_path, is_energy, offset, new_file_name='hhm.txt'):
        ip = self.hhm.ip
        orig_file_path = self.trajectory_path

        print('[Load Trajectory] Starting...')
        traj_fn = orig_file_name

        # Check if new_file_path is between the possible values
        if int(new_file_path) > 9 or int(new_file_path) < 1:
            print(
                "[Load Trajectory] Path '{}' not possible. Please use a value in the range 1 <= new_file_path <= 9.".format(
                    new_file_path))
            return False

        # Get number of lines in file
        file_size = self.file_len(orig_file_path + orig_file_name)
        print('[Load Trajectory] Number of lines in file: {}'.format(file_size))

        # Get min and max of trajectory in eV
        if orig_file_path[-1] != '/':
            fp += '/'

        traj = pd.read_table('{}{}'.format(orig_file_path, orig_file_name), header=None, comment='#')
        name = orig_file_name
        header = self.read_header('{}{}'.format(orig_file_path, orig_file_name))
        if is_energy:
            min_energy = int(np.round(traj).min())
            max_energy = int(np.round(traj).max())
            enc = np.int64(np.round(xray.energy2encoder(-traj, self.hhm.pulses_per_deg, -offset)))
            orig_file_name = '.energy_traj_aux.txt'
            np.savetxt('{}{}'.format(orig_file_path, orig_file_name), enc, fmt='%d', header=header, comments='')
        else:
            min_energy = int(xray.encoder2energy((-traj, self.hhm.pulses_per_deg).min()))
            max_energy = int(xray.encoder2energy((-traj, self.hhm.pulses_per_deg).max()))

        print('[Load Trajectory] Min energy: {}'.format(min_energy))
        print('[Load Trajectory] Max energy: {}'.format(max_energy))

        # Create ftp connection with default credential
        ftp = FTP(ip)
        ftp.login()
        s = pxssh.pxssh()
        ssh_login = s.login(ip, 'root', 'deltatau')

        if ssh_login:
            # Check if the directory exists in /usrflash/lut/. If it does not, create it.
            if str(new_file_path) != '':
                ftp.cwd('/usrflash/')
                dir_list = ftp.nlst()
                dir_exists = 0
                for dir_name in dir_list:
                    if dir_name == 'lut':
                        dir_exists = 1
                if not dir_exists:
                    print('[Load Trajectory] mkdir: /usrflash/lut')
                    ftp.mkd('/usrflash/lut')
                    s.sendline('chown ftp:root /var/ftp/usrflash/lut')
                    s.sendline('chmod a+wrx /var/ftp/usrflash/lut')

                ftp.cwd('/usrflash/lut/')
                dir_list = ftp.nlst()
                dir_exists = 0
                for dir_name in dir_list:
                    if dir_name == str(new_file_path):
                        dir_exists = 1
                if not dir_exists:
                    print('[Load Trajectory] mkdir: /usrflash/lut/{}'.format(new_file_path))
                    ftp.mkd('/usrflash/lut/{}'.format(new_file_path))
                    s.sendline('chown ftp:root /var/ftp/usrflash/lut/{}'.format(new_file_path))
                    s.sendline('chmod a+wrx /var/ftp/usrflash/lut/{}'.format(new_file_path))

                s.sendline('chown ftp:root /var/ftp/usrflash/lut/{}/hhm.txt'.format(new_file_path))
                s.sendline('chmod 777 /var/ftp/usrflash/lut/{}/hhm.txt'.format(new_file_path))

            ftp_file_path = '/var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name)

            # Open file and transfer to the power pmac
            f = open(orig_file_path + str(orig_file_name), 'rb')
            if (f.readable()):
                line = f.readline().decode('utf-8')
                if line[0] == '#':
                    element = line[line.find('element:') + 9: line.find(',')].lstrip()
                    edge_value = line[line.find('edge:') + 6: line.find(',', line.find('edge:'))].lstrip()
                    e0_value = line[line.find('E0:') + 4:].lstrip()
                    curr_hhm_traj = getattr(self.hhm, 'traj{}'.format(new_file_path))
                    curr_hhm_traj.filename.put(traj_fn)
                    curr_hhm_traj.elem.put(element)
                    curr_hhm_traj.edge.put(edge_value)
                    curr_hhm_traj.e0.put(e0_value)
                    curr_hhm_traj.bla = 'bla'
                else:
                    curr_hhm_traj = getattr(self.hhm, 'traj{}'.format(new_file_path))
                    curr_hhm_traj.filename.put(traj_fn)
                    curr_hhm_traj.elem.put('')
                    curr_hhm_traj.edge.put('')
                    curr_hhm_traj.e0.put('')
                    f.close()
                    f = open(orig_file_path + str(orig_file_name), 'rb')
                result = ftp.storbinary('STOR ' + '/usrflash/lut/' + str(new_file_path) + '/' + new_file_name, f)
                if (result == '226 File receive OK.'):
                    print('[Load Trajectory] File sent OK')
                    s.sendline('chown ftp:root /var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name))
                    s.sendline('chmod a+wrx /var/ftp/usrflash/lut/{}/{}'.format(new_file_path, new_file_name))
                    s.sendline('echo "{}\n{}\n{}\n{}" > /var/ftp/usrflash/lut/{}/hhm-size.txt'.format(file_size, name,
                                                                                                      min_energy,
                                                                                                      max_energy,
                                                                                                      new_file_path))
                    ttime.sleep(0.01)
                    ftp.close()
                    print('[Load Trajectory] Permissions OK')

                f.close()

            s.logout()
            s.pid = None
            print('[Load Trajectory] Completed!')
        else:
            print('[Load Trajectory] Fail! Not able to ssh into the controller...')

    ########## init ##########
    # Transfer the trajectory from the flash to the ram memory in the controller
    # It must be called everytime you decide to use a different trajectory
    # arg1 = lut_number                -> lookup table number of the trajectory that will be used - must be a number between 1 and 9
    # arg2 (optional) = ip            -> IP of the controller that will receive the file. Default = '10.8.2.86'
    # arg3 (optional) = filename    -> Filename of the trajectory file in the controller. Currently, it MUST be 'hhm.txt'
    def init(self, lut_number, filename='hhm.txt'):
        ip = self.hhm.ip
        print('[Init Trajectory] Starting...')

        self.hhm.lut_number.put(lut_number)

        ttime.sleep(0.5)
        while (int(self.hhm.lut_number_rbv.get()) != int(lut_number)):
            ttime.sleep(.001)
            QtCore.QCoreApplication.processEvents()

        self.hhm.lut_start_transfer.put("1")
        while (self.hhm.lut_transfering.get() == 0):
            ttime.sleep(.001)
            QtCore.QCoreApplication.processEvents()
        while (self.hhm.lut_transfering.get() == 1):
            ttime.sleep(.001)
            QtCore.QCoreApplication.processEvents()
        ttime.sleep(.25)
        # while (self.hhm.trajectory_loading.get() == 0):
        #    ttime.sleep(.001)
        #    QtCore.QCoreApplication.processEvents()
        while (self.hhm.trajectory_loading.get() == 1):
            ttime.sleep(.001)
            QtCore.QCoreApplication.processEvents()

        ftp = FTP(ip)
        ftp.login()
        ftp.cwd('/usrflash/lut/{}'.format(lut_number))

        file_list = ftp.nlst()
        file_exists = 0
        for file_name in file_list:
            if file_name == filename:
                file_exists = 1
        if file_exists == 0:
            print('[Init Trajectory] File not found. :(\nAre you sure \'{}\' is the correct lut number?'.format(
                lut_number))
        else:
            info = []

            def handle_binary(more_data):
                info.append(more_data)

            resp = ftp.retrlines('RETR hhm-size.txt', callback=handle_binary)
            if (len(info) == 2):
                size = int(info[0])
                name = info[1]
            elif (len(info) == 4):
                size = int(info[0])
                name = info[1]
                min_en = int(info[2])
                max_en = int(info[3])
            else:
                print(
                    '[Init Trajectory] Could not find the size and name info in the controller. Please, try sending the trajectory file again using trajectory_load(...)')
                return False

            if (size == 0):
                print(
                    '[Init Trajectory] Size seems to be equal to 0. Please, try sending the trajectory file again using trajectory_load(...)')
                return False
            else:
                self.hhm.cycle_limit.put(size)
                while (self.hhm.cycle_limit_rbv.get() != size):
                    ttime.sleep(.01)
                print('[Init Trajectory] New lut number: {}'.format(lut_number))
                print('[Init Trajectory] Trajectory name: {}'.format(name))
                print('[Init Trajectory] Number of points: {}'.format(size))
                print('[Init Trajectory] Completed!')
                self.hhm.trajectory_name.put(name)
            ftp.close()

    ########## read_info ##########
    # Function that prints info about the trajectories currently stored in the controller
    # arg1 (optional) = ip    -> IP of the controller. Default = '10.8.2.86's
    def read_info(self, silent=False):
        ip = self.hhm.ip
        ftp = FTP(ip)
        ftp.login()
        ftp.cwd('/usrflash/lut/')
        if not silent:
            print('-' * 62)
            print('The trajectories found in the controller (ip: {}) are:'.format(ip))
        self.traj_info.clear()

        def handle_binary(more_data):
            info.append(more_data)

        ret_txt = ''
        for i in range(1, 10):
            ftp.cwd('/usrflash/lut/{}'.format(i))

            file_list = ftp.nlst()
            filename = 'hhm-size.txt'
            file_exists = 0
            for file_name in file_list:
                if file_name == filename:
                    file_exists = 1
            if file_exists == 1:

                info = []

                resp = ftp.retrlines('RETR hhm-size.txt', callback=handle_binary)
                if (len(info) == 2):
                    size = int(info[0])
                    name = info[1]
                    self.traj_info[str(i)] = {'name': str(name), 'size': str(size)}
                    if not silent:
                        print('{}: {:<24} (Size: {})'.format(i, name, size))
                elif (len(info) == 4):
                    size = int(info[0])
                    name = info[1]
                    min_en = int(info[2])
                    max_en = int(info[3])
                    self.traj_info[str(i)] = {'name': str(name), 'size': str(size), 'min': str(min_en),
                                              'max': str(max_en)}
                    if not silent:
                        print('{}: {:<24} (Size: {}, min: {}, max: {})'.format(i, name, size, min_en, max_en))
                else:
                    self.traj_info[str(i)] = {'name': 'undefined', 'size': 'undefined'}
                    if not silent:
                        print('{}: Could not find the size and name info'.format(i))
            elif not silent:
                self.traj_info[str(i)] = {'name': 'undefined', 'size': 'undefined'}
                print('{}: Could not find the size and name info'.format(i))

        if not silent:
            print('-' * 62)

        return self.traj_info

    @property
    def current_lut(self):
        return int(self.hhm.lut_number_rbv.get())

    def reinit(self):
        self.init(self.current_lut)

    def read_trajectory_limits(self):
        # current_lut = self.current_lut
        # int(hhm.lut_number_rbv.get())
        # traj_manager = trajectory_manager(hhm)
        info = self.read_info(silent=True)
        try:
            e_min = int(info[str(self.current_lut)]['min'])
            e_max = int(info[str(self.current_lut)]['max'])
            return e_min, e_max
        except KeyError: # if 'max' not in info[str(self.current_lut)] or 'min' not in info[str(self.current_lut)]:


            raise Exception(
                'Could not find max or min information in the trajectory.'
                ' Try sending it again to the controller.')

    @property
    def current_trajectory_duration(self):
        info = trajectory_manager.read_info(silent=True)
        lut = str(trajectory_manager.current_lut)
        return int(info[lut]['size']) / self.hhm.servocycle

    def validate_element(self, element, edge):
        # check if current trajectory is good for this calibration
        r = db_proc.search({'Sample_name': element + ' foil'})
        if len(r) == 0:
            print_to_gui(f'Error: No matching foil has been found')
            return False

        e_min, e_max = self.read_trajectory_limits()
        edge_energy = xraydb.xray_edge(element, edge).energy
        if not ((edge_energy > e_min) and (edge_energy < e_max)):
            print_to_gui(f'Error: invalid trajectory for this calibration')
            return False

        return True



trajectory_manager = TrajectoryManager(hhm)


# trajectory_manager.current_trajectory_duration