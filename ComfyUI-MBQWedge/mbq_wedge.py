from decimal import Decimal, getcontext
import comfy.samplers


class MBQWedge:
    """
    Parameter sweep (photography-style wedge/bracket).
    Wire INT output → steps/seed offset/etc; FLOAT output → cfg/denoise/guidance/etc.
    ComfyUI greys out incompatible socket types automatically when dragging a link.
    Number of runs = floor((stop - start) / increment) + 1, shown live on the node.

    The JS extension intercepts Queue and submits one job per value, each with
    start=stop=V and current=V patched in. Each PNG gets the exact swept value
    embedded under MBQWedge.inputs.current, readable by MBQ Viewer and any tool
    that inspects PNG text chunks.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "parameter_name": ("STRING", {"default": "connect output →", "multiline": False}),
                "start":     ("FLOAT", {"default": 1.0,  "min": -99999.0, "max": 99999.0, "step": 0.1}),
                "stop":      ("FLOAT", {"default": 10.0, "min": -99999.0, "max": 99999.0, "step": 0.1}),
                "increment":  ("FLOAT", {"default": 1.0,  "min": 0.001,    "max": 99999.0, "step": 0.05}),
            }
        }

    RETURN_TYPES   = ("INT", "FLOAT")
    RETURN_NAMES   = ("int_value", "float_value")
    OUTPUT_IS_LIST = (True, True)
    FUNCTION       = "sweep"
    CATEGORY       = "MBQ"

    def sweep(self, parameter_name, start, stop, increment):
        getcontext().prec = 12
        decimals = 2
        values = []
        v      = Decimal(str(start))
        d_step = Decimal(str(increment))
        d_stop = Decimal(str(stop))
        while v <= d_stop + Decimal("1e-9"):
            values.append(float(round(v, decimals)))
            v += d_step
        int_values = [int(round(x)) for x in values]
        return (int_values, values)


class MBQWedgeSampler:
    """
    Sweeps all available sampler names.
    Wire sampler_name output → any sampler_name input (e.g. KSampler).
    Output type matches the sampler COMBO so ComfyUI accepts the link.
    JS submits one job per sampler; viewer only lights if the output is connected.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "parameter_name": ("STRING", {"default": "sampler_name", "multiline": False}),
                "current":        (comfy.samplers.KSampler.SAMPLERS, {}),
            }
        }

    RETURN_TYPES = (comfy.samplers.KSampler.SAMPLERS,)
    RETURN_NAMES = ("sampler_name",)
    FUNCTION  = "sweep"
    CATEGORY  = "MBQ"

    def sweep(self, parameter_name, current):
        return (current,)


class MBQWedgeScheduler:
    """
    Sweeps scheduler names. Leave filter blank to sweep all; add names one per
    line to sweep only those. Output type matches the scheduler COMBO so
    ComfyUI accepts the link. JS submits one job per value; viewer only lights
    if the output is connected.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "parameter_name": ("STRING", {"default": "scheduler", "multiline": False}),
                "filter":         ("STRING", {"default": "", "multiline": True,
                                              "placeholder": "leave blank to sweep all\none name per line"}),
                "current":        (comfy.samplers.KSampler.SCHEDULERS, {}),
            }
        }

    RETURN_TYPES = (comfy.samplers.KSampler.SCHEDULERS,)
    RETURN_NAMES = ("scheduler",)
    FUNCTION  = "sweep"
    CATEGORY  = "MBQ"

    def sweep(self, parameter_name, filter, current):
        return (current,)
