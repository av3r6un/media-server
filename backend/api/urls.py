from django.urls import path
from . import views
from . import cac

urlpatterns = [
	path('search/', views.search, name='api-search'),
	path('all/', views.all_data, name='api-all'),
	path('user/', views.user_info, name='api-user-info'),
	path('user/queue', views.user_queue_info, name='api-user-queue'),
	path('user/queue/delete', views.clear_user_queue, name='api-clear-queue'),
	path('user/downloads', views.manage_user_downloads, name='api-user-downloads'),
	path('user/advice', views.send_advice, name='api-user-advice'),
	path('media/<str:uid>', views.media_info, name='api-media-info'),
	path('episode/<str:uid>', views.episode_info, name='api-episode-info'),
	path('voices/<str:media_type>', views.parse_voices, name='api-parse-voices'),
	path('meta/<str:media_type>/<str:imdb_id>', views.parse_meta, name='api-parse-meta'),
	path('meta/edit/<str:media_type>/<str:uid>', views.edit_meta, name='api-edit-meta'),
	path('download/', views.download, name='api-download'),
	path('watch/beacon', views.watch_beacon, name='api-watch-beacon'),
	path('mark-seen/<str:uid>', views.mark_media_seen, name='api-mark-seen'),
	path('cac/meta/<str:filename>', cac.gather_meta, name='api-cac-meta'),
	path('cac/queue/<int:queue_id>', cac.queue, name='api-cac-queue'),
	path('cac/download', cac.manage_download, name='api-cac-download'),
	path('<str:media_type>/', views.media_elements, name='api-media-elements'),
]


