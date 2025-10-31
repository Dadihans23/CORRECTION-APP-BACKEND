from django.contrib import admin
from .models import Subscription , Pack , UsageLog

# Register your models here.
admin.site.register(Subscription)
admin.site.register(Pack)
admin.site.register(UsageLog)
