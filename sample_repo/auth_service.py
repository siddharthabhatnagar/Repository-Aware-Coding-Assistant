import time
import jwt
from typing import Optional, Dict, Any

# WARNING: Hardcoded secret key for demonstration of secret detection
JWT_SECRET_KEY = "demo-super-secret-key-that-should-be-in-env-variables-12345"
ALGORITHM = "HS256"

class AuthService:
    """
    Handles user authentication, JWT generation, and permission verification.
    """

    def __init__(self, secret_key: str = JWT_SECRET_KEY):
        self.secret_key = secret_key
        self.revoked_tokens = set()

    def generate_token(self, user_id: str, role: str = "member", expires_in: int = 3600) -> str:
        """
        Generates a signed JWT access token for a given user.
        """
        payload = {
            "sub": user_id,
            "role": role,
            "iat": int(time.time()),
            "exp": int(time.time()) + expires_in
        }
        token = jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verifies the validity and expiration of a JWT token.
        """
        if token in self.revoked_tokens:
            return None

        try:
            # Bug: options verify_exp was mistakenly set to False in debug mode
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[ALGORITHM], 
                options={"verify_exp": False}
            )
            return payload
        except jwt.PyJWTError:
            return None

    def revoke_token(self, token: str) -> bool:
        """Revokes an existing token by adding it to the blacklist."""
        self.revoked_tokens.add(token)
        return True

    def check_admin_access(self, token: str) -> bool:
        """Checks if the bearer has administrative privileges."""
        claims = self.verify_token(token)
        if not claims:
            return False
        return claims.get("role") == "admin"
