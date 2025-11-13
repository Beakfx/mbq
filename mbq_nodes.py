"""
mbq_nodes.py
---------------------------------------------------------------------
Contains a static snapshot of ComfyUI's standard node registry,
plus a small helper for classifying workflow nodes and extracting
basic parameters for MBQ.

To update:
  1. Open ComfyUI/nodes.py in the version you’re using.
  2. Copy the NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS
     sections directly into this file.
  3. Replace the dictionaries below.
---------------------------------------------------------------------
"""

from pathlib import Path

# ---------------------------------------------------------------------
#  NODE REGISTRY SNAPSHOT  (ComfyUI 2025-01)
# ---------------------------------------------------------------------
NODE_CLASS_MAPPINGS = {
    "KSampler": "KSampler",
    "KSamplerAdvanced": "KSamplerAdvanced",
    "CLIPTextEncode": "CLIPTextEncode",
    "CheckpointLoaderSimple": "CheckpointLoaderSimple",
    "VAEDecode": "VAEDecode",
    "VAEEncode": "VAEEncode",
    "VAEEncodeForInpaint": "VAEEncodeForInpaint",
    "LoadImage": "LoadImage",
    "SaveImage": "SaveImage",
    "ImageUpscale": "ImageUpscale",
    "LatentUpscale": "LatentUpscale",
    "UpscaleModelLoader": "UpscaleModelLoader",
    "ControlNetLoader": "ControlNetLoader",
    "ControlNetApply": "ControlNetApply",
    "LoraLoader": "LoraLoader",
    "CLIPTextEncodeSDXL": "CLIPTextEncodeSDXL",
    "VAEDecodeSDXL": "VAEDecodeSDXL",
    "VAEEncodeSDXL": "VAEEncodeSDXL",
    "VAEDecodeTiled": "VAEDecodeTiled",
    "VAEEncodeTiled": "VAEEncodeTiled",
    "EmptyLatentImage": "EmptyLatentImage",
    "LatentComposite": "LatentComposite",
    "LatentMix": "LatentMix",
    "LatentNoise": "LatentNoise",
    "LatentFromBatch": "LatentFromBatch",
    "ConditioningCombine": "ConditioningCombine",
    "ConditioningConcat": "ConditioningConcat",
    "CLIPSetLastLayer": "CLIPSetLastLayer",
    "UpscaleImageBy": "UpscaleImageBy",
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # Sampling
    "KSampler": "KSampler",
    "KSamplerAdvanced": "KSampler (Advanced)",
    # Loaders
    "CheckpointLoader": "Load Checkpoint With Config (DEPRECATED)",
    "CheckpointLoaderSimple": "Load Checkpoint",
    "VAELoader": "Load VAE",
    "LoraLoader": "Load LoRA",
    "CLIPLoader": "Load CLIP",
    "ControlNetLoader": "Load ControlNet Model",
    "DiffControlNetLoader": "Load ControlNet Model (diff)",
    "StyleModelLoader": "Load Style Model",
    "CLIPVisionLoader": "Load CLIP Vision",
    "UNETLoader": "Load Diffusion Model",
    # Conditioning
    "CLIPVisionEncode": "CLIP Vision Encode",
    "StyleModelApply": "Apply Style Model",
    "CLIPTextEncode": "CLIP Text Encode (Prompt)",
    "CLIPSetLastLayer": "CLIP Set Last Layer",
    "ConditioningCombine": "Conditioning (Combine)",
    "ConditioningAverage ": "Conditioning (Average)",
    "ConditioningConcat": "Conditioning (Concat)",
    "ConditioningSetArea": "Conditioning (Set Area)",
    "ConditioningSetAreaPercentage": "Conditioning (Set Area with Percentage)",
    "ConditioningSetMask": "Conditioning (Set Mask)",
    "ControlNetApply": "Apply ControlNet (OLD)",
    "ControlNetApplyAdvanced": "Apply ControlNet",
    # Latent
    "VAEEncodeForInpaint": "VAE Encode (for Inpainting)",
    "SetLatentNoiseMask": "Set Latent Noise Mask",
    "VAEDecode": "VAE Decode",
    "VAEEncode": "VAE Encode",
    "LatentRotate": "Rotate Latent",
    "LatentFlip": "Flip Latent",
    "LatentCrop": "Crop Latent",
    "EmptyLatentImage": "Empty Latent Image",
    "LatentUpscale": "Upscale Latent",
    "LatentUpscaleBy": "Upscale Latent By",
    "LatentComposite": "Latent Composite",
    "LatentBlend": "Latent Blend",
    "LatentFromBatch" : "Latent From Batch",
    "RepeatLatentBatch": "Repeat Latent Batch",
    # Image
    "SaveImage": "Save Image",
    "PreviewImage": "Preview Image",
    "LoadImage": "Load Image",
    "LoadImageMask": "Load Image (as Mask)",
    "LoadImageOutput": "Load Image (from Outputs)",
    "ImageScale": "Upscale Image",
    "ImageScaleBy": "Upscale Image By",
    "ImageInvert": "Invert Image",
    "ImagePadForOutpaint": "Pad Image for Outpainting",
    "ImageBatch": "Batch Images",
    "ImageCrop": "Image Crop",
    "ImageStitch": "Image Stitch",
    "ImageBlend": "Image Blend",
    "ImageBlur": "Image Blur",
    "ImageQuantize": "Image Quantize",
    "ImageSharpen": "Image Sharpen",
    "ImageScaleToTotalPixels": "Scale Image to Total Pixels",
    "GetImageSize": "Get Image Size",
    # _for_testing
    "VAEDecodeTiled": "VAE Decode (Tiled)",
    "VAEEncodeTiled": "VAE Encode (Tiled)",
}


