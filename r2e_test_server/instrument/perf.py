import inspect
import functools
import timeit
from typing import List, Dict, Any
from r2e_test_server.instrument.base import Instrumenter

# Custom timeit template
timeit.template = """def inner(_it, _timer{init}):
    {setup}
    _t0 = _timer()
    for _i in _it:
        retval = {stmt}
    _t1 = _timer()
    return _t1 - _t0, retval"""


class TimeItInstrumenter(Instrumenter):
    def __init__(self):
        super().__init__()
        self.timing_logs: List[Dict[str, Any]] = []

    def instrument(self, func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self.current_frame = inspect.currentframe()
            if self.current_frame is not None:
                self.previous_frame = self.current_frame.f_back

            timer = timeit.Timer(lambda: func(*args, **kwargs))
            duration, output = timer.timeit(number=1)

            log_entry = {
                "func_name": func.__name__,
                "duration": duration,
                "caller_info": self.caller_info(),
            }
            self.timing_logs.append(log_entry)

            return output

        return wrapper

    def clear(self):
        self.timing_logs.clear()

    def get_logs(self) -> List[Dict[str, Any]]:
        return self.timing_logs

    def dump_logs(self, file_path: str):
        import json

        with open(file_path, "w") as f:
            json.dump(self.timing_logs, f, indent=4)
