from rest_framework import serializers
from .models import ExerciseProcessing
from rest_framework import serializers
from .models import CorrectionHistory

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