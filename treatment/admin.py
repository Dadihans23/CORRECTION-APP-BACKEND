
# Register your models here.
from django.contrib import admin
from .models import CorrectionHistory , ChatMessage , ChatSession , ImageCorrection

admin.site.register(CorrectionHistory)
admin.site.register(ChatMessage)
admin.site.register(ChatSession)
admin.site.register(ImageCorrection)



