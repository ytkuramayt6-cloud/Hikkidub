from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from django.db import transaction
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import messages
import os
import shutil
from datetime import datetime
from pathlib import Path
from .models import (
    Genre, Anime, Episode, VideoQuality, 
    VoiceActor, Character, DatabaseBackup
)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'anime_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def anime_count(self, obj):
        count = obj.anime.count()
        if count > 0:
            url = reverse('admin:hikkiinfo_anime_changelist') + f'?genres__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    anime_count.short_description = 'Количество аниме'


class VideoQualityInline(admin.TabularInline):
    model = VideoQuality
    extra = 1
    fields = ['quality', 'video_url', 'file_size', 'is_active']
    ordering = ['-quality']


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ['episode_info', 'anime_link', 'duration', 'is_published', 
                    'views_count', 'release_date', 'created_at']
    list_filter = ['is_published', 'release_date', 'created_at', 'anime']
    search_fields = ['title', 'anime__title', 'number']
    list_editable = ['is_published']
    readonly_fields = ['views_count', 'created_at', 'updated_at']
    inlines = [VideoQualityInline]
    date_hierarchy = 'release_date'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('anime', 'number', 'title', 'description', 'duration')
        }),
        ('Публикация', {
            'fields': ('is_published', 'release_date', 'views_count')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def episode_info(self, obj):
        return f"Эпизод {obj.number}" + (f": {obj.title}" if obj.title else "")
    episode_info.short_description = 'Эпизод'

    def anime_link(self, obj):
        url = reverse('admin:hikkiinfo_anime_change', args=[obj.anime.pk])
        return format_html('<a href="{}">{}</a>', url, obj.anime.title)
    anime_link.short_description = 'Аниме'

    actions = ['publish_episodes', 'unpublish_episodes', 'recalculate_views']

    def publish_episodes(self, request, queryset):
        updated = queryset.update(is_published=True)
        # Автоматически обновляем статусы связанных аниме
        anime_ids = queryset.values_list('anime_id', flat=True).distinct()
        for anime_id in anime_ids:
            anime = Anime.objects.get(pk=anime_id)
            published_count = anime.episodes.filter(is_published=True).count()
            if published_count == anime.total_episodes and anime.total_episodes > 0:
                anime.status = 'completed'
            elif published_count > 0:
                anime.status = 'ongoing'
            anime.save()
        self.message_user(request, f'{updated} эпизодов опубликовано.')
    publish_episodes.short_description = 'Опубликовать выбранные эпизоды'

    def unpublish_episodes(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} эпизодов снято с публикации.')
    unpublish_episodes.short_description = 'Снять с публикации выбранные эпизоды'

    def recalculate_views(self, request, queryset):
        anime_ids = queryset.values_list('anime_id', flat=True).distinct()
        updated_count = 0
        for anime_id in anime_ids:
            anime = Anime.objects.get(pk=anime_id)
            total_views = anime.episodes.aggregate(total=Sum('views_count'))['total'] or 0
            if anime.views_count != total_views:
                anime.views_count = total_views
                anime.save(update_fields=['views_count'])
                updated_count += 1
        self.message_user(request, f'Просмотры пересчитаны для {updated_count} аниме.')
    recalculate_views.short_description = 'Пересчитать просмотры аниме'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Автоматически обновляем счетчики аниме
        if obj.anime:
            obj.anime.total_episodes = obj.anime.episodes.count()
            obj.anime.views_count = obj.anime.episodes.aggregate(
                total=Sum('views_count')
            )['total'] or 0
            obj.anime.save(update_fields=['total_episodes', 'views_count'])


class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 1
    fields = ['number', 'title', 'is_published', 'release_date']
    ordering = ['number']


class CharacterInline(admin.TabularInline):
    model = Character
    extra = 1
    fields = ['name', 'name_original', 'voice_actor']


@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin):
    list_display = ['poster_thumbnail', 'title', 'status_badge', 'release_date', 
                    'rating', 'episodes_info', 'views_count', 'is_featured', 'created_at']
    list_filter = ['status', 'is_featured', 'release_date', 'genres', 'created_at']
    search_fields = ['title', 'title_original', 'description']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['views_count', 'created_at', 'updated_at', 'poster_preview']
    filter_horizontal = ['genres']
    inlines = [EpisodeInline, CharacterInline]
    date_hierarchy = 'release_date'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'title_original', 'slug', 'description', 'poster', 'poster_preview')
        }),
        ('Детали', {
            'fields': ('release_date', 'status', 'genres', 'rating', 
                      'duration_per_episode', 'total_episodes')
        }),
        ('Настройки', {
            'fields': ('is_featured', 'views_count')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def poster_thumbnail(self, obj):
        if obj.poster:
            return format_html(
                '<img src="{}" width="50" height="70" style="object-fit: cover; border-radius: 4px;" />',
                obj.poster.url
            )
        return "—"
    poster_thumbnail.short_description = 'Постер'

    def poster_preview(self, obj):
        if obj.poster:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 400px; border-radius: 8px;" />',
                obj.poster.url
            )
        return "Постер не загружен"
    poster_preview.short_description = 'Предпросмотр постера'

    def status_badge(self, obj):
        colors = {
            'ongoing': '#4caf50',
            'completed': '#2196f3',
            'planned': '#ff9800',
            'on_hold': '#9e9e9e',
            'cancelled': '#f44336',
        }
        color = colors.get(obj.status, '#9e9e9e')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def episodes_info(self, obj):
        completed = obj.completed_episodes_count
        total = obj.total_episodes
        if total > 0:
            percentage = int((completed / total) * 100)
            color = '#4caf50' if percentage == 100 else '#ff9800'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}/{} ({}%)</span>',
                color, completed, total, percentage
            )
        return f"{completed} эпизодов"
    episodes_info.short_description = 'Эпизоды'

    actions = ['mark_as_featured', 'mark_as_not_featured', 'mark_as_completed', 
               'mark_as_ongoing', 'recalculate_total_episodes', 'sync_episodes_count']

    def mark_as_featured(self, request, queryset):
        # Автоматически ограничиваем количество рекомендуемых
        featured_count = Anime.objects.filter(is_featured=True).exclude(
            pk__in=queryset.values_list('pk', flat=True)
        ).count()
        new_featured = len(queryset)
        
        if featured_count + new_featured > 10:
            # Убираем старые из рекомендуемых
            excess = (featured_count + new_featured) - 10
            oldest_featured = Anime.objects.filter(
                is_featured=True
            ).exclude(pk__in=queryset.values_list('pk', flat=True)).order_by('created_at')[:excess]
            Anime.objects.filter(pk__in=[a.pk for a in oldest_featured]).update(is_featured=False)
        
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} аниме отмечено как рекомендуемое.')
    mark_as_featured.short_description = 'Отметить как рекомендуемое'

    def mark_as_not_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} аниме убрано из рекомендуемых.')
    mark_as_not_featured.short_description = 'Убрать из рекомендуемых'

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} аниме отмечено как завершенное.')
    mark_as_completed.short_description = 'Отметить как завершенное'

    def mark_as_ongoing(self, request, queryset):
        updated = queryset.update(status='ongoing')
        self.message_user(request, f'{updated} аниме отмечено как в процессе.')
    mark_as_ongoing.short_description = 'Отметить как в процессе'

    def recalculate_total_episodes(self, request, queryset):
        updated_count = 0
        with transaction.atomic():
            for anime in queryset:
                actual_count = anime.episodes.count()
                if anime.total_episodes != actual_count:
                    anime.total_episodes = actual_count
                    anime.save(update_fields=['total_episodes'])
                    updated_count += 1
        self.message_user(request, f'Количество эпизодов пересчитано для {updated_count} аниме.')
    recalculate_total_episodes.short_description = 'Пересчитать количество эпизодов'

    def sync_episodes_count(self, request, queryset):
        updated_count = 0
        with transaction.atomic():
            for anime in queryset:
                # Пересчитываем total_episodes
                anime.total_episodes = anime.episodes.count()
                
                # Пересчитываем views_count
                total_views = anime.episodes.aggregate(
                    total=Sum('views_count')
                )['total'] or 0
                anime.views_count = total_views
                
                # Автоматически обновляем статус
                published_count = anime.episodes.filter(is_published=True).count()
                if published_count == anime.total_episodes and anime.total_episodes > 0:
                    anime.status = 'completed'
                elif published_count > 0 and published_count < anime.total_episodes:
                    anime.status = 'ongoing'
                
                anime.save()
                updated_count += 1
        self.message_user(request, f'Синхронизация выполнена для {updated_count} аниме.')
    sync_episodes_count.short_description = 'Синхронизировать все счетчики'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Автоматически синхронизируем счетчики
        if change:  # Только при изменении, не при создании
            obj.total_episodes = obj.episodes.count()
            obj.views_count = obj.episodes.aggregate(
                total=Sum('views_count')
            )['total'] or 0
            obj.save(update_fields=['total_episodes', 'views_count'])


