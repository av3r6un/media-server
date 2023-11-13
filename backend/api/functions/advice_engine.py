from api.models import Episodes, MediaElements
from authy.models import Users


class AdviceEngine:
	def __init__(self, user: Users):
		self.user = user
		self.suggestion = {'id': 1}
		self.unwatched = self._detect_unwatched()
		self.new = self._detect_recently_added()
		self.movies = self._detect_movies()
		self.tvs = self._detect_tvs()
		self._filter_suggestions()

	def _detect_unwatched(self):
		unwatched = []
		for watching in self.user.watching:
			if not watching.seen and not watching.hidden:
				watch_id = watching.episode_uid if watching.episode_uid else watching.media_uid
				info = watch_id.advice(self.user.uid)
				info['w_uid'] = watching.uid
				unwatched.append(info)
		return unwatched

	def _detect_next(self, media):
		try:
			if media.media_uid:
				next_ = self._is_next_episode(media)
				if next_:
					return next_.short_info()
		except AttributeError:
			return None

	@staticmethod
	def _is_next_episode(m):
		next_ = Episodes.objects.filter(media_uid=m.media_uid, season=m.season, episode=m.episode + 1).first()
		if not next_:
			next_ = Episodes.objects.filter(media_uid=m.media_uid, season=m.season + 1, episode=m.episode).first()
		if not next_:
			return None
		if next_ and next_.meta:
			return next_

	def _detect_recently_added(self):
		recently_added = []
		seen_list = [w for w in self.user.watching if w.seen]
		for seen in seen_list:
			watch_id = seen.episode_uid if seen.episode_uid else seen.media_uid
			recently_added.append(self._detect_next(watch_id))
		return recently_added

	def _filter_suggestions(self):
		sorted_episodes = sorted([a for a in self.unwatched if a['type'] == 'episode'],
								  key=lambda x: (x['type'], x['season'], x['episode']))
		unique_movies = [a for a in self.unwatched if a['type'] == 'movie']
		unique_unwatched = []
		seen_media = set()
		for uw in sorted_episodes:
			if uw['media_uid'] not in seen_media:
				uw.pop('episode')
				uw.pop('season')
				unique_unwatched.append(uw)
				seen_media.add(uw['media_uid'])
				uw.pop('media_uid')
		unwatched_uids = [a['uid'] for a in unique_unwatched]
		self.suggestion = {
			'unwatched': unique_movies + unique_unwatched,
			'new': [a for a in self.new if a and a['uid'] not in unwatched_uids],
			'movies': self.movies, 'tvs': self.tvs
		}

	def _detect_movies(self):
		all_movies = MediaElements.objects.filter(media_type='movie').all()
		user_seen_movies = [m.media_uid.uid for m in self.user.watching if m.media_uid and m.seen]
		all_unseen = [a.small_info(self.user.uid) for a in all_movies if a.uid not in user_seen_movies]
		return all_unseen

	def _detect_tvs(self):
		all_tvs = MediaElements.objects.filter(media_type='tv').all()
		user_seen_tvs = [m.uid for m in self.user.seen_media.all() if m.media_type == 'tv']
		all_unseen = [a.small_info(self.user.uid) for a in all_tvs if a.uid not in user_seen_tvs]
		return all_unseen
