from django.contrib import admin

from firstbrief.messaging.models import (
    Approval,
    FileAsset,
    LifecycleCommand,
    Message,
    MessageAudienceRight,
    MessagePolicy,
    MessageStatusHistory,
    MessageVersion,
)

admin.site.register(
    (
        Message,
        MessageVersion,
        MessageAudienceRight,
        Approval,
        MessageStatusHistory,
        LifecycleCommand,
        FileAsset,
        MessagePolicy,
    )
)
