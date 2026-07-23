"""Rate-limited local authentication backend."""

from __future__ import annotations

import hashlib
from datetime import timedelta

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpRequest
from django.utils import timezone

from firstbrief.assurance.services import record_event
from firstbrief.identity.models import IdentityPolicy, User


class LocalAccountBackend(ModelBackend):
    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: object,
    ) -> User | None:
        if not username or password is None:
            return None
        policy = IdentityPolicy.load()
        remote_address = request.META.get("REMOTE_ADDR", "") if request else ""
        key_material = f"{remote_address}:{username.casefold()}".encode()
        key = "login:" + hashlib.sha256(key_material).hexdigest()
        attempts = int(cache.get(key, 0))
        if attempts >= policy.max_failed_logins * 3:
            return None
        cache.set(key, attempts + 1, timeout=300)
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            check_password(password, User().password)
            record_event("identity.login.failed", reason="unknown_account")
            return None
        now = timezone.now()
        if not user.local_auth_enabled or (user.locked_until and user.locked_until > now):
            record_event("identity.login.blocked", subject=user, reason="account_locked")
            return None
        if not user.check_password(password):
            user.failed_login_count += 1
            if user.failed_login_count >= policy.max_failed_logins:
                user.locked_until = now + timedelta(minutes=policy.lockout_minutes)
                recipients = [
                    value.strip()
                    for value in policy.account_lock_distribution_list.split(",")
                    if value.strip()
                ]
                if recipients:
                    send_mail(
                        "FirstBrief account locked",
                        f"Account {user.username} was locked. Contact an administrator.",
                        None,
                        recipients,
                    )
                action = "identity.account.locked"
            else:
                action = "identity.login.failed"
            user.save(update_fields=("failed_login_count", "locked_until"))
            record_event(action, subject=user)
            return None
        user.failed_login_count = 0
        user.locked_until = None
        if (
            user.password_changed_at
            and (now - user.password_changed_at).days >= policy.password_expiry_days
        ):
            user.must_change_password = True
        user.save(update_fields=("failed_login_count", "locked_until", "must_change_password"))
        cache.delete(key)
        record_event("identity.login.succeeded", actor=user, subject=user)
        return user
