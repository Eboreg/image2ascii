import functools
import time
from collections.abc import Iterator
from typing import TypedDict


TIMING_ENABLED: bool = False

timings: "list[TimingDict]" = []
running_timings: "list[TimingDict]" = []


class TimingDict(TypedDict):
    name: str
    parent: str | None
    elapsed_time: float


def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global timings, running_timings, TIMING_ENABLED

        if not TIMING_ENABLED:
            return func(*args, **kwargs)

        start_time = time.monotonic()

        timing: TimingDict = {
            "name": func.__qualname__,
            "parent": running_timings[-1]["name"] if running_timings else None,
            "elapsed_time": 0.0,
        }
        timings.append(timing)
        running_timings.append(timing)

        ret = func(*args, **kwargs)

        running_timings.remove(timing)
        timing["elapsed_time"] = time.monotonic() - start_time

        return ret

    return wrapper


class TimingResult:
    executions = 1
    children: "list[TimingResult]"

    def __init__(
        self,
        name: str,
        total_time: float,
        parent: str | None = None,
        is_root: bool = False,
        executions: int = 1,
        children: list["TimingResult"] | None = None,
    ):
        self.name = name
        self.total_time = total_time
        self.parent = parent
        self.children = []
        self.is_root = is_root
        self.executions = executions
        self.children = children or []

    @property
    def average_time(self):
        return self.total_time / self.executions

    @property
    def total_own_time(self):
        child_time = sum((c.total_time for c in self.children), 0.0)
        return self.total_time - child_time

    @property
    def average_own_time(self):
        return self.total_own_time / self.executions

    def collect(self) -> Iterator["TimingResult"]:
        yield self
        for child in self.children:
            yield from child.collect()

    def copy(self):
        return TimingResult(
            name=self.name,
            total_time=self.total_time,
            parent=self.parent,
            is_root=self.is_root,
            executions=self.executions,
            children=[c.copy() for c in self.children],
        )

    def print(self, total_time: float, indent: int, print_children: bool):
        def ff(v):
            return f"{round(v, 6)} s"

        prefix = " " * indent
        percent_own_time = self.total_own_time / total_time * 100 if total_time > 0 else 0.0
        percent_total = self.total_time / total_time * 100 if total_time > 0 else 0.0
        child_count = sum(c.executions for c in self.collect()) - self.executions

        print(
            f"{prefix}{self.name:{46 - indent}.{46 - indent}s} {self.executions:7d} {child_count:8d}  "
            f"{ff(self.average_own_time):12s} {ff(self.average_time):12s} {ff(self.total_own_time):12s} "
            f"{ff(self.total_time):12s} {percent_own_time:8.4f} {percent_total:8.4f}"
        )

        if print_children:
            for child in self.children:
                child.print(total_time, indent + 2, print_children=True)

    @classmethod
    def print_header(cls):
        print("AT = avg time | TT = total time | %TT = % total time | #CH = # children")
        print("*:O = excl children | *:T = incl children")
        print(
            "Function                                             #      #CH  AT:O         AT:T         "
            "TT:O         TT:T            %TT:O    %TT:T"
        )
        print(
            "---------------------------------------------------------------------------------------------------------"
            "---------------------------------"
        )


def clear_results():
    global timings
    timings.clear()


def print_results(hierarchical: bool = True, by_function: bool = True):
    root, timings = summarize_timing()

    if hierarchical:
        TimingResult.print_header()
        root.print(root.total_time, 0, print_children=True)
        if by_function:
            print("\n")

    if by_function:
        TimingResult.print_header()
        total_time = sum(t.total_time for t in timings if not t.is_root)
        for timing in timings:
            timing.print(total_time, 0, print_children=False)


def summarize_timing() -> tuple[TimingResult, list[TimingResult]]:
    result: dict[str, TimingResult] = {}
    root = summarize_timing_by_hierarchy()

    for timing in root.collect():
        if not timing.is_root:
            if timing.name in result:
                result[timing.name].executions += timing.executions
                result[timing.name].total_time += timing.total_time
            else:
                result[timing.name] = timing.copy()

    return root, sorted(list(result.values()), key=lambda t: t.total_own_time, reverse=True)


def summarize_timing_by_hierarchy() -> TimingResult:
    global timings

    result: dict[tuple[str, str | None], TimingResult] = {}

    for t in timings:
        key = (t["name"], t["parent"])

        if key in result:
            result[key].executions += 1
            result[key].total_time += t["elapsed_time"]
        else:
            result[key] = TimingResult(t["name"], t["elapsed_time"], t["parent"])
            for r in result.values():
                if r.name == t["parent"]:
                    r.children.append(result[key])
                    break

    root = TimingResult("Total", sum(t["elapsed_time"] for t in timings), None, is_root=True)
    root.children.extend([r for r in result.values() if r.parent is None])

    return root
