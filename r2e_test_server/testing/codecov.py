import inspect
from types import ModuleType
from coverage import Coverage
from typing import Dict, List


class R2ECodeCoverage(object):
    def __init__(
        self,
        cov: Coverage,
        fut_module: ModuleType,
        fut_module_path: str,
        funclass_name: str,
    ):
        self.cov = cov
        self.fut_module = fut_module
        self.fut_module_path = fut_module_path
        self.funclass_name = funclass_name

    def report_coverage(self):
        if not self.source_exists():
            return {}

        self.load_coverage_data()
        self.limit_data_to_target_source()

        metrics = {}
        metrics.update(self.get_line_metrics())
        metrics.update(self.get_branch_metrics())

        return metrics

    def dump_to(self, file_name):
        """dump raw cov to a file"""
        self.cov.load()
        self.cov.json_report(outfile=file_name)

    # TODO: modify this to give precise cov information
    # should be a good idea to mount the whole FUT folder into docker, but only allow modification of one file
    def get_line_metrics(self) -> Dict:
        """Get the line coverage metrics for the FUT."""
        num_executable_lines = len(self.executable_lines)
        num_excluded_lines = len(self.excluded_lines)

        num_unexec_lines = len(self.unexecuted_lines) - 1
        num_exec_lines = num_executable_lines - num_excluded_lines - num_unexec_lines

        # get the coverage percentage
        line_cov_perc = (
            num_exec_lines / (num_executable_lines - num_excluded_lines)
        ) * 100

        coverage_metrics = {
            "num_executable_lines": num_executable_lines,
            "num_excluded_lines": num_excluded_lines,
            "num_unexecuted_lines": num_unexec_lines,
            "line_coverage_percentage": line_cov_perc,
        }

        return coverage_metrics

    def get_branch_metrics(self) -> Dict:
        """Get the branch coverage metrics for the FUT."""
        num_executed_branches = len(self.executed_branches)
        num_missing_branches = len(self.missing_branches)

        if num_executed_branches + num_missing_branches == 0:
            branch_cov_perc = 100
        else:
            branch_cov_perc = (
                num_executed_branches / (num_executed_branches + num_missing_branches)
            ) * 100

        branch_coverage_metrics = {
            "num_executed_branches": num_executed_branches,
            "num_missing_branches": num_missing_branches,
            "branch_coverage_percentage": branch_cov_perc,
        }

        return branch_coverage_metrics

    def load_coverage_data(self):
        """Load the coverage data for the FUT from coverage.py"""
        self.cov.load()
        analysis = self.cov._analyze(self.fut_module_path)

        self.executable_lines: List = sorted(analysis.statements)
        self.excluded_lines: List = sorted(analysis.excluded)
        self.unexecuted_lines: List = sorted(analysis.missing)
        self.missing_branches: Dict = analysis.missing_branch_arcs()
        self.executed_branches: Dict = analysis.executed_branch_arcs()

    def limit_data_to_target_source(self):
        """Filter the coverage data to only the FUT's source code."""
        line_filter_func = (
            lambda line: self.fut_first_line <= line <= self.fut_last_line
        )
        branch_filter_func = (
            lambda branch: self.fut_first_line <= branch[0] <= self.fut_last_line
        )

        self.executable_lines = self.filter_lines_list(
            self.executable_lines, line_filter_func
        )
        self.unexecuted_lines = self.filter_lines_list(
            self.unexecuted_lines, line_filter_func
        )
        self.excluded_lines = self.filter_lines_list(
            self.excluded_lines, line_filter_func
        )
        self.missing_branches = self.filter_lines_dict(
            self.missing_branches, branch_filter_func
        )
        self.executed_branches = self.filter_lines_dict(
            self.executed_branches, branch_filter_func
        )

    # helper functions

    def filter_lines_dict(self, data, filter_func) -> Dict:
        """Apply a filter function to a dictionary of items."""
        return dict(filter(filter_func, data.items()))

    def filter_lines_list(self, data, filter_func) -> List:
        """Apply a filter function to a list of items."""
        return list(filter(filter_func, data))

    def source_exists(self) -> bool:
        """Check if the source code exists in a file."""
        try:

            # method case
            if "." in self.funclass_name:
                class_name, method_name = self.funclass_name.split(".")
                class_obj = getattr(self.fut_module, class_name)
                method_obj = getattr(class_obj, method_name)
                lines_info = inspect.getsourcelines(method_obj)

            # func/class case
            else:
                func_obj = getattr(self.fut_module, self.funclass_name)
                lines_info = inspect.getsourcelines(func_obj)

        except (OSError, AttributeError):
            # print(f"{self.funclass_name} not found\n{self.fut_module.__dict__}")
            return False

        # set FUT's first and last line, if exists
        self.fut_first_line = lines_info[1]
        self.fut_last_line = self.fut_first_line + len(lines_info[0]) - 1
        return True
