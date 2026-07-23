from django.contrib import admin

from firstbrief.notifications.models import (
    LifecycleJob,
    NotificationJob,
    NotificationPolicy,
    OutboxEvent,
)

admin.site.register((NotificationPolicy, OutboxEvent, LifecycleJob, NotificationJob))