KNOWN_NODES = set(NODE_CLASS_MAPPINGS.keys())

# ---------------------------------------------------------------------
#  Node classification helper
# ---------------------------------------------------------------------
def classify_nodes(workflow_json):
    """
    Given a workflow JSON, return (core_nodes, third_party_nodes).
    """
    core_nodes = []
    extra_nodes = []

    if not workflow_json or "nodes" not in workflow_json:
        return core_nodes, extra_nodes

    for node in workflow_json["nodes"]:
        ctype = node.get("class_type") or node.get("type", "")
        if ctype in KNOWN_NODES:
            core_nodes.append(node)
        else:
            extra_nodes.append(node)
    return core_nodes, extra_nodes


# ---------------------------------------------------------------------
#  Basic parameter summary (optional helper)
# ---------------------------------------------------------------------
def summarize_parameters(core_nodes):
    """
    Extract a few top-level parameters from recognized core nodes.
    Returns a summary dict suitable for ImageMetadata.
    """
    summary = {
        "model": None,
        "prompt": "",
        "negative_prompt": "",
        "sampler": None,
        "scheduler": None,
        "steps": None,
        "cfg": None,
        "seed": None,
        "denoise": None,
    }

    for node in core_nodes:
        ctype = node.get("class_type", "").lower()
        wv = node.get("widgets_values", [])
        inputs = node.get("inputs", {})

        # Model loader
        if "checkpointloader" in ctype and wv:
            summary["model"] = Path(wv[0]).stem

        # Sampler
        elif "sampler" in ctype:
            if len(wv) >= 1:
                summary["seed"] = wv[0]
            if len(wv) >= 3:
                summary["steps"] = wv[2]
            if len(wv) >= 4:
                summary["cfg"] = wv[3]
            if len(wv) >= 5:
                summary["sampler"] = wv[4]
            if len(wv) >= 6:
                summary["scheduler"] = wv[5]
            if len(wv) >= 7:
                summary["denoise"] = wv[6]

        # Prompts
        elif "cliptextencode" in ctype:
            text = inputs.get("text") or (wv[0] if wv else "")
            if "neg" in ctype:
                summary["negative_prompt"] += text + "\n"
            else:
                summary["prompt"] += text + "\n"

    summary["prompt"] = summary["prompt"].strip()
    summary["negative_prompt"] = summary["negative_prompt"].strip()
    return summary

# ---------------------------------------------------------------------
#  Legacy wrapper (keeps old code working)
# ---------------------------------------------------------------------
def parse_nodes(workflow_json):
    core_nodes, extra_nodes = classify_nodes(workflow_json)
    summary = summarize_parameters(core_nodes)
    return core_nodes, extra_nodes, summary
