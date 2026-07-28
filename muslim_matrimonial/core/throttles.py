from rest_framework.throttling import SimpleRateThrottle


class AnonIPThrottle(SimpleRateThrottle):
    """IP-based throttle for anonymous requests, rated by the view's `throttle_scope`."""

    scope_attr = "throttle_scope"

    def __init__(self):
        pass

    def allow_request(self, request, view):
        if request.user and request.user.is_authenticated:
            return True
        self.scope = getattr(view, self.scope_attr, None)
        if not self.scope:
            return True
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class AuthenticatedUserThrottle(SimpleRateThrottle):
    """User ID-based throttle for authenticated requests, rated by the view's `throttle_scope`."""

    scope_attr = "throttle_scope"

    def __init__(self):
        pass

    def allow_request(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return True
        self.scope = getattr(view, self.scope_attr, None)
        if not self.scope:
            return True
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class CombinedThrottle(SimpleRateThrottle):
    """
    Single throttle class applying the view's `throttle_scope` rate to both
    anonymous requests (keyed by IP) and authenticated requests (keyed by user id).
    """

    scope_attr = "throttle_scope"

    def __init__(self):
        pass

    def allow_request(self, request, view):
        self.scope = getattr(view, self.scope_attr, None)
        if not self.scope:
            return True
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
