from django.core.cache import cache
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.profiles.models import Profile
from core.utils import calculate_age, years_ago

SUGGESTION_TTL_SECONDS = 24 * 60 * 60


def _viewer_context(user):
    try:
        return user.profile, user.preference
    except (Profile.DoesNotExist, AttributeError):
        return None, None


def require_viewer_context(user):
    """Raise a clear 400 instead of letting callers silently get back an
    empty/rejected result when the viewer hasn't set up matching yet."""
    viewer_profile, preference = _viewer_context(user)
    if not viewer_profile or not preference:
        raise ValidationError("Set your match preferences before viewing or requesting matches.")
    return viewer_profile, preference


def _reciprocal_filters(viewer_profile):
    viewer_age = calculate_age(viewer_profile.dob)
    return (
        Q(user__preference__age_range_min__lte=viewer_age)
        & Q(user__preference__age_range_max__gte=viewer_age)
        & (Q(user__preference__city_pref__isnull=True) | Q(user__preference__city_pref="") | Q(user__preference__city_pref__iexact=viewer_profile.city))
        & (Q(user__preference__education_pref__isnull=True) | Q(user__preference__education_pref="") | Q(user__preference__education_pref__iexact=viewer_profile.education))
        & (Q(user__preference__sect_pref__isnull=True) | Q(user__preference__sect_pref="") | Q(user__preference__sect_pref=viewer_profile.sect_maslak))
    )


def eligible_profiles(user, filters=None):
    """Profiles satisfying both users' gender, interest, and preference filters."""
    viewer_profile, preference = _viewer_context(user)
    if not viewer_profile or not preference:
        return Profile.objects.none()

    selected = {
        "interested_in": preference.interested_in,
        "age_range_min": preference.age_range_min,
        "age_range_max": preference.age_range_max,
        "city_pref": preference.city_pref,
        "education_pref": preference.education_pref,
        "sect_pref": preference.sect_pref,
    }
    selected.update({key: value for key, value in (filters or {}).items() if value not in (None, "")})

    queryset = (
        Profile.objects.select_related("user", "user__preference")
        .prefetch_related("photos")
        .filter(
            is_deleted=False,
            user__is_active=True,
            user__status="active",
            is_muslim_confirmed=True,
            gender=selected["interested_in"],
            user__preference__interested_in=viewer_profile.gender,
        )
        .exclude(user=user)
        .filter(_reciprocal_filters(viewer_profile))
    )

    minimum_age = selected["age_range_min"]
    maximum_age = selected["age_range_max"]
    queryset = queryset.filter(dob__gte=years_ago(maximum_age), dob__lte=years_ago(minimum_age))
    if selected.get("city_pref"):
        queryset = queryset.filter(city__iexact=selected["city_pref"])
    if selected.get("education_pref"):
        queryset = queryset.filter(education__iexact=selected["education_pref"])
    if selected.get("sect_pref"):
        queryset = queryset.filter(sect_maslak=selected["sect_pref"])
    return queryset.order_by("-updated_at")


def is_profile_visible_to(viewer, candidate_profile):
    return eligible_profiles(viewer).filter(pk=candidate_profile.pk).exists()


def suggestion_cache_key(user_id):
    return f"daily-suggestions:{user_id}"


def get_daily_suggestions(user, limit=10, refresh=False):
    """Return up to `limit` suggested profiles, evaluating eligible_profiles() exactly once.

    Cache hit: one query (pk__in=cached_ids) -- also revalidates that cached
    candidates are still eligible, since a profile can stop being eligible
    (deactivated, deleted, updated preferences) during the 24h cache TTL.
    Cache miss: one query (the sliced, prefetch-ready eligible_profiles()
    queryset itself), then the cache is populated from those same results --
    no separate values_list() query is needed to get the id list.
    """
    cache_key = suggestion_cache_key(user.pk)
    if not refresh:
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            profiles = eligible_profiles(user).filter(pk__in=cached_ids)
            by_id = {str(profile.pk): profile for profile in profiles}
            return [by_id[str(profile_id)] for profile_id in cached_ids if str(profile_id) in by_id]

    profiles = list(eligible_profiles(user)[:limit])
    cache.set(cache_key, [str(profile.pk) for profile in profiles], SUGGESTION_TTL_SECONDS)
    return profiles
