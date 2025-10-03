# workflow_parser.py reads and anylizes TEXT-prompt and TEXT-workflow chunks for display in mbq

def parse_workflow(chunks: dict) -> dict:
    """
    chunks: JSON-like dict from image metadata
    returns: normalized dict of parameters:
      {
        "process": "inpaint",
        "model": "sd3.5_large.safetensors",
        "sampler": "euler",
        "steps": 30,
        "cfg": 7.5,
        "denoise": 0.2,
        "prompt": "...",
        "negative_prompt": "...",
        ...
      }
    """
