from xas.file_io import validate_file_exists
import time as ttime
from datetime import datetime
from ophyd.status import SubscriptionStatus



class FlyerAPBwithTrigger(FlyerAPB):

    def __init__(self, det, pbs, motor, trigger): #, xs_det):
        super().__init__( det, pbs, motor)
        self.trigger = trigger

    def kickoff(self, traj_duration=None):
        self.trigger.stage()
        st_super = super().kickoff(traj_duration=traj_duration)
        return st_super

    def complete(self):
        st_super = super().complete()
        def callback_motor():
            self.trigger.complete()

        self._motor_status.add_callback(callback_motor)
        return st_super & self._motor_status #& st_xs

    def describe_collect(self):
        dict_super = super().describe_collect()
        dict_trig = self.trigger.describe_collect()
        return {**dict_super, **dict_trig}#, **dict_xs}

    def collect_asset_docs(self):
        yield from super().collect_asset_docs()
        yield from self.trigger.collect_asset_docs()

    def collect(self):
        yield from super().collect()
        yield from self.trigger.collect()
        self.trigger.unstage()


flyer_apb_trigger = FlyerAPBwithTrigger(det=apb_stream, pbs=[pb9.enc1], motor=hhm, trigger=apb_trigger)



class FlyerXS(FlyerAPBwithTrigger):

    def __init__(self, det, pbs, motor, trigger, xs_det):
        super().__init__( det, pbs, motor, trigger)
        self.xs_det = xs_det

    def kickoff(self, traj_duration=None):
        traj_duration = trajectory_manager.current_trajectory_duration
        acq_rate = self.trigger.freq.get()
        self.xs_det.stage(acq_rate, traj_duration)
        st_super = super().kickoff(traj_duration=traj_duration)
        return st_super

    def complete(self):
        st_super = super().complete()
        def callback_xs(value, old_value, **kwargs):
            if int(round(old_value)) == 1 and int(round(value)) == 0:
                self.xs_det.complete()
                return True
            else:
                return False

        saving_st = SubscriptionStatus(self.xs_det.hdf5.capture, callback_xs)
        return st_super & saving_st

    def describe_collect(self):
        print(f'{ttime.ctime()} Plan describe_collect is starting...')
        dict_super = super().describe_collect()
        dict_xs = self.xs_det.describe_collect()
        print(f'{ttime.ctime()} Plan describe_collect is complete')
        return {**dict_super, **dict_xs}

    def collect_asset_docs(self):
        print(f'{ttime.ctime()} Plan collect_asset_docs is starting...')
        print(f'                     {ttime.ctime()} super start')
        yield from super().collect_asset_docs()
        print(f'                     {ttime.ctime()} super end')
        print(f'                     {ttime.ctime()} xs3 start')
        yield from self.xs_det.collect_asset_docs()
        print(f'                     {ttime.ctime()} xs3 end')
        print(f'{ttime.ctime()} Plan collect_asset_docs is complete')

    def collect(self):
        print(f'{ttime.ctime()} Plan collect is starting...')
        yield from super().collect()
        yield from self.xs_det.collect()
        self.xs_det.unstage()
        print(f'{ttime.ctime()} Plan collect is complete')


flyer_xs = FlyerXS(det=apb_stream, pbs=[pb9.enc1], motor=hhm, trigger=apb_trigger, xs_det=xs_stream)


