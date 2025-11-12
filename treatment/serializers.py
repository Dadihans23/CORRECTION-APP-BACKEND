from rest_framework import serializers
from rest_framework import serializers
from .models import CorrectionHistory , ChatMessage , ChatSession
# backend/serializers.py
from rest_framework import serializers
from .models import ChatSession, ChatMessage , ImageCorrection , SiteSettings







class ProcessImageSerializer(serializers.Serializer):
    image = serializers.ImageField()
    context = serializers.JSONField(required=False)

class SolutionSerializer(serializers.Serializer):
    result = serializers.CharField()
    steps = serializers.ListField(child=serializers.CharField())
    
    

        

class CorrectionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CorrectionHistory
        fields = '__all__'        
        



class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'created_at', 'gemini_response_time']
        read_only_fields = ['created_at', 'gemini_response_time']

class ChatSessionListSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    message_count = serializers.IntegerField(source='messages.count', read_only=True)

    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'updated_at', 'message_count', 'last_message']

    def get_last_message(self, obj):
        last = obj.messages.last()
        return ChatMessageSerializer(last).data if last else None

class ChatSessionDetailSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages']
        
        
        
        



class ImageCorrectionSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ImageCorrection
        fields = [
            'id', 'domaine', 'niveau', 'type_exercice', 'attente',
            'infos_complementaires', 'correction_text',
            'created_at', 'image_url'
        ]
        read_only_fields = ['created_at', 'image_url']

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None        
    

class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = [
            'site_name',
            'maintenance_mode',
            'allow_registrations',
            'support_email',
            'support_whatsapp',
            'support_phone',
            'support_facebook',
            'support_instagram',
            'timezone',
            'default_language',
            'primary_color',
            'updated_at'
        ]
    