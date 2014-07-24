from django.conf.urls import patterns, url
from resultsdisplay import views

urlpatterns = patterns('', 
	url(r'^$', views.IndexView.as_view(), name='index'),

	url(r'^login/$', 'django.contrib.auth.views.login', 
		{'template_name':'resultsdisplay/login.html'}, name='login'),

    url(r'^logout$', 'django.contrib.auth.views.logout', {'next_page': '/'}, name='logout'),

	url(r'^api/(?P<project_name>\w+)/$', views.jsonDump, name='api'),
	url(r'^Project(?P<pk>\d+)/TestRuns/$', views.TestRunView.as_view(), name='TestRun'),
	url(r'^Project(?P<project_pk>\d+)/TestRun(?P<run_num>\d+)/TestGroups/$', views.TestGroupView.as_view(), name='TestGroup'),
	url(r'^Project(?P<project_pk>\d+)/TestRun(?P<run_num>\d+)/TestGroup(?P<group_id>\d+)/TestCases/$', views.TestCaseView.as_view(), name='TestCase'),
	url(r'^Project(?P<project_pk>\d+)/TestRun(?P<run_num>\d+)/TestGroup(?P<group_id>\d+)/TestCase(?P<pk>\d+)/Details/$', views.TestResultView.as_view(), name='Details'),
	)
