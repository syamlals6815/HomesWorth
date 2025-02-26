from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
from datetime import timedelta  # This is needed for timedelta usage

class FreeUserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='free_user_profile')
    credits = models.IntegerField(default=300)
    subscription_status = models.CharField(max_length=50, default="Free User")
    trial_count = models.PositiveIntegerField(default=0)
    subscription_expiry = models.DateTimeField(null=True, blank=True)
    current_plan = models.CharField(max_length=50, default="No Plan")

    def can_use_free_trial(self):
        """Check if the user has remaining free trials."""
        return self.trial_count < 3

    def use_free_trial(self):
        """Deduct credits and increment trial count."""
        if self.can_use_free_trial():
            self.trial_count += 1
            self.credits = max(300 - (self.trial_count * 100), 0)
            self.save()
            return True
        return False

    def is_active_subscriber(self):
        """Check if the user has an active subscription."""
        return self.subscription_expiry and now() < self.subscription_expiry

    def set_subscription_expiry(self, plan):
        """Calculate and set subscription expiry date based on plan."""
        plan_duration_map = {
            '1 Month': 30,
            '3 Months': 90,
            '6 Months': 180,
        }
        if plan in plan_duration_map:
            self.subscription_expiry = now() + timedelta(days=plan_duration_map[plan])
            self.save()
