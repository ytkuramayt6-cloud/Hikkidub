"""Корневые URL проекта HikkiDub."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from hikkiinfo import views
from hikkiinfo.admin import create_database_backup, restore_backup_view, download_backup_view


urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin/backup/create/', create_database_backup, name='create_backup'),
    path('admin/backup/<int:backup_id>/restore/', restore_backup_view, name='restore_backup'),
    path('admin/backup/<int:backup_id>/download/', download_backup_view, name='download_backup'),
    path('', include('hikkiinfo.urls')),
]

# Раздача медиафайлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

