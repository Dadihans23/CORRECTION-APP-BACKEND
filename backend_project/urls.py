"""backend_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from custom_admin.views import landing_page


# ─── Handlers d'erreur personnalisés ───
def handler404_view(request, _exception=None):
    return render(request, '404.html', status=404)

def handler403_view(request, _exception=None):
    return render(request, '403.html', status=403)

def handler500_view(request):
    return render(request, '404.html', status=500)

handler404 = handler404_view
handler403 = handler403_view
handler500 = handler500_view


urlpatterns = [
    path('landing/', landing_page, name='landing'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentification.urls')),
    path('api/treatment/', include('treatment.urls')),
    path('api/subscription/', include('subscriptions.urls')),
    path('custom-admin/', include('custom_admin.urls')),
    path('api/classes/', include('classes.urls')),
]


# SERVIR MEDIA EN DÉVELOPPEMENT
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




