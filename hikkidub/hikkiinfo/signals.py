"""
Сигналы: счётчики эпизодов/просмотров, статус аниме, активное качество видео,
лимит избранного (10), дата эпизода из аниме, slug по названию.
"""
from django.db.models import Sum
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Anime, Episode, VideoQuality

QUALITY_ORDER = {'480p': 1, '720p': 2, '1080p': 3, '2160p': 4}


def _highest_quality(queryset):
    return max(queryset, key=lambda q: QUALITY_ORDER.get(q.quality, 0))


@receiver(post_save, sender=Episode)
def update_anime_episodes_count(sender, instance, created, **kwargs):
    anime = instance.anime
    total_episodes = anime.episodes.count()
    if anime.total_episodes != total_episodes:
        Anime.objects.filter(pk=anime.pk).update(total_episodes=total_episodes)
    update_anime_status(anime)


@receiver(post_delete, sender=Episode)
def update_anime_episodes_count_on_delete(sender, instance, **kwargs):
    anime = instance.anime
    total_episodes = anime.episodes.count()
    if anime.total_episodes != total_episodes:
        Anime.objects.filter(pk=anime.pk).update(total_episodes=total_episodes)
    update_anime_status(anime)


@receiver(post_save, sender=Episode)
def update_anime_views_count(sender, instance, created, **kwargs):
    anime = instance.anime
    total_views = anime.episodes.aggregate(total=Sum('views_count'))['total'] or 0
    if anime.views_count != total_views:
        Anime.objects.filter(pk=anime.pk).update(views_count=total_views)


@receiver(post_save, sender=Episode)
def auto_update_anime_status(sender, instance, **kwargs):
    update_anime_status(instance.anime)


def update_anime_status(anime):
    if anime.total_episodes == 0:
        return
    published_count = anime.episodes.filter(is_published=True).count()
    if published_count == anime.total_episodes and anime.total_episodes > 0:
        if anime.status != 'completed':
            Anime.objects.filter(pk=anime.pk).update(status='completed')
    elif 0 < published_count < anime.total_episodes:
        if anime.status not in ('ongoing', 'completed'):
            Anime.objects.filter(pk=anime.pk).update(status='ongoing')


@receiver(post_save, sender=VideoQuality)
def activate_highest_quality(sender, instance, created, **kwargs):
    if not created:
        return
    episode = instance.episode
    qualities = episode.video_qualities.all()
    if not qualities.exists():
        return
    highest = _highest_quality(qualities)
    VideoQuality.objects.filter(episode=episode).update(is_active=False)
    VideoQuality.objects.filter(pk=highest.pk).update(is_active=True)


@receiver(post_delete, sender=VideoQuality)
def reactivate_quality_on_delete(sender, instance, **kwargs):
    if not instance.is_active:
        return
    episode = instance.episode
    remaining = episode.video_qualities.filter(is_active=False)
    if remaining.exists():
        highest = _highest_quality(remaining)
        VideoQuality.objects.filter(pk=highest.pk).update(is_active=True)


@receiver(post_save, sender=Anime)
def update_featured_anime_limit(sender, instance, created, **kwargs):
    if not instance.is_featured:
        return
    featured_count = Anime.objects.filter(is_featured=True).count()
    if featured_count <= 10:
        return
    excess = featured_count - 10
    oldest = (
        Anime.objects.filter(is_featured=True)
        .exclude(pk=instance.pk)
        .order_by('created_at')[:excess]
    )
    Anime.objects.filter(pk__in=[a.pk for a in oldest]).update(is_featured=False)


@receiver(pre_save, sender=Episode)
def auto_set_release_date(sender, instance, **kwargs):
    if instance.release_date or not instance.anime_id:
        return
    try:
        anime = Anime.objects.get(pk=instance.anime_id)
        if anime.release_date:
            instance.release_date = anime.release_date
    except Anime.DoesNotExist:
        pass


@receiver(post_save, sender=Anime)
def update_anime_slug_if_title_changed(sender, instance, created, **kwargs):
    if created or not instance.slug:
        return
    expected_slug = slugify(instance.title)
    if instance.slug == expected_slug:
        return
    if not Anime.objects.filter(slug=expected_slug).exclude(pk=instance.pk).exists():
        Anime.objects.filter(pk=instance.pk).update(slug=expected_slug)
