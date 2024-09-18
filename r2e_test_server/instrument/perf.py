import json
import inspect
import datetime
from typing import Any
from decimal import Decimal
from collections.abc import Iterable
from typing import List, Dict

from r2e_test_server.instrument.base import Instrumenter


class TimeItInstrumenter(Instrumenter):
    def __init__(self):
        super().__init__()
        self.args_with_names = {}
        self.serialized_args_with_names = {}
        self.captured_args_list = []

    def before_call(self, func, *args, **kwargs):
        bound_arguments = inspect.signature(func).bind(*args, **kwargs)
        bound_arguments.apply_defaults()

        self.args_with_names = bound_arguments.arguments
        self.serialized_args_with_names = {
            k: self.serialize(v) for k, v in self.args_with_names.items()
        }

    def after_call(self, func, *args, **kwargs):
        output = self.output
        serialized_output = self.serialize(output)

        self.captured_args_list.append(
            {
                "func_name": func.__name__,
                "inputs": self.args_with_names,
                "serialized_inputs": self.serialized_args_with_names,
                "input_types": {
                    k: f"{type(v).__module__}.{type(v).__qualname__}"
                    for k, v in self.args_with_names.items()
                },
                "output": output,
                "serialized_output": serialized_output,
                "output_type": f"{type(output).__module__}.{type(output).__qualname__}",
                "caller_info": self.caller_info(),
            }
        )

    def clear(self):
        super().clear()
        self.captured_args_list.clear()
        self.args_with_names.clear()
        self.serialized_args_with_names.clear()


    def get_logs(self) -> List[Dict[str, Any]]:
        logs = []
        for captured_args in self.captured_args_list:

            # FIXME: isn't this the same as serialize_inputs and serialize_output?
            captured_args["inputs"] = {
                k: Serializers.serialize_default(v)
                for k, v in captured_args["inputs"].items()
            }
            captured_args["output"] = Serializers.serialize_default(
                captured_args["output"]
            )

            logs.append(captured_args)
        return logs

    def dump_logs(self, file_path: str):
        logs = self.get_logs()

        with open(file_path, "w") as f:
            json.dump(logs, f, indent=4, default=Serializers.serialize_default)

    # helpers

    def serialize(self, obj: Any) -> Any:

        # get all the handlers from the Serializer class
        handlers = [
            getattr(Serializers, method_name)
            for method_name in dir(Serializers)
            if method_name.startswith("serialize_")
            and not method_name == "serialize_default"
        ]

        for handler in handlers:
            serialized_obj = handler(obj)
            if serialized_obj is not None:
                return serialized_obj

        serialized_obj = Serializers.serialize_default(obj)

        if isinstance(serialized_obj, Iterable) and len(serialized_obj) > 180:
            return serialized_obj[:90] + "  ......  " + serialized_obj[-90:]  # type: ignore

        return serialized_obj

    @staticmethod
    def serialize_datetime(obj):
        try:
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
        except:
            pass

        return None

    @staticmethod
    def serialize_decimal(obj):
        try:
            if isinstance(obj, Decimal):
                return float(obj)
        except:
            pass

        return None

    @staticmethod
    def serialize_function(obj):
        try:
            if isinstance(obj, type(lambda: 1)):
                return inspect.getsource(obj)
        except:
            pass
        return None

    @staticmethod
    def serialize_networkx(obj):
        try:
            import networkx as nx  # type: ignore

            if isinstance(obj, nx.Graph):
                from networkx.readwrite import json_graph  # type: ignore

                return (
                    str(json_graph.node_link_data(obj))
                    .replace("source", "src")
                    .replace("target", "tgt")
                )
        except:
            pass
        return None

    @staticmethod
    def serialize_pandas(obj):
        try:
            import pandas as pd  # type: ignore

            if isinstance(obj, (pd.DataFrame, pd.Series)):  # type: ignore
                return str(obj.head(5))
        except:
            pass
        return None

    @staticmethod
    def serialize_numpy(obj):
        try:
            import numpy as np  # type: ignore

            if isinstance(obj, np.ndarray):  # type: ignore
                if obj.size > 25:
                    return f"np.ndarray(shape={obj.shape}, dtype={obj.dtype})"
                return f"np-array: {obj.round(2)}"
        except:
            pass
        return None

    @staticmethod
    def serialize_torch(obj):
        try:
            import torch  # type: ignore

            if isinstance(obj, torch.Tensor) and obj.numel() > 25:
                return f"torch.Tensor(shape={obj.shape}, dtype={obj.dtype})"

        except:
            pass
        return None

    @staticmethod
    def serialize_tensorflow(obj):
        try:
            import tensorflow as tf  # type: ignore

            if isinstance(obj, tf.Tensor) and obj.shape.num_elements() > 25:  # type: ignore
                return f"tf.Tensor(shape={obj.shape}, dtype={obj.dtype})"

        except:
            pass
        return None

    @staticmethod
    def serialize_jax(obj):
        try:
            import jax.numpy as jnp  # type: ignore

            if isinstance(obj, jnp.ndarray) and obj.size > 25:
                return f"jax.numpy.ndarray(shape={obj.shape}, dtype={obj.dtype})"

        except:
            pass
        return None

    @staticmethod
    def serialize_jaxlib(obj):
        try:
            import jaxlib.xla_extension  # type: ignore

            if isinstance(obj, jaxlib.xla_extension.DeviceArray) and obj.size > 25:  # type: ignore
                return f"jaxlib.xla_extension.DeviceArray(shape={obj.shape}, dtype={obj.dtype})"

        except:
            pass
        return None

