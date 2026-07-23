from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from apps.profiles.models import Preference, Profile
from apps.users.models import User

from .services import eligible_profiles


class ReciprocalProfileVisibilityTests(TestCase):
    def make_user(self, phone, name, gender, interested_in, city="Lahore"):
        user = User.objects.create_user(
            email=f"{phone.lstrip('+')}@example.com",
            password="StrongPass123!",
            phone=phone,
            otp_verified=True,
        )
        profile = Profile.objects.create(
            user=user,
            name=name,
            gender=gender,
            dob=date(1995, 1, 1),
            city=city,
            country="Pakistan",
            sect_maslak="sunni",
            education="Bachelors",
            marital_status="never_married",
            is_muslim_confirmed=True,
        )
        Preference.objects.create(user=user, interested_in=interested_in, age_range_min=20, age_range_max=45)
        return user, profile

    def setUp(self):
        self.viewer, self.viewer_profile = self.make_user("+920000000001", "Viewer", "male", "female")
        self.compatible, self.compatible_profile = self.make_user("+920000000002", "Compatible", "female", "male")
        self.wrong_gender, self.wrong_gender_profile = self.make_user("+920000000003", "Wrong gender", "male", "female")
        self.not_interested, self.not_interested_profile = self.make_user("+920000000004", "Not interested", "female", "female")

    def test_only_reciprocally_compatible_gender_is_visible(self):
        visible_ids = set(eligible_profiles(self.viewer).values_list("pk", flat=True))
        self.assertEqual(visible_ids, {self.compatible_profile.pk})

    def test_runtime_filter_cannot_select_own_gender(self):
        client = APIClient()
        client.force_authenticate(self.viewer)
        response = client.post("/api/matches/filter", {"interested_in": "male"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_incompatible_direct_profile_is_hidden(self):
        client = APIClient()
        client.force_authenticate(self.viewer)
        response = client.get(f"/api/profile/{self.not_interested_profile.pk}")
        self.assertEqual(response.status_code, 404)

    def test_match_request_requires_reciprocal_visibility(self):
        client = APIClient()
        client.force_authenticate(self.viewer)
        compatible = client.post(f"/api/matches/request/{self.compatible.pk}", format="json")
        incompatible = client.post(f"/api/matches/request/{self.not_interested.pk}", format="json")
        self.assertEqual(compatible.status_code, 201)
        self.assertEqual(incompatible.status_code, 400)
