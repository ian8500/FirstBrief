from django.contrib import admin

from firstbrief.configuration.models import (
    EmailDistribution,
    MessageGroup,
    MessageGroupType,
    MessageSubType,
    MessageType,
    PrimaryMessageGroup,
    Sector,
    Site,
)

admin.site.register(
    (
        Site,
        PrimaryMessageGroup,
        MessageGroupType,
        MessageGroup,
        MessageType,
        MessageSubType,
        Sector,
        EmailDistribution,
    )
)
