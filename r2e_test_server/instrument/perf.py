from typing import List
import timeit

from r2e_test_server.instrument.base import Instrumenter

# WARNING: only keep the last result
timeit.template = """
def inner(_it, _timer{init}):
    {setup}
    _t0 = _timer()
    for _i in _it:
        retval = {stmt}
    _t1 = _timer()
    return _t1 - _t0, retval
"""

class TimeItInstrumenter(Instrumenter):
    durations: List[float]
    def __init__(self):
        super().__init__()
        self.durations = []

    def call(self, func, *args, **kwargs):
        duration, result = timeit.Timer(lambda: func(*args, **kwargs))
        self.durations.append(duration)
        return result

    def clear(self):
        super().clear()
        self.durations.clear()

    def get_logs(self) -> List[float]:
        return self.durations

class ProfilerInstrumenter(TimeItInstrumenter):
    pass
