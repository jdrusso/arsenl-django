from django.shortcuts import render, render_to_response
from django.views import generic
from django.views.generic.list import MultipleObjectMixin
from django.http import HttpResponse
from resultsdisplay.models import TestResult, TestCase, Project
from django.db.models import Sum, Max
from django.conf import settings
import xml.etree.ElementTree as ET
import requests, base64, json
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django import forms
import re

group_id = {'Unit' : 0, 'Regression' : 1}
group_name = {0 : 'Unit', 1 : 'Regression'}

JENKINS_HOSTNAME = 'jabba'
JENKINS_USERNAME = settings.JENKINS_USERNAME
JENKINS_TOKEN = settings.JENKINS_TOKEN

class RunSelectForm(forms.Form):

	choices = tuple([x['run_num'] for x in TestResult.objects.filter(
				project_id__exact='0').distinct('run_num').values()])
	runs = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple)

class LoginRequiredMixin(object):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)

def jsonDump(request, project_name):

	job_url = 'https://%s/ci/job/%s/'%(JENKINS_HOSTNAME, project_name)
	
	base64string = base64.encodestring('%s:%s' % 
		(JENKINS_USERNAME, JENKINS_TOKEN)).replace('\n','')

	auth_header = {"Authorization":"Basic %s" % base64string}

	job_json = requests.get('%slastBuild/api/json?depth=1' % job_url, 
		verify=False, headers=auth_header).json()

	response_data = {
		'name':project_name,
		'running':(job_json['building'] == True)
	}

	try:
		response_data['progress'] = job_json['executor']['progress']
	except TypeError:
		response_data['progress'] = 0

	return HttpResponse(json.dumps(response_data), content_type="application/json")

class IndexView(LoginRequiredMixin, generic.ListView):

	template_name = 'resultsdisplay/index.html'
	context_object_name = 'project_list'

	def get_queryset(self):
		"""Return all the current projects."""
		return Project.objects.order_by('project_id')

	def get_context_data(self, **kwargs):
		context = super(IndexView, self).get_context_data(**kwargs)

		for aproject in context['project_list']:

			aproject.mostRecentRun = TestResult.objects.aggregate(Max('run_num'))['run_num__max']

			aproject.lastRun = TestResult.objects.filter(
				run_num__exact=aproject.mostRecentRun,
				project_id__exact=aproject.project_id).values()[0]['datestamp']

			aproject.total_time = TestResult.objects.filter(
				run_num__exact=aproject.mostRecentRun,
				project_id__exact=aproject.project_id).aggregate(Sum('run_time'))['run_time__sum']

			aproject.total_tests = TestResult.objects.filter(
				run_num__exact=aproject.mostRecentRun,
				project_id__exact=aproject.project_id).count()

			aproject.total_runs = TestResult.objects.filter(
				project_id__exact=aproject.project_id).distinct('run_num').count()

			aproject.passed = TestResult.objects.filter(
				run_num__exact=aproject.mostRecentRun,
				project_id__exact=aproject.project_id,
				result__exact="PASS").count()

			aproject.failed = TestResult.objects.filter(
				run_num__exact=aproject.mostRecentRun,
				project_id__exact=aproject.project_id,
				result__exact="FAIL").count()

			aproject.errored = TestResult.objects.filter(
				run_num__exact=aproject.mostRecentRun,
				project_id__exact=aproject.project_id,
				result__exact="ERROR").count()

			aproject.total = TestResult.objects.filter(
				run_num__exact=aproject.mostRecentRun,
				project_id__exact=aproject.project_id).count()

		jobs = []

		context['test_running'] = False

		try:

			for project in context['project_list']:

				api_url = 'https://%s/api/%s/' % (JENKINS_HOSTNAME, project.name)

				job_json = requests.get(api_url, verify=False).json()

				a_job = {
					'name':project.name,
					'running': job_json['running'],
					'apiurl':api_url,
				}

				if a_job['running']:
					context['test_running'] = True

					context['err'] = ''

				jobs.append(a_job)

		except Exception as e:
			context['test_running'] = False
			context['err'] = e

		context['job_list'] = jobs

		return context

	def get(self, request, *args, **kwargs):

		self.object_list = self.get_queryset()
		context = self.get_context_data()

		return addCORSHeaders(render(request, self.template_name, context))