@admin.register(VideoQuality)
class VideoQualityAdmin(admin.ModelAdmin):
    list_display = ['episode_link', 'quality', 'video_url_short', 'file_size', 
                    'is_active', 'created_at']
    list_filter = ['quality', 'is_active', 'created_at']
    search_fields = ['episode__anime__title', 'episode__title', 'video_url']
    list_editable = ['is_active']
    readonly_fields = ['created_at']
    actions = ['activate_all_qualities', 'deactivate_all_qualities', 'activate_highest_quality']

    def episode_link(self, obj):
        url = reverse('admin:hikkiinfo_episode_change', args=[obj.episode.pk])
        return format_html('<a href="{}">{}</a>', url, str(obj.episode))
    episode_link.short_description = 'Эпизод'

    def video_url_short(self, obj):
        if len(obj.video_url) > 50:
            return obj.video_url[:47] + '...'
        return obj.video_url
    video_url_short.short_description = 'URL видео'

    def activate_all_qualities(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} качеств активировано.')
    activate_all_qualities.short_description = 'Активировать выбранные качества'

    def deactivate_all_qualities(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} качеств деактивировано.')
    deactivate_all_qualities.short_description = 'Деактивировать выбранные качества'

    def activate_highest_quality(self, request, queryset):
        episode_ids = queryset.values_list('episode_id', flat=True).distinct()
        activated_count = 0
        
        quality_order = {'480p': 1, '720p': 2, '1080p': 3, '2160p': 4}
        
        for episode_id in episode_ids:
            # Деактивируем все качества для этого эпизода
            VideoQuality.objects.filter(episode_id=episode_id).update(is_active=False)
            
            # Находим и активируем самое высокое качество
            qualities = VideoQuality.objects.filter(episode_id=episode_id)
            if qualities.exists():
                highest = max(qualities, key=lambda q: quality_order.get(q.quality, 0))
                highest.is_active = True
                highest.save(update_fields=['is_active'])
                activated_count += 1
        
        self.message_user(request, f'Самое высокое качество активировано для {activated_count} эпизодов.')
    activate_highest_quality.short_description = 'Активировать самое высокое качество'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Автоматически активируем самое высокое качество если создано новое
        if not change and obj.is_active:
            quality_order = {'480p': 1, '720p': 2, '1080p': 3, '2160p': 4}
            all_qualities = VideoQuality.objects.filter(episode=obj.episode)
            if all_qualities.exists():
                highest = max(all_qualities, key=lambda q: quality_order.get(q.quality, 0))
                VideoQuality.objects.filter(episode=obj.episode).exclude(pk=highest.pk).update(is_active=False)
                VideoQuality.objects.filter(pk=highest.pk).update(is_active=True)


