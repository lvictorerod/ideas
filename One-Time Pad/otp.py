import argparse
import secrets
import os
import sys

CHUNK_SIZE = 4096 * 1024  # 4MB default chunk size

def main():
    parser = argparse.ArgumentParser(
        description="Secure One-Time Pad Encryption/Decryption Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="""Security Notes:
- Always store keys securely and never reuse them
- Generated key files are set to read-only automatically
- Use large chunk sizes for better performance with big files"""
    )
    parser.add_argument('mode', choices=['encrypt', 'decrypt'], 
                      help="Operation mode: 'encrypt' or 'decrypt'")
    parser.add_argument('input_file', help="Path to the input file")
    parser.add_argument('key_file', help="Path to the key file")
    parser.add_argument('output_file', help="Path to the output file")
    parser.add_argument('-g', '--generate-key', action='store_true',
                      help="Generate new key during encryption")
    parser.add_argument('-f', '--force', action='store_true',
                      help="Overwrite existing files without prompt")
    parser.add_argument('-c', '--chunk-size', type=int, default=CHUNK_SIZE,
                      help="Chunk size in bytes for file processing")

    args = parser.parse_args()

    try:
        if args.mode == 'encrypt':
            handle_encryption(args)
        else:
            handle_decryption(args)
        print(f"{args.mode.capitalize()}ion completed successfully.")
    except (IOError, ValueError, PermissionError) as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)

def handle_encryption(args):
    if args.generate_key:
        if not check_file_overwrite(args.key_file, args.force, "key"):
            return
        encrypt_with_new_key(args)
    else:
        encrypt_with_existing_key(args)

def handle_decryption(args):
    key = read_key_file(args.key_file)
    process_operation(args.input_file, args.output_file, key, args.chunk_size, 'decrypt')

def encrypt_with_new_key(args):
    try:
        with open(args.input_file, 'rb') as inf, \
             open(args.key_file, 'wb') as kf, \
             open(args.output_file, 'wb') as outf:

            while True:
                data_chunk = inf.read(args.chunk_size)
                if not data_chunk:
                    break
                key_chunk = secrets.token_bytes(len(data_chunk))
                kf.write(key_chunk)
                outf.write(bytes(a ^ b for a, b in zip(data_chunk, key_chunk)))

        os.chmod(args.key_file, 0o400)  # Set key file to read-only
    except PermissionError:
        raise PermissionError(f"Permission denied modifying key file '{args.key_file}'")

def encrypt_with_existing_key(args):
    key = read_key_file(args.key_file)
    process_operation(args.input_file, args.output_file, key, args.chunk_size, 'encrypt')

def process_operation(input_path, output_path, key, chunk_size, mode):
    if not check_file_overwrite(output_path, False, "output"):
        return

    key_index = 0
    try:
        with open(input_path, 'rb') as inf, open(output_path, 'wb') as outf:
            while True:
                data_chunk = inf.read(chunk_size)
                if not data_chunk:
                    break

                chunk_len = len(data_chunk)
                if key_index + chunk_len > len(key):
                    raise ValueError(f"Key is too short for {mode} operation")

                key_chunk = key[key_index:key_index + chunk_len]
                processed = bytes(a ^ b for a, b in zip(data_chunk, key_chunk))
                outf.write(processed)
                key_index += chunk_len
    except PermissionError:
        raise PermissionError(f"Permission denied accessing file '{output_path}'")

def read_key_file(key_path):
    try:
        with open(key_path, 'rb') as kf:
            return kf.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Key file '{key_path}' not found")
    except PermissionError:
        raise PermissionError(f"Permission denied reading key file '{key_path}'")

def check_file_overwrite(file_path, force, file_type):
    if os.path.exists(file_path) and not force:
        if file_type == "key":
            message = f"Key file '{file_path}' exists. Overwrite? [y/N] "
        else:
            message = f"Output file '{file_path}' exists. Overwrite? [y/N] "
        
        response = input(message).strip().lower()
        if response != 'y':
            print("Operation aborted.")
            return False
    return True

if __name__ == '__main__':
    main()