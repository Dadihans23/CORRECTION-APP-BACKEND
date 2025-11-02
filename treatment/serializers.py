from rest_framework import serializers
from .models import ExerciseProcessing
from rest_framework import serializers
from .models import CorrectionHistory , ChatMessage , ChatSession
# backend/serializers.py
from rest_framework import serializers
from .models import ChatSession, ChatMessage





class ProcessImageSerializer(serializers.Serializer):
    image = serializers.ImageField()
    context = serializers.JSONField(required=False)

class SolutionSerializer(serializers.Serializer):
    result = serializers.CharField()
    steps = serializers.ListField(child=serializers.CharField())
    
    

class ExerciseProcessingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseProcessing
        fields = ['id', 'user', 'image', 'extracted_text', 'solution', 'context', 'created_at']
        

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