@admin.register(VoiceActor)
class VoiceActorAdmin(admin.ModelAdmin):
    list_display = ['photo_thumbnail', 'name', 'characters_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'bio']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at', 'photo_preview']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'bio', 'photo', 'photo_preview')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def photo_thumbnail(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="40" height="40" style="object-fit: cover; border-radius: 50%;" />',
                obj.photo.url
            )
        return "—"
    photo_thumbnail.short_description = 'Фото'

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 8px;" />',
                obj.photo.url
            )
        return "Фото не загружено"
    photo_preview.short_description = 'Предпросмотр фото'

    def characters_count(self, obj):
        count = obj.characters.count()
        if count > 0:
            url = reverse('admin:hikkiinfo_character_changelist') + f'?voice_actor__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    characters_count.short_description = 'Персонажей'


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ['name', 'anime_link', 'voice_actor_link', 'created_at']
    list_filter = ['anime', 'voice_actor', 'created_at']
    search_fields = ['name', 'name_original', 'anime__title', 'description']
    readonly_fields = ['created_at', 'photo_preview']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'name_original', 'anime', 'voice_actor', 'description', 
                      'photo', 'photo_preview')
        }),
        ('Метаданные', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def anime_link(self, obj):
        url = reverse('admin:hikkiinfo_anime_change', args=[obj.anime.pk])
        return format_html('<a href="{}">{}</a>', url, obj.anime.title)
    anime_link.short_description = 'Аниме'

    def voice_actor_link(self, obj):
        if obj.voice_actor:
            url = reverse('admin:hikkiinfo_voiceactor_change', args=[obj.voice_actor.pk])
            return format_html('<a href="{}">{}</a>', url, obj.voice_actor.name)
        return "—"
    voice_actor_link.short_description = 'Актер озвучки'

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 8px;" />',
                obj.photo.url
            )
        return "Фото не загружено"
    photo_preview.short_description = 'Предпросмотр фото'


