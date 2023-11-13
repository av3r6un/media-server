from django.urls import path
from . import views

urlpatterns = [
	path('', views.authorize, name='auth-authorize'),
	path('get-me/', views.get_me, name='auth-getme'),
	path('refresh/', views.refresh, name='auth-refresh'),
	path('new/', views.new_user, name='auth-new-user'),
]