class TestRunView(LoginRequiredMixin, generic.ListView):

	pk_url_kwarg = 'run_pk'

	template_name = 'resultsdisplay/TestRun.html'
	context_object_name = 'testrun_list'

	def get_queryset(self):
		return TestResult.objects.values().distinct('run_num')[::-1]

	def get_context_data(self, **kwargs):
		context = super(TestRunView, self).get_context_data(**kwargs)
		context['project_id'] = int(self.kwargs['pk'])
		context['project_name'] = \
			Project.objects.filter(project_id__exact=context['project_id']).values()[0]['name']

		for run in context['testrun_list']:
			var = TestResult.objects.raw('''SELECT sum(CAST (run_time AS float)) AS x
				WHERE run_num = %s''',
				params=[run['run_num']])
			run['total_time'] = TestResult.objects.filter(
				run_num__exact=run['run_num']).aggregate(Sum('run_time'))['run_time__sum']

			run['passed'] = TestResult.objects.filter(
				run_num__exact=run['run_num'],
				result__exact="PASS", 
				project_id__exact=context['project_id']).count()
			run['failed'] = TestResult.objects.filter(
				run_num__exact=run['run_num'],
				project_id__exact=context['project_id'],
				result__exact="FAIL").count()
			run['errored'] = TestResult.objects.filter(
				run_num__exact=run['run_num'],
				project_id__exact=context['project_id'],
				result__exact="ERROR").count()
			run['total'] = TestResult.objects.filter(
				project_id__exact=context['project_id'],
				run_num__exact=run['run_num']).count()

		return context


	def get(self, request, *args, **kwargs):

		self.object_list = self.get_queryset()
		context = self.get_context_data()


		context['POST'] = False
		context['thename'] = 'POST'

		if request.method == 'POST':
			for run in request.POST.getlist('checkbox'):
				TestResult.objects.filter(
					project_id__exact=context['project_id'],
					run_num__exact=run).delete()
			form = RunSelectForm()
			context['POST'] = True
			context['Checkboxes'] = request.POST.getlist('checkbox')

			#Reload objects and context
			self.object_list = self.get_queryset()
			context = self.get_context_data()

		return render(request, self.template_name, context)

	def post(self, request, *args, **kwargs):

		return self.get(request, *args, **kwargs)

class PrinterFriendlyView(LoginRequiredMixin, generic.ListView):

	pk_url_kwarg = 'run_pk'

	template_name = 'resultsdisplay/PrinterFriendly.html'
	context_object_name = 'testresult_list'

	def get_queryset(self):
		"""Return all the current tests for a given run."""
		return TestResult.objects.filter(
			run_num__exact=int(self.kwargs['run_num'])).values()

	def get_context_data(self, **kwargs):
		context = super(PrinterFriendlyView, self).get_context_data(**kwargs)
		context['run_num'] = int(self.kwargs['run_num'])
		context['ordered_run_num'] = int(self.kwargs['ordered_run_num'])
		context['project_id'] = int(self.kwargs['project_pk'])
		context['project_name'] = \
			Project.objects.filter(project_id__exact=context['project_id']).values()[0]['name']
		
		context['total_time'] = TestResult.objects.filter(
			run_num__exact=context['run_num']).aggregate(Sum('run_time'))['run_time__sum']

		context['num_passed'] = TestResult.objects.filter(
			run_num__exact=context['run_num'],
			result__exact="PASS", 
			project_id__exact=context['project_id']).count()
		context['num_failed'] = TestResult.objects.filter(
			run_num__exact=context['run_num'],
			project_id__exact=context['project_id'],
			result__exact="FAIL").count()
		context['num_errored'] = TestResult.objects.filter(
			run_num__exact=context['run_num'],
			project_id__exact=context['project_id'],
			result__exact="ERROR").count()
		context['num_tests'] = TestResult.objects.filter(
			project_id__exact=context['project_id'],
			run_num__exact=context['run_num']).count()

		for run in context['testresult_list']:


			run['name'] = TestCase.objects.filter(test_case_id__exact=run['test_case_id']).values()[0]['name'] 
			
			repo_string = Project.objects.filter(project_id__exact=run['project_id']).values()[0]['repo_list']
			run['repo_list'] = re.findall(r"[\w'\-]+", repo_string)
			run['sha_list'] = re.findall(r"[A-Za-z0-9]+", run['sha_list'])
			run['sha_list'] = [x[:10] for x in run['sha_list']]

			try:
				run['sha_list'] = ["%s: %s" % (run['repo_list'][x], run['sha_list'][x]) for x in range(len(run['sha_list']))]
			except IndexError:
				run['sha_list'] = ['SHAs not available for this run.']

		return context