class FlyerPilatus(FlyerAPBwithTrigger):

    def __init__(self, det, pbs, motor, trigger, pil_det):
        super().__init__( det, pbs, motor, trigger)
        self.pil_det = pil_det

    def kickoff(self, traj_duration=None):
        print(f'     !!!!! {datetime.now()} PIL100K KICKOFF')
        traj_duration = trajectory_manager.current_trajectory_duration
        acq_rate = self.trigger.freq.get()
        self.pil_det.stage(acq_rate, traj_duration)

        st_pil = self.pil_det.trigger()
        st_super = super().kickoff(traj_duration=traj_duration)
        ttime.sleep(0.1)
        return st_super & st_pil

    def complete(self):
        print(f'     !!!!! {datetime.now()} PIL100K COMPLETE')
        shutter._close_direct()
        st_super = super().complete()
        # def callback_pil(value, old_value, **kwargs):
        #     print(f'     !!!!! {datetime.now()} callback_pil100k_capture {value} --> {old_value}')
        #     if int(round(old_value)) == 1 and int(round(value)) == 0:
        #         print(f'     !!!!! {datetime.now()} callback_pil100k_capture')
        #         self.pil_det.complete()
        #         return True
        #     else:
        #         return False
        # saving_st = SubscriptionStatus(self.pil_det.tiff.capture, callback_pil)
        self.pil_det.complete()
        return st_super# & saving_st

    def describe_collect(self):
        print(f'     !!!!! {datetime.now()} PIL100K DESCRIBE COLLECT')
        dict_super = super().describe_collect()
        dict_pil = self.pil_det.describe_collect()
        return {**dict_super, **dict_pil}

    def collect_asset_docs(self):
        print(f'     !!!!! {datetime.now()} PIL100K COLLECT ASSET DOCS')
        yield from super().collect_asset_docs()
        yield from self.pil_det.collect_asset_docs()

    def collect(self):
        print(f'     !!!!! {datetime.now()} PIL100K COLLECT')
        self.pil_det.unstage()
        yield from super().collect()
        yield from self.pil_det.collect()


# flyer_pil = FlyerPilatus(det=apb_stream, pbs=[pb9.enc1], motor=hhm, trigger=apb_trigger_pil100k, pil_det=pil100k_stream)
flyer_pil = FlyerPilatus(det=apb_stream, pbs=[pb9.enc1], motor=hhm, trigger=apb_trigger_pil100k, pil_det=pil100k_stream)

### general flyer in development

class FlyerPilatus_:
    def __init__(self, det, pil_det, pbs, motor, trigger, shutter):
        self.name = f'{det.name}-{"-".join([pb.name for pb in pbs])}-flyer'
        self.parent = None
        self.det = det
        self.pil_det = pil_det
        self.pbs = pbs  # a list of passed pizza-boxes
        self.motor = motor
        self._motor_status = None
        self.trigger = trigger
        self.shutter = shutter

    def kickoff(self, traj_duration=None, *args, **kwargs):
        # set_and_wait(self.det.trig_source, 1)
        # TODO: handle it on the plan level
        # set_and_wait(self.motor, 'prepare')

        def callback(value, old_value, **kwargs):

            if int(round(old_value)) == 0 and int(round(value)) == 1:
                # Now start mono move
                self._motor_status = self.motor.set('start')
                return True
            else:
                return False

        # print(f'     !!!!! {datetime.now()} Flyer kickoff is complete at')

        streaming_st = SubscriptionStatus(self.det.streaming, callback)

        if traj_duration is None:
            traj_duration = get_traj_duration()
        acq_rate = self.trigger.freq.get()

        self.det.stage(traj_duration)
        self.pil_det.stage(acq_rate, traj_duration)
        st_pil = self.pil_det.trigger()

        # Start apb after encoder pizza-boxes, which will trigger the motor.
        self.det.stream.set(1)

        ttime.sleep(1)
        self.trigger.stage()

        for pb in self.pbs:
            pb.stage()
            pb.kickoff()

        return streaming_st & st_pil

    def complete(self):
        def callback_motor():
            # When motor arrives to the position, it should stop streaming on
            # the detector. That will run 'callback_det' defined below, which
            # will perform the 'complete' step for all involved detectors.
            self.det.stream.put(0)
        self._motor_status.add_callback(callback_motor)

        def callback_det(value, old_value, **kwargs):
            if int(round(old_value)) == 1 and int(round(value)) == 0:
                if self.shutter.state == 'open':
                    yield from self.shutter.close_plan()

                self.det.complete()
                for pb in self.pbs:
                    pb.complete()
                return True
            else:
                return False

        def callback_trigger():
            self.trigger.complete()

        self._motor_status.add_callback(callback_trigger)

        self.pil_det.complete()
        streaming_st = SubscriptionStatus(self.det.streaming, callback_det)

        return self._motor_status & streaming_st

    def describe_collect(self):
        return_dict = self.det.describe_collect()
        # Also do it for all pizza-boxes
        for pb in self.pbs:
            return_dict[pb.name] = pb.describe_collect()[pb.name]

        dict_trig = self.trigger.describe_collect()
        dict_pil = self.pil_det.describe_collect()

        return {**return_dict, **dict_trig, **dict_pil}

    def collect(self):
        def collect_and_unstage_all():
            for pb in self.pbs:
                yield from pb.collect()
            yield from self.det.collect()

            yield from self.trigger.collect()
            yield from self.pil_det.collect()

            # The .unstage() method resets self._datum_counter, which is needed
            # by .collect(), so calling .unstage() afteer .collect().
            self.det.unstage()
            for pb in self.pbs:
                pb.unstage()
            self.trigger.unstage()
            self.pil_det.unstage()

        return (yield from collect_and_unstage_all())

    def collect_asset_docs(self):
        yield from self.det.collect_asset_docs()
        for pb in self.pbs:
            yield from pb.collect_asset_docs()
        yield from self.trigger.collect_asset_docs()
        yield from self.pil_det.collect_asset_docs()


    # def stop(self,*args, **kwargs):
    #     print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>.. AT STOP ')

