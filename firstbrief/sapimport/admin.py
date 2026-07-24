from django.contrib import admin

from firstbrief.sapimport.models import ImportBatch, ImportChange

admin.site.register(ImportBatch)
admin.site.register(ImportChange)
