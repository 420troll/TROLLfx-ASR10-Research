import unittest
from tools.audio_validation.clock_experiment import (
    rate_hz, selected_clock, schedule_frames, CPU_HZ, OLD_OTTO_HZ, VOICE24_OTTO_HZ,
)

class ClockSchedulerTests(unittest.TestCase):
    def test_original_hall_clock_rate(self):
        self.assertEqual(rate_hz(OLD_OTTO_HZ,31),29761.89453125)
    def test_24_slot_mode_rate(self):
        self.assertEqual(rate_hz(selected_clock(23),23),44100.0)
    def test_clock_choice_tracks_voice_slots_not_effect(self):
        self.assertEqual(selected_clock(22),VOICE24_OTTO_HZ)
        self.assertEqual(selected_clock(23),VOICE24_OTTO_HZ)
        self.assertEqual(selected_clock(24),OLD_OTTO_HZ)
    def test_cycle_scheduler_matches_rate_over_long_window(self):
        chunks=[32]*500000
        frames,acc=schedule_frames(chunks,OLD_OTTO_HZ,31)
        measured=frames*CPU_HZ/(len(chunks)*32)
        expected=rate_hz(OLD_OTTO_HZ,31)
        self.assertLess(abs(measured-expected), expected/frames)
        self.assertGreaterEqual(acc,0.0)
        self.assertLess(acc,16*32)
    def test_frame_count_and_phase_carry_across_chunks(self):
        a=schedule_frames([1]*10000,VOICE24_OTTO_HZ,23)
        b=schedule_frames([10000],VOICE24_OTTO_HZ,23)
        self.assertEqual(a[0],b[0]); self.assertAlmostEqual(a[1],b[1])

if __name__=='__main__': unittest.main()

class SerialAnalysisTests(unittest.TestCase):
    def test_impulse_decay_frame_and_time_domains_are_separate(self):
        import csv, tempfile
        from pathlib import Path
        from tools.audio_validation.clock_experiment import serial_metrics
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'impulse.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f); w.writerow(('frame','cycles','ser1_left','ser1_right'))
                w.writerows([(i,0,10000 if i==0 else 0,10000 if i==0 else 0) for i in range(4)])
            slow=serial_metrics(p,10,2); fast=serial_metrics(p,20,2)
            self.assertEqual(slow['frames'],4)
            self.assertEqual(slow['one_percent_peak_frame'],2)
            self.assertAlmostEqual(slow['one_percent_peak_seconds'],0.2)
            self.assertAlmostEqual(fast['one_percent_peak_seconds'],0.1)
    def test_extract_all_eight_serial_lanes(self):
        import tempfile
        from pathlib import Path
        from tools.audio_validation.clock_experiment import extract_all_lanes
        with tempfile.TemporaryDirectory() as d:
            log=Path(d)/'capture.log'; out=Path(d)/'input.csv'
            log.write_text('ESPPFRAME kind=input index=0 frame=10 cycles=20 host_pc=abcdef serial=48 lanes=0000,0001,ffff,0003,0004,0005,0006,0007\n')
            self.assertEqual(extract_all_lanes(log,10,1,out),1)
            row=out.read_text().splitlines()[1].split(',')
            self.assertEqual(row[0],'0'); self.assertEqual(row[1],'10')
            self.assertEqual(row[-8:],['0','1','-1','3','4','5','6','7'])
    def test_fixed_frame_compare_never_shifts(self):
        import csv, tempfile
        from pathlib import Path
        from tools.audio_validation.clock_experiment import compare_serial
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.csv'; b=Path(d)/'b.csv'
            for p,frame in ((a,1),(b,2)):
                with p.open('w',newline='') as f:
                    w=csv.writer(f); w.writerow(('frame','cycles','ser1_left','ser1_right')); w.writerow((frame,0,1,2))
            with self.assertRaises(ValueError): compare_serial(a,b,29761,44100)