# flyer_pil = FlyerPilatus_(det=apb_stream, pbs=[pb9.enc1], motor=hhm, trigger=apb_trigger_pil100k, pil_det=pil100k_hdf5_stream, shutter=shutter)



###




def execute_trajectory_apb_trigger(name, **metadata):
    md = get_md_for_scan(name,
                         'fly_scan',
                         'execute_trajectory_apb_trigger',
                         'fly_energy_scan_apb_trigger',
                         **metadata)
    yield from bp.fly([flyer_apb_trigger], md=md)


import bluesky.plan_stubs as bps
def fly_local(flyers, *, md=None):
    """
    Perform a fly scan with one or more 'flyers'.
    Parameters
    ----------
    flyers : collection
        objects that support the flyer interface
    md : dict, optional
        metadata
    Yields
    ------
    msg : Msg
        'kickoff', 'wait', 'complete, 'wait', 'collect' messages
    See Also
    --------
    :func:`bluesky.preprocessors.fly_during_wrapper`
    :func:`bluesky.preprocessors.fly_during_decorator`
    """
    uid = yield from bps.open_run(md)


    for flyer in flyers:
        print(f'({ttime.ctime()}) {flyer.name} kickoff start')
        yield from bps.kickoff(flyer, wait=True)
        print(f'({ttime.ctime()}) {flyer.name} kickoff end')
    for flyer in flyers:
        print(f'({ttime.ctime()}) {flyer.name} complete start')
        yield from bps.complete(flyer, wait=True)
        print(f'({ttime.ctime()}) {flyer.name} complete end')
    for flyer in flyers:
        print(f'({ttime.ctime()}) {flyer.name} collect start')
        yield from bps.collect(flyer)
        print(f'({ttime.ctime()}) {flyer.name} collect end')
    print(f'({ttime.ctime()}) close_run start')
    yield from bps.close_run()
    print(f'({ttime.ctime()}) close_run end')
    return uid



def execute_trajectory_xs(name, **metadata):
    md = get_md_for_scan(name,
                         'fly_scan',
                         'execute_trajectory_xs',
                         'fly_energy_scan_xs3',
                         **metadata)
    md['aux_detector'] = 'XSpress3'
    yield from fly_local([flyer_xs], md=md)



def execute_trajectory_pil100k(name, **metadata):
    md = get_md_for_scan(name,
                         'fly_scan',
                         'execute_trajectory_pil100k',
                         'fly_energy_scan_pil100k',
                         **metadata)
    md['aux_detector'] = 'Pilatus100k'

    roi_data = [[pil100k.roi1.min_xyz.min_x.get(), pil100k.roi1.min_xyz.min_y.get(),
                 pil100k.roi1.size.x.get(),        pil100k.roi1.size.y.get()        ],
                [pil100k.roi2.min_xyz.min_x.get(), pil100k.roi2.min_xyz.min_y.get(),
                 pil100k.roi2.size.x.get(),        pil100k.roi2.size.y.get()        ],
                [pil100k.roi3.min_xyz.min_x.get(), pil100k.roi3.min_xyz.min_y.get(),
                 pil100k.roi3.size.x.get(),        pil100k.roi3.size.y.get()],
                [pil100k.roi4.min_xyz.min_x.get(), pil100k.roi4.min_xyz.min_y.get(),
                 pil100k.roi4.size.x.get(),        pil100k.roi4.size.y.get()]]
    md['roi'] = roi_data
    yield from bp.fly([flyer_pil], md=md)
