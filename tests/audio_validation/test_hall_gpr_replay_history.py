import csv
import tempfile
import unittest
from pathlib import Path

from tools.audio_validation.replay_hall import extract_load_history


class HallGprHistoryTests(unittest.TestCase):
    def _trace(self, rows):
        f=tempfile.NamedTemporaryFile("w",newline="",delete=False)
        try:
            w=csv.writer(f);w.writerow(("event","cycles","frame","seconds","pc","type","fields..."));w.writerows(rows)
        finally:f.close()
        self.addCleanup(Path(f.name).unlink,missing_ok=True)
        return Path(f.name)

    def test_prior_gpr_commit_survives_hall_pipeline_clear_and_reload(self):
        trace=self._trace([
            ["1","10","1","0","fff000","PIPELINE_CLEAR","reason=boot"],
            ["2","11","1","0","fff000","BOTH_COMMIT","index=90","word=000000000000","gpr=123456"],
            ["3","20","2","0","fff000","PIPELINE_CLEAR","reason=hall"],
            ["4","21","2","0","fff000","GPR_COMMIT","index=01","value=00abcd"],
            ["5","22","3","0","fff000","DSP_RUN","program_ready=1"],
            ["6","22","3","0","fff000","RUN_SNAPSHOT","ok"],
        ])
        history,current=extract_load_history(trace,3)
        self.assertEqual(history,[ ("seed_gpr","90","123456","0") ])
        self.assertEqual(current,[ ("gpr","01","00abcd","0") ])
        state=[0]*192
        for kind,address,value,_ in history+current:
            if kind in ("seed_gpr","gpr"):state[int(address,16)]=int(value,16)
        self.assertEqual(state[0x90],0x123456)
        self.assertEqual(state[1],0xabcd)

    def test_target_hall_commit_overrides_retained_prior_value_in_order(self):
        trace=self._trace([
            ["1","10","1","0","fff000","PIPELINE_CLEAR","reason=boot"],
            ["2","11","1","0","fff000","GPR_COMMIT","index=90","value=111111"],
            ["3","20","2","0","fff000","PIPELINE_CLEAR","reason=hall"],
            ["4","21","2","0","fff000","BOTH_COMMIT","index=90","word=000000000000","gpr=222222"],
            ["5","22","3","0","fff000","DSP_RUN","program_ready=1"],
            ["6","22","3","0","fff000","RUN_SNAPSHOT","ok"],
        ])
        history,current=extract_load_history(trace,3)
        state=[0]*192
        for kind,address,value,second in history+current:
            if kind=="seed_gpr":state[int(address,16)]=int(value,16)
            elif kind=="gpr":state[int(address,16)]=int(value,16)
            elif kind=="both":state[int(address,16)]=int(second,16)
        self.assertEqual(state[0x90],0x222222)


if __name__=="__main__":unittest.main()