@admin.register(DatabaseBackup)
class DatabaseBackupAdmin(admin.ModelAdmin):
    list_display = ['name', 'file_size_display', 'created_at', 'created_by', 'backup_actions']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['file_path', 'file_size', 'created_at', 'created_by', 'file_size_display']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description')
        }),
        ('Детали файла', {
            'fields': ('file_path', 'file_size_display', 'file_size', 'created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['restore_backup', 'delete_backup_files']
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_create_backup'] = True
        extra_context['create_backup_url'] = reverse('create_backup')
        return super().changelist_view(request, extra_context=extra_context)
    
    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = 'Размер файла'
    
    def backup_actions(self, obj):
        restore_url = reverse('restore_backup', args=[obj.pk])
        download_url = reverse('download_backup', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="margin-right: 5px; background-color: #417690; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Восстановить</a>'
            '<a class="button" href="{}" style="background-color: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Скачать</a>',
            restore_url, download_url
        )
    backup_actions.short_description = 'Действия'
    
    def restore_backup(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Пожалуйста, выберите ровно один бэкап для восстановления.', level=messages.ERROR)
            return
        
        backup = queryset.first()
        try:
            # Закрываем все соединения с БД
            from django.db import connections
            for conn in connections.all():
                conn.close()
            
            # Получаем путь к текущей БД
            db_path = settings.DATABASES['default']['NAME']
            # Преобразуем Path объект в строку если необходимо
            if isinstance(db_path, Path):
                db_path = str(db_path)
            backup_path = backup.file_path
            
            # Проверяем существование файла бэкапа
            if not os.path.exists(backup_path):
                self.message_user(request, f'Файл бэкапа не найден: {backup_path}', level=messages.ERROR)
                return
            
            # Создаем резервную копию текущей БД перед восстановлением
            current_backup_path = str(db_path) + f'.pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            if os.path.exists(db_path):
                shutil.copy2(db_path, current_backup_path)
            
            # Восстанавливаем БД
            shutil.copy2(backup_path, db_path)
            
            self.message_user(
                request, 
                f'База данных успешно восстановлена из бэкапа "{backup.name}". '
                f'Текущая БД сохранена как: {current_backup_path}',
                level=messages.SUCCESS
            )
        except Exception as e:
            self.message_user(request, f'Ошибка при восстановлении: {str(e)}', level=messages.ERROR)
    restore_backup.short_description = 'Восстановить базу данных из выбранных бэкапов'
    
    def delete_backup_files(self, request, queryset):
        deleted_count = 0
        errors = []
        
        for backup in queryset:
            try:
                if os.path.exists(backup.file_path):
                    os.remove(backup.file_path)
                backup.delete()
                deleted_count += 1
            except Exception as e:
                errors.append(f'{backup.name}: {str(e)}')
        
        if deleted_count > 0:
            self.message_user(request, f'Удалено {deleted_count} бэкапов.')
        if errors:
            self.message_user(request, f'Ошибки при удалении: {"; ".join(errors)}', level=messages.ERROR)
    delete_backup_files.short_description = 'Удалить выбранные бэкапы и их файлы'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user.username if request.user.is_authenticated else 'system'
        super().save_model(request, obj, form, change)


def create_database_backup(request):
    try:
        # Получаем путь к БД
        db_path = settings.DATABASES['default']['NAME']
        # Преобразуем Path объект в строку если необходимо
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        if not os.path.exists(db_path):
            messages.error(request, 'Файл базы данных не найден.')
            return HttpResponseRedirect(reverse('admin:hikkiinfo_databasebackup_changelist'))
        
        # Создаем директорию для бэкапов если её нет
        backups_dir = Path(settings.BASE_DIR) / 'backups'
        backups_dir.mkdir(exist_ok=True)
        
        # Генерируем имя файла с timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'db_backup_{timestamp}.sqlite3'
        backup_path = backups_dir / backup_filename
        
        # Закрываем соединения с БД перед копированием
        from django.db import connections
        for conn in connections.all():
            conn.close()
        
        # Копируем файл БД
        shutil.copy2(db_path, str(backup_path))
        
        # Получаем размер файла
        file_size = os.path.getsize(str(backup_path))
        
        # Создаем запись в БД
        backup = DatabaseBackup.objects.create(
            name=f'Резервная копия от {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}',
            file_path=str(backup_path),
            file_size=file_size,
            description=f'Автоматически созданная резервная копия',
            created_by=request.user.username if request.user.is_authenticated else 'system'
        )
        
        messages.success(
            request, 
            f'Резервная копия успешно создана: {backup.name} ({backup.get_file_size_display()})'
        )
    except Exception as e:
        messages.error(request, f'Ошибка при создании резервной копии: {str(e)}')
    
    return HttpResponseRedirect(reverse('admin:hikkiinfo_databasebackup_changelist'))


def restore_backup_view(request, backup_id):
    try:
        backup = DatabaseBackup.objects.get(pk=backup_id)
        
        # Закрываем все соединения с БД
        from django.db import connections
        for conn in connections.all():
            conn.close()
        
        # Получаем путь к текущей БД
        db_path = settings.DATABASES['default']['NAME']
        # Преобразуем Path объект в строку если необходимо
        if isinstance(db_path, Path):
            db_path = str(db_path)
        backup_path = backup.file_path
        
        # Проверяем существование файла бэкапа
        if not os.path.exists(backup_path):
            messages.error(request, f'Файл бэкапа не найден: {backup_path}')
            return HttpResponseRedirect(reverse('admin:hikkiinfo_databasebackup_changelist'))
        
        # Создаем резервную копию текущей БД перед восстановлением
        current_backup_path = str(db_path) + f'.pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        if os.path.exists(db_path):
            shutil.copy2(db_path, current_backup_path)
        
        # Восстанавливаем БД
        shutil.copy2(backup_path, db_path)
        
        messages.success(
            request,
            f'База данных успешно восстановлена из бэкапа "{backup.name}". '
            f'Текущая БД сохранена как: {os.path.basename(current_backup_path)}'
        )
    except DatabaseBackup.DoesNotExist:
        messages.error(request, 'Резервная копия не найдена.')
    except Exception as e:
        messages.error(request, f'Ошибка при восстановлении: {str(e)}')
    
    return HttpResponseRedirect(reverse('admin:hikkiinfo_databasebackup_changelist'))


def download_backup_view(request, backup_id):
    try:
        backup = DatabaseBackup.objects.get(pk=backup_id)
        
        if not os.path.exists(backup.file_path):
            messages.error(request, 'Файл бэкапа не найден.')
            return HttpResponseRedirect(reverse('admin:hikkiinfo_databasebackup_changelist'))
        
        with open(backup.file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/x-sqlite3')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(backup.file_path)}"'
            return response
    except DatabaseBackup.DoesNotExist:
        messages.error(request, 'Резервная копия не найдена.')
        return HttpResponseRedirect(reverse('admin:hikkiinfo_databasebackup_changelist'))


# Настройка заголовков админ-панели
admin.site.site_header = "HikkiDub - Администрирование"
admin.site.site_title = "HikkiDub Admin"
admin.site.index_title = "Панель управления базой данных"
