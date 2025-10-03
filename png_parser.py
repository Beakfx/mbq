# png_parser.py
import struct
import json

def parse_png_workflow(file_path):
    """Parse PNG file and extract ComfyUI workflow data"""
    try:
        with open(file_path, 'rb') as f:
            signature = f.read(8)
            if signature != b'\x89PNG\r\n\x1a\n':
                return None
            
            workflow_data = {}
            
            while True:
                length_data = f.read(4)
                if not length_data:
                    break
                    
                chunk_length = struct.unpack('>I', length_data)[0]
                chunk_type = f.read(4).decode('ascii')
                chunk_data = f.read(chunk_length)
                f.read(4)  # Skip CRC
                
                if chunk_type == 'tEXt':
                    parts = chunk_data.split(b'\x00', 1)
                    if len(parts) == 2:
                        keyword = parts[0].decode('latin-1')
                        text = parts[1].decode('latin-1')
                        
                        if keyword == 'prompt':
                            workflow_data['prompt_json'] = json.loads(text)
                        elif keyword == 'workflow':
                            workflow_data['workflow_json'] = json.loads(text)
                
                if chunk_type == 'IEND':
                    break
            
            return workflow_data if workflow_data else None
                    
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def extract_prompt_info(prompt_json):
    """Extract human-readable info from ComfyUI prompt JSON"""
    try:
        info = {
            'positive_prompt': '',
            'negative_prompt': '', 
            'model': '',
            'sampler': '',
            'steps': '',
            'seed': '',
            'cfg_scale': ''
        }
        
        # Find positive prompt (look for CLIPTextEncode nodes)
        for node_id, node_data in prompt_json.items():
            if node_data.get('class_type') == 'CLIPTextEncode':
                text = node_data.get('inputs', {}).get('text', '')
                if text and not info['positive_prompt']:  # First one is usually positive
                    info['positive_prompt'] = text
                elif text:  # Second one is usually negative
                    info['negative_prompt'] = text
        
        # Find KSampler settings
        for node_id, node_data in prompt_json.items():
            if node_data.get('class_type') == 'KSampler':
                inputs = node_data.get('inputs', {})
                info['steps'] = inputs.get('steps', '')
                info['seed'] = inputs.get('seed', '')
                info['sampler'] = inputs.get('sampler_name', '')
                info['cfg_scale'] = inputs.get('cfg', '')


        # 🔑 Find model (Checkpoint or UNET/Flux)
        for node_id, node_data in prompt_json.items():
            ctype = node_data.get('class_type')
            inputs = node_data.get('inputs', {})

            if ctype in ('CheckpointLoaderSimple', 'CheckpointLoader'):
                info['model'] = inputs.get('ckpt_name', '')
            elif ctype == 'UNETLoader':  # Flux / SDXL style
                info['model'] = inputs.get('unet_name', '')
        return info
    
    except Exception as e:
        print(f"Error extracting prompt info: {e}")
        return {}
    
