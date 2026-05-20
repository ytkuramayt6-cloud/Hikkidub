from django.urls import path, register_converter
from django.contrib.auth import views as auth_views
from . import views
from . import converters

register_converter(converters.FourDigitYearConverter, "year4")


urlpatterns = [
    path('', views.index, name='index'),
    path('anime/<int:anime_id>/', views.categories),
    path('anime/<slug:anime_slug>/', views.categories_by_slug),
    path('player/', views.player, name='player'),
    path('login/', auth_views.LoginView.as_view(template_name='hikkiinfo/auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
]