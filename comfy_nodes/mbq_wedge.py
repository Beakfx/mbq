from decimal import Decimal, getcontext


class MBQWedge:
    """
    Parameter sweep (photography-style wedge/bracket).
    Wire INT output → steps/seed offset/etc; FLOAT output → cfg/denoise/guidance/etc.
    ComfyUI greys out incompatible socket types automatically when dragging a link.
    Number of runs = floor((stop - start) / step_size) + 1, shown live on the node.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "parameter_name": ("STRING", {"default": "connect output →", "multiline": False}),
                "start":     ("FLOAT", {"default": 1.0,  "min": -99999.0, "max": 99999.0, "step": 0.1}),
                "step_size": ("FLOAT", {"default": 1.0,  "min": 0.001,    "max": 99999.0, "step": 0.1}),
                "stop":      ("FLOAT", {"default": 10.0, "min": -99999.0, "max": 99999.0, "step": 0.1}),
                # "decimals": ("INT", {"default": 2, "min": 0, "max": 6}),  # reserved for future use
            }
        }

    RETURN_TYPES   = ("INT", "FLOAT")
    RETURN_NAMES   = ("int_value", "float_value")
    OUTPUT_IS_LIST = (True, True)
    FUNCTION       = "sweep"
    CATEGORY       = "MBQ"

    def sweep(self, parameter_name, start, step_size, stop):
        getcontext().prec = 12
        decimals = 2  # reserved: restore from INPUT_TYPES when needed
        values = []
        v      = Decimal(str(start))
        d_step = Decimal(str(step_size))
        d_stop = Decimal(str(stop))
        while v <= d_stop + Decimal("1e-9"):
            values.append(float(round(v, decimals)))
            v += d_step
        int_values = [int(round(x)) for x in values]
        return (int_values, values)
