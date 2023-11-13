from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from django.views.static import serve
from . import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('auth/', include('authy.urls')),
    path('i/<path:path>', serve, {'document_root': '../storage/images'}),
    path('p/<path:path>', serve, {'document_root': '../storage/pics'}),
    path('f/<path:path>', static.file_serve),
    path('s/<path:path>/<str:filename>', static.subtitles_serve),
]