class MemProfInstrumenter(Instrumenter):
    def __init__(self):
        super().__init__()

    def before_call(self, func, *args, **kwargs):
        bound_arguments = inspect.signature(func).bind(*args, **kwargs)
        bound_arguments.apply_defaults()

        self.args_with_names = bound_arguments.arguments
        self.serialized_args_with_names = {
            k: self.serialize(v) for k, v in self.args_with_names.items()
        }

    def after_call(self, func, *args, **kwargs):
        output = self.output
        serialized_output = self.serialize(output)

        self.captured_args_list.append(
            {
                "func_name": func.__name__,
                "inputs": self.args_with_names,
                "serialized_inputs": self.serialized_args_with_names,
                "input_types": {
                    k: f"{type(v).__module__}.{type(v).__qualname__}"
                    for k, v in self.args_with_names.items()
                },
                "output": output,
                "serialized_output": serialized_output,
                "output_type": f"{type(output).__module__}.{type(output).__qualname__}",
                "caller_info": self.caller_info(),
            }
        )

    def clear(self):
        super().clear()
        self.captured_args_list.clear()
        self.args_with_names.clear()
        self.serialized_args_with_names.clear()


    def get_logs(self) -> List[Dict[str, Any]]:
        logs = []
        for captured_args in self.captured_args_list:

            # FIXME: isn't this the same as serialize_inputs and serialize_output?
            captured_args["inputs"] = {
                k: Serializers.serialize_default(v)
                for k, v in captured_args["inputs"].items()
            }
            captured_args["output"] = Serializers.serialize_default(
                captured_args["output"]
            )

            logs.append(captured_args)
        return logs

    def dump_logs(self, file_path: str):
        logs = self.get_logs()

        with open(file_path, "w") as f:
            json.dump(logs, f, indent=4, default=Serializers.serialize_default)

    # helpers

    def serialize(self, obj: Any) -> Any:

        # get all the handlers from the Serializer class
        handlers = [
            getattr(Serializers, method_name)
            for method_name in dir(Serializers)
            if method_name.startswith("serialize_")
            and not method_name == "serialize_default"
        ]

        for handler in handlers:
            serialized_obj = handler(obj)
            if serialized_obj is not None:
                return serialized_obj

        serialized_obj = Serializers.serialize_default(obj)

        if isinstance(serialized_obj, Iterable) and len(serialized_obj) > 180:
            return serialized_obj[:90] + "  ......  " + serialized_obj[-90:]  # type: ignore

        return serialized_obj