class TestGroupView(LoginRequiredMixin, generic.ListView):

	pk_url_kwarg = 'run_pk'

	template_name = 'resultsdisplay/TestGroup.html'
	context_object_name = 'testgroup_list'

	def get_queryset(self):
		"""Return all the current test groups."""
		return TestCase.objects.values().distinct('test_type')

	def get_context_data(self, **kwargs):
		context = super(TestGroupView, self).get_context_data(**kwargs)
		context['run_num'] = int(self.kwargs['run_num'])
		context['ordered_run_num'] = int(self.kwargs['ordered_run_num'])
		context['project_id'] = int(self.kwargs['project_pk'])
		context['project_name'] = \
			Project.objects.filter(project_id__exact=context['project_id']).values()[0]['name']

		for group in context['testgroup_list']:

			group['type_num'] = group_id[group['test_type']]


			type_id = {}
			for case in TestCase.objects.values():
				type_id[case['test_case_id']] = case['test_type']

			this_type_name = group['test_type']
			this_type_id = group_id[this_type_name]

			valid_ids = [x for x in type_id if type_id[x] == this_type_name]

			group['total_time'] = TestResult.objects.filter(
				test_case_id__in=valid_ids,
				run_num__exact=context['run_num'],
				project_id__exact=context['project_id']
				).aggregate(Sum('run_time'))['run_time__sum']

			group['passed'] = TestResult.objects.filter(
				test_case_id__in=valid_ids,
				run_num__exact=context['run_num'],
				result__exact="PASS", 
				project_id__exact=context['project_id']).count()

			group['failed'] = TestResult.objects.filter(
				test_case_id__in=valid_ids,
				run_num__exact=context['run_num'],
				project_id__exact=context['project_id'],
				result__exact="FAIL").count()

			group['errored'] = TestResult.objects.filter(
				test_case_id__in=valid_ids,
				run_num__exact=context['run_num'],
				project_id__exact=context['project_id'],
				result__exact="ERROR").count()

			group['total'] = TestResult.objects.filter(
				test_case_id__in=valid_ids,
				run_num__exact=context['run_num'],
				project_id__exact=context['project_id']).count()

		return context

