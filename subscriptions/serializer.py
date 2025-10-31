# backend/serializers.py
from rest_framework import serializers
from .models import Pack, Subscription, UsageLog

class PackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pack
        fields = [
            'id', 'name', 'slug', 'price', 'description', 'features',
            'image_corrections_limit', 'chat_questions_limit',
            'duration', 'is_best_plan', 'subscribers_count'
        ]
        read_only_fields = ['subscribers_count']

class SubscriptionSerializer(serializers.ModelSerializer):
    pack = PackSerializer(read_only=True)
    pack_id = serializers.IntegerField(write_only=True)
    remaining_images = serializers.IntegerField(source='image_corrections_remaining', read_only=True)
    remaining_questions = serializers.IntegerField(source='chat_questions_remaining', read_only=True)
    expired = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'pack', 'pack_id', 'token', 'api_key',
            'remaining_images', 'remaining_questions',
            'is_active', 'created_at', 'expires_at', 'expired'
        ]

    def get_expired(self, obj):
        return obj.is_expired()

    def create(self, validated_data):
        pack_id = validated_data.pop('pack_id')
        pack = Pack.objects.get(id=pack_id)
        subscription = Subscription.objects.create(pack=pack, **validated_data)
        return subscription