from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpResponse
from .forms import RegisterForm


def index(request):
    return render(request, 'hikkiinfo/index.html')

def categories(request, anime_id):
    return HttpResponse(f"<h1>Жанры аниме<h1><p>id: {anime_id}</p>")

def categories_by_slug(request, anime_slug):
    return HttpResponse(f"<h1>Жанры аниме<h1><p>slug: {anime_slug}</p>")

def archive(request, year):
    return HttpResponse(f"<h1>Архив по годам</h1><p> {year} </p>")

def player(request):
    """Плеер: GET — video_url, video_title, episode_number, description, poster_url, duration, release_date."""
    video_url = request.GET.get('video_url', '/static/videos/sample.mp4')
    video_title = request.GET.get('video_title', 'Видео')
    episode_number = request.GET.get('episode_number', '1')
    description = request.GET.get('description', '')
    poster_url = request.GET.get('poster_url', '')
    duration = request.GET.get('duration', '24:00')
    release_date = request.GET.get('release_date', '2024')
    
    # Качества видео (пример данных)
    qualities = [
        {'value': '1080p', 'label': '1080p', 'url': video_url, 'active': True},
        {'value': '720p', 'label': '720p', 'url': video_url.replace('.mp4', '_720p.mp4'), 'active': False},
        {'value': '480p', 'label': '480p', 'url': video_url.replace('.mp4', '_480p.mp4'), 'active': False},
    ]
    
    # Список эпизодов (пример данных)
    current_episode = int(episode_number) if episode_number.isdigit() else 1
    episodes = []
    for i in range(1, 13):  # Пример: 12 эпизодов
        episodes.append({
            'number': i,
            'title': f'Эпизод {i}',
            'active': i == current_episode
        })
    
    context = {
        'video_url': video_url,
        'video_title': video_title,
        'episode_number': episode_number,
        'description': description,
        'poster_url': poster_url,
        'duration': duration,
        'release_date': release_date,
        'qualities': qualities,
        'episodes': episodes,
    }
    
    return render(request, 'hikkiinfo/player.html', context)


def register(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Аккаунт создан. Вы вошли в систему.")
            return redirect("profile")
        messages.error(request, "Исправьте ошибки в форме.")
    else:
        form = RegisterForm()

    return render(request, "hikkiinfo/auth/register.html", {"form": form})


@login_required
def profile(request):
    return render(request, "hikkiinfo/auth/profile.html")
