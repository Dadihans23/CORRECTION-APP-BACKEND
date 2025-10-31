# backend/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Pack
from .serializer import PackSerializer
from rest_framework.permissions import IsAdminUser


class PackListCreateView(generics.ListCreateAPIView):
    """
    GET  : Récupère tous les packs actifs
    POST : Crée un nouveau pack (admin only)
    """
    
    queryset = Pack.objects.filter(is_active=True)
    serializer_class = PackSerializer
    permission_classes = [IsAuthenticated]    # Optionnel : admin seulement si tu veux

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            pack = serializer.save()
            return Response({
                'success': True,
                'message': 'Pack créé avec succès.',
                'data': PackSerializer(pack).data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'message': 'Erreur de validation.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'count': queryset.count(),
            'data': serializer.data
        })





