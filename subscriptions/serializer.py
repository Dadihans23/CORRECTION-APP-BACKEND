# backend/serializers.py
from rest_framework import serializers
from .models import Pack, Subscription, UsageLog , Transaction

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
    # ← NOUVEAUX CHAMPS
    image_limit = serializers.IntegerField(source='pack.image_corrections_limit', read_only=True)
    question_limit = serializers.IntegerField(source='pack.chat_questions_limit', read_only=True)
    expired = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'pack', 'pack_id', 'token', 'api_key',
            'remaining_images', 'remaining_questions',
            'image_limit', 'question_limit',  # ← Ajoutés
            'is_active', 'created_at', 'expires_at', 'expired'
        ]

    def get_expired(self, obj):
        return obj.is_expired()


    def create(self, validated_data):
        pack_id = validated_data.pop('pack_id')
        pack = Pack.objects.get(id=pack_id)
        subscription = Subscription.objects.create(pack=pack, **validated_data)
        return subscription



# backend/serializers.py
class TransactionSerializer(serializers.ModelSerializer):
    pack = PackSerializer(read_only=True)
    previous_pack = PackSerializer(read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'pack', 'previous_pack',
            'transaction_type', 'transaction_type_display',
            'price_paid', 'created_at'
        ]