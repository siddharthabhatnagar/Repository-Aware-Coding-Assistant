import os
import re
from pathlib import Path
from typing import Tuple, List

class SecurityViolation(Exception):
    """Raised when an untrusted repository content or operation violates security constraints."""
    pass

# Common patterns for API keys, tokens, and private keys
SECRET_PATTERNS = [
    (re.compile(r'(?i)(api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{16,})["\']?'), r'\1="[REDACTED_SECRET]"'),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), '[REDACTED_GITHUB_TOKEN]'),
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), '[REDACTED_API_KEY]'),
    (re.compile(r'gsk_[a-zA-Z0-9]{20,}'), '[REDACTED_GROQ_KEY]'),
    (re.compile(r'AIza[0-9A-Za-z-_]{35}'), '[REDACTED_GOOGLE_KEY]'),
    (re.compile(r'AKIA[0-9A-Z]{16}'), '[REDACTED_AWS_KEY]'),
    (re.compile(r'-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----'), '[REDACTED_PRIVATE_KEY]'),
    (re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s]{6,})["\']?'), r'\1="[REDACTED_PASSWORD]"'),
]

DANGEROUS_GIT_FLAGS = {
    "--upload-pack", "--receive-pack", "--exec", "-c", "--config",
    "core.fsmonitor", "ext::"
}

def validate_safe_path(base_dir: str | Path, target_path: str | Path) -> Path:
    """
    Validates that target_path resolves strictly within base_dir.
    Prevents path traversal, symlink escapes, and directory climbing.
    """
    try:
        base = Path(base_dir).resolve()
        
        # If target_path is relative, resolve relative to base
        target = Path(target_path)
        if not target.is_absolute():
            resolved = (base / target).resolve()
        else:
            resolved = target.resolve()
            
        # Ensure the resolved path begins with the base directory
        if not (resolved == base or base in resolved.parents):
            raise SecurityViolation(
                f"Path traversal detected! Path '{target_path}' escapes repository boundary '{base}'."
            )
            
        return resolved
    except (ValueError, RuntimeError) as e:
        raise SecurityViolation(f"Invalid path representation: {str(e)}")

def is_safe_file_to_read(file_path: Path, max_size_bytes: int = 1_000_000) -> Tuple[bool, str]:
    """
    Checks if a file is safe to read:
    - Exists and is a regular file
    - Size is within safe bounds (prevents memory exhaustion)
    - Not a binary executable / image / zip bomb
    """
    if not file_path.exists():
        return False, "File does not exist"
        
    if not file_path.is_file():
        return False, "Not a regular file (e.g. socket, FIFO, device)"
        
    try:
        stat = file_path.stat()
        if stat.st_size > max_size_bytes:
            return False, f"File size ({stat.st_size} bytes) exceeds limit ({max_size_bytes} bytes)"
            
        # Quick null-byte check to detect binary files
        with open(file_path, "rb") as f:
            chunk = f.read(2048)
            if b"\x00" in chunk:
                return False, "Binary file detected (contains null bytes)"
                
        return True, "Safe"
    except Exception as e:
        return False, f"File inspection failed: {str(e)}"

def mask_secrets(content: str) -> Tuple[str, int]:
    """
    Detects and masks sensitive credentials (API keys, private keys, passwords).
    Returns masked text and count of secrets redacted.
    """
    if not content:
        return "", 0
        
    masked = content
    redaction_count = 0
    for pattern, replacement in SECRET_PATTERNS:
        matches = len(pattern.findall(masked))
        if matches > 0:
            redaction_count += matches
            masked = pattern.sub(replacement, masked)
            
    return masked, redaction_count

def sanitize_git_ref(ref_name: str) -> str:
    """
    Ensures git branch or ref is alphanumeric with safe delimiters.
    Prevents argument injection into git commands.
    """
    ref_name = ref_name.strip()
    if not ref_name:
        raise SecurityViolation("Git reference name cannot be empty")
        
    # Check for dangerous flags or subcommands
    for flag in DANGEROUS_GIT_FLAGS:
        if flag in ref_name:
            raise SecurityViolation(f"Dangerous flag detected in git reference: '{flag}'")
            
    # Allow letters, digits, slashes, dashes, underscores, dots
    if not re.match(r'^[a-zA-Z0-9_\-\./]+$', ref_name):
        raise SecurityViolation(f"Invalid characters in git reference: '{ref_name}'")
        
    if ".." in ref_name:
        raise SecurityViolation("Double dot '..' not allowed in git reference")
        
    return ref_name
