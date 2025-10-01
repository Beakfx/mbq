# extract_chunks.py
import struct
import sys
import os

def extract_png_text_chunks(file_path):
    """Extract only text chunks from PNG and print them"""
    print(f"🔍 Attempting to read: {file_path}")
    print(f"   File exists: {os.path.exists(file_path)}")
    print(f"   File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 'N/A'} bytes")
    
    try:
        with open(file_path, 'rb') as f:
            signature = f.read(8)
            print(f"📄 PNG signature: {signature.hex()}")
            
            if signature != b'\x89PNG\r\n\x1a\n':
                print("❌ Not a valid PNG file")
                return
            
            print(f"✅ Valid PNG file detected")
            print("🔍 Scanning for chunks...")
            
            text_chunks = []
            chunk_count = 0
            
            while True:
                length_data = f.read(4)
                if not length_data:
                    print("📄 End of file reached")
                    break
                    
                chunk_length = struct.unpack('>I', length_data)[0]
                chunk_type = f.read(4).decode('ascii')
                chunk_data = f.read(chunk_length)
                f.read(4)  # Skip CRC
                
                chunk_count += 1
                print(f"   Chunk #{chunk_count}: {chunk_type} ({chunk_length} bytes)")
                
                if chunk_type in ['tEXt', 'iTXt', 'zTXt']:
                    print(f"   ✅ Found text chunk: {chunk_type}")
                    try:
                        if chunk_type == 'tEXt':
                            parts = chunk_data.split(b'\x00', 1)
                            if len(parts) == 2:
                                keyword = parts[0].decode('latin-1')
                                text = parts[1].decode('latin-1')
                                text_chunks.append((chunk_type, keyword, text))
                                print(f"      Keyword: '{keyword}', Text length: {len(text)}")
                        else:
                            hex_preview = chunk_data[:100].hex()
                            text_chunks.append((chunk_type, "raw_data", hex_preview))
                            print(f"      Raw data (hex): {hex_preview}...")
                    except Exception as e:
                        print(f"      Decode error: {e}")
                        text_chunks.append((chunk_type, "binary_data", "Could not decode"))
                
                if chunk_type == 'IEND':
                    print("📄 IEND chunk - end of PNG data")
                    break
            
            print(f"\n📊 Summary: Found {len(text_chunks)} text chunks out of {chunk_count} total chunks")
            
            if text_chunks:
                print("\n" + "=" * 50)
                print("TEXT CHUNKS FOUND:")
                print("=" * 50)
                for chunk_type, keyword, content in text_chunks:
                    print(f"Chunk: {chunk_type}")
                    print(f"Keyword: {keyword}")
                    print(f"Content: {content}")
                    print("-" * 30)
            else:
                print("❌ No text chunks found in PNG")
                
    except Exception as e:
        print(f"❌ Error reading file: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_png_text_chunks(sys.argv[1])
    else:
        print("Usage: python extract_chunks.py <png_file>")
        print("Example: python extract_chunks.py my_image.png")

