# Overview: One-Time Pad encryption/decryption tool

# Features: 
    1. Memory Efficiency: Processes files in configurable chunks (default 4MB) to handle large files

    2. Security Improvements:
       - Auto-sets generated key files to read-only
       - Uses cryptographically secure random number generation
       - Includes comprehensive error checking

    3. User Experience:
       - Interactive prompts for file overwrites
       - Clear error messages with suggestions
       - Detailed help documentation
       - Progress feedback

    4. Code Quality:
        - Modular architecture with separate functions
        - Comprehensive error handling
        - Type checking and validation
        - PEP8 compliant formatting

    5. New Features:
        - Configurable chunk size for performance tuning
        - Force overwrite flag for scripting
        - Input validation for all operations
        - Permission checking for file access

# How to use:
    # Encryption with new key
    python otp.py encrypt plaintext.txt key.otp ciphertext.otp --generate-key

    # Encryption with existing key
    python otp.py encrypt plaintext.txt key.otp ciphertext.otp

    # Decryption
    python otp.py decrypt ciphertext.otp key.otp decrypted.txt

    # Force overwrite existing files
    python otp.py encrypt plaintext.txt key.otp ciphertext.otp --generate-key --force

    # Use custom chunk size
    python otp.py encrypt largefile.iso key.otp encrypted.iso --generate-key --chunk-size 16777216