class TestCaseView(LoginRequiredMixin, generic.ListView):

	pk_url_kwarg = 'group_pk'

	template_name = 'resultsdisplay/TestCase.html'
	context_object_name = 'testcase_list'

	def get_queryset(self):
		"""Return all the current test cases"""

		this_type_id = int(self.kwargs['group_id'])
		this_type_name = group_name[this_type_id]

		type_id = {}

		for case in TestCase.objects.values():
			type_id[case['test_case_id']] = case['test_type']

		valid_ids = [x for x in type_id if type_id[x] == this_type_name]

		return TestResult.objects.extra(where=["run_num = %s", "test_case_id BETWEEN %s and %s"], 
			params=[int(self.kwargs['run_num']),  min(valid_ids), max(valid_ids)])

	def get_context_data(self, **kwargs):
		context = super(TestCaseView, self).get_context_data(**kwargs)
		context['project_id'] = int(self.kwargs['project_pk'])
		context['group_id'] = int(self.kwargs['group_id'])
		context['run_num'] = int(self.kwargs['run_num'])
		context['ordered_run_num'] = int(self.kwargs['ordered_run_num'])
		context['type_name'] = group_name[int(self.kwargs['group_id'])]
		context['project_name'] = \
			Project.objects.filter(project_id__exact=context['project_id']).values()[0]['name']

		for case in context['testcase_list']:

			case.name = TestCase.objects.extra(where=['test_case_id=%s'],
			 	params=[case.test_case_id])[0]

			case.test_function = TestCase.objects.filter(test_case_id__exact=case.test_case_id).values()[0]['test_function']

			case.type = TestCase.objects.filter(test_case_id__exact=case.test_case_id).values()[0]['test_type']

		return context

class TestResultView(LoginRequiredMixin, generic.DetailView):

	template_name = 'resultsdisplay/TestResult.html'
	context_object_name = 'testresult'

	def get_queryset(self):
		"""Return all the current test cases"""
		return TestResult.objects.values()

	def get_context_data(self, **kwargs):
		context = super(TestResultView, self).get_context_data(**kwargs)
		context['project_id'] = int(self.kwargs['project_pk'])
		context['run_num'] = int(self.kwargs['run_num'])
		context['ordered_run_num'] = int(self.kwargs['ordered_run_num'])
		context['group_id'] = int(self.kwargs['group_id'])
		context['type_name'] = group_name[int(self.kwargs['group_id'])]
		context['project_name'] = \
			Project.objects.filter(project_id__exact=context['project_id']).values()[0]['name']

		#context['testresult']['name'] = TestCase.objects.extra(where=['test_case_id=%s'], 
		# 	params=[context['testresult']['test_case_id']])[0]

		context['testresult']['name'] = TestCase.objects.filter(
			test_case_id__exact=context['testresult']['test_case_id']).values()[0]['name']


		repo_string = Project.objects.filter(
			project_id__exact=context['testresult']['project_id']).values()[0]['repo_list']
		context['testresult']['repo_list'] = re.findall(r"[\w'\-]+", repo_string)
		context['testresult']['sha_list'] = re.findall(r"[A-Za-z0-9]+", context['testresult']['sha_list'])
		context['testresult']['sha_list'] = [x[:10] for x in context['testresult']['sha_list']]

		try:
			context['testresult']['sha_list'] = ["%s: %s" % (context['testresult']['repo_list'][x],
				context['testresult']['sha_list'][x]) for x in range(len(context['testresult']['sha_list']))]

		except IndexError:
			context['testresult']['sha_list'] = ['SHAs not available for this run.']

		xml_url = getattr(settings, "STATIC_ROOT", None) + r'web/' + context['testresult']['xml_path']
		context['xml_url'] = getattr(settings, "STATIC_URL", None) + r'web/' + context['testresult']['xml_path']

		self.xmlTree = ET.parse(xml_url)

		context['mavout'] = self.xmlTree.getroot()[0].text
		context['jsbout'] = self.xmlTree.getroot()[1].text
		context['sysout'] = self.xmlTree.getroot()[2].text

		return context

def addCORSHeaders(theHttpResponse):
    if theHttpResponse and isinstance(theHttpResponse, HttpResponse):
        theHttpResponse['Access-Control-Allow-Origin'] = '*'
        theHttpResponse['Access-Control-Max-Age'] = '120'
        theHttpResponse['Access-Control-Allow-Credentials'] = 'true'
        theHttpResponse['Access-Control-Allow-Methods'] = 'HEAD, GET, OPTIONS, POST, DELETE'
        theHttpResponse['Access-Control-Allow-Headers'] = 'origin, content-type, accept, x-requested-with'
    return theHttpResponse