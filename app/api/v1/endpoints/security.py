"""
Security Monitoring Endpoints
API endpoints for security monitoring, threat detection, and security management
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, require_admin
from app.db.database import get_db
from app.models.user import User
from app.services.security_service import security_service

router = APIRouter()


@router.post("/analyze-request")
async def analyze_request_threats(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    Analyze current request for security threats

    This endpoint analyzes the incoming request for potential security threats
    including SQL injection, XSS, and other attack patterns.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for security analysis",
        )

    analysis = security_service.analyze_request_for_threats(request, str(current_user.id))

    return analysis


@router.get("/status")
async def get_security_status(
    current_user: User = Depends(require_admin),
):
    """
    Get current security status and statistics

    Returns comprehensive security metrics including active blocks,
    suspicious activities, and security thresholds.
    """
    return security_service.get_security_status()


@router.get("/report")
async def get_security_report(
    hours: int = Query(24, ge=1, le=168, description="Time period in hours (max 1 week)"),
    current_user: User = Depends(require_admin),
):
    """
    Generate comprehensive security report

    Returns detailed security analysis including threat breakdown,
    risk levels, and security recommendations.
    """
    return security_service.generate_security_report(hours)


@router.post("/validate-password")
async def validate_password_strength(
    password: str = Query(..., description="Password to validate"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Validate password strength

    Returns password strength analysis with score and recommendations.
    """
    # Only allow users to check their own password strength
    # In production, you might want to restrict this further
    analysis = security_service.validate_password_strength(password)

    return analysis


@router.get("/suspicious-activity")
async def get_suspicious_activity(
    limit: int = Query(50, ge=1, le=500, description="Maximum records to return"),
    risk_level: Optional[str] = Query(
        None, description="Filter by risk level (critical, high, medium, low)"
    ),
    current_user: User = Depends(require_admin),
):
    """
    Get recent suspicious activity logs

    Returns filtered list of suspicious requests and security events.
    """
    # Get all suspicious requests from the service
    all_requests = list(security_service.suspicious_requests)

    # Apply filters
    if risk_level:
        filtered_requests = [
            req for req in all_requests
            if req.get("risk_level") == risk_level
        ]
    else:
        filtered_requests = all_requests

    # Sort by timestamp (newest first) and limit
    filtered_requests.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {
        "total_records": len(all_requests),
        "filtered_records": len(filtered_requests),
        "returned_records": min(len(filtered_requests), limit),
        "suspicious_activity": filtered_requests[:limit],
    }


@router.post("/block-ip")
async def block_ip_address(
    ip_address: str = Query(..., description="IP address to block"),
    reason: str = Query(..., description="Reason for blocking"),
    duration_hours: int = Query(24, ge=1, le=168, description="Block duration in hours"),
    current_user: User = Depends(require_admin),
):
    """
    Manually block an IP address

    Adds IP to the security blocklist for specified duration.
    """
    # Add IP to blocklist
    security_service.ip_blocklist.add(ip_address)

    # In a production system, you'd want to persist this to database
    # and implement automatic unblocking after duration

    return {
        "message": f"IP address {ip_address} blocked successfully",
        "ip_address": ip_address,
        "reason": reason,
        "blocked_by": current_user.username,
        "duration_hours": duration_hours,
        "blocked_until": "manual_unblock_required",  # In production, calculate actual timestamp
    }


@router.post("/unblock-ip")
async def unblock_ip_address(
    ip_address: str = Query(..., description="IP address to unblock"),
    current_user: User = Depends(require_admin),
):
    """
    Remove IP address from blocklist
    """
    if ip_address in security_service.ip_blocklist:
        security_service.ip_blocklist.remove(ip_address)
        return {
            "message": f"IP address {ip_address} unblocked successfully",
            "ip_address": ip_address,
            "unblocked_by": current_user.username,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IP address {ip_address} is not in blocklist",
        )


@router.get("/blocked-ips")
async def get_blocked_ips(
    current_user: User = Depends(require_admin),
):
    """
    Get list of currently blocked IP addresses
    """
    return {
        "blocked_ips": list(security_service.ip_blocklist),
        "total_blocked": len(security_service.ip_blocklist),
    }


@router.post("/clear-failed-logins")
async def clear_failed_login_attempts(
    username: Optional[str] = Query(None, description="Specific username to clear"),
    ip_address: Optional[str] = Query(None, description="Specific IP to clear"),
    current_user: User = Depends(require_admin),
):
    """
    Clear failed login attempts

    Useful for unlocking accounts that were temporarily blocked.
    """
    # This is a simplified implementation
    # In production, you'd want more sophisticated clearing logic

    cleared_count = 0

    if username and ip_address:
        key = f"{username}:{ip_address}"
        if key in security_service.failed_login_attempts:
            del security_service.failed_login_attempts[key]
            cleared_count = 1
    elif username:
        # Clear all entries for this username
        keys_to_remove = [
            key for key in security_service.failed_login_attempts.keys()
            if key.startswith(f"{username}:")
        ]
        for key in keys_to_remove:
            del security_service.failed_login_attempts[key]
        cleared_count = len(keys_to_remove)
    elif ip_address:
        # Clear all entries for this IP
        keys_to_remove = [
            key for key in security_service.failed_login_attempts.keys()
            if key.endswith(f":{ip_address}")
        ]
        for key in keys_to_remove:
            del security_service.failed_login_attempts[key]
        cleared_count = len(keys_to_remove)
    else:
        # Clear all failed login attempts
        cleared_count = len(security_service.failed_login_attempts)
        security_service.failed_login_attempts.clear()

    return {
        "message": f"Cleared {cleared_count} failed login attempts",
        "cleared_count": cleared_count,
        "cleared_by": current_user.username,
    }


@router.get("/threat-patterns")
async def get_threat_patterns(
    current_user: User = Depends(require_admin),
):
    """
    Get configured threat detection patterns

    Returns the security patterns used for threat detection.
    """
    return {
        "threat_patterns": security_service.suspicious_patterns,
        "pattern_count": sum(len(patterns) for patterns in security_service.suspicious_patterns.values()),
        "threat_types": list(security_service.suspicious_patterns.keys()),
    }


@router.post("/test-threat-detection")
async def test_threat_detection(
    test_input: str = Query(..., description="Input string to test for threats"),
    threat_type: Optional[str] = Query(
        None, description="Specific threat type to test (sql_injection, xss, etc.)"
    ),
    current_user: User = Depends(require_admin),
):
    """
    Test threat detection patterns

    Useful for validating that threat detection is working correctly.
    """
    test_results = []

    if threat_type:
        if threat_type not in security_service.suspicious_patterns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown threat type: {threat_type}",
            )

        patterns = security_service.suspicious_patterns[threat_type]
        for pattern in patterns:
            match = re.search(pattern, test_input, re.IGNORECASE)
            test_results.append({
                "threat_type": threat_type,
                "pattern": pattern,
                "matched": match is not None,
                "match_details": match.group(0) if match else None,
            })
    else:
        # Test all threat types
        for threat_type_name, patterns in security_service.suspicious_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, test_input, re.IGNORECASE)
                if match:
                    test_results.append({
                        "threat_type": threat_type_name,
                        "pattern": pattern,
                        "matched": True,
                        "match_details": match.group(0),
                    })

    return {
        "test_input": test_input,
        "threats_detected": len(test_results) > 0,
        "detection_results": test_results,
        "total_patterns_tested": sum(
            len(patterns) for patterns in security_service.suspicious_patterns.values()
        ),
    }