from django.contrib import admin

from firstbrief.configuration.models import MessageGroup, MessageType, PrimaryMessageGroup, Site

admin.site.register((Site, PrimaryMessageGroup, MessageGroup, MessageType))
