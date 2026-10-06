import os
from functools import wraps

import jwt
import redis
from flask import jsonify, request

from shared.redis_support import RedisUnavailable, record_metric, require_redis


def jwt_secret():
    return os.getenv("JWT_SECRET_KEY")


def verify_request_token():
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None, {"error": "Missing Authorization Bearer token"}, 401

    secret = jwt_secret()
    if not secret:
        return None, {"error": "Authentication service is not configured"}, 503

    try:
        claims = jwt.decode(
            token.strip(),
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "jti", "user_id", "role_id"]},
        )
        if (
            not isinstance(claims["user_id"], int)
            or claims["user_id"] < 1
            or not isinstance(claims["role_id"], int)
            or claims["role_id"] < 1
            or not isinstance(claims.get("role"), str)
            or not claims["role"].strip()
        ):
            return None, {"error": "Invalid token claims"}, 401
        if str(claims.get("sub", "")) != str(claims["user_id"]):
            return None, {"error": "Invalid token claims"}, 401
        client = require_redis()
        if client.exists(f"jwt:revoked:{claims['jti']}"):
            return None, {"error": "Token revoked"}, 401
        record_metric("jwt.validated", failed=False)
        return claims, None, None
    except RedisUnavailable:
        return None, {"error": "Authorization service temporarily unavailable"}, 503
    except redis.RedisError:
        record_metric("jwt.revocation_check", failed=True)
        return None, {"error": "Authorization service temporarily unavailable"}, 503
    except jwt.ExpiredSignatureError:
        return None, {"error": "Token expired"}, 401
    except jwt.InvalidTokenError:
        return None, {"error": "Invalid token"}, 401
    except (KeyError, TypeError, ValueError):
        return None, {"error": "Invalid token claims"}, 401


def jwt_required(roles=None):
    required_roles = set(roles or [])

    def decorate(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            claims, error, status = verify_request_token()
            if error:
                return jsonify(error), status
            if required_roles and claims.get("role") not in required_roles:
                return jsonify({"error": "Insufficient role"}), 403
            request.jwt_claims = claims
            return handler(*args, **kwargs)

        return wrapped

    return decorate