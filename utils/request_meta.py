from ipware import get_client_ip as _ipware_get_client_ip
from user_agents import parse as parse_ua


def get_client_ip(request):
    ip, is_routable = _ipware_get_client_ip(request)
    return ip


def parse_user_agent(request):
    raw = request.META.get("HTTP_USER_AGENT", "")
    ua = parse_ua(raw)
    if ua.is_mobile:
        device_type = "mobile"
    elif ua.is_tablet:
        device_type = "tablet"
    elif ua.is_pc:
        device_type = "desktop"
    else:
        device_type = "other"
    return {
        "raw": raw[:500],
        "browser": f"{ua.browser.family} {ua.browser.version_string}".strip(),
        "os": f"{ua.os.family} {ua.os.version_string}".strip(),
        "device_type": device_type,
    }